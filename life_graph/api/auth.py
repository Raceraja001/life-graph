"""Service-to-service API key authentication for Life Graph.

In SaaS mode, only the SaaS backend calls Life Graph.
Auth is via `Authorization: Bearer <key>` header.
Tenant identity comes from `X-Tenant-ID` header (set by the SaaS app).
"""

from __future__ import annotations

import logging

from fastapi import Request, HTTPException, status

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

    # Dev mode: no auth required
    if settings.is_development and not settings.service_api_keys_list:
        # Also accept legacy single api_key for backward compatibility
        if not settings.api_key:
            return None

    # Extract bearer token
    auth_header = request.headers.get("Authorization", "")
    api_key = None

    if auth_header.startswith("Bearer "):
        api_key = auth_header[7:].strip()
    else:
        # Fallback: X-API-Key header (backward compatibility)
        api_key = request.headers.get("X-API-Key")
        # Fallback: query parameter (backward compatibility)
        if not api_key:
            api_key = request.query_params.get("api_key")

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
