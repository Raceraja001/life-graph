"""Unit tests for the nightly consolidation pipeline (`jobs/consolidation.py`).

This module runs unattended at 03:00 UTC via ARQ cron and had **zero** test
coverage. The tenant-isolation tests here exist because the pipeline is
invoked once per tenant by ``run_all_consolidations`` — any query that
forgets its ``tenant_id`` filter silently processes (and archives) every
other tenant's memories.

No database is required: a recording fake session factory captures the
SQLAlchemy statements so we can assert on the compiled SQL.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from life_graph.core.tenant import set_tenant_context
from life_graph.jobs.consolidation import (
    ConsolidationPipeline,
    _cosine_similarity,
)
from life_graph.models.db import Memory

# ── Fakes ─────────────────────────────────────────────────────────────


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeSession:
    """Records every statement passed to execute()/add()."""

    def __init__(self, recorder, rows):
        self._recorder = recorder
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self._recorder["statements"].append(stmt)
        return _FakeResult(self._rows)

    def add(self, obj):
        self._recorder["added"].append(obj)

    async def commit(self):
        self._recorder["commits"] += 1

    async def refresh(self, obj):
        return None


def _factory(rows=()):
    """Return (session_factory, recorder)."""
    recorder = {"statements": [], "added": [], "commits": 0}

    def factory():
        return _FakeSession(recorder, rows)

    return factory, recorder


def _where(stmt) -> str:
    """Render only the WHERE clause.

    Asserting against the full SQL is useless here: ``select(Memory)`` emits
    ``memories.tenant_id`` in the column list, so a naive substring check
    passes even when the filter is absent.
    """
    clause = stmt.whereclause
    return "" if clause is None else str(clause)


def _sql(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": False}))


def _make_memory(content="hello world", *, embedding=None, tenant_id="acme", **kw) -> Memory:
    return Memory(
        id=kw.pop("id", uuid.uuid4()),
        content=content,
        tenant_id=tenant_id,
        embedding=embedding,
        importance=kw.pop("importance", 0.5),
        importance_tier=kw.pop("importance_tier", "normal"),
        access_count=kw.pop("access_count", 0),
        last_accessed=kw.pop("last_accessed", datetime.now(UTC)),
        created_at=kw.pop("created_at", datetime.now(UTC)),
        decay_rate=kw.pop("decay_rate", 0.1),
        **kw,
    )


def _pipeline(rows=()):
    factory, recorder = _factory(rows)
    embedding = MagicMock()
    embedding.embed.return_value = [0.1] * 8
    return ConsolidationPipeline(session_factory=factory, embedding_service=embedding), recorder


# ── _cosine_similarity ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ([1.0, 0.0], [1.0, 0.0], 1.0),
        ([1.0, 0.0], [0.0, 1.0], 0.0),
        ([1.0, 0.0], [-1.0, 0.0], -1.0),
        ([], [1.0], 0.0),
        ([1.0], [], 0.0),
        ([0.0, 0.0], [1.0, 1.0], 0.0),
        ([1.0, 2.0], [1.0, 2.0, 3.0], 0.0),
    ],
)
def test_cosine_similarity(a, b, expected):
    assert _cosine_similarity(a, b) == pytest.approx(expected)


# ── _cluster ──────────────────────────────────────────────────────────


def test_cluster_groups_similar_and_splits_dissimilar():
    pipeline, _ = _pipeline()
    a = _make_memory("a", embedding=[1.0, 0.0])
    b = _make_memory("b", embedding=[0.99, 0.01])  # ~1.0 similarity with a
    c = _make_memory("c", embedding=[0.0, 1.0])  # orthogonal

    clusters = pipeline._cluster([a, b, c])

    assert len(clusters) == 2
    assert {m.content for m in clusters[0]} == {"a", "b"}
    assert [m.content for m in clusters[1]] == ["c"]


def test_cluster_isolates_memories_without_embeddings():
    pipeline, _ = _pipeline()
    a = _make_memory("a", embedding=None)
    b = _make_memory("b", embedding=None)

    clusters = pipeline._cluster([a, b])

    assert len(clusters) == 2


def test_cluster_empty_input():
    pipeline, _ = _pipeline()
    assert pipeline._cluster([]) == []


# ── _dedup_cluster ────────────────────────────────────────────────────


def test_dedup_keeps_longest_of_near_identical_pair():
    pipeline, _ = _pipeline()
    short = _make_memory("short", embedding=[1.0, 0.0])
    detailed = _make_memory("a much more detailed version", embedding=[1.0, 0.001])

    kept = pipeline._dedup_cluster([short, detailed])

    assert [m.content for m in kept] == ["a much more detailed version"]


def test_dedup_preserves_distinct_memories():
    pipeline, _ = _pipeline()
    a = _make_memory("aaa", embedding=[1.0, 0.0])
    b = _make_memory("bbb", embedding=[0.0, 1.0])

    assert len(pipeline._dedup_cluster([a, b])) == 2


def test_dedup_single_and_empty_cluster_passthrough():
    pipeline, _ = _pipeline()
    one = [_make_memory("solo")]
    assert pipeline._dedup_cluster(one) is one
    assert pipeline._dedup_cluster([]) == []


def test_dedup_ignores_memories_without_embeddings():
    pipeline, _ = _pipeline()
    a = _make_memory("aaaa", embedding=None)
    b = _make_memory("bbb", embedding=None)

    assert len(pipeline._dedup_cluster([a, b])) == 2


# ── _score ────────────────────────────────────────────────────────────


def test_score_returns_triple_per_memory():
    pipeline, _ = _pipeline()
    mems = [_make_memory("I decided to move to Postgres"), _make_memory("ate a sandwich")]

    scored = pipeline._score(mems)

    assert len(scored) == 2
    for mem, score, tier in scored:
        assert isinstance(mem, Memory)
        assert 0.0 <= score <= 1.0
        assert isinstance(tier, str) and tier


def test_score_empty():
    pipeline, _ = _pipeline()
    assert pipeline._score([]) == []


# ── Tenant isolation ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gather_recent_filters_by_tenant():
    """A per-tenant nightly job must not read other tenants' memories."""
    set_tenant_context("acme", "system")
    pipeline, recorder = _pipeline(rows=[])

    await pipeline._gather_recent()

    assert recorder["statements"], "expected a SELECT to be issued"
    assert "tenant_id" in _where(recorder["statements"][0])


