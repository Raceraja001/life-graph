"""Two tenants with look-alike memories: search keeps them apart.

Every other search test seeds one tenant, so a missing ``tenant_id`` filter
would still pass them all: the only rows to find are the right ones. Here
tenants A and B hold the same words about the same person, each linked to an
entity of the same name, and every way of finding memories is asked from A's
side and from B's side:

- ``PostgresMemoryStore.hybrid_search`` (the store's search),
- ``services/memory/retrieval.retrieve`` (search + entity links + judge),
- ``services/entities.memories_for`` (memories linked to an entity),
- ``POST /api/v1/search/`` through the app, chosen by ``X-Tenant-ID``,
- the recall candidate pool (``list_recall_candidates`` and the recall
  engine's ``_retrieve_candidates``) and ``POST /api/v1/search/recall``.

Each check also asserts that the asking tenant's own memories ARE found, so an
empty result cannot pass for isolation. Every test gets a fresh pair of
tenants, so rows from one test never hide a leak in the next.

Embeddings cannot be written under pytest (tests/conftest.py fakes the Vector
type), so search runs through the keyword leg, which carries the same tenant
filter as the vector leg.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

NOW = datetime.now(UTC)


@dataclass
class _Tenant:
    tenant_id: str
    ids: set[str]
    entity: uuid.UUID


@dataclass
class _Pair:
    """Tenants A and B, and the words both of them hold."""

    word: str
    name: str
    a: _Tenant
    b: _Tenant

    @property
    def question(self) -> str:
        return f"where does {self.name} teach {self.word}"

    def side(self, which: str) -> tuple[_Tenant, _Tenant]:
        """(asking tenant, other tenant)."""
        return (self.a, self.b) if which == "A" else (self.b, self.a)


async def _seed(tenant: str, content: str) -> str:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
            importance=0.9,
            tags=["test"],
            status="active",
            trust_tier="verified",
            source_type="test",
        )
        m.created_at = NOW - timedelta(days=1)
        m.valid_from = NOW - timedelta(days=1)
        s.add(m)
        await s.commit()
        return str(m.id)


async def _entity_id(tenant: str, name: str) -> uuid.UUID:
    from sqlalchemy import select

    from life_graph.models.assistant import Entity
    from life_graph.services import entities
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.scalar(
            select(Entity.id).where(
                Entity.tenant_id == tenant, Entity.key == entities.normalize(name)
            )
        )


async def _seed_tenant(tenant: str, word: str, name: str) -> _Tenant:
    from life_graph.services import entities

    ids = {
        await _seed(tenant, f"{name} teaches maths at {word} school"),
        await _seed(tenant, f"{name} takes the 8:10 bus to {word}"),
    }
    for mid in ids:
        await entities.link(tenant, uuid.UUID(mid), [name])
    return _Tenant(tenant, ids, await _entity_id(tenant, name))


@pytest_asyncio.fixture
async def pair() -> _Pair:
    """A fresh A and B: the same two notes in each, linked to an entity named alike."""
    run = uuid.uuid4().hex[:8]
    word, name = f"quillmore{run}", f"Vaishnavi{run}"
    a = await _seed_tenant(f"isoa_{run}", word, name)
    b = await _seed_tenant(f"isob_{run}", word, name)
    assert a.entity is not None and b.entity is not None and a.entity != b.entity
    return _Pair(word, name, a, b)


@pytest.fixture
def stand_ins(monkeypatch):
    """A fixed embedding, and a judge that keeps everything it is shown.

    The entity index is left real, so retrieve() also takes the entity-link path.
    """
    from life_graph import runtime
    from life_graph.config import settings
    from life_graph.core.memory_manager import MemoryManager
    from life_graph.models.db import _EMBED_DIM
    from life_graph.services.memory import retrieval

    async def fixed(self, text):
        return [0.0] * _EMBED_DIM

    class _Manager:
        async def generate_embedding(self, text):
            return [0.0] * _EMBED_DIM

    class _Embedder:
        async def embed_async(self, text):
            return [0.0] * _EMBED_DIM

    async def keep_all_judge(question, contents):
        return list(range(len(contents)))

    async def keep_all(question, memories):
        return list(memories)

    monkeypatch.setattr(MemoryManager, "_generate_embedding", fixed)
    monkeypatch.setattr(runtime, "get_memory_manager", lambda: _Manager())
    monkeypatch.setattr(runtime, "get_embedding_service", lambda: _Embedder())
    monkeypatch.setattr(retrieval, "judge", keep_all_judge)
    monkeypatch.setattr(retrieval, "_judged", keep_all)
    monkeypatch.setattr(settings, "memory_links", False)
    monkeypatch.setattr(settings, "memory_start_at", "")


def _assert_kept_apart(found: set[str], asking: _Tenant, other: _Tenant) -> None:
    leaked = found & other.ids
    assert not leaked, f"{asking.tenant_id} saw {other.tenant_id}'s memories: {sorted(leaked)}"
    # A positive control: isolation by finding nothing at all proves nothing.
    assert asking.ids <= found, f"{asking.tenant_id} did not find its own memories"


@skip_on_db_error
@pytest.mark.parametrize("which", ["A", "B"])
async def test_hybrid_search_keeps_tenants_apart(pair, which):
    from life_graph.core.tenant import tenant_scope
    from life_graph.models.db import _EMBED_DIM
    from life_graph.storage.postgres import PostgresMemoryStore

    asking, other = pair.side(which)
    with tenant_scope(asking.tenant_id):
        hits = await PostgresMemoryStore().hybrid_search(
            embedding=[0.0] * _EMBED_DIM, query_text=pair.question, limit=50
        )
    _assert_kept_apart({str(m.id) for m, _ in hits}, asking, other)
    assert {m.tenant_id for m, _ in hits} == {asking.tenant_id}


@skip_on_db_error
@pytest.mark.parametrize("which", ["A", "B"])
async def test_retrieve_keeps_tenants_apart(pair, stand_ins, which):
    from life_graph.core.tenant import tenant_scope
    from life_graph.services.memory.retrieval import retrieve

    asking, other = pair.side(which)
    with tenant_scope(asking.tenant_id):
        found = await retrieve(pair.question, limit=20)
    assert found is not None
    _assert_kept_apart({str(m.id) for m in found}, asking, other)


@skip_on_db_error
async def test_retrieve_entity_path_keeps_tenants_apart(pair, stand_ins, monkeypatch):
    """With search finding nothing, the entity links alone must stay in A."""
    from life_graph.core.tenant import tenant_scope
    from life_graph.services.memory import retrieval
    from life_graph.storage.postgres import PostgresMemoryStore

    async def no_hits(self, *args, **kwargs):
        return []

    monkeypatch.setattr(PostgresMemoryStore, "hybrid_search", no_hits)
    with tenant_scope(pair.a.tenant_id):
        found = await retrieval.retrieve(pair.question, limit=20)
    assert found is not None
    _assert_kept_apart({str(m.id) for m in found}, pair.a, pair.b)


@skip_on_db_error
async def test_memories_for_ignores_another_tenants_entity(pair):
    """Even handed B's entity id, A's lookup returns only A's memories."""
    from life_graph.services import entities

    both = await entities.memories_for(pair.a.tenant_id, [pair.a.entity, pair.b.entity], limit=50)
    _assert_kept_apart({str(m.id) for m in both}, pair.a, pair.b)

    only_b = await entities.memories_for(pair.a.tenant_id, [pair.b.entity], limit=50)
    assert only_b == []


