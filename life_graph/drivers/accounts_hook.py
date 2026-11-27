"""Which account a driver run uses, and what the run taught us about it.

Called by the account-aware drivers (codex, gemini through
``drivers/cli_driver.py``, and claude_code) around each CLI run, so the
dispatcher needs no change and a bounce (attempt 2) picks an account the
same way attempt 1 did:

    lease = await accounts_hook.acquire(driver, tenant)   # before the run
    if lease.refusal: return lease.refusal                # fail closed
    env = lease.apply(env)                                # home + key overlay
    ... run ...
    await accounts_hook.release(lease, result)            # cooldown, limits

With ``driver_accounts_enabled`` off, or no enabled account for the driver,
:func:`acquire` returns an empty lease without touching the database and the
run is exactly what it was before accounts existed.

Fail-closed (CHARTER invariant 5): when accounts are on and configured, a run
never quietly falls back to the host's default login. A database error, an
unsafe home or a missing key refuses the run (``exit_status =
account_unavailable``); every account cooling down refuses it as
``rate_limited`` with ``resets_at`` = the earliest cooldown end (Phase 3b
part 2 parks the task until then). Only ``rate_limited`` moves on to the next
account, and that move (a re-dispatch) is part 2's: :func:`release` only
puts the account into cooldown and names the next one in
``metadata.account.next``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from life_graph.config import settings
from life_graph.drivers.base import DriverResult
from life_graph.services.agent_accounts import homes, limits, pool, service
from life_graph.services.agent_accounts.catalog import AccountError

if TYPE_CHECKING:
    from life_graph.services.agent_accounts.env import AccountEnv

logger = logging.getLogger(__name__)

_session_factory: Any = None


def configure(session_factory: Any) -> None:
    """Point the hook at a session factory (tests); None = the app's."""
    global _session_factory
    _session_factory = session_factory


def _sf() -> Any:
    if _session_factory is not None:
        return _session_factory
    from life_graph.storage.database import async_session

    return async_session


@dataclass
class AccountLease:
    """One run's account: nothing (the default login), a chosen account, or a refusal."""

    driver: str
    tenant_id: str = ""
    account_id: Any = None
    name: str | None = None
    kind: str | None = None
    model: str | None = None
    env: AccountEnv | None = field(default=None, repr=False)
    refusal: DriverResult | None = None

    @property
    def active(self) -> bool:
        return self.account_id is not None and self.env is not None

    def apply(self, env: dict[str, str]) -> dict[str, str]:
        """The run environment with this account's overlay (unchanged when none)."""
        return self.env.apply(env) if self.active else env

    def metadata(self) -> dict | None:
        """What the result records about the account (no secret, no path)."""
        if not self.active:
            return None
        return {
            "id": str(self.account_id),
            "name": self.name,
            "kind": self.kind,
            "env": self.env.names(),
        }


def _refuse(driver: str, status: str, error: str, **metadata: Any) -> DriverResult:
    return DriverResult(
        success=False,
        error=error,
        metadata={"exit_status": status, "driver": driver, **metadata},
    )


