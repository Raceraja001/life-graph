"""Tenant context management for multi-tenant isolation.

Uses Python contextvars to propagate tenant_id and user_id
through the async call stack without parameter drilling.
Set by middleware, read by storage layer.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

# ── Context Variables ──────────────────────────────────
# Set per-request by TenantMiddleware, read by storage layer.
_tenant_id_var: ContextVar[str] = ContextVar("tenant_id")
_user_id_var: ContextVar[str] = ContextVar("user_id")


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Immutable tenant context extracted from request headers."""

    tenant_id: str
    user_id: str = ""
    plan: str = "free"  # free | pro | enterprise


# ── Accessors ──────────────────────────────────────────

def get_current_tenant_id() -> str:
    """Get the current tenant ID from context.

    Raises:
        RuntimeError: If no tenant context is set (middleware not applied).
    """
    try:
        return _tenant_id_var.get()
    except LookupError:
        raise RuntimeError(
            "No tenant context set. Ensure TenantMiddleware is applied "
            "and X-Tenant-ID header is present."
        )


def get_current_user_id() -> str:
    """Get the current user ID from context (empty string if not set)."""
    return _user_id_var.get("")


def set_tenant_context(tenant_id: str, user_id: str = "") -> None:
    """Set tenant context for the current request.

    Called by TenantMiddleware. Should not be called directly
    by application code.
    """
    _tenant_id_var.set(tenant_id)
    _user_id_var.set(user_id)


def has_tenant_context() -> bool:
    """Check if tenant context is set for the current request."""
    try:
        _tenant_id_var.get()
        return True
    except LookupError:
        return False
