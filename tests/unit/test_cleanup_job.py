"""Unit tests for the one-time memory cleanup job (life_graph.workers.cleanup).

Queues merge approvals for fragment/duplicate memory pairs (near-dup cosine
band or overlapping properties.entities) with source='cleanup'. Never
auto-merges. Idempotent via a stable hash of the sorted memory-id pair.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import life_graph.workers.cleanup as cleanup_mod
from life_graph.models.db import Approval


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    """Tracks queued Approvals; answers the source_ref seen-set query.

    Mirrors tests/unit/test_reembed.py's fake session — the only query the
    job issues is `select(Approval.source_ref).where(source == "cleanup", ...)`.
    """

    def __init__(self):
        self.added: list[Approval] = []
        self.commits = 0
        self.flushes = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def execute(self, _stmt):
        refs = [a.source_ref for a in self.added if a.source == "cleanup"]
        return _Result(refs)


class _FakeStore:
    """Minimal PostgresMemoryStore stand-in.

    `neighbor_map` keys by str(memory.id) -> list of (other_memory, score)
    that `find_similar` returns for that memory's embedding, filtered by
    the threshold the job passes in (mirrors real find_similar semantics).
    """

    def __init__(self, memories, neighbor_map):
        self._memories = memories
        self._by_embedding = {tuple(m.embedding): m for m in memories}
        self._neighbor_map = neighbor_map

    async def list_memories(self, filters=None, limit=20):
        return self._memories, False

    async def find_similar(self, embedding, threshold=0.92, limit=5):
        mem = self._by_embedding.get(tuple(embedding))
        if mem is None:
            return []
        return [
            (other, score)
            for other, score in self._neighbor_map.get(str(mem.id), [])
            if score >= threshold
        ][:limit]


def _mem(content, entities=None, embedding=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        embedding=embedding if embedding is not None else [0.1, 0.2],
        properties={"entities": entities or []},
    )


def _wire(monkeypatch, session, store):
    monkeypatch.setattr(cleanup_mod, "async_session", lambda: session)
    monkeypatch.setattr(cleanup_mod, "PostgresMemoryStore", lambda: store)


async def test_queues_merge_approval_for_high_similarity_pair(monkeypatch):
    a = _mem("Deploy freeze on Fridays", entities=["acme_corp"], embedding=[1.0, 0.0])
    b = _mem("No prod deploys Friday afternoons", entities=["acme_corp"], embedding=[0.0, 1.0])

    # A's neighbor scan finds B at 0.90 (review band, [merge_review_low, dedup_threshold)).
    neighbor_map = {str(a.id): [(b, 0.90)], str(b.id): [(a, 0.90)]}
    store = _FakeStore([a, b], neighbor_map)
    session = _FakeSession()
    _wire(monkeypatch, session, store)

    result = await cleanup_mod.cleanup_memories_tenant({}, "tenant-1")

    assert result == {"tenant_id": "tenant-1", "queued": 1}
    assert len(session.added) == 1
    approval = session.added[0]
    assert isinstance(approval, Approval)
    assert approval.kind == "merge"
    assert approval.source == "cleanup"
    assert approval.tenant_id == "tenant-1"
    assert approval.source_ref  # stable hash, non-empty
    assert approval.payload["memory_id_a"] in (str(a.id), str(b.id))
    assert approval.payload["memory_id_b"] in (str(a.id), str(b.id))
    assert session.commits == 1


async def test_idempotent_on_rerun(monkeypatch):
    a = _mem("Deploy freeze on Fridays", entities=["acme_corp"], embedding=[1.0, 0.0])
    b = _mem("No prod deploys Friday afternoons", entities=["acme_corp"], embedding=[0.0, 1.0])
    neighbor_map = {str(a.id): [(b, 0.90)], str(b.id): [(a, 0.90)]}
    store = _FakeStore([a, b], neighbor_map)
    session = _FakeSession()
    _wire(monkeypatch, session, store)

    first = await cleanup_mod.cleanup_memories_tenant({}, "tenant-1")
    second = await cleanup_mod.cleanup_memories_tenant({}, "tenant-1")

    assert first["queued"] == 1
    assert second["queued"] == 0
    assert len(session.added) == 1  # nothing re-queued


async def test_entity_overlap_queues_even_above_dedup_threshold(monkeypatch):
    # Score is >= dedup_threshold (would normally be auto-merged at ingest),
    # but since it still coexists as two active memories with shared
    # entities, the cleanup job should surface it for human review too.
    a = _mem("Acme Corp renewed the contract", entities=["acme_corp"], embedding=[1.0, 0.0])
    b = _mem("Acme Corp signed a new contract", entities=["acme_corp"], embedding=[0.0, 1.0])
    neighbor_map = {str(a.id): [(b, 0.97)], str(b.id): [(a, 0.97)]}
    store = _FakeStore([a, b], neighbor_map)
    session = _FakeSession()
    _wire(monkeypatch, session, store)

    result = await cleanup_mod.cleanup_memories_tenant({}, "tenant-1")

    assert result["queued"] == 1


async def test_no_overlap_and_below_review_band_is_skipped(monkeypatch):
    a = _mem("Likes coffee", entities=["coffee"], embedding=[1.0, 0.0])
    b = _mem("Unrelated note about hiking", entities=["hiking"], embedding=[0.0, 1.0])
    # No neighbors returned at all (simulates score below merge_review_low).
    neighbor_map = {str(a.id): [], str(b.id): []}
    store = _FakeStore([a, b], neighbor_map)
    session = _FakeSession()
    _wire(monkeypatch, session, store)

    result = await cleanup_mod.cleanup_memories_tenant({}, "tenant-1")

    assert result["queued"] == 0
    assert session.added == []
