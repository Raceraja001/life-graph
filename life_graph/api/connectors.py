"""Connector accounts: list, add, change, sync, Google sign-in, and today's view.

Prefix: /connectors. Credentials go in (app passwords, feed URLs, the Google
OAuth client) and are written to 0600 files; they never come back out of any
endpoint. The OAuth callback is the one unauthenticated route: the browser
arrives from Google without an API key, and the one-time ``state`` it carries
is what ties it to the account that started the sign-in.
"""

from __future__ import annotations

import asyncio
import html
import logging
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from life_graph.api.responses import success_response
from life_graph.config import settings
from life_graph.connectors import google_oauth, secrets
from life_graph.connectors.base import AUTH_OAUTH, ConnectorError
from life_graph.connectors.runtime import AccountError, get_runtime
from life_graph.core.tenant import get_current_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connectors", tags=["connectors"])

# Background syncs started from the API, kept referenced so they are not
# garbage-collected mid-run.
_running: set[asyncio.Task] = set()


class AccountCreate(BaseModel):
    connector: str
    display_name: str = Field(..., min_length=1, max_length=128)
    auth_method: str
    settings: dict[str, Any] = Field(default_factory=dict)
    exposure: str = "standard"
    # {"password": "..."} for app_password, {"url": "..."} for a feed; omitted for OAuth.
    secret: dict[str, str] | None = None


class AccountUpdate(BaseModel):
    display_name: str | None = None
    enabled: bool | None = None
    exposure: str | None = None
    sync_interval_min: int | None = None
    settings: dict[str, Any] | None = None


class CredentialUpdate(BaseModel):
    auth_method: str
    secret: dict[str, str]


MAX_IMPORT_CHARS = 5_000_000


class FileImport(BaseModel):
    # The file's text, read in the browser (a .vcf export).
    vcard: str = Field(..., min_length=1, max_length=MAX_IMPORT_CHARS)


class GoogleClient(BaseModel):
    # The JSON downloaded from Google Cloud for a "Desktop app" OAuth client.
    client: dict[str, Any]


def _bad(exc: Exception) -> HTTPException:
    status = 404 if "not found" in str(exc) else 400
    return HTTPException(status_code=status, detail=str(exc))


def recommend(username: str | None, workspace_admin: bool | None) -> dict[str, str]:
    """The auth method Life Graph suggests for an account (the user may override)."""
    domain = (username or "").rsplit("@", 1)[-1].lower()
    if domain in ("gmail.com", "googlemail.com"):
        return {
            "auth_method": "app_password",
            "reason": "Personal Gmail: an app password works at once. OAuth here needs your own"
            " Google Cloud app and shows an unverified-app warning.",
        }
    if workspace_admin:
        return {
            "auth_method": "oauth",
            "reason": "You administer this Workspace: an Internal OAuth app is read-only at"
            " Google's side, with no warning screen and no expiry.",
        }
    return {
        "auth_method": "app_password",
        "reason": "A workplace account you don't administer: try an app password first (Google"
        " Account → Security → App passwords). If it's missing, IT has disabled it; OAuth"
        " through your own app is the fallback and may be blocked too. Check your employer's"
        " policy on connecting work mail, and keep this account local-only.",
        "exposure": "local_only",
    }


@router.get("", summary="Connector catalogue and accounts")
async def list_connectors(tenant_id: str = Depends(get_current_tenant_id)):
    runtime = get_runtime()
    return success_response(
        data={
            "enabled": settings.connectors_enabled,
            "connectors": runtime.catalogue(),
            "accounts": await runtime.list_accounts(tenant_id),
            "google_client_configured": secrets.has_google_client(),
            "oauth_redirect_uri": google_oauth.redirect_uri(),
            "timezone": settings.user_timezone,
        }
    )


@router.get("/recommend", summary="Suggested auth method for an address")
async def recommend_method(username: str = Query(""), workspace_admin: bool | None = Query(None)):
    return success_response(data=recommend(username, workspace_admin))


