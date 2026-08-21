"""
Shared test helpers for integration tests.

``skip_on_db_error`` exists so the suite can run in an environment with no
database — CI's lint and unit jobs, a fresh checkout — without every
DB-backed test failing.

It deliberately does NOT decide that from the exception. It used to: any
error whose text contained a marker like "relation", "asyncpg" or "does not
exist" was treated as "no database" and skipped. Those strings appear in
plenty of genuine failures, so real bugs were silently reported as skips,
and when the containers died mid-run 263 tests skipped rather than failing.

Instead it asks the database directly, once per session. If Postgres is
reachable, every exception is a real failure and propagates. Only when the
database genuinely cannot be reached does a test skip.
"""

from __future__ import annotations

import socket
from functools import wraps
from typing import Any
from urllib.parse import urlparse

import pytest

# ── Database reachability ─────────────────────────────────────

_db_reachable_cache: bool | None = None


def db_reachable() -> bool:
    """True if the configured Postgres accepts a TCP connection.

    Checked once per session — a test run does not start and stop its own
    database, so re-probing per test would only add latency.
    """
    global _db_reachable_cache
    if _db_reachable_cache is not None:
        return _db_reachable_cache

    from life_graph.config import settings

    url = settings.database_url
    try:
        parsed = urlparse(url.split("+")[0] + "://" + url.split("://", 1)[1])
        host, port = parsed.hostname or "127.0.0.1", parsed.port or 5432
    except Exception:
        host, port = "127.0.0.1", 5432

    with socket.socket() as s:
        s.settimeout(1.0)
        _db_reachable_cache = s.connect_ex((host, port)) == 0
    return _db_reachable_cache


def pytest_report_header(config) -> str:
    """Say plainly whether the database is there.

    Without this, a run against a stopped database looks like a pile of
    skips with no explanation at the top of the output.
    """
    if db_reachable():
        return "database: reachable — DB-backed tests will run"
    return (
        "database: UNREACHABLE — DB-backed tests will SKIP, not fail. "
        "Start it with ./start.sh --infra"
    )


def skip_on_db_error(func):
    """Skip *func* only when the database is genuinely unreachable.

    With Postgres up, every exception propagates — a schema mismatch, a
    constraint violation or a bug in the code under test is a failure, not a
    skip. This is the whole point: the previous version pattern-matched
    exception text and turned real defects into green runs.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any):
        try:
            return await func(*args, **kwargs)
        except (ConnectionRefusedError, OSError) as exc:
            # A refused connection is unambiguous, whether or not the probe
            # agrees (the DB may have died mid-run).
            pytest.skip(f"DB unavailable — {type(exc).__name__}: {str(exc)[:100]}")
        except Exception:
            if not db_reachable():
                pytest.skip("DB unavailable — no Postgres on the configured port")
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
