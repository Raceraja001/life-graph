"""Unit tests for the versioned re-embed job (life_graph.workers.reembed)."""

from __future__ import annotations

import life_graph.api.dependencies as deps_mod
import life_graph.workers.reembed as reembed_mod
from life_graph.config import settings
from life_graph.models.db import Memory
from life_graph.workers.reembed import REGISTRY, _EmbedTarget, reembed_table


class _Row:
    def __init__(self, content):
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

    def embed_batch(self, texts, batch_size=64):
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
    assert rows[0].embedding_model == settings.embedding_model  # versioned -> stamped
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
