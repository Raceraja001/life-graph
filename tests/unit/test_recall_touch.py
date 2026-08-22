"""Recalling a memory must count as accessing it.

PostgresMemoryStore.touch() increments access_count and sets last_accessed.
It was called from exactly two places, both in MemoryManager, and both on a
*dedup hit* — when an incoming memory matched an existing one. Nothing in the
recall path called it.

The consequence, measured on the live database: 916 of 922 memories had
last_accessed IS NULL and access_count = 0.

That propagates into three separate behaviours, none of which raise:

  Archival   DecayCalculator resolves days-since-access from last_accessed,
             falling back to created_at when it is NULL. So decay measured age
             since *creation*, not age since *use*, and every non-critical
             memory was archived 24-51 days after being created no matter how
             often it was recalled. Only importance >= 0.85 ("critical") is
             exempt, and importance otherwise moves that deadline by nine days
             across its whole range, because it is a linear multiplier inside
             an exponential.

  Frequency  _frequency_score(0) == _frequency_score(1) == 0.1, so the
             frequency signal (weight 0.10) was constant across ~all
             candidates and took no part in ranking.

  Recency    the recency signal (weight 0.15) measured how long ago a memory
             was written rather than how long ago it was used.

A forgetting curve where use does not reinforce is not a forgetting curve.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.services.recall import RecallEngine


class _Memory:
    def __init__(self, **kw):
        now = datetime.now(UTC)
        self.id = kw.get("id", uuid.uuid4())
        self.content = kw.get("content", "a memory")
        self.tags = kw.get("tags", ["decision"])
        self.properties = kw.get("properties", {})
        self.importance = kw.get("importance", 0.5)
        self.trust_score = 0.5
        self.impact_score = kw.get("impact_score", 0.5)
        self.access_count = kw.get("access_count", 0)
        self.last_accessed = kw.get("last_accessed")
        self.created_at = now
        self.source_type = "inferred"
        self.status = "active"
        self.confidence = 0.5
        self.reasoning = None
        self.extraction_tier = None
        self.extraction_confidence = None
        self.supersedes = None
        self.superseded_by = None
        self.last_reinforced = None
        self.reinforced_count = 0


def _engine(rows=()):
    store = MagicMock()

    async def _candidates(**kw):
        return list(rows)

    store.list_recall_candidates = _candidates
    store.touch_many = AsyncMock()

    ranker = MagicMock()
    ranker.rank = lambda c, current_context=None: list(c)
    ranker.rerank = lambda c, max_results=5: list(c)[:max_results]

    builder = MagicMock()
    fp = MagicMock()
    fp.project = None
    fp.as_dict = lambda: {}
    builder.build = lambda ctx: fp

    engine = RecallEngine(store, ranker, builder)
    engine._trigger_matcher = MagicMock()

    async def _check_all(_fp):
        return {"time": [], "context": []}

    engine._trigger_matcher.check_all = _check_all
    return engine, store


@pytest.mark.asyncio
async def test_session_start_touches_what_it_surfaced():
    rows = [_Memory(content="a"), _Memory(content="b")]
    engine, store = _engine(rows)

    await engine.session_start_recall({})

    store.touch_many.assert_awaited_once()
    touched = set(store.touch_many.await_args.args[0])
    assert touched == {m.id for m in rows}


@pytest.mark.asyncio
async def test_mid_session_touches_what_it_surfaced():
    rows = [_Memory(content="a")]
    engine, store = _engine(rows)

    results = await engine.mid_session_recall({}, "file_opened")

    assert results
    store.touch_many.assert_awaited_once()


@pytest.mark.asyncio
async def test_nothing_surfaced_means_nothing_touched():
    engine, store = _engine([])
    await engine.session_start_recall({})
    store.touch_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failing_touch_never_breaks_recall():
    """Access bookkeeping is not worth losing the recall over."""
    rows = [_Memory(content="a")]
    engine, store = _engine(rows)
    store.touch_many = AsyncMock(side_effect=RuntimeError("db gone"))

    result = await engine.session_start_recall({})

    assert len(result.decisions) == 1


@pytest.mark.asyncio
async def test_touch_is_one_call_not_one_per_memory():
    """Recall surfaces up to 5 memories; that should not be 5 round trips."""
    rows = [_Memory(content=str(i)) for i in range(5)]
    engine, store = _engine(rows)

    await engine.session_start_recall({})

    assert store.touch_many.await_count == 1
    assert len(store.touch_many.await_args.args[0]) == 5


def test_store_exposes_a_batch_touch():
    import inspect

    from life_graph.storage.postgres import PostgresMemoryStore

    assert hasattr(PostgresMemoryStore, "touch_many")
    sig = inspect.signature(PostgresMemoryStore.touch_many)
    assert "memory_ids" in sig.parameters


def test_batch_touch_is_tenant_scoped():
    import inspect

    from life_graph.storage.postgres import PostgresMemoryStore

    src = inspect.getsource(PostgresMemoryStore.touch_many)
    assert "get_current_tenant_id" in src, "a batch update by id must still be tenant-scoped"