async def acquire(
    driver: str, tenant_id: str, *, account_id: Any = None, now: datetime | None = None
) -> AccountLease:
    """The account this run uses (see the module docstring for the rules).

    *account_id* pins one account (a resume must run in the home its session
    lives in): it must exist, be enabled and not be cooling down, else the
    run is refused; the pool is not consulted.
    """
    lease = AccountLease(driver=driver, tenant_id=tenant_id)
    if not settings.driver_accounts_enabled:
        return lease
    now = now or datetime.now(UTC)
    try:
        async with _sf()() as session:
            if account_id is not None:
                picked = await _pinned(session, tenant_id, driver, account_id, now)
            else:
                picked, _pool = await service.choose(session, tenant_id, driver, now)
            if picked.state == "missing":
                lease.refusal = _refuse(
                    driver,
                    "account_unavailable",
                    f"{driver} account {account_id} is missing or disabled",
                )
                return lease
            if picked.state == "none":
                return lease
            if picked.state == "cooling":
                resets = picked.retry_at.isoformat().replace("+00:00", "Z")
                lease.refusal = _refuse(
                    driver,
                    "rate_limited",
                    f"every {driver} account is cooling down (resets {resets})",
                    failure={
                        "kind": "rate_limited",
                        "resets_at": resets,
                        "message": f"every {driver} account is cooling down",
                    },
                    account_pool={"state": "cooling", "retry_at": resets},
                )
                return lease
            row = picked.account
            try:
                account_env = await service.account_env(session, tenant_id, row)
            except (AccountError, homes.HomeError) as exc:
                row.last_error = str(exc)[:200]
                await session.commit()
                lease.refusal = _refuse(
                    driver,
                    "account_unavailable",
                    f"{driver} account {row.name!r} cannot run: {exc}",
                    account={"id": str(row.id), "name": row.name, "kind": row.kind},
                )
                return lease
            await session.commit()  # the vault's use count
            lease.account_id, lease.name, lease.kind = row.id, row.name, row.kind
            lease.model = (row.properties or {}).get("model")
            lease.env = account_env
            return lease
    except Exception:  # noqa: BLE001 - fail closed on any lookup failure
        logger.warning("%s: account lookup failed; refusing the run", driver, exc_info=True)
        lease.refusal = _refuse(
            driver,
            "account_unavailable",
            f"{driver}: agent accounts are on but could not be read; refusing to run on "
            "another login",
        )
        return lease


async def _pinned(
    session: Any, tenant_id: str, driver: str, account_id: Any, now: datetime
) -> pool.Pick:
    try:
        row = await service.get_account(session, tenant_id, account_id)
    except service.AccountNotFoundError:
        return pool.Pick("missing")
    if row.driver != driver or not row.enabled:
        return pool.Pick("missing")
    if pool.is_cooling(row, now):
        until = row.cooldown_until
        until = until if until.tzinfo else until.replace(tzinfo=UTC)
        return pool.Pick("cooling", retry_at=until)
    return pool.Pick("selected", account=row)


async def release(
    lease: AccountLease, result: DriverResult, *, now: datetime | None = None
) -> None:
    """Record a finished run on its account: last use, cooldown, error, limits.

    Adds ``metadata.account`` to *result*; on a rate limit also
    ``metadata.account.cooldown_until`` and ``.next`` (the account a retry
    would use, or ``{"state": "cooling", "retry_at"}``). Never raises.
    """
    if not lease.active:
        return
    now = now or datetime.now(UTC)
    info = lease.metadata() or {}
    result.metadata["account"] = info
    try:
        async with _sf()() as session:
            row = await service.get_account(session, lease.tenant_id, lease.account_id)
            until = service.apply_outcome(
                row,
                success=result.success,
                failure=result.metadata.get("failure"),
                now=now,
                default_cooldown_minutes=settings.driver_accounts_default_cooldown_minutes,
            )
            windows = limits.windows_from_metadata(lease.driver, result.metadata)
            if windows:
                await service.record_limits(
                    session, lease.tenant_id, row.id, windows, source="run", observed_at=now
                )
            if until is not None:
                info["cooldown_until"] = until.isoformat().replace("+00:00", "Z")
                rows = await service.list_accounts(session, lease.tenant_id, lease.driver)
                nxt = pool.next_after(rows, row.id, now)
                if nxt.state == "selected":
                    info["next"] = {"id": str(nxt.account.id), "name": nxt.account.name}
                elif nxt.state == "cooling":
                    info["next"] = {
                        "state": "cooling",
                        "retry_at": nxt.retry_at.isoformat().replace("+00:00", "Z"),
                    }
                else:
                    info["next"] = None
            await session.commit()
    except Exception:  # noqa: BLE001 - bookkeeping never fails a finished run
        logger.warning("%s: could not record the run on its account", lease.driver, exc_info=True)
