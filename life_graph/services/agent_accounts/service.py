"""Agent accounts in the database: CRUD, the API-key secret, pool, cooldown, limits.

Every query filters by ``tenant_id`` (CHARTER invariant 4). Callers commit.
What leaves this module for the API (:func:`to_dict`) has no credential, no
vault reference and no home path; the home is given only by
:func:`home_info`, which the API serves to the owner alone.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from life_graph.drivers.cli_failure import failure_message
from life_graph.models.agent_accounts import AgentAccount, AgentAccountLimit
from life_graph.services import vault
from life_graph.services.agent_accounts import homes, identity, pool
from life_graph.services.agent_accounts.catalog import (
    API_ORIGIN,
    HOME_ENV,
    LOGIN_COMMAND,
    AccountError,
    check_driver_kind,
    clean_name,
    clean_properties,
)
from life_graph.services.agent_accounts.env import AccountEnv, build_account_env

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AccountNotFoundError(LookupError):
    """No such account for this tenant."""


class AccountConflictError(ValueError):
    """A name or identity already used by another account of this driver (HTTP 409)."""


def iso_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


def to_dict(row: AgentAccount, *, now: datetime | None = None) -> dict[str, Any]:
    """An account as the API shows it: no secret, no vault ref, no home path."""
    now = now or datetime.now(UTC)
    cooling = pool.is_cooling(row, now)
    return {
        "id": str(row.id),
        "driver": row.driver,
        "name": row.name,
        "kind": row.kind,
        "enabled": row.enabled,
        "priority": row.priority,
        "identity": row.identity_masked,
        "has_secret": row.secret_ref is not None,
        "secret_set_at": iso_time(row.secret_set_at),
        "has_home": bool(row.home_dir),
        "properties": dict(row.properties or {}),
        "status": (
            "disabled"
            if not row.enabled
            else "cooling_down"
            if cooling
            else "error"
            if row.last_error
            else "ready"
        ),  # fmt: skip
        "cooldown_until": iso_time(row.cooldown_until) if cooling else None,
        "last_error": row.last_error,
        "last_used_at": iso_time(row.last_used_at),
        "created_at": iso_time(row.created_at),
        "updated_at": iso_time(row.updated_at),
    }


def home_info(row: AgentAccount) -> dict[str, Any]:
    """Owner only: where the account's CLI home is and how to sign it in.

    race-app runs ``command`` in its PTY with ``env`` set; nothing here logs in.
    """
    env_var = HOME_ENV.get(row.driver)
    return {
        "id": str(row.id),
        "driver": row.driver,
        "home_dir": row.home_dir,
        "env": {env_var: row.home_dir} if env_var and row.home_dir else {},
        "login_command": LOGIN_COMMAND.get(row.driver, []) if row.kind == "subscription" else [],
    }


def limit_dict(row: AgentAccountLimit) -> dict[str, Any]:
    return {
        "window": row.window,
        "used_percent": row.used_percent,
        "window_minutes": row.window_minutes,
        "resets_at": iso_time(row.resets_at),
        "status": row.status,
        "source": row.source,
        "observed_at": iso_time(row.observed_at),
    }


# ── Reads ──────────────────────────────────────────────


async def list_accounts(
    session: AsyncSession, tenant_id: str, driver: str | None = None
) -> list[AgentAccount]:
    """This tenant's accounts (one driver's, when given), in pool order."""
    stmt = select(AgentAccount).where(AgentAccount.tenant_id == tenant_id)
    if driver:
        stmt = stmt.where(AgentAccount.driver == driver)
    rows = list((await session.execute(stmt)).scalars().all())
    return sorted(pool.ordered(rows), key=lambda a: a.driver)


async def get_account(session: AsyncSession, tenant_id: str, account_id: Any) -> AgentAccount:
    """One account by id, refusing another tenant's row."""
    try:
        key = account_id if isinstance(account_id, uuid.UUID) else uuid.UUID(str(account_id))
    except ValueError:
        raise AccountNotFoundError("account not found") from None
    stmt = select(AgentAccount).where(AgentAccount.tenant_id == tenant_id, AgentAccount.id == key)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None or row.tenant_id != tenant_id:
        raise AccountNotFoundError("account not found")
    return row


async def get_limits(
    session: AsyncSession, tenant_id: str, account_id: Any
) -> list[AgentAccountLimit]:
    stmt = select(AgentAccountLimit).where(
        AgentAccountLimit.tenant_id == tenant_id, AgentAccountLimit.account_id == account_id
    )
    return list((await session.execute(stmt)).scalars().all())


# ── Writes ─────────────────────────────────────────────