@router.post("/accounts", status_code=201, summary="Add an account")
async def create_account(body: AccountCreate, tenant_id: str = Depends(get_current_tenant_id)):
    try:
        account = await get_runtime().create_account(
            tenant_id,
            connector=body.connector,
            display_name=body.display_name,
            auth_method=body.auth_method,
            account_settings=body.settings,
            exposure=body.exposure,
            secret=body.secret,
        )
    except (AccountError, ValueError) as exc:
        raise _bad(exc) from exc
    return success_response(data=account)


@router.patch("/accounts/{account_id}", summary="Change an account")
async def update_account(
    account_id: str, body: AccountUpdate, tenant_id: str = Depends(get_current_tenant_id)
):
    try:
        account = await get_runtime().update_account(
            tenant_id, account_id, **body.model_dump(exclude_none=True)
        )
    except (AccountError, ValueError) as exc:
        raise _bad(exc) from exc
    return success_response(data=account)


@router.put("/accounts/{account_id}/credential", summary="Replace an account's credential")
async def set_credential(
    account_id: str, body: CredentialUpdate, tenant_id: str = Depends(get_current_tenant_id)
):
    if body.auth_method == AUTH_OAUTH:
        raise HTTPException(400, "OAuth credentials come from the sign-in flow, not this endpoint")
    try:
        account = await get_runtime().set_credential(
            tenant_id, account_id, body.auth_method, body.secret
        )
    except (AccountError, ValueError) as exc:
        raise _bad(exc) from exc
    return success_response(data=account)


@router.delete("/accounts/{account_id}", summary="Remove an account and its indexed items")
async def delete_account(account_id: str, tenant_id: str = Depends(get_current_tenant_id)):
    try:
        await get_runtime().delete_account(tenant_id, account_id)
    except AccountError as exc:
        raise _bad(exc) from exc
    google_oauth.forget(account_id)
    return success_response(data={"id": account_id, "deleted": True})


@router.post("/accounts/{account_id}/sync", status_code=202, summary="Sync now (background)")
async def sync_now(account_id: str, tenant_id: str = Depends(get_current_tenant_id)):
    runtime = get_runtime()
    accounts = {a["id"]: a for a in await runtime.list_accounts(tenant_id)}
    if account_id not in accounts:
        raise HTTPException(404, "account not found")

    async def _run() -> None:
        try:
            await runtime.sync_account(tenant_id, account_id)
        except Exception:
            logger.exception("Manual connector sync failed")

    task = asyncio.create_task(_run())
    _running.add(task)
    task.add_done_callback(_running.discard)
    return success_response(data={"id": account_id, "status": "started"})


@router.post("/accounts/{account_id}/import", summary="Replace an account's items from a file")
async def import_file(
    account_id: str, body: FileImport, tenant_id: str = Depends(get_current_tenant_id)
):
    """A vCard export for a contacts account. The file itself is not kept."""
    try:
        outcome = await get_runtime().import_file(tenant_id, account_id, body.vcard)
    except (AccountError, ValueError) as exc:
        raise _bad(exc) from exc
    return success_response(data={"id": account_id, **outcome.as_dict()})


@router.put("/google-client", summary="Store the Google OAuth client (Desktop app JSON)")
async def put_google_client(body: GoogleClient, tenant_id: str = Depends(get_current_tenant_id)):
    try:
        secrets.write_google_client(body.client)
    except secrets.SecretError as exc:
        raise HTTPException(400, str(exc)) from exc
    return success_response(data={"google_client_configured": True})


@router.post("/accounts/{account_id}/oauth/start", summary="Begin Google sign-in")
async def oauth_start(account_id: str, tenant_id: str = Depends(get_current_tenant_id)):
    accounts = {a["id"]: a for a in await get_runtime().list_accounts(tenant_id)}
    account = accounts.get(account_id)
    if not account:
        raise HTTPException(404, "account not found")
    if account["auth_method"] != AUTH_OAUTH:
        raise HTTPException(400, "this account does not use Google sign-in")
    try:
        url = google_oauth.start(
            tenant_id, account_id, account["connector"], account["settings"].get("username")
        )
    except secrets.SecretError as exc:
        raise HTTPException(400, f"Google OAuth client not configured: {exc}") from exc
    except ConnectorError as exc:
        raise HTTPException(400, str(exc)) from exc
    return success_response(data={"url": url, "redirect_uri": google_oauth.redirect_uri()})


