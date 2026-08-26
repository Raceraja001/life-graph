"""Tenant context management for multi-tenant isolation.

Uses Python contextvars to propagate tenant_id and user_id
through the async call stack without parameter drilling.
Set by middleware, read by storage layer.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

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
    except LookupError as exc:
        raise RuntimeError(
            "No tenant context set. Ensure TenantMiddleware is applied "
            "and X-Tenant-ID header is present."
        ) from exc


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


@contextmanager
def tenant_scope(tenant_id: str, user_id: str = "") -> Iterator[None]:
    """Set tenant context for a block, restoring the previous value on exit.

    ``set_tenant_context`` is fire-and-forget, which is correct for
    ``TenantMiddleware`` because each request already runs in its own context.
    Background consumers are not like that: the Telegram poller handles many
    chats, potentially belonging to different tenants, sequentially inside one
    asyncio task and therefore one context. Setting without restoring would
    leave one chat's tenant in place for whatever ran next, and the storage
    layer reads this variable rather than taking a parameter — so a handler
    that forgot to set it would silently query the previous chat's tenant.

    Use this anywhere a tenant is established outside the request cycle.
    """
    tenant_token = _tenant_id_var.set(tenant_id)
    user_token = _user_id_var.set(user_id)
    try:
        yield
    finally:
        _tenant_id_var.reset(tenant_token)
        _user_id_var.reset(user_token)


def has_tenant_context() -> bool:
    """Check if tenant context is set for the current request."""
    try:
        _tenant_id_var.get()
        return True
    except LookupError:
        return False
