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
``rate_limited`` with ``resets_at`` = the earliest cooldown end (the task can
park until then). Only ``rate_limited`` moves on to the next account: the
dispatcher re-dispatches on ``metadata.account.next`` (drivers/run_health.py),
pinning it with ``packet.account_id``; :func:`release` only puts the account
into cooldown and names the next one.

Subscription budget (risk D4, Phase 3b part 2): an unattended run
(``packet.unattended``) skips subscription accounts at or above
``driver_accounts_subscription_max_share`` of a plan window
(services/agent_accounts/budget.py).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from life_graph.config import settings
from life_graph.drivers.base import DriverResult
from life_graph.services.agent_accounts import budget, homes, limits, pool, service
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
    # The subscription-budget decision (D4) for an unattended run, if any.
    budget: dict | None = None

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
        info = {
            "id": str(self.account_id),
            "name": self.name,
            "kind": self.kind,
            "env": self.env.names(),
        }
        if self.budget:
            info["budget"] = self.budget
        return info

    def billing(self, default: str) -> str:
        """``subscription`` / ``api`` for this run's account, else *default*."""
        return billing_of(self.kind, default) if self.active else default


def _refuse(driver: str, status: str, error: str, **metadata: Any) -> DriverResult:
    return DriverResult(
        success=False,
        error=error,
        metadata={"exit_status": status, "driver": driver, **metadata},
    )


def billing_of(kind: str | None, default: str) -> str:
    """How a run on an account of *kind* is paid for: ``subscription`` or ``api``.

    A subscription login is the plan's (risk D4: gated on window share, not
    dollars); an API key or Vertex project is billed per use (the Governor's
    dollar cap). No account = the driver's own *default*.
    """
    if kind == "subscription":
        return "subscription"
    if kind in ("api_key", "vertex"):
        return "api"
    return default


@dataclass
class _Selection:
    """What the pool (and the subscription budget) chose for one run."""

    pick: pool.Pick
    budget: dict | None = None  # the D4 decision, for the task's events
    over_budget_until: datetime | None = None  # every account over the share


async def _select(
    session: Any,
    tenant_id: str,
    driver: str,
    *,
    account_id: Any,
    unattended: bool,
    now: datetime,
) -> _Selection:
    """The pool pick for one run, with the subscription budget (D4) applied.

    Only an unattended run is budgeted; someone who asked for a run now may
    spend their own quota.
    """
    share = float(settings.driver_accounts_subscription_max_share)
    if account_id is not None:
        picked = await _pinned(session, tenant_id, driver, account_id, now)
        rows = [picked.account] if picked.state == "selected" else []
    else:
        rows = await service.list_accounts(session, tenant_id, driver)
        picked = pool.pick(rows, now)
    if not unattended or share >= 1.0:
        return _Selection(picked)
    subs = [r for r in rows if r.enabled and r.kind == "subscription"]
    if not subs:
        return _Selection(picked)
    limits_rows = await service.limits_for(session, tenant_id, [r.id for r in subs])
    readings = budget.fullest(subs, limits_rows, now)
    over = budget.over_share(readings, share)
    decision: dict[str, Any] = {"share_limit": share}
    if over:
        decision["skipped"] = [r.as_dict() for r in over.values()]
        decision["reason"] = budget.reason(over, share)
    if account_id is None and over:
        picked = pool.pick(rows, now, exclude=set(over))
    elif account_id is not None and picked.state == "selected" and picked.account.id in over:
        picked = pool.Pick("none")
    chosen = picked.account if picked.state == "selected" else None
    if chosen is not None:
        mine = readings.get(chosen.id)
        decision["account"] = chosen.name
        decision["used_percent"] = round(mine.used_percent, 1) if mine else None
        decision["window"] = mine.window if mine else None
        return _Selection(picked, decision)
    if not over:
        return _Selection(picked, decision)
    # Every enabled account is over the share or cooling down: refuse until the
    # first one frees up.
    until = budget.earliest_reset(over, now, settings.driver_accounts_default_cooldown_minutes)
    if picked.state == "cooling" and picked.retry_at is not None:
        until = min(until, picked.retry_at)
    return _Selection(picked, decision, over_budget_until=until)


async def preview(
    driver: str, tenant_id: str, *, unattended: bool = False, now: datetime | None = None
) -> dict | None:
    """What :func:`acquire` would choose, without leasing anything.

    For the dispatcher's budget gate: ``None`` when accounts are off or the
    driver has no enabled account (today's path), else ``{state, kind, name,
    budget}`` with state ``selected`` / ``cooling`` / ``over_budget``.
    Raises nothing: an unreadable pool returns ``{"state": "error"}`` (the
    driver's own acquire then refuses the run).
    """
    if not settings.driver_accounts_enabled:
        return None
    now = now or datetime.now(UTC)
    try:
        async with _sf()() as session:
            sel = await _select(
                session, tenant_id, driver, account_id=None, unattended=unattended, now=now
            )
    except Exception:  # noqa: BLE001
        logger.debug("%s: account preview failed", driver, exc_info=True)
        return {"state": "error"}
    if sel.over_budget_until is not None:
        return {"state": "over_budget", "kind": None, "name": None, "budget": sel.budget}
    if sel.pick.state == "none":
        return None
    if sel.pick.state == "cooling":
        return {"state": "cooling", "kind": None, "name": None, "budget": sel.budget}
    row = sel.pick.account
    return {"state": "selected", "kind": row.kind, "name": row.name, "budget": sel.budget}


async def acquire(
    driver: str,
    tenant_id: str,
    *,
    account_id: Any = None,
    unattended: bool = False,
    now: datetime | None = None,
) -> AccountLease:
    """The account this run uses (see the module docstring for the rules).

    *account_id* pins one account (a resume must run in the home its session
    lives in): it must exist, be enabled and not be cooling down, else the
    run is refused; the pool is not consulted. *unattended* applies the
    subscription budget (D4, services/agent_accounts/budget.py): accounts over
    their plan-window share are skipped, and when none is left the run is
    refused as ``rate_limited`` (``exit_status=subscription_budget``) until the
    earliest window reset.
    """
    lease = AccountLease(driver=driver, tenant_id=tenant_id)
    if not settings.driver_accounts_enabled:
        return lease
    now = now or datetime.now(UTC)
    try:
        async with _sf()() as session:
            sel = await _select(
                session,
                tenant_id,
                driver,
                account_id=account_id,
                unattended=unattended,
                now=now,
            )
            picked = sel.pick
            lease.budget = sel.budget
            if sel.over_budget_until is not None:
                resets = sel.over_budget_until.isoformat().replace("+00:00", "Z")
                why = (sel.budget or {}).get("reason") or "over the plan-window share"
                lease.refusal = _refuse(
                    driver,
                    "subscription_budget",
                    f"no {driver} account may run unattended: {why} (resets {resets})",
                    failure={
                        "kind": "rate_limited",
                        "resets_at": resets,
                        "reason": "subscription_budget",
                        "message": f"every {driver} account is over its plan-window share",
                    },
                    account_pool={"state": "over_budget", "retry_at": resets},
                    account_budget=sel.budget,
                )
                return lease
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
                    info["next"] = {
                        "id": str(nxt.account.id),
                        "name": nxt.account.name,
                        "kind": nxt.account.kind,
                    }
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
