"""Service-to-service API key authentication for Life Graph.

In SaaS mode, only the SaaS backend calls Life Graph.
Auth is via `Authorization: Bearer <key>` header.
Tenant identity comes from `X-Tenant-ID` header (set by the SaaS app).
"""

from __future__ import annotations

import logging
from secrets import compare_digest
from typing import Any

from fastapi import HTTPException, Request, status

from life_graph.config import settings
from life_graph.core.trust import UNVERIFIED, Ingress

logger = logging.getLogger(__name__)

# Routes that never require authentication or tenant context
AUTH_EXEMPT_PREFIXES = (
    "/health",
    "/live",
    "/ready",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/brain",
    "/ws",
)
# The Google OAuth callback: the browser arrives from Google without an API
# key; the one-time state it carries is the credential (api/connectors.py).
# Pairing a phone: it has no credential yet; the one-time code is it, and
# api/devices.py caps failed attempts (services/devices.PairingLimiter).
AUTH_EXEMPT_EXACT = frozenset(
    {"/", "/openapi.json", "/api/v1/connectors/oauth/callback", "/api/v1/devices/pair"}
)


def is_exempt_path(path: str) -> bool:
    """Check if a path is exempt from auth and tenant requirements.

    Prefixes match only on a path-segment boundary: ``/brain`` and
    ``/brain/app.js`` are exempt, ``/brainX`` is not (a bare ``startswith``
    let any path that merely began with an exempt word skip auth).
    """
    if path in AUTH_EXEMPT_EXACT:
        return True
    return any(path == prefix or path.startswith(prefix + "/") for prefix in AUTH_EXEMPT_PREFIXES)


def extract_api_key(headers: Any, query_params: Any) -> str | None:
    """Extract a candidate API key from request-like headers/query params.

    Checks, in order: ``Authorization: Bearer``, then ``X-API-Key``
    header, then an ``api_key`` query parameter. Shared between the
    HTTP auth path below and the WebSocket handshake in
    ``api/websocket.py`` — the WS route is the one path where a browser
    client can't know the real secret itself and instead relies on
    Caddy injecting ``X-API-Key`` after Cloudflare Access has already
    gated the request (see docs/... GCP deployment notes); a check that
    only looked at the query param never saw that header and treated
    every browser connection as unauthenticated.

    Args:
        headers: A ``Headers``-like mapping (``request.headers`` or
            ``websocket.headers``).
        query_params: A ``QueryParams``-like mapping (``request.
            query_params`` or ``websocket.query_params``).

    Returns:
        The candidate key, or None if none of the three sources had one.
        Callers are responsible for validating it.
    """
    auth_header = headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    api_key = headers.get("X-API-Key")
    if api_key:
        return api_key
    return query_params.get("api_key")


def verify_service_key(request: Request) -> str | None:
    """Verify the service API key from Authorization header.

    Returns:
        The validated API key, or None if auth is disabled (dev mode).

    Raises:
        HTTPException: 401 if the key is invalid.
    """
    # Skip auth for exempt routes
    if is_exempt_path(request.url.path):
        return None

    # Dev mode with no keys configured at all — neither the service-key list
    # nor the legacy single api_key — requires no auth.
    if settings.is_development and not settings.service_api_keys_list and not settings.api_key:
        return None

    api_key = extract_api_key(request.headers, request.query_params)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Use Authorization: Bearer <key>",
        )

    # Check against configured service keys
    valid_keys = settings.service_api_keys_list
    # Also accept legacy single api_key
    if settings.api_key:
        valid_keys = valid_keys + [settings.api_key]

    if not valid_keys:
        # No keys configured — allow in dev mode
        if settings.is_development:
            return api_key
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No API keys configured on server",
        )

    if api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return api_key


# ── Who is calling, as the server sees it ─────────────────────────────────


def _is_owner_key(api_key: str | None) -> bool:
    """True when *api_key* is one the deployment named as the owner's own.

    Compared with :func:`secrets.compare_digest` rather than ``in``: this is
    the check that decides whether a caller may claim the owner's provenance,
    and an early-exit comparison leaks the key a character at a time.
    """
    if not api_key:
        return False
    return any(compare_digest(api_key, key) for key in settings.owner_api_keys_list)


def _auth_is_off() -> bool:
    """True on a local dev stack with no credential configured at all.

    The same condition :func:`verify_service_key` uses to wave a request
    through. Anyone who can reach the port is already unauthenticated-admin
    there, so treating that caller as the owner changes nothing about who can
    do what — and without it the developer's own dashboard, which holds a key
    only when one exists, could not write a note in its own words.
    """
    return (
        settings.is_development
        and not settings.service_api_keys_list
        and not settings.api_key
        and not settings.owner_api_keys_list
    )


def ingress_for(request: Request) -> Ingress:
    """The authenticated :class:`~life_graph.core.trust.Ingress` for *request*.

    Derived from server-side state only — the device identity
    ``AuthMiddleware`` established, and the key the request actually
    presented. Nothing here reads the body, the ``X-User-ID`` header or any
    other field a caller can write, because the whole point is to have one
    statement about the caller that the caller did not author.

    Anything unrecognised comes back :data:`~life_graph.core.trust.UNVERIFIED`,
    so a path that forgets to establish an ingress fails closed.
    """
    device_id = getattr(request.state, "device_id", None)
    if device_id:
        # A phone paired with a one-time code, calling with its own token
        # (services/devices.py). Its tenant comes from the pairing too.
        return Ingress(actor=f"device:{device_id}", owner_verified=True, device_id=str(device_id))

    api_key = extract_api_key(request.headers, request.query_params)
    if _is_owner_key(api_key):
        return Ingress(actor="owner:api_key", owner_verified=True)
    if _auth_is_off():
        return Ingress(actor="owner:local", owner_verified=True)
    return UNVERIFIED
