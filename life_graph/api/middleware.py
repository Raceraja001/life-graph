"""Request middleware stack for Life Graph SaaS microservice.

Middleware order (applied bottom-to-top in FastAPI):
  1. RequestIDMiddleware  — Generate X-Request-ID
  2. AuthMiddleware       — Verify service API key
  3. TenantMiddleware     — Extract X-Tenant-ID, set context
  4. RateLimitMiddleware  — Per-tenant rate limiting via Redis
  5. RequestLoggingMiddleware — Log request/response
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from life_graph.api.auth import is_exempt_path, verify_service_key
from life_graph.config import settings
from life_graph.core.metrics import track_request
from life_graph.core.rate_limit import check_rate_limit
from life_graph.core.tenant import set_tenant_context

logger = logging.getLogger(__name__)

# Default tenant for dev mode when no header is provided
DEV_DEFAULT_TENANT = "dev"
DEV_DEFAULT_USER = "dev-user"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate a unique request ID for each request.

    Sets X-Request-ID on both request state and response header
    for request tracing and log correlation.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-API-Version"] = "1.0"
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Verify service-to-service API key.

    Checks Authorization: Bearer <key> header against configured
    service API keys. Skips auth for exempt paths and dev mode.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            verify_service_key(request)
        except Exception as e:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": str(e.detail) if hasattr(e, "detail") else str(e),
                        "request_id": getattr(request.state, "request_id", ""),
                    }
                },
            )

        return await call_next(request)


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract tenant context from request headers.

    Reads X-Tenant-ID and X-User-ID headers, sets context vars
    for downstream use by storage layer and services.

    In dev mode, defaults to "dev" tenant when header is missing.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip for exempt paths
        if is_exempt_path(request.url.path):
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID", "")
        user_id = request.headers.get("X-User-ID", "")

        if not tenant_id:
            if settings.is_development:
                tenant_id = DEV_DEFAULT_TENANT
                user_id = user_id or DEV_DEFAULT_USER
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "MISSING_TENANT",
                            "message": "X-Tenant-ID header is required",
                            "request_id": getattr(
                                request.state, "request_id", ""
                            ),
                        }
                    },
                )

        # Set context vars for this request
        set_tenant_context(tenant_id, user_id)
        request.state.tenant_id = tenant_id
        request.state.user_id = user_id

        # ── Tenant deactivation check ─────────────────────────
        # Block write operations for deactivated tenants (read-only mode).
        # GET requests are always allowed. Admin paths are exempt so
        # operators can still reactivate or delete the tenant.
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if not request.url.path.startswith(
                "/admin"
            ) and not request.url.path.startswith("/api/v1/admin"):
                try:
                    from life_graph.models.db import TenantConfig
                    from life_graph.storage.database import (
                        async_session as _async_session,
                    )
                    from life_graph.api.responses import error_response

                    async with _async_session() as _db:
                        _config = await _db.get(TenantConfig, tenant_id)
                        if _config and _config.status == "deactivated":
                            return JSONResponse(
                                status_code=403,
                                content=error_response(
                                    "TENANT_DEACTIVATED",
                                    "Tenant is deactivated. Read-only access only.",
                                ),
                            )
                except Exception:
                    # If we can't check, allow the request through
                    pass

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration.

    Produces structured log entries with tenant and request ID
    for observability.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        tenant_id = getattr(request.state, "tenant_id", "-")
        request_id = getattr(request.state, "request_id", "-")

        logger.info(
            "%s %s → %d (%.0fms) tenant=%s rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            tenant_id,
            request_id[:8] if len(request_id) > 8 else request_id,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 1),
                "tenant_id": tenant_id,
                "request_id": request_id,
            },
        )

        # Track metrics
        track_request(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration=duration_ms / 1000,
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-tenant rate limiting via Redis sliding window.

    Checks the tenant's plan limits and returns 429 Too Many Requests
    when exceeded. Adds X-RateLimit-* headers to all responses.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip for exempt paths
        if is_exempt_path(request.url.path):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return await call_next(request)

        # Check rate limit
        result = await check_rate_limit(tenant_id, resource="requests")

        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Rate limit exceeded. Limit: {result.limit}/min.",
                        "request_id": getattr(request.state, "request_id", ""),
                    }
                },
                headers={
                    **result.headers,
                    "Retry-After": str(result.reset_at - int(__import__('time').time())),
                },
            )

        response = await call_next(request)

        # Add rate limit headers to all responses
        for key, value in result.headers.items():
            response.headers[key] = value

        return response
