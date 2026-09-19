"""Google OAuth for connector accounts (read-only scopes), over plain HTTPS.

Flow (a "Desktop app" OAuth client, whose redirect may be any localhost port):

1. ``start()`` → a consent URL with PKCE and a one-time ``state``;
2. Google redirects the browser to ``/api/v1/connectors/oauth/callback``;
3. ``finish()`` exchanges the code for a refresh token and stores it in the
   account's 0600 secret file;
4. syncs call ``access_token()``, which refreshes and caches short-lived
   access tokens. A refused refresh raises ``ReauthRequiredError`` so the account
   shows **Reconnect** instead of failing silently.

Scopes are read-only (``gmail.readonly``, ``calendar.readonly``,
``contacts.readonly``, ``contacts.other.readonly``): with OAuth,
Google itself enforces that Life Graph can only read. Pending sign-ins live in
process memory (single API process); a restart mid-sign-in just means
clicking "Sign in" again.
"""

from __future__ import annotations

import base64
import hashlib
import secrets as pysecrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

from life_graph.config import settings
from life_graph.connectors import secrets
from life_graph.connectors.base import ConnectorError, ReauthRequiredError

if TYPE_CHECKING:
    from life_graph.connectors.models import ConnectorAccount

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALLBACK_PATH = "/api/v1/connectors/oauth/callback"

SCOPES = {
    "email": ["https://www.googleapis.com/auth/gmail.readonly"],
    "calendar": ["https://www.googleapis.com/auth/calendar.readonly"],
    # Saved contacts, and the "Other contacts" Google keeps from mail.
    "contacts": [
        "https://www.googleapis.com/auth/contacts.readonly",
        "https://www.googleapis.com/auth/contacts.other.readonly",
    ],
    "tasks": ["https://www.googleapis.com/auth/tasks.readonly"],
}
_PENDING_TTL = 600


@dataclass
class _Pending:
    tenant_id: str
    account_id: str
    verifier: str
    scopes: list[str]
    expires: float


_pending: dict[str, _Pending] = {}
_tokens: dict[str, tuple[str, float]] = {}  # account_id -> (access_token, expiry)


def redirect_uri() -> str:
    return settings.connector_oauth_redirect_base.rstrip("/") + CALLBACK_PATH


def scopes_for(connector: str) -> list[str]:
    try:
        return SCOPES[connector]
    except KeyError:
        raise ConnectorError(f"{connector} has no Google sign-in") from None


def start(tenant_id: str, account_id: str, connector: str, login_hint: str | None) -> str:
    """Return the Google consent URL for one account."""
    client = secrets.google_client()
    now = time.time()
    for key in [k for k, p in _pending.items() if p.expires < now]:
        _pending.pop(key, None)
    state = pysecrets.token_urlsafe(24)
    verifier = pysecrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    scopes = scopes_for(connector)
    _pending[state] = _Pending(tenant_id, account_id, verifier, scopes, now + _PENDING_TTL)
    params = {
        "client_id": client["client_id"],
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "code_challenge": challenge.decode(),
        "code_challenge_method": "S256",
        # offline + consent: Google only returns a refresh token on consent.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "false",
    }
    if login_hint:
        params["login_hint"] = login_hint
    return f"{AUTH_URL}?{urlencode(params)}"


def finish_cancelled(state: str) -> None:
    """The user declined or Google returned an error: drop the pending sign-in."""
    _pending.pop(state, None)


def pending_account(state: str) -> tuple[str, str] | None:
    p = _pending.get(state)
    if not p or p.expires < time.time():
        return None
    return p.tenant_id, p.account_id


async def finish(
    state: str, code: str, *, http: httpx.AsyncClient | None = None
) -> tuple[str, str]:
    """Exchange the code; store the refresh token. Returns (tenant_id, account_id)."""
    p = _pending.pop(state, None)
    if not p or p.expires < time.time():
        raise ConnectorError("sign-in expired or already used; start it again")
    client = secrets.google_client()
    data = {
        "code": code,
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "redirect_uri": redirect_uri(),
        "grant_type": "authorization_code",
        "code_verifier": p.verifier,
    }
    token = await _post(TOKEN_URL, data, http)
    refresh = token.get("refresh_token")
    if not refresh:
        raise ConnectorError("Google returned no refresh token; remove the app's access and retry")
    granted = token.get("scope", " ".join(p.scopes)).split()
    missing = [s for s in p.scopes if s not in granted]
    if missing:
        raise ConnectorError(f"permission not granted: {', '.join(missing)}")
    secrets.write_secret(
        p.tenant_id,
        p.account_id,
        {"method": "oauth", "refresh_token": refresh, "scopes": granted},
    )
    if token.get("access_token"):
        _tokens[p.account_id] = (
            token["access_token"],
            time.time() + int(token.get("expires_in", 3000)),
        )
    return p.tenant_id, p.account_id


async def access_token(
    row: ConnectorAccount, secret: dict[str, Any], *, http: httpx.AsyncClient | None = None
) -> str:
    """A valid access token for the account, refreshing when needed."""
    key = str(row.id)
    cached = _tokens.get(key)
    if cached and cached[1] - 60 > time.time():
        return cached[0]
    refresh = secret.get("refresh_token")
    if not refresh:
        raise ReauthRequiredError("no Google sign-in stored for this account")
    client = secrets.google_client()
    token = await _post(
        TOKEN_URL,
        {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        },
        http,
    )
    access = token.get("access_token")
    if not access:
        raise ReauthRequiredError("Google did not issue an access token")
    _tokens[key] = (access, time.time() + int(token.get("expires_in", 3000)))
    return access


def forget(account_id: str) -> None:
    _tokens.pop(account_id, None)


async def _post(url: str, data: dict[str, str], http: httpx.AsyncClient | None) -> dict[str, Any]:
    own = http is None
    client = http or httpx.AsyncClient(timeout=20)
    try:
        resp = await client.post(url, data=data)
    except httpx.HTTPError as exc:
        raise ConnectorError(f"could not reach Google: {type(exc).__name__}") from exc
    finally:
        if own:
            await client.aclose()
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code == 400 and body.get("error") in ("invalid_grant", "unauthorized_client"):
        raise ReauthRequiredError(f"Google refused the sign-in ({body.get('error')}); reconnect")
    if resp.status_code >= 400:
        raise ConnectorError(f"Google token endpoint error {resp.status_code}: {body.get('error')}")
    return body
