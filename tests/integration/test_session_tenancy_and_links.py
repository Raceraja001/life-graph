"""Sessions, intentions and memory<->session links, against the real database.

Review findings of 2026-10-22 this file pins:

1. ``POST /sessions/start`` set no tenant, so every session landed in the
   ``"legacy"`` default; end/get/heartbeat looked a session up by primary
   key alone, so any tenant could end or read another's.
2. ``EndSessionRequest`` had no ``summary``: the MCP tool's summary was
   dropped silently.
3. ``IntentionService.create`` set no tenant either, while every read and
   ``TriggerMatcher`` filter by the current one — API intentions never fired.
5. Nothing wrote ``memory_sessions``, so micro-consolidation and
   ImpactScorer always saw an empty table; ``count_session_memories``
   filtered on a column that table does not have.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from life_graph.core.tenant import tenant_scope
from tests.integration.conftest import skip_on_db_error

TENANT = f"sl_{uuid.uuid4().hex[:8]}"
OTHER = f"sl_other_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _no_background_consolidation(monkeypatch):
    """end_session spawns micro-consolidation as a fire-and-forget task; it
    would outlive the test's event loop. It is exercised directly below."""
    from life_graph.api import sessions

    async def _noop(session_id):
        return None

    monkeypatch.setattr(sessions, "_run_micro_consolidation", _noop)


def _client(tenant: str) -> AsyncClient:
    from life_graph.main import app

    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "tester"},
    )


@pytest_asyncio.fixture
async def client():
    async with _client(TENANT) as c:
        yield c


@pytest_asyncio.fixture
async def other_client():
    async with _client(OTHER) as c:
        yield c


async def _start(c: AsyncClient, context: dict | None = None) -> uuid.UUID:
    r = await c.post("/api/v1/sessions/start", json={"context": context or {}})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["id"])


async def _session_row(session_id: uuid.UUID):
    from life_graph.models.db import Session
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Session, session_id)


async def _seed_memory(content: str, *, tenant: str = TENANT, properties: dict | None = None):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{tenant}{content}{uuid.uuid4()}".encode()).hexdigest(),
            status="active",
            trust_tier="self",
            source_type="test",
            properties=properties or {},
        )
        s.add(m)
        await s.commit()
        return m.id


async def _links(session_id: uuid.UUID) -> dict[uuid.UUID, str]:
    from life_graph.models.db import MemorySession
    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = await s.execute(
            select(MemorySession.memory_id, MemorySession.role).where(
                MemorySession.session_id == session_id
            )
        )
        return dict(rows.all())


# ── 1. Session tenancy ───────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_started_session_belongs_to_the_callers_tenant(client):
    sid = await _start(client, {"project": "p4a"})
    row = await _session_row(sid)
    assert row.tenant_id == TENANT, "landed in the column default, not the caller's tenant"

    listed = await client.get("/api/v1/sessions/", params={"limit": 100})
    assert str(sid) in {s["id"] for s in listed.json()["data"]}


@pytest.mark.asyncio
@skip_on_db_error
async def test_another_tenants_session_is_not_found(client, other_client):
    sid = await _start(client)

    assert (await other_client.get(f"/api/v1/sessions/{sid}")).status_code == 404
    assert (await other_client.post(f"/api/v1/sessions/{sid}/end", json={})).status_code == 404
    hb = await other_client.post(f"/api/v1/sessions/{sid}/heartbeat", json={"context": {"x": 1}})
    assert hb.status_code == 404

    row = await _session_row(sid)
    assert row.ended_at is None, "another tenant ended this session"
    assert "x" not in (row.context or {})

    # The owner still can.
    assert (await client.get(f"/api/v1/sessions/{sid}")).status_code == 200


@pytest.mark.asyncio
@skip_on_db_error
async def test_heartbeat_merges_context(client):
    sid = await _start(client, {"project": "p4a"})
    r = await client.post(f"/api/v1/sessions/{sid}/heartbeat", json={"context": {"file": "a.py"}})
    assert r.status_code == 200
    row = await _session_row(sid)
    assert row.context == {"project": "p4a", "file": "a.py"}


