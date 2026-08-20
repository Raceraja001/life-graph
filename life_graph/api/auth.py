"""Service-to-service API key authentication for Life Graph.

In SaaS mode, only the SaaS backend calls Life Graph.
Auth is via `Authorization: Bearer <key>` header.
Tenant identity comes from `X-Tenant-ID` header (set by the SaaS app).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request, status

from life_graph.config import settings

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
AUTH_EXEMPT_EXACT = frozenset({"/", "/openapi.json"})


def is_exempt_path(path: str) -> bool:
    """Check if a path is exempt from auth and tenant requirements."""
    if path in AUTH_EXEMPT_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES)


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
