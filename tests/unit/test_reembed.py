"""Unit tests for the versioned re-embed job (life_graph.workers.reembed)."""

from __future__ import annotations

import uuid

import life_graph.api.dependencies as deps_mod
import life_graph.workers.reembed as reembed_mod
from life_graph.config import settings
from life_graph.models.db import Memory
from life_graph.services.embeddings import current_embedding_model
from life_graph.workers.reembed import (
    REGISTRY,
    _EmbedTarget,
    _needs_embedding_clause,
    reembed_table,
)


class _Row:
    def __init__(self, content):
        self.id = uuid.uuid4()
        self.content = content
        self.embedding = None
        self.embedding_model = None


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    """Yields one batch of rows, then empties (to terminate the loop)."""

    def __init__(self, batches):
        self._batches = list(batches)
        self.commits = 0

    async def execute(self, *_a, **_k):
        return _Result(self._batches.pop(0) if self._batches else [])

    async def commit(self):
        self.commits += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


class _FakeService:
    def __init__(self, vectors_per_text):
        self._v = vectors_per_text
        self.sync_calls = 0

    def embed_batch(self, texts, batch_size=64):
        # The sync path always used sentence-transformers, even in local-LLM
        # mode; the job must not call it.
        self.sync_calls += 1
        return [self._v for _ in texts]

    async def embed_batch_async(self, texts, batch_size=64):
        return [self._v for _ in texts]


def _wire(monkeypatch, session, service):
    monkeypatch.setattr(reembed_mod, "async_session", lambda: session)
    monkeypatch.setattr(deps_mod, "get_embedding_service", lambda: service)


# ── registry sanity ───────────────────────────────────────────────────


def test_registry_covers_eight_tables():
    assert len(REGISTRY) == 8


# ── re-embed writes vectors + version ─────────────────────────────────


async def test_reembed_table_writes_embedding_and_model(monkeypatch):
    rows = [_Row("hello"), _Row("world")]
    session = _FakeSession([rows])  # one batch then empty
    _wire(monkeypatch, session, _FakeService([0.1] * 4))

    target = _EmbedTarget(Memory, "content", versioned=True)
    result = await reembed_table(target, batch_size=64)

    assert result["processed"] == 2
    assert result["failed"] == 0
    assert rows[0].embedding == [0.1] * 4
    assert rows[0].embedding_model == current_embedding_model()  # versioned -> stamped
    assert session.commits == 1


async def test_reembed_counts_empty_vectors_as_failed(monkeypatch):
    rows = [_Row("x")]
    session = _FakeSession([rows])
    _wire(monkeypatch, session, _FakeService([]))  # embedder returns empty

    target = _EmbedTarget(Memory, "content", versioned=True)
    result = await reembed_table(target, batch_size=64)

    assert result["processed"] == 0
    assert result["failed"] == 1
    assert rows[0].embedding is None  # never written


async def test_reembed_empty_table_is_noop(monkeypatch):
    session = _FakeSession([])  # no batches -> immediately empty
    _wire(monkeypatch, session, _FakeService([0.1] * 4))

    target = _EmbedTarget(Memory, "content", versioned=False)
    result = await reembed_table(target, batch_size=64)

    assert result == {"table": "memories", "processed": 0, "failed": 0}


# ── code review 2026-10-22 ────────────────────────────────────────────


class _StuckSession:
    """One good batch, then the same unembeddable rows on every query that
    does not exclude them — the shape of a table with rows that can never be
    embedded. Capped so a regression fails instead of hanging."""

    def __init__(self, good, bad, cap=20):
        self._good = list(good)
        self._bad = bad
        self.statements = []
        self._cap = cap
        self.commits = 0

    async def execute(self, stmt, *_a, **_k):
        self.statements.append(stmt)
        if len(self.statements) > self._cap:
            return _Result([])
        if self._good:
            batch, self._good = self._good, []
            return _Result(batch)
        excluded = "NOT IN" in str(stmt.whereclause).upper()
        return _Result([] if excluded else self._bad)

    async def commit(self):
        self.commits += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


class _PickyService:
    """Embeds everything except rows whose text is empty."""

    async def embed_batch_async(self, texts, batch_size=64):
        return [[0.2] * 4 if t else [] for t in texts]


async def test_reembed_terminates_on_unembeddable_rows_after_progress(monkeypatch):
    """The stop guard used the cumulative processed count, so once one batch
    had succeeded, rows that could never be embedded looped forever."""
    good = [_Row("hello"), _Row("world")]
    bad = [_Row(""), _Row("")]
    session = _StuckSession(good, bad)
    _wire(monkeypatch, session, _PickyService())

    result = await reembed_table(_EmbedTarget(Memory, "content", versioned=True), batch_size=2)

    assert result["processed"] == 2
    assert result["failed"] == 2  # each unembeddable row counted once
    assert len(session.statements) <= 3


async def test_reembed_excludes_failed_rows_from_later_batches(monkeypatch):
    bad = _Row("")
    session = _StuckSession([_Row("hello"), bad], [bad])  # mixed first batch
    _wire(monkeypatch, session, _PickyService())

    result = await reembed_table(_EmbedTarget(Memory, "content", versioned=True), batch_size=2)

    assert result == {"table": "memories", "processed": 1, "failed": 1}
    assert len(session.statements) == 2
    assert "NOT IN" in str(session.statements[1].whereclause).upper()


async def test_reembed_uses_async_backend_not_sync_sentence_transformers(monkeypatch):
    rows = [_Row("hello")]
    service = _FakeService([0.1] * 4)
    _wire(monkeypatch, _FakeSession([rows]), service)

    await reembed_table(_EmbedTarget(Memory, "content", versioned=True))

    assert service.sync_calls == 0
    assert rows[0].embedding == [0.1] * 4


def test_current_model_is_what_local_ingest_stamps(monkeypatch):
    """Ingest stamped lm_embedding_model while re-embed compared against
    embedding_model, so every locally embedded memory looked stale."""
    monkeypatch.setattr(settings, "use_local_llm", True)
    monkeypatch.setattr(settings, "lm_embedding_model", "bge-m3")
    monkeypatch.setattr(settings, "embedding_model", "BAAI/bge-m3")

    assert current_embedding_model() == "bge-m3"
    clause = _needs_embedding_clause(
        _EmbedTarget(Memory, "content", versioned=True), current_embedding_model()
    )
    sql = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "'bge-m3'" in sql
    assert "BAAI" not in sql


def test_current_model_outside_local_mode(monkeypatch):
    monkeypatch.setattr(settings, "use_local_llm", False)
    monkeypatch.setattr(settings, "embedding_model", "BAAI/bge-m3")

    assert current_embedding_model() == "BAAI/bge-m3"