def _back(status: str, message: str) -> HTMLResponse:
    target = f"{settings.connector_oauth_return_url}?{urlencode({'connector': status, 'message': message})}"
    safe = html.escape(target, quote=True)
    return HTMLResponse(
        f'<!doctype html><meta http-equiv="refresh" content="0;url={safe}">'
        f'<p>{html.escape(message)} — <a href="{safe}">back to Life Graph</a></p>'
    )


@router.get("/oauth/callback", include_in_schema=False)
async def oauth_callback(state: str = Query(""), code: str = Query(""), error: str = Query("")):
    """Where Google sends the browser back. Exempt from API-key auth (see api/auth.py)."""
    if error:
        google_oauth.finish_cancelled(state)
        return _back("error", f"Google sign-in was not completed ({error}).")
    if not state or not code:
        return _back("error", "Sign-in response was incomplete.")
    try:
        tenant_id, account_id = await google_oauth.finish(state, code)
        await get_runtime().mark_reconnected(tenant_id, account_id)
    except ConnectorError as exc:
        return _back("error", str(exc))
    except Exception:
        logger.exception("OAuth callback failed")
        return _back("error", "Sign-in failed; see the API log.")
    return _back("ok", "Google account connected. The first sync starts within 5 minutes.")


@router.post("/items/{item_id}/remind", summary="Turn a promise from sent mail into a reminder")
async def remind_promise(item_id: str, tenant_id: str = Depends(get_current_tenant_id)):
    """Create a time-triggered intention for a promise the user made by email.

    Nothing is created until the user asks: this is the one step that turns a
    detected promise into a reminder. Due at 09:00 (user's timezone) on the
    promised date, or tomorrow when the email gave no date. Written directly
    (not via IntentionService, whose rows carry no tenant) so the reminder
    belongs to this tenant.
    """
    import uuid
    from datetime import date, datetime, time, timedelta
    from zoneinfo import ZoneInfo

    from life_graph.connectors import store
    from life_graph.models.db import Intention
    from life_graph.storage.database import async_session

    async with async_session() as session:
        row = await store.item_dict(session, tenant_id, item_id)
        commitment = ((row or {}).get("flags") or {}).get("commitment")
        if not row or not commitment:
            raise HTTPException(404, "no promise on this item")
        try:
            tz = ZoneInfo(settings.user_timezone)
        except Exception:
            tz = ZoneInfo("UTC")
        due_raw = row["flags"].get("commitment_due")
        try:
            due = date.fromisoformat(due_raw) if due_raw else None
        except ValueError:
            due = None
        day = due or (datetime.now(tz).date() + timedelta(days=1))
        trigger = datetime.combine(day, time(9, 0), tzinfo=tz)
        intention = Intention(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            content=f"{commitment} (you promised in '{row['title']}')",
            trigger_type="time",
            trigger_condition=f"promised by email on {row['occurred_at']:%d %b}",
            trigger_time=trigger,
            context_match={"connector_item_id": item_id},
            priority="normal",
            status="pending",
        )
        session.add(intention)
        await store.set_flag(session, tenant_id, item_id, promise_state="reminded")
        await session.commit()
    return success_response(
        data={"intention_id": str(intention.id), "trigger_time": trigger.isoformat()}
    )


@router.post("/items/{item_id}/dismiss-promise", summary="Hide a detected promise")
async def dismiss_promise(item_id: str, tenant_id: str = Depends(get_current_tenant_id)):
    from life_graph.connectors import store
    from life_graph.storage.database import async_session

    async with async_session() as session:
        if not await store.set_flag(session, tenant_id, item_id, promise_state="dismissed"):
            raise HTTPException(404, "item not found")
        await session.commit()
    return success_response(data={"id": item_id, "dismissed": True})


@router.get("/today", summary="Today's events and mail waiting on you (dashboard view)")
async def today(tenant_id: str = Depends(get_current_tenant_id)):
    """The full local rendering: the dashboard is the user's own screen."""
    from life_graph.connectors.brief import brief_sections

    sections = await brief_sections(tenant_id)
    if not sections:
        return success_response(data=None)
    return success_response(data={**sections["local"], "timezone": settings.user_timezone})
