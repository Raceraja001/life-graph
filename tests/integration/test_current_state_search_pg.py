"""Search and proactive recall answer about the present: an ended fact stays out.

Until 2026-11-25 only retrieve() checked ``valid_until``. /search (every
mode) and /search/recall returned "in Chennai until Friday" long after
Friday. The condition now lives in the store's filter builders
(storage/postgres.py ``valid_at``), which hybrid_search applies by default.

Embeddings cannot be written under pytest (tests/conftest.py fakes the Vector
type), so search goes through the keyword leg, which runs the same WHERE
clauses, and recall through its SQL-ranked candidate pool.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = f"curst_{uuid.uuid4().hex[:8]}"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "current-state-user"}
WORD = f"brindle{uuid.uuid4().hex[:6]}"
NOW = datetime.now(UTC)


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS
    ) as c:
        yield c


async def _seed(content: str, *, valid_until: datetime | None = None, tenant: str = TENANT) -> str:
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
        m.created_at = NOW - timedelta(days=3)
        m.valid_from = NOW - timedelta(days=3)
        m.valid_until = valid_until
        s.add(m)
        await s.commit()
        return str(m.id)


@pytest_asyncio.fixture
async def seeded() -> tuple[str, str, str]:
    """An ended fact, a fact that ends tomorrow, and an open-ended one, under a
    word of this test's own (so rows from other tests never crowd them out)."""
    global WORD
    WORD = f"brindle{uuid.uuid4().hex[:6]}"
    ended = await _seed(f"{WORD} is in Chennai", valid_until=NOW - timedelta(days=1))
    ends_later = await _seed(f"{WORD} is on leave", valid_until=NOW + timedelta(days=1))
    current = await _seed(f"{WORD} works on Life Graph")
    return ended, ends_later, current


@pytest.fixture
def stand_ins(monkeypatch):
    """A fixed embedding, and a judge that keeps everything it is shown."""
    from life_graph import runtime
    from life_graph.config import settings
    from life_graph.core.memory_manager import MemoryManager
    from life_graph.models.db import _EMBED_DIM
    from life_graph.services import entities
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

    async def no_entities(tenant_id, text):
        return []

    monkeypatch.setattr(MemoryManager, "_generate_embedding", fixed)
    monkeypatch.setattr(runtime, "get_memory_manager", lambda: _Manager())
    monkeypatch.setattr(runtime, "get_embedding_service", lambda: _Embedder())
    monkeypatch.setattr(retrieval, "judge", keep_all_judge)
    monkeypatch.setattr(retrieval, "_judged", keep_all)
    monkeypatch.setattr(entities, "known_in_text", no_entities)
    monkeypatch.setattr(settings, "memory_links", False)
    monkeypatch.setattr(settings, "memory_start_at", "")


@skip_on_db_error
@pytest.mark.parametrize("mode", ["hybrid", "judged", "tri_hybrid"])
async def test_search_leaves_out_an_ended_fact(client, seeded, stand_ins, mode):
    ended, ends_later, current = seeded
    resp = await client.post(
        "/api/v1/search/", json={"query": f"where is {WORD}", "search_mode": mode, "limit": 20}
    )
    assert resp.status_code == 200, resp.text
    ids = {m["id"] for m in resp.json()["data"]["memories"]}
    assert current in ids
    assert ends_later in ids
    assert ended not in ids


@skip_on_db_error
async def test_hybrid_search_valid_at_and_include_expired(seeded):
    """The default is now; an earlier valid_at, or include_expired (the cold
    tier, an explicit status browse), still finds the ended fact."""
    from life_graph.core.tenant import tenant_scope
    from life_graph.models.db import _EMBED_DIM
    from life_graph.storage.postgres import PostgresMemoryStore

    ended, _ends_later, current = seeded
    store = PostgresMemoryStore()

    async def ids(**kwargs) -> set[str]:
        with tenant_scope(TENANT):
            hits = await store.hybrid_search(
                embedding=[0.0] * _EMBED_DIM, query_text=f"where is {WORD}", limit=20, **kwargs
            )
        return {str(m.id) for m, _ in hits}

    assert ended not in await ids()
    assert current in await ids()
    assert ended in await ids(valid_at=NOW - timedelta(days=2))
    assert ended in await ids(include_expired=True)