async def _check_unique(
    session: AsyncSession,
    tenant_id: str,
    driver: str,
    *,
    name: str | None = None,
    identity_hash: str | None = None,
    exclude: Any = None,
) -> None:
    for column, value, what in (
        (AgentAccount.name, name, "name"),
        (AgentAccount.identity_hash, identity_hash, "identity"),
    ):
        if value is None:
            continue
        stmt = select(AgentAccount.id).where(
            AgentAccount.tenant_id == tenant_id, AgentAccount.driver == driver, column == value
        )
        found = (await session.execute(stmt)).scalar_one_or_none()
        if found is not None and found != exclude:
            raise AccountConflictError(f"another {driver} account already has this {what}")


async def create_account(
    session: AsyncSession,
    tenant_id: str,
    *,
    driver: str,
    name: str,
    kind: str,
    enabled: bool = True,
    priority: int = 100,
    identity_value: str | None = None,
    properties: dict | None = None,
) -> AgentAccount:
    """Validate, create the row and its private home. No secret is taken here."""
    check_driver_kind(driver, kind)
    name = clean_name(name)
    props = clean_properties(driver, kind, properties)
    masked = hashed = None
    if identity_value and identity.normalize(identity_value):
        masked = identity.mask(identity_value)
        hashed = identity.identity_hash(tenant_id, driver, identity_value)
    await _check_unique(session, tenant_id, driver, name=name, identity_hash=hashed)
    account_id = uuid.uuid4()
    home = homes.ensure_home(tenant_id, driver, account_id) if driver in HOME_ENV else None
    now = datetime.now(UTC)
    row = AgentAccount(
        id=account_id,
        tenant_id=tenant_id,
        driver=driver,
        name=name,
        kind=kind,
        home_dir=str(home) if home else None,
        identity_masked=masked,
        identity_hash=hashed,
        enabled=enabled,
        priority=priority,
        properties=props,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    logger.info("Agent account %s (%s/%s) created for %s", row.id, driver, kind, tenant_id)
    return row


async def update_account(
    session: AsyncSession,
    tenant_id: str,
    account_id: Any,
    *,
    name: str | None = None,
    enabled: bool | None = None,
    priority: int | None = None,
    identity_value: str | None = None,
    properties: dict | None = None,
) -> AgentAccount:
    """Change the non-secret fields. Kind and driver are fixed at creation."""
    row = await get_account(session, tenant_id, account_id)
    if name is not None:
        name = clean_name(name)
        await _check_unique(session, tenant_id, row.driver, name=name, exclude=row.id)
        row.name = name
    if identity_value is not None:
        if identity.normalize(identity_value):
            hashed = identity.identity_hash(tenant_id, row.driver, identity_value)
            await _check_unique(
                session, tenant_id, row.driver, identity_hash=hashed, exclude=row.id
            )
            row.identity_masked, row.identity_hash = identity.mask(identity_value), hashed
        else:
            row.identity_masked = row.identity_hash = None
    if properties is not None:
        row.properties = clean_properties(row.driver, row.kind, properties)
    if enabled is not None:
        row.enabled = enabled
    if priority is not None:
        row.priority = priority
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


async def delete_account(
    session: AsyncSession, tenant_id: str, account_id: Any, *, wipe_home: bool = False
) -> bool:
    """Delete the row, revoke its vault secret; remove its home when asked.

    Returns whether the home was removed.
    """
    row = await get_account(session, tenant_id, account_id)
    if row.secret_ref is not None:
        with contextlib.suppress(vault.SecretNotFoundError):
            await vault.revoke(session, tenant_id, row.secret_ref)
    home = row.home_dir
    await session.execute(
        delete(AgentAccount).where(AgentAccount.tenant_id == tenant_id, AgentAccount.id == row.id)
    )
    await session.flush()
    return homes.remove_home(home) if wipe_home else False


async def set_secret(
    session: AsyncSession, tenant_id: str, account_id: Any, value: str
) -> AgentAccount:
    """Write-only: store an api_key account's key in the vault, revoke the old one."""
    row = await get_account(session, tenant_id, account_id)
    if row.kind != "api_key":
        raise AccountError(f"a {row.kind} account takes no secret")
    value = (value or "").strip()
    if not value or len(value) > 4096 or any(c.isspace() for c in value):
        raise AccountError("the key must be one line with no spaces")
    stored = await vault.store(
        session,
        tenant_id,
        label=f"agent account: {row.driver} {row.name}",
        value=value,
        allowed_origins=[API_ORIGIN[row.driver]],
        secret_type="token",
    )
    previous = row.secret_ref
    row.secret_ref = stored.id
    row.secret_set_at = datetime.now(UTC)
    row.updated_at = row.secret_set_at
    if previous is not None:
        with contextlib.suppress(vault.SecretNotFoundError):
            await vault.revoke(session, tenant_id, previous)
    await session.flush()
    return row


async def clear_secret(session: AsyncSession, tenant_id: str, account_id: Any) -> AgentAccount:
    """Revoke the key (its ciphertext is destroyed) and forget the reference."""
    row = await get_account(session, tenant_id, account_id)
    if row.secret_ref is not None:
        with contextlib.suppress(vault.SecretNotFoundError):
            await vault.revoke(session, tenant_id, row.secret_ref)
    row.secret_ref = row.secret_set_at = None
    await session.flush()
    return row


async def set_pool_order(
    session: AsyncSession, tenant_id: str, driver: str, order: list[Any]
) -> list[AgentAccount]:
    """Rewrite the priorities of *driver*'s accounts so *order* runs first."""
    rows = await list_accounts(session, tenant_id, driver)
    try:
        ids = [uuid.UUID(str(i)) for i in order]
        priorities = pool.reorder(rows, ids)
    except ValueError as exc:
        raise AccountError(str(exc)) from None
    for row in rows:
        row.priority = priorities[row.id]
    await session.flush()
    return pool.ordered(rows)


async def reset_cooldown(session: AsyncSession, tenant_id: str, account_id: Any) -> AgentAccount:
    row = await get_account(session, tenant_id, account_id)
    row.cooldown_until = None
    row.last_error = None
    await session.flush()
    return row


async def record_limits(
    session: AsyncSession,
    tenant_id: str,
    account_id: Any,
    windows: list[dict],
    *,
    source: str,
    observed_at: datetime | None = None,
) -> int:
    """Upsert the latest reading of each window. Returns how many were written."""
    when = observed_at or datetime.now(UTC)
    count = 0
    for w in windows:
        resets = w.get("resets_at")
        values = {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "account_id": account_id,
            "window": str(w["window"])[:32],
            "used_percent": float(w["used_percent"]),
            "window_minutes": w.get("window_minutes"),
            "resets_at": datetime.fromisoformat(resets.replace("Z", "+00:00")) if resets else None,
            "status": w.get("status"),
            "source": source,
            "observed_at": when,
        }
        stmt = insert(AgentAccountLimit).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_agent_account_limits_window",
            set_={k: stmt.excluded[k] for k in values if k not in ("id", "account_id", "window")},
        )
        await session.execute(stmt)
        count += 1
    return count