@pytest.mark.asyncio
async def test_update_decay_scores_filters_by_tenant():
    """Decay archives rows — an unscoped WHERE archives every tenant."""
    set_tenant_context("acme", "system")
    pipeline, recorder = _pipeline(rows=[])

    await pipeline._update_decay_scores()

    assert recorder["statements"], "expected a SELECT to be issued"
    assert "tenant_id" in _where(recorder["statements"][0])


@pytest.mark.asyncio
async def test_decay_archive_update_is_tenant_scoped():
    """The UPDATE ... SET status='archived' must carry a tenant filter."""
    set_tenant_context("acme", "system")
    old = datetime(2020, 1, 1, tzinfo=UTC)
    doomed = _make_memory(
        "stale", embedding=[1.0], importance=0.01, last_accessed=old, created_at=old
    )
    pipeline, recorder = _pipeline(rows=[doomed])

    await pipeline._update_decay_scores()

    updates = [s for s in recorder["statements"] if "UPDATE" in _sql(s).upper()]
    if updates:  # only asserted when something actually decayed
        assert "tenant_id" in _where(updates[0])


@pytest.mark.asyncio
async def test_persist_scores_is_tenant_scoped():
    set_tenant_context("acme", "system")
    pipeline, recorder = _pipeline()
    mem = _make_memory("something")

    await pipeline._persist_scores([(mem, 0.9, "high")])

    assert recorder["statements"]
    assert "tenant_id" in _where(recorder["statements"][0])


@pytest.mark.asyncio
async def test_persist_scores_noop_on_empty():
    pipeline, recorder = _pipeline()
    await pipeline._persist_scores([])
    assert recorder["statements"] == []
    assert recorder["commits"] == 0


@pytest.mark.asyncio
async def test_distilled_principle_carries_current_tenant(monkeypatch):
    """A principle written with the column default lands in tenant 'legacy'."""
    set_tenant_context("acme", "system")
    pipeline, recorder = _pipeline()

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = "  Prefer boring technology.  "
    fake_response._hidden_params = {"response_cost": 0.0002}

    async def _acompletion(**kwargs):
        return fake_response

    fake_llm = MagicMock()
    fake_llm.acompletion = _acompletion
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_resilient_llm", lambda: fake_llm, raising=False
    )

    cluster = [_make_memory(f"memory {i}", embedding=[1.0, 0.0]) for i in range(3)]
    principles = await pipeline._distill([cluster])

    assert len(principles) == 1
    assert principles[0]["content"] == "Prefer boring technology."
    assert principles[0]["source_count"] == 3
    assert principles[0]["cost_usd"] == pytest.approx(0.0002)

    assert recorder["added"], "principle was never added to a session"
    assert recorder["added"][0].tenant_id == "acme"


@pytest.mark.asyncio
async def test_distill_skips_clusters_below_minimum():
    pipeline, recorder = _pipeline()
    small = [_make_memory("only two"), _make_memory("memories here")]

    assert await pipeline._distill([small]) == []
    assert recorder["added"] == []


@pytest.mark.asyncio
async def test_run_short_circuits_when_nothing_recent():
    set_tenant_context("acme", "system")
    pipeline, _ = _pipeline(rows=[])

    report = await pipeline.run()

    assert report.gathered == 0
    assert report.clusters_found == 0
    assert report.principles_created == 0
    assert report.duration_seconds >= 0.0


# ── Report → JobRun result mapping ────────────────────────────────────


def test_task_result_keys_all_exist_on_report():
    """``run_tenant_consolidation`` records the report into ``JobRun.result``.

    It previously read four field names that ConsolidationReport does not
    define (``duplicates_merged``, ``memories_scored``, ``distilled``,
    ``decayed``); ``getattr(..., 0)`` turned each into a silent zero, so every
    nightly job run logged bogus stats.
    """
    import ast
    import dataclasses
    import inspect
    import textwrap

    from life_graph.jobs.consolidation import ConsolidationReport
    from life_graph.workers import tasks

    fields = {f.name for f in dataclasses.fields(ConsolidationReport)}

    src = inspect.getsource(tasks.run_tenant_consolidation)
    tree = ast.parse(textwrap.dedent(src))
    read: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "report"
        ):
            read.add(node.attr)
        # getattr(report, "name", default)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "report"
            and isinstance(node.args[1], ast.Constant)
        ):
            read.add(node.args[1].value)

    assert read, "expected run_tenant_consolidation to read from the report"
    assert read <= fields, f"reads fields absent from ConsolidationReport: {sorted(read - fields)}"