# ── 2. Caller-written summary ────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_end_session_keeps_the_callers_summary_and_outcome(client, monkeypatch):
    from life_graph.api import sessions

    async def _must_not_generate(sess, count):
        raise AssertionError("a caller summary must not be replaced by a generated one")

    monkeypatch.setattr(sessions, "_generate_summary", _must_not_generate)
    sid = await _start(client)

    r = await client.post(
        f"/api/v1/sessions/{sid}/end",
        json={"summary": "Fixed the login bug.", "outcome": "success"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["summary"] == "Fixed the login bug."
    row = await _session_row(sid)
    assert row.summary == "Fixed the login bug."
    assert row.outcome == "success"


# ── 3. Intention tenancy ─────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_api_intention_is_the_callers_and_fires(client):
    from life_graph.models.db import Intention
    from life_graph.services.triggers import TriggerMatcher
    from life_graph.storage.database import async_session
    from life_graph.storage.postgres import PostgresMemoryStore

    due = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    r = await client.post(
        "/api/v1/intentions/",
        json={"content": "Rotate the keys", "trigger_type": "time", "trigger_time": due},
    )
    assert r.status_code in (200, 201), r.text
    iid = uuid.UUID(r.json()["data"]["id"])

    async with async_session() as s:
        assert (await s.get(Intention, iid)).tenant_id == TENANT

    with tenant_scope(TENANT):
        fired = await TriggerMatcher(PostgresMemoryStore()).check_time_triggers()
    assert iid in {i.id for i in fired}, "a due time intention did not fire for its tenant"

    with tenant_scope(OTHER):
        fired_elsewhere = await TriggerMatcher(PostgresMemoryStore()).check_time_triggers()
    assert iid not in {i.id for i in fired_elsewhere}


# ── 5. memory_sessions links ─────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_memory_stored_with_a_session_id_is_linked_as_created(client):
    from life_graph.models.schemas import MemoryCreate
    from life_graph.storage.postgres import PostgresMemoryStore

    sid = await _start(client)
    store = PostgresMemoryStore()
    with tenant_scope(TENANT):
        row = await store.store(
            MemoryCreate(
                content=f"Uses ruff {uuid.uuid4().hex[:6]}", properties={"session_id": str(sid)}
            ),
            status="active",
        )
        assert await store.count_session_memories(sid) == 1

    assert (await _links(sid)) == {row.id: "created"}
    assert (await _session_row(sid)).memories_created == 1

    got = await client.get(f"/api/v1/sessions/{sid}")
    assert got.json()["data"]["memories_created"] == 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_links_never_cross_tenants_or_reach_ended_sessions(client, other_client):
    from life_graph.models.schemas import MemoryCreate
    from life_graph.storage.postgres import PostgresMemoryStore

    store = PostgresMemoryStore()
    theirs = await _start(other_client)
    ended = await _start(client)
    assert (
        await client.post(f"/api/v1/sessions/{ended}/end", json={"summary": "x"})
    ).status_code == 200

    with tenant_scope(TENANT):
        for sid in (theirs, ended):
            await store.store(
                MemoryCreate(
                    content=f"note {uuid.uuid4().hex[:6]}", properties={"session_id": str(sid)}
                ),
                status="active",
            )
        # A malformed id must not cost the caller the memory.
        kept = await store.store(
            MemoryCreate(content=f"odd {uuid.uuid4().hex[:6]}", properties={"session_id": "nope"}),
            status="active",
        )
    assert kept.id is not None
    assert await _links(theirs) == {}
    assert await _links(ended) == {}

    # Another tenant's memory cannot be linked into my session either.
    mine = await _start(client)
    foreign = await _seed_memory("their memory", tenant=OTHER)
    with tenant_scope(TENANT):
        assert await store.link_recalls_to_session([foreign], mine) == 0
    assert await _links(mine) == {}


@pytest.mark.asyncio
@skip_on_db_error
async def test_recall_links_keep_the_first_role_and_are_idempotent(client):
    from life_graph.storage.postgres import PostgresMemoryStore

    store = PostgresMemoryStore()
    sid = await _start(client)
    created = await _seed_memory("made here")
    old = await _seed_memory("recalled here")

    with tenant_scope(TENANT):
        assert await store.link_memory_to_session(created, sid) is True
        assert await store.link_memory_to_session(created, sid) is False, "a repeat must not raise"
        assert await store.link_recalls_to_session([created, old, old], sid) == 1
        assert await store.link_recall_to_session(old, sid) is False
        assert await store.get_recalled_memory_ids(sid) == [old]
        assert await store.count_session_memories(sid) == 2
    with tenant_scope(OTHER):
        assert await store.get_recalled_memory_ids(sid) == []
        assert await store.count_session_memories(sid) == 0

    assert await _links(sid) == {created: "created", old: "recalled"}
    row = await _session_row(sid)
    assert (row.memories_created, row.memories_accessed) == (1, 1)


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_expand_in_a_session_feeds_impact_scoring(client):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    sid = await _start(client)
    mid = await _seed_memory("Deploy with blue-green")
    async with async_session() as s:
        before = (await s.get(Memory, mid)).impact_score

    r = await client.post(
        "/api/v1/memories/batch",
        json={"ids": [str(mid)], "session_id": str(sid)},
    )
    assert r.status_code == 200, r.text
    assert await _links(sid) == {mid: "recalled"}

    end = await client.post(
        f"/api/v1/sessions/{sid}/end", json={"summary": "shipped", "outcome": "success"}
    )
    assert end.status_code == 200
    assert end.json()["data"]["memories_created"] == 0, "a recalled memory is not a created one"

    async with async_session() as s:
        after = (await s.get(Memory, mid)).impact_score
    assert after > before, "the recalled memory was not credited with the session's success"


@pytest.mark.asyncio
@skip_on_db_error
async def test_micro_consolidation_gathers_created_memories_only(client):
    from life_graph.services.micro_consolidation import MicroConsolidator
    from life_graph.storage.database import async_session
    from life_graph.storage.postgres import PostgresMemoryStore

    store = PostgresMemoryStore()
    sid = await _start(client)
    created = await _seed_memory("written in session")
    recalled = await _seed_memory("read in session")
    with tenant_scope(TENANT):
        await store.link_memory_to_session(created, sid)
        await store.link_recalls_to_session([recalled], sid)
        gathered = await MicroConsolidator(async_session, None)._gather_session_memories(sid)
    assert [m.id for m in gathered] == [created]
