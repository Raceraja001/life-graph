"""Agent accounts API: named logins per driver CLI, the pool, cooldown, plan limits.

Prefix: /kernel/agent-accounts. Spec: docs/specs/agent-drivers.md, "Phase 3b
(2026-11-27): accounts, pool, limits, resume".

- Reads (list, one, limits) are tenant-scoped and carry no credential, no
  vault reference and no home path (services/agent_accounts/service.to_dict).
- Everything that creates, changes or reveals how an account signs in is
  **owner only** (api/approval_identity.owner_only): create, update, delete,
  the API key (write-only), pool order, enable/disable, cooldown reset, the
  home directory race-app launches ``claude auth login`` / ``codex login`` in,
  and a live limits refresh.
- The API key goes in through ``PUT .../secret`` into the vault and never
  comes back out: no route returns it, its length or its vault handle.
- Sign-in is not here: race-app runs the CLI's own login in its PTY with the
  home from ``GET .../home``.
"""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from life_graph.api.approval_identity import owner_only
from life_graph.api.responses import success_response
from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.drivers.cli_run import cli_env, resolve_binary
from life_graph.services.agent_accounts import homes, limits, service
from life_graph.services.agent_accounts.catalog import CREDENTIAL_ENV, AccountError
from life_graph.storage.database import async_session

router = APIRouter(prefix="/kernel/agent-accounts", tags=["agent-accounts"])

_OWNER = "Managing agent accounts"

DriverName = Literal["claude_code", "codex", "gemini", "opencode"]
KindName = Literal["subscription", "api_key", "vertex"]

# One live Codex probe per account per 5 minutes (race-app U3's throttle).
PROBE_INTERVAL_SECONDS = 300
_last_probe: dict[str, float] = {}


class AccountCreate(BaseModel):
    """A new account. No secret here: set an API key with PUT .../secret."""

    model_config = ConfigDict(extra="forbid")

    driver: DriverName
    name: str = Field(..., min_length=1, max_length=60)
    kind: KindName
    enabled: bool = True
    priority: int = Field(100, ge=0, le=10_000)
    identity: str | None = Field(
        None, max_length=254, description="The login's email/org; stored masked + hashed only"
    )
    properties: dict = Field(
        default_factory=dict, description="Non-secret: vertex project/region, model"
    )


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=60)
    enabled: bool | None = None
    priority: int | None = Field(None, ge=0, le=10_000)
    identity: str | None = Field(None, max_length=254, description="Empty string clears it")
    properties: dict | None = None


class SecretSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(..., min_length=1, max_length=4096, description="Stored in the vault only")


class PoolOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: list[str] = Field(..., description="Account ids, first runs first")


def _errors(exc: Exception) -> HTTPException:
    if isinstance(exc, service.AccountNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    if isinstance(exc, service.AccountConflictError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, (AccountError, homes.HomeError)):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    raise exc


_KNOWN = (LookupError, ValueError)


# ── Reads ──────────────────────────────────────────────


@router.get("", summary="List agent accounts (no secrets, no paths)")
async def list_accounts(driver: DriverName | None = None):
    async with async_session() as session:
        rows = await service.list_accounts(session, get_current_tenant_id(), driver)
        return success_response(data={"accounts": [service.to_dict(r) for r in rows]})


@router.get("/limits", summary="Latest plan-limit windows of every account")
async def all_limits(driver: DriverName | None = None):
    tenant = get_current_tenant_id()
    async with async_session() as session:
        rows = await service.list_accounts(session, tenant, driver)
        out = []
        for row in rows:
            windows = await service.get_limits(session, tenant, row.id)
            out.append(_limits_payload(row, windows))
        return success_response(data={"accounts": out})


@router.put("/pool/{driver}", summary="Set a driver's pool order (owner)")
async def set_pool(driver: DriverName, body: PoolOrder, request: Request):
    owner_only(request, _OWNER)
    async with async_session() as session:
        try:
            rows = await service.set_pool_order(
                session, get_current_tenant_id(), driver, body.order
            )
        except _KNOWN as exc:
            raise _errors(exc) from None
        data = [service.to_dict(r) for r in rows]
        await session.commit()
        return success_response(data={"driver": driver, "accounts": data})


@router.get("/{account_id}", summary="One agent account")
async def get_account(account_id: str):
    async with async_session() as session:
        try:
            row = await service.get_account(session, get_current_tenant_id(), account_id)
        except _KNOWN as exc:
            raise _errors(exc) from None
        return success_response(data=service.to_dict(row))


@router.get("/{account_id}/home", summary="The account's CLI home, for sign-in (owner)")
async def get_home(account_id: str, request: Request):
    owner_only(request, _OWNER)
    async with async_session() as session:
        try:
            row = await service.get_account(session, get_current_tenant_id(), account_id)
        except _KNOWN as exc:
            raise _errors(exc) from None
        return success_response(data=service.home_info(row))


@router.get("/{account_id}/limits", summary="The account's plan-limit windows")
async def get_limits(
    account_id: str,
    request: Request,
    refresh: bool = Query(False, description="Codex only: read live via codex app-server (owner)"),
):
    tenant = get_current_tenant_id()
    async with async_session() as session:
        try:
            row = await service.get_account(session, tenant, account_id)
        except _KNOWN as exc:
            raise _errors(exc) from None
        probe: dict | None = None
        if refresh:
            owner_only(request, _OWNER)
            probe = await _refresh(session, tenant, row)
        windows = await service.get_limits(session, tenant, row.id)
        payload = _limits_payload(row, windows)
        if probe is not None:
            payload["refresh"] = probe
        return success_response(data=payload)


def _limits_payload(row, windows) -> dict:  # noqa: ANN001
    observed = [w.observed_at for w in windows if w.observed_at]
    data = {
        "account_id": str(row.id),
        "driver": row.driver,
        "name": row.name,
        "windows": [service.limit_dict(w) for w in windows],
        "observed_at": service.iso_time(max(observed)) if observed else None,
    }
    if not windows:
        if row.driver == "gemini":
            data["unavailable_reason"] = "Gemini reports no plan limits; runs only"
        elif row.kind != "subscription":
            data["unavailable_reason"] = "This account type has no plan limits"
        elif row.driver == "claude_code":
            data["unavailable_reason"] = "Claude reports limits during runs"
    return data


async def _refresh(session, tenant: str, row) -> dict:  # noqa: ANN001
    """The opt-in Codex probe for one subscription account; recorded on success."""
    if row.driver != "codex":
        return {"kind": "unavailable", "reason": "only Codex limits can be read live (U4)"}
    if not settings.driver_accounts_codex_probe_enabled:
        return {"kind": "unavailable", "reason": "driver_accounts_codex_probe_enabled is off"}
    if row.kind != "subscription":
        return {"kind": "unavailable", "reason": limits.API_KEY_REASON}
    key = str(row.id)
    now = time.monotonic()
    last = _last_probe.get(key)
    if last is not None and now - last < PROBE_INTERVAL_SECONDS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "limits were read less than 5 minutes ago",
            headers={"Retry-After": str(int(PROBE_INTERVAL_SECONDS - (now - last)) + 1)},
        )
    binary = resolve_binary(settings.driver_codex_bin)
    if binary is None:
        return {"kind": "unavailable", "reason": "Codex CLI not installed"}
    try:
        home = homes.checked_home(row.home_dir)
    except homes.HomeError as exc:
        return {"kind": "unavailable", "reason": str(exc)}
    env = {k: v for k, v in cli_env(binary).items() if k not in CREDENTIAL_ENV["codex"]}
    env["CODEX_HOME"] = str(home)
    _last_probe[key] = now
    result = await limits.probe_codex(binary, env)
    if result.get("kind") == "windows" and result.get("windows"):
        await service.record_limits(session, tenant, row.id, result["windows"], source="probe")
        await session.commit()
    return {k: v for k, v in result.items() if k != "windows"}


