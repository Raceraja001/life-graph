# tests/unit/test_list_endpoint_sweep_fixes.py
"""Unit tests for the second sweep of list/CRUD latency fixes:
- PreferenceStore.list() / EvidenceStore.list_for_preference() defer
  unused heavy columns (embedding, raw_content).
- PostgresMemoryStore.search_similar()/hybrid_search() defer embedding
  where the caller never reads it.
- PersonaService.list_all() / SchedulerService.list_all() drop an
  always-redundant COUNT(*) (no pagination -> total == len(rows) always).
- NotificationEngine.list_all()'s two COUNT(*) queries become opt-in.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.core.tenant import set_tenant_context
from life_graph.kernel.notification_engine import NotificationEngine
from life_graph.kernel.personas import PersonaService
from life_graph.kernel.scheduler import SchedulerService
from life_graph.services.evidence_store import EvidenceStore
from life_graph.services.preference_store import PreferenceStore
from life_graph.storage.postgres import PostgresMemoryStore


def _deferred_columns(stmt) -> set[str]:
    deferred = set()
    for opt in stmt._with_options:
        for entry in getattr(opt, "context", ()):
            strategy = dict(getattr(entry, "strategy", ()) or ())
            if strategy.get("deferred"):
                deferred.add(entry.path.path[-1].key)
    return deferred


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows=None, scalar_value=None):
        self._rows = rows
        self._scalar_value = scalar_value

    def scalars(self):
        return _FakeScalars(self._rows or [])

    def scalar(self):
        return self._scalar_value


class _CapturingSession:
    """Captures every executed statement; list queries return `rows`,
    everything else (COUNT queries) returns `scalar_value`."""

    def __init__(self, rows, scalar_value=0):
        self._rows = rows
        self._scalar_value = scalar_value
        self.executed: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, stmt):
        self.executed.append(stmt)
        # A COUNT(*) statement (select(func.count())...) has exactly one
        # selected column with key=None; a full-entity select (select(Model))
        # has many columns, one per mapped attribute. That's a reliable way
        # to tell them apart without depending on SQLAlchemy internals.
        cols = list(stmt.selected_columns)
        if len(cols) == 1 and cols[0].key is None:
            return _FakeResult(scalar_value=self._scalar_value)
        return _FakeResult(rows=self._rows)


# ── PreferenceStore.list() ──────────────────────────────────────


@pytest.mark.asyncio
async def test_preference_list_defers_embedding():
    session = _CapturingSession(rows=[])
    store = PreferenceStore(session_factory=lambda: session, embedding_service=None)

    await store.list("t1")

    assert "embedding" in _deferred_columns(session.executed[0])


# ── EvidenceStore.list_for_preference() ─────────────────────────


@pytest.mark.asyncio
async def test_evidence_list_defers_embedding_and_raw_content():
    session = _CapturingSession(rows=[])
    store = EvidenceStore(session_factory=lambda: session, embedding_service=None)
    import uuid

    await store.list_for_preference("t1", uuid.uuid4())

    deferred = _deferred_columns(session.executed[0])
    assert deferred == {"embedding", "raw_content"}


# ── PostgresMemoryStore.search_similar() / hybrid_search() ──────
#
# NOTE: search_similar()'s query also calls Memory.embedding.cosine_distance()
# for the ORDER BY, which isn't implemented by tests/conftest.py's minimal
# _FakeVector comparator (real pgvector isn't installed for unit tests, see
# conftest.py's docstring) -- so that method's query construction was never
# unit-testable before this change either (confirmed: no pre-existing unit
# test exercises it). Not adding a broken test for it; the include_embedding
# addition there is the exact same defer() idiom already covered above and
# in test_list_memories_defer_embedding.py. hybrid_search()'s final re-fetch
# doesn't touch cosine_distance, so it IS testable:


class _HybridSearchSession:
    """First execute() is the raw-SQL scoring query (needs .fetchall());
    second is the ORM re-fetch by id (needs .scalars().all())."""

    def __init__(self, scored_ids, rows):
        self._scored_ids = scored_ids
        self._rows = rows
        self.executed: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, stmt, params=None):
        self.executed.append(stmt)
        if len(self.executed) == 1:
            return SimpleNamespace(fetchall=lambda: self._scored_ids)
        return _FakeResult(rows=self._rows)


@pytest.mark.asyncio
async def test_hybrid_search_defers_embedding_on_refetch():
    set_tenant_context("t1")
    store = PostgresMemoryStore()
    session = _HybridSearchSession(scored_ids=[], rows=[])
    from unittest.mock import patch

    with patch("life_graph.storage.postgres.async_session", lambda: session):
        await store.hybrid_search(embedding=[0.1, 0.2], query_text="test")

    # No scored ids -> the method returns early after the raw-SQL call, so
    # the ORM re-fetch never runs. Re-drive with a non-empty scored_ids to
    # actually reach the defer()'d statement.
    session2 = _HybridSearchSession(scored_ids=[("id-1", 0.9)], rows=[])
    with patch("life_graph.storage.postgres.async_session", lambda: session2):
        await store.hybrid_search(embedding=[0.1, 0.2], query_text="test")

    assert len(session2.executed) == 2
    assert "embedding" in _deferred_columns(session2.executed[1])


# ── PersonaService.list_all() ────────────────────────────────────


@pytest.mark.asyncio
async def test_persona_list_all_skips_count_query():
    rows = [SimpleNamespace(name="a"), SimpleNamespace(name="b")]
    session = _CapturingSession(rows=rows)
    svc = PersonaService(session_factory=lambda: session)
    svc._persona_to_dict = lambda row: {"name": row.name}

    personas, total = await svc.list_all("t1")

    assert len(session.executed) == 1  # only the list select, no COUNT
    assert total == 2 == len(personas)


# ── SchedulerService.list_all() ──────────────────────────────────


@pytest.mark.asyncio
async def test_scheduler_list_all_skips_count_query():
    rows = [SimpleNamespace(id="j1")]
    session = _CapturingSession(rows=rows)
    svc = SchedulerService(session_factory=lambda: session, process_manager=None)
    svc._job_to_dict = lambda row: {"id": row.id}

    jobs, total = await svc.list_all("t1")

    assert len(session.executed) == 1
    assert total == 1 == len(jobs)


# ── NotificationEngine.list_all() ────────────────────────────────


@pytest.mark.asyncio
async def test_notification_list_all_skips_both_counts_by_default():
    rows = [SimpleNamespace(id="n1")]
    session = _CapturingSession(rows=rows)
    svc = NotificationEngine(session_factory=lambda: session)
    svc._notif_to_dict = lambda row: {"id": row.id}

    notifs, total, unread = await svc.list_all("t1")

    assert len(session.executed) == 1  # only the list select
    assert total is None
    assert unread is None
    assert len(notifs) == 1


@pytest.mark.asyncio
async def test_notification_list_all_runs_counts_when_requested():
    rows = [SimpleNamespace(id="n1")]
    session = _CapturingSession(rows=rows, scalar_value=5)
    svc = NotificationEngine(session_factory=lambda: session)
    svc._notif_to_dict = lambda row: {"id": row.id}

    notifs, total, unread = await svc.list_all(
        "t1", include_total=True, include_unread_count=True
    )

    assert len(session.executed) == 3  # list + total COUNT + unread COUNT
    assert total == 5
    assert unread == 5