@skip_on_db_error
async def test_vector_mode_filters_build_the_same_condition(seeded):
    """Vector mode and recall go through _apply_filters; no vectors can be
    stored here, so the shared builder is exercised through list_recall_candidates."""
    from life_graph.core.tenant import tenant_scope
    from life_graph.storage.postgres import PostgresMemoryStore

    ended, ends_later, current = seeded
    store = PostgresMemoryStore()
    with tenant_scope(TENANT):
        now_rows = await store.list_recall_candidates(
            filters={"status": "active", "valid_at": datetime.now(UTC)}, limit=50
        )
        past_rows = await store.list_recall_candidates(
            filters={"status": "active", "valid_at": NOW - timedelta(days=2)}, limit=50
        )
    now_ids = {str(m.id) for m in now_rows}
    assert {current, ends_later} <= now_ids
    assert ended not in now_ids
    assert ended in {str(m.id) for m in past_rows}


@skip_on_db_error
@pytest.mark.parametrize("index_only", [True, False])
async def test_proactive_recall_leaves_out_an_ended_fact(stand_ins, index_only):
    # A tenant of its own: recall surfaces only a few memories, so rows the
    # other tests seed must not crowd these out.
    tenant = f"currc_{uuid.uuid4().hex[:8]}"
    ended = await _seed(
        "ended fact: in Chennai", valid_until=NOW - timedelta(days=1), tenant=tenant
    )
    current = await _seed("current fact: works on Life Graph", tenant=tenant)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-Tenant-ID": tenant}
    ) as c:
        resp = await c.post(
            "/api/v1/search/recall",
            json={"context": {"project": "life-graph"}, "index_only": index_only},
        )
    assert resp.status_code == 200, resp.text
    assert current in resp.text  # recall ran and surfaced this tenant's memories
    assert ended not in resp.text


@skip_on_db_error
async def test_recall_candidates_leave_out_an_ended_fact(seeded, stand_ins):
    """The pool recall ranks from, before any of its own filtering."""
    from life_graph.core.tenant import tenant_scope
    from life_graph.runtime import get_recall_engine

    ended, ends_later, current = seeded
    engine = get_recall_engine()
    with tenant_scope(TENANT):
        fingerprint = engine._context_builder.build({"project": "life-graph"})
        pool = await engine._retrieve_candidates(fingerprint, limit=50)
    ids = {str(c["id"]) for c in pool}
    assert {current, ends_later} <= ids
    assert ended not in ids


@skip_on_db_error
async def test_ask_tells_the_model_each_memory_s_status_and_end(client, seeded, stand_ins):
    """/ask built its LLM context from MemoryResponse, which has no validity
    window, so valid_until always reached the model as None."""
    from life_graph.api.dependencies import get_synthesis_service

    ended, _ends_later, _current = seeded
    seen: list[dict] = []

    class _Synth:
        async def synthesize(self, question, memories, **kwargs):
            seen.extend(memories)
            return {"answer": "ok", "source_count": len(memories), "model": "fake"}

    app.dependency_overrides[get_synthesis_service] = lambda: _Synth()
    try:
        resp = await client.post(
            "/api/v1/search/ask",
            json={
                "question": f"where is {WORD}",
                "as_of": (NOW - timedelta(days=2)).isoformat(),
            },
        )
    finally:
        app.dependency_overrides.pop(get_synthesis_service, None)
    assert resp.status_code == 200, resp.text
    by_id = {m["id"]: m for m in seen}
    assert ended in by_id
    assert by_id[ended]["valid_until"] is not None
    assert by_id[ended]["status"] == "active"


@skip_on_db_error
async def test_retrieve_as_of_a_past_instant_still_finds_the_ended_fact(seeded, stand_ins):
    from life_graph.core.tenant import tenant_scope
    from life_graph.services.memory.retrieval import retrieve

    ended, _ends_later, current = seeded
    with tenant_scope(TENANT):
        now = await retrieve(f"where is {WORD}", limit=10)
        then = await retrieve(f"where is {WORD}", limit=10, as_of=NOW - timedelta(days=2))
    assert ended not in {str(m.id) for m in now}
    assert current in {str(m.id) for m in now}
    assert ended in {str(m.id) for m in then}
