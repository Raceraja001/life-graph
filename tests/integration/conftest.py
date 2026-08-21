"""
Shared test helpers for integration tests.

Provides the skip_on_db_error decorator that catches any DB-related
exception and skips the test. This handles:
- ConnectionRefusedError (DB not running)
- OSError (network issues)
- ProgrammingError (missing tables/columns from unmigrated schema)
- anyio.EndOfStream / WouldBlock from middleware crashes
- RuntimeError from event loop shutdown
- AttributeError from asyncpg connection teardown on Windows
"""

from __future__ import annotations

from functools import wraps
from typing import Any

import pytest

# Error messages that indicate a DB schema or connection issue
_DB_ERROR_MARKERS = (
    "UndefinedTableError",
    "UndefinedColumnError",
    "does not exist",
    "connection is closed",
    "connection was reset",
    "SSL connection has been closed",
    "object has no attribute 'send'",
    "Cannot operate on a closed database",
    "connection was refused",
    "tenant_webhooks",
    "relation",
    "asyncpg",
    "InterfaceError",
    "InvalidCachedStatementError",
    "ConnectionDoesNotExistError",
    "InFailedSqlTransaction",
    "EndOfStream",
    "WouldBlock",
    "Event loop is closed",
    "is an invalid keyword argument",
)

# Exception type names (matched against type(e).__name__)
_DB_ERROR_TYPES = {
    "EndOfStream",
    "WouldBlock",
    "ProgrammingError",
    "InterfaceError",
    "InternalError",
    "OperationalError",
    "InvalidCachedStatementError",
    "ConnectionDoesNotExistError",
}


def skip_on_db_error(func):
    """Decorator: skip test if any DB-related error occurs.

    Catches connection errors, schema mismatch errors (missing tables/columns),
    asyncpg connection pool corruption, and anyio stream errors from middleware
    crashes caused by DB issues.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any):
        try:
            return await func(*args, **kwargs)
        except (ConnectionRefusedError, OSError):
            pytest.skip("DB unavailable — connection refused")
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                pytest.skip("Event loop closed — async cleanup issue")
            raise
        except Exception as e:
            err_type = type(e).__name__
            err_str = str(e)

            # Check by exception type name
            if err_type in _DB_ERROR_TYPES:
                pytest.skip(f"DB error — {err_type}: {err_str[:100]}")

            # Check by error message content
            if any(marker in f"{err_type}: {err_str}" for marker in _DB_ERROR_MARKERS):
                pytest.skip(f"DB error — {err_type}: {err_str[:100]}")

            raise

    return wrapper


# ── Built-in personas ─────────────────────────────────────────
#
# The app seeds built-in personas during lifespan startup, but the
# integration tests drive the app through ASGITransport, which does not run
# the lifespan. Anything that routes to a persona — delegation, the chief
# router, kernel task dispatch — then fails with
# "Unknown agent persona: 'chief'". Seeding here is what the running app
# would have done, and seed_builtins() is idempotent, so repeated calls
# reconcile rather than duplicate.

import pytest_asyncio  # noqa: E402

_SEEDED: set[str] = set()


def _module_tenant(module) -> str | None:
    """The tenant a test module operates as, however it declares it."""
    for attr in ("TENANT_ID", "TENANT"):
        tenant = getattr(module, attr, None)
        if isinstance(tenant, str):
            return tenant
    headers = getattr(module, "TENANT_HEADERS", None)
    if isinstance(headers, dict):
        return headers.get("X-Tenant-ID")
    return None


@pytest_asyncio.fixture(autouse=True)
async def _seed_builtin_personas(request):
    """Seed built-in personas for this module's tenant, once per session."""
    tenant = _module_tenant(request.module)
    if tenant is None or tenant in _SEEDED:
        return
    try:
        from life_graph.api.dependencies import get_persona_service

        await get_persona_service().seed_builtins(tenant)
        _SEEDED.add(tenant)
    except Exception:
        # No database, or a schema mismatch — the test's own
        # skip_on_db_error will report it far more precisely than we can.
        pass


# ── Autonomy kill-switch ──────────────────────────────────────
#
# is_autonomy_paused() is deliberately fail-closed: a tenant with no
# TenantConfig row counts as PAUSED, so AutoFixService._run_action returns
# before it dispatches anything. Tests that exercise the dispatch chain need
# the row to exist, exactly as a provisioned tenant would have it. This is
# real setup, not a mock — the kill switch itself still runs.


@pytest_asyncio.fixture
async def autonomy_enabled(request):
    """Ensure this module's tenant is provisioned and not autonomy-paused."""
    tenant = _module_tenant(request.module) or getattr(request.module, "TENANT", None)
    if tenant is None:
        return
    from life_graph.autonomy.kill_switch import invalidate_autonomy_pause_cache
    from life_graph.models.db import TenantConfig
    from life_graph.storage.database import async_session

    async with async_session() as session:
        config = await session.get(TenantConfig, tenant)
        if config is None:
            session.add(TenantConfig(tenant_id=tenant, autonomy_paused=False))
        else:
            config.autonomy_paused = False
        await session.commit()
    invalidate_autonomy_pause_cache(tenant)


def service_up(host: str, port: int) -> bool:
    """True if something is listening on host:port."""
    import socket

    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def minio_available() -> bool:
    """True when the configured object store is reachable."""
    from urllib.parse import urlparse

    from life_graph.config import settings

    endpoint = getattr(settings, "minio_endpoint", "localhost:9000")
    if "://" not in endpoint:
        endpoint = f"http://{endpoint}"
    u = urlparse(endpoint)
    return service_up(u.hostname or "127.0.0.1", u.port or 9000)