# ── Writes (owner) ─────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create an agent account (owner)")
async def create_account(body: AccountCreate, request: Request):
    owner_only(request, _OWNER)
    async with async_session() as session:
        try:
            row = await service.create_account(
                session,
                get_current_tenant_id(),
                driver=body.driver,
                name=body.name,
                kind=body.kind,
                enabled=body.enabled,
                priority=body.priority,
                identity_value=body.identity,
                properties=body.properties,
            )
        except _KNOWN as exc:
            raise _errors(exc) from None
        data = service.to_dict(row)
        await session.commit()
        return success_response(data=data)


@router.patch("/{account_id}", summary="Change an account's name, order, identity (owner)")
async def update_account(account_id: str, body: AccountUpdate, request: Request):
    owner_only(request, _OWNER)
    async with async_session() as session:
        try:
            row = await service.update_account(
                session,
                get_current_tenant_id(),
                account_id,
                name=body.name,
                enabled=body.enabled,
                priority=body.priority,
                identity_value=body.identity,
                properties=body.properties,
            )
        except _KNOWN as exc:
            raise _errors(exc) from None
        data = service.to_dict(row)
        await session.commit()
        return success_response(data=data)


@router.post("/{account_id}/enable", summary="Put the account back in its pool (owner)")
async def enable_account(account_id: str, request: Request):
    return await update_account(account_id, AccountUpdate(enabled=True), request)


@router.post("/{account_id}/disable", summary="Take the account out of its pool (owner)")
async def disable_account(account_id: str, request: Request):
    return await update_account(account_id, AccountUpdate(enabled=False), request)


@router.post("/{account_id}/cooldown/reset", summary="End a cooldown now (owner)")
async def reset_cooldown(account_id: str, request: Request):
    owner_only(request, _OWNER)
    async with async_session() as session:
        try:
            row = await service.reset_cooldown(session, get_current_tenant_id(), account_id)
        except _KNOWN as exc:
            raise _errors(exc) from None
        data = service.to_dict(row)
        await session.commit()
        return success_response(data=data)


@router.put("/{account_id}/secret", summary="Set the API key — write-only, into the vault (owner)")
async def set_secret(account_id: str, body: SecretSet, request: Request):
    owner_only(request, _OWNER)
    async with async_session() as session:
        try:
            row = await service.set_secret(session, get_current_tenant_id(), account_id, body.value)
        except _KNOWN as exc:
            raise _errors(exc) from None
        data = service.to_dict(row)
        await session.commit()
        return success_response(data=data)


@router.delete("/{account_id}/secret", summary="Revoke the API key (owner)")
async def clear_secret(account_id: str, request: Request):
    owner_only(request, _OWNER)
    async with async_session() as session:
        try:
            row = await service.clear_secret(session, get_current_tenant_id(), account_id)
        except _KNOWN as exc:
            raise _errors(exc) from None
        data = service.to_dict(row)
        await session.commit()
        return success_response(data=data)


@router.delete("/{account_id}", summary="Delete an account; its key is revoked (owner)")
async def delete_account(
    account_id: str,
    request: Request,
    wipe_home: bool = Query(False, description="Also delete its CLI home (and the login in it)"),
):
    owner_only(request, _OWNER)
    async with async_session() as session:
        try:
            wiped = await service.delete_account(
                session, get_current_tenant_id(), account_id, wipe_home=wipe_home
            )
        except _KNOWN as exc:
            raise _errors(exc) from None
        await session.commit()
        return success_response(data={"id": account_id, "deleted": True, "home_removed": wiped})
