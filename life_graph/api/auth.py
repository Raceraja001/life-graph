"""API key authentication for Life Graph.

Supports API key via header (X-API-Key) or query parameter (?api_key=...).
When LIFE_GRAPH_API_KEY is not set, all requests are allowed (dev mode).
"""

from fastapi import Request, Security, HTTPException, status
from fastapi.security import APIKeyHeader, APIKeyQuery

from life_graph.config import settings

# Accept API key from either header or query parameter
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)

# Routes that never require authentication
AUTH_EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/brain",
)
# Exact paths exempt from auth (can't use prefix matching for "/")
AUTH_EXEMPT_EXACT = frozenset({"/"})


async def verify_api_key(
    request: Request,
    header_key: str | None = Security(api_key_header),
    query_key: str | None = Security(api_key_query),
) -> str:
    """Verify API key from header or query parameter.

    Auth is skipped for:
    - Exempt paths (health, docs, dashboard)
    - When no API key is configured (dev mode)

    Returns the validated API key or "anonymous" when auth is disabled.
    """
    # Skip auth for exempt routes
    path = request.url.path
    if path in AUTH_EXEMPT_EXACT or any(
        path.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES
    ):
        return "anonymous"

    # If no API key configured, allow all requests (dev mode)
    if not settings.api_key:
        return "anonymous"

    api_key = header_key or query_key

    if not api_key or api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
