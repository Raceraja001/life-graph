"""Database quick wins from the 2026-11-19 audit (L4, L15, M9), without a database.

* L4  vector searches send ``hnsw.iterative_scan`` when pgvector has it (0.8+).
* L15 the graph pool carries search_path as a connection default, so a Cypher
      query no longer re-runs ``LOAD 'age'`` and ``SET search_path``; one arq
      pool per process and loop instead of one per enqueue.
* M9  the Telegram (chat_id, message_id) key used against the unique index.

The Postgres side of each is in tests/integration/test_db_quick_wins_pg.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

# ── L4: iterative index scans ────────────────────────────────


@pytest.mark.parametrize(
    ("version", "expected"),
    [("0.8.0", True), ("0.8.7", True), ("1.0", True), ("0.7.4", False), ("", False), (None, False)],
)
def test_iterative_scan_needs_pgvector_0_8(version, expected):
    from life_graph.storage.postgres import _pgvector_has_iterative_scan

    assert _pgvector_has_iterative_scan(version) is expected


class _RecordingSession:
    def __init__(self, version):
        self.version = version
        self.sql: list[str] = []
        self.probes = 0

    async def execute(self, stmt, params=None):
        self.sql.append(str(stmt))

    async def scalar(self, stmt, params=None):
        self.probes += 1
        return self.version


@pytest.mark.asyncio
async def test_vector_search_sets_iterative_scan_when_supported(monkeypatch):
    import life_graph.storage.postgres as pg

    monkeypatch.setattr(pg, "_iterative_scan_supported", None)
    session = _RecordingSession("0.8.7")
    await pg._apply_vector_scan_settings(session, ef_search=100)
    await pg._apply_vector_scan_settings(session)

    assert "SET LOCAL hnsw.ef_search = 100" in session.sql
    assert session.sql.count("SET LOCAL hnsw.iterative_scan = relaxed_order") == 2
    assert session.probes == 1, "the version is read once per process"


@pytest.mark.asyncio
async def test_old_pgvector_gets_no_iterative_scan(monkeypatch):
    """pgvector < 0.8 rejects the parameter; sending it would fail every search."""
    import life_graph.storage.postgres as pg

    monkeypatch.setattr(pg, "_iterative_scan_supported", None)
    session = _RecordingSession("0.7.4")
    await pg._apply_vector_scan_settings(session)
    assert not any("iterative_scan" in s for s in session.sql)


# ── L15: graph connection setup ──────────────────────────────


@pytest.mark.asyncio
async def test_cypher_does_not_repeat_age_setup_per_query(monkeypatch):
    from life_graph.config import settings
    from life_graph.storage import graph as graph_module

    monkeypatch.setattr(graph_module, "_pool", None)
    monkeypatch.setattr(graph_module, "_available", None)
    monkeypatch.setattr(settings, "graph_enabled", True)

    executed: list[str] = []
    create_kwargs: dict = {}

    class _Conn:
        async def fetchrow(self, *a, **k):
            return (1,)

        async def fetch(self, sql, *a):
            executed.append(sql)
            return []

        async def execute(self, sql, *a):
            executed.append(sql)

    class _Acquire:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *exc):
            return False

    class _Pool:
        def acquire(self):
            return _Acquire()

    async def create_pool(*a, **kw):
        create_kwargs.update(kw)
        return _Pool()

    monkeypatch.setattr(graph_module.asyncpg, "create_pool", create_pool)

    store = graph_module.GraphStore()
    for _ in range(3):
        await store.execute_cypher("MATCH (n) RETURN n")

    assert create_kwargs["server_settings"]["search_path"].startswith("ag_catalog")
    assert not [s for s in executed if "LOAD" in s or "search_path" in s], executed
    assert len([s for s in executed if "cypher(" in s]) == 3


# ── L15: one arq pool ────────────────────────────────────────


@pytest.mark.asyncio
async def test_one_arq_pool_per_process_closed_at_shutdown(monkeypatch):
    import life_graph.runtime as runtime

    created: list[AsyncMock] = []

    async def create_pool(*a, **k):
        pool = AsyncMock()
        created.append(pool)
        return pool

    monkeypatch.setattr("arq.create_pool", create_pool)
    monkeypatch.setattr(runtime, "_arq_pool", None)
    monkeypatch.setattr(runtime, "_arq_pool_loop", None)

    first = await runtime.get_arq_pool()
    assert await runtime.get_arq_pool() is first
    assert len(created) == 1

    await runtime.close_arq_pool()
    first.close.assert_awaited_once()
    await runtime.close_arq_pool()  # idempotent
    assert await runtime.get_arq_pool() is not first, "a closed pool is never handed out"


def test_api_enqueue_sites_use_the_shared_pool():
    """The per-call create_pool sites this batch converted stay converted."""
    import inspect

    from life_graph.api import conversations, transcript_ingest
    from life_graph.services import multimodal
    from life_graph.workers import distill, tasks

    for mod in (conversations, transcript_ingest, multimodal, distill, tasks):
        assert "create_pool(" not in inspect.getsource(mod), mod.__name__


# ── M9: the Telegram message key ─────────────────────────────


@pytest.mark.parametrize(
    ("surface", "props", "expected"),
    [
        ("telegram", {"chat_id": 77, "message_id": 5}, ("77", "5")),
        ("telegram", {"chat_id": "77", "message_id": "5"}, ("77", "5")),
        ("telegram", {"chat_id": 77, "message_id": None}, None),
        ("telegram", {"chat_id": 77}, None),
        ("telegram", None, None),
        ("mcp", {"chat_id": 77, "message_id": 5}, None),
    ],
)
def test_telegram_message_key(surface, props, expected):
    from life_graph.services.capture import _telegram_message_key

    assert _telegram_message_key(surface, props) == expected