@skip_on_db_error
@pytest.mark.parametrize("mode", ["hybrid", "judged", "tri_hybrid"])
@pytest.mark.parametrize("which", ["A", "B"])
async def test_search_endpoint_keeps_tenants_apart(pair, stand_ins, mode, which):
    asking, other = pair.side(which)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": asking.tenant_id, "X-User-ID": "isolation-user"},
    ) as c:
        resp = await c.post(
            "/api/v1/search/", json={"query": pair.question, "search_mode": mode, "limit": 50}
        )
    assert resp.status_code == 200, resp.text
    found = {m["id"] for m in resp.json()["data"]["memories"]}
    _assert_kept_apart(found, asking, other)


@skip_on_db_error
@pytest.mark.parametrize("which", ["A", "B"])
async def test_recall_candidates_keep_tenants_apart(pair, stand_ins, which):
    """The pool proactive recall ranks from: the store query and the engine's."""
    from life_graph.core.tenant import tenant_scope
    from life_graph.runtime import get_recall_engine
    from life_graph.storage.postgres import PostgresMemoryStore

    asking, other = pair.side(which)
    with tenant_scope(asking.tenant_id):
        rows = await PostgresMemoryStore().list_recall_candidates(
            filters={"status": "active"}, limit=200
        )
        engine = get_recall_engine()
        fingerprint = engine._context_builder.build({"project": "life-graph"})
        pool = await engine._retrieve_candidates(fingerprint, limit=200)
    _assert_kept_apart({str(m.id) for m in rows}, asking, other)
    _assert_kept_apart({str(c["id"]) for c in pool}, asking, other)


@skip_on_db_error
@pytest.mark.parametrize("which", ["A", "B"])
async def test_recall_endpoint_keeps_tenants_apart(pair, stand_ins, which):
    asking, other = pair.side(which)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": asking.tenant_id},
    ) as c:
        resp = await c.post(
            "/api/v1/search/recall",
            json={"context": {"project": "life-graph"}, "index_only": True},
        )
    assert resp.status_code == 200, resp.text
    # Recall surfaces only a few memories, so: at least one of this tenant's,
    # and none of the other's.
    assert any(mid in resp.text for mid in asking.ids)
    assert not any(mid in resp.text for mid in other.ids)