# ── Dispatch ───────────────────────────────────────────


async def choose(
    session: AsyncSession, tenant_id: str, driver: str, now: datetime | None = None
) -> tuple[pool.Pick, list[AgentAccount]]:
    """The pool pick for one dispatch, and the pool it was picked from."""
    rows = await list_accounts(session, tenant_id, driver)
    return pool.pick(rows, now or datetime.now(UTC)), rows


async def account_env(session: AsyncSession, tenant_id: str, row: AgentAccount) -> AccountEnv:
    """The run environment overlay for *row*; resolves its key from the vault.

    Raises AccountError (or homes.HomeError) when the account cannot run:
    unsafe or missing home, no key set, a revoked key.
    """
    home = str(homes.checked_home(row.home_dir)) if row.driver in HOME_ENV else None
    api_key = None
    if row.kind == "api_key":
        if row.secret_ref is None:
            raise AccountError("api_key account has no key set")
        try:
            secret = await vault.get(session, tenant_id, row.secret_ref)
            api_key = await vault.resolve_for_origin(
                session, tenant_id, vault.handle_uri(secret), API_ORIGIN[row.driver]
            )
        except vault.VaultError:
            raise AccountError("api_key account's key is missing or revoked") from None
    return build_account_env(
        row.driver, row.kind, home=home, api_key=api_key, properties=row.properties
    )


def apply_outcome(
    row: AgentAccount,
    *,
    success: bool,
    failure: dict | None,
    now: datetime,
    default_cooldown_minutes: int,
) -> datetime | None:
    """Update *row* after a run on it; returns the cooldown set, if any (pure)."""
    row.last_used_at = now
    if success:
        row.last_error = None
        return None
    kind = (failure or {}).get("kind")
    until = pool.cooldown_until(failure, now, default_minutes=default_cooldown_minutes)
    if until is not None:
        row.cooldown_until = until
        row.last_error = failure_message(f"rate limited: {failure.get('message') or ''}")
    elif kind == "auth":
        hint = failure.get("hint") or ""
        row.last_error = failure_message(f"signed out: {failure.get('message') or ''} {hint}")
    return until
