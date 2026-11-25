"""Every supersede records when the fact was replaced; every undo takes it back.

``superseded_at`` has no column: it lives in ``memories.properties``, and
retrieval's transaction-time check reads it (services/memory/retrieval.py
is_known_at). Until 2026-11-25 no supersede path wrote it, so a question
"as of now" (which lets superseded rows into the search, then asks whether
each was still believed) read every replaced value as current belief.

Embeddings cannot be written under pytest (tests/conftest.py fakes the Vector
type), so the retrieval checks go through the keyword leg of hybrid_search;
the relevance judge is replaced by "keep everything" so the temporal filter is
the only thing deciding what comes back.
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

TENANT = f"supat_{uuid.uuid4().hex[:8]}"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "superseded-at-user"}
# Seeded rows are dated well before "before the supersede", so that instant
# is after they were recorded and before they were replaced, whatever the
# clock skew between Python and Postgres.
SEEDED_AT = datetime.now(UTC) - timedelta(hours=2)
BEFORE = datetime.now(UTC) - timedelta(hours=1)


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS
    ) as c:
        yield c


async def _seed(content: str, *, status: str = "active", properties: dict | None = None) -> str:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=TENANT,
            content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
            importance=0.6,
            tags=["test"],
            status=status,
            trust_tier="verified",
            source_type="test",
            properties=properties or {},
        )
        m.created_at = SEEDED_AT
        s.add(m)
        await s.commit()
        return str(m.id)


async def _memory(mem_id: str):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, uuid.UUID(mem_id))


async def _pair() -> tuple[str, str, str]:
    word = f"quillon{uuid.uuid4().hex[:6]}"
    old_id = await _seed(f"{word} lives in Chennai")
    new_id = await _seed(f"{word} lives in Mumbai", properties={"saved_by": "owner"})
    return word, old_id, new_id


@pytest.fixture
def plain_retrieval(monkeypatch):
    """retrieve() over the real store, with a stand-in embedding and judge."""
    from life_graph import runtime
    from life_graph.config import settings
    from life_graph.models.db import _EMBED_DIM
    from life_graph.services import entities
    from life_graph.services.memory import retrieval

    class _Manager:
        async def generate_embedding(self, text):
            return [0.0] * _EMBED_DIM

    async def keep_all(question, memories):
        return list(memories)

    async def no_entities(tenant_id, text):
        return []

    monkeypatch.setattr(runtime, "get_memory_manager", lambda: _Manager())
    monkeypatch.setattr(retrieval, "_judged", keep_all)
    monkeypatch.setattr(entities, "known_in_text", no_entities)
    monkeypatch.setattr(settings, "memory_links", False)
    monkeypatch.setattr(settings, "memory_start_at", "")


async def _ids(question: str, **kwargs) -> set[str]:
    from life_graph.core.tenant import tenant_scope
    from life_graph.services.memory.retrieval import retrieve

    with tenant_scope(TENANT):
        found = await retrieve(question, limit=10, **kwargs)
    assert found is not None
    return {str(m.id) for m in found}


def _stamp(mem) -> datetime:
    raw = (mem.properties or {}).get("superseded_at")
    assert raw, f"no superseded_at on {mem.id}: {mem.properties}"
    return datetime.fromisoformat(raw)


@skip_on_db_error
async def test_a_correction_is_history_now_belief_before_and_undo_restores_it(plain_retrieval):
    from life_graph.services.memory.page import _restore_replaced
    from life_graph.tools.memory_search import _supersede

    word, old_id, new_id = await _pair()
    question = f"where does {word} live?"

    before_call = datetime.now(UTC)
    assert await _supersede(TENANT, uuid.UUID(old_id), uuid.UUID(new_id)) is not None
    old = await _memory(old_id)
    assert old.status == "superseded"
    assert str(old.superseded_by) == new_id
    assert _stamp(old) >= before_call - timedelta(seconds=1)
    # A correction ends our belief in it, not (by itself) its truth in the
    # world: valid_until is left alone (see the PR / retrieval.is_valid_at).
    assert old.valid_until is None

    now_ids = await _ids(question, as_of=datetime.now(UTC))
    assert old_id not in now_ids
    assert new_id in now_ids

    then_ids = await _ids(question, recorded_as_of=BEFORE)
    assert old_id in then_ids

    await _restore_replaced(TENANT, uuid.UUID(new_id))
    old = await _memory(old_id)
    assert old.status == "active"
    assert "superseded_at" not in (old.properties or {})
    assert old_id in await _ids(question, as_of=datetime.now(UTC))


@skip_on_db_error
async def test_undoing_a_correction_on_jarvis_clears_superseded_at(client, plain_retrieval):
    from life_graph.tools.memory_search import _supersede

    word, old_id, new_id = await _pair()
    await _supersede(TENANT, uuid.UUID(old_id), uuid.UUID(new_id))
    assert _stamp(await _memory(old_id))

    resp = await client.post(f"/api/v1/jarvis/memories/{new_id}/undo")
    assert resp.status_code == 200, resp.text
    old = await _memory(old_id)
    assert old.status == "active"
    assert "superseded_at" not in (old.properties or {})
    assert old_id in await _ids(f"where does {word} live?", as_of=datetime.now(UTC))


@skip_on_db_error
async def test_a_contradiction_approved_then_rejected(client, plain_retrieval):
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    word, old_id, new_id = await _pair()
    async with async_session() as s:
        ap = Approval(
            tenant_id=TENANT,
            kind="contradiction",
            source="judgment",
            source_ref=f"{old_id}|{new_id}",
            title="Review a suspected contradiction",
            detail="test",
            status="pending",
            payload={"memory_id_old": old_id, "memory_id_new": new_id, "applied": False},
        )
        s.add(ap)
        await s.commit()
        ap_id = str(ap.id)

    # The approve route resolves; a reject of a resolved item is refused, so
    # the undo is exercised through a second, already-applied approval.
    resp = await client.post(f"/api/v1/approvals/{ap_id}/approve")
    assert resp.status_code == 200, resp.text
    old = await _memory(old_id)
    assert old.status == "superseded"
    assert _stamp(old)
    assert old.valid_until is None
    question = f"where does {word} live?"
    assert old_id not in await _ids(question, as_of=datetime.now(UTC))
    assert old_id in await _ids(question, recorded_as_of=BEFORE)

    async with async_session() as s:
        undo = Approval(
            tenant_id=TENANT,
            kind="contradiction",
            source="correction",
            source_ref=f"{old_id}|{new_id}|undo",
            title="You corrected a memory",
            detail="test",
            status="pending",
            payload={"memory_id_old": old_id, "memory_id_new": new_id, "applied": True},
        )
        s.add(undo)
        await s.commit()
        undo_id = str(undo.id)
    resp = await client.post(f"/api/v1/approvals/{undo_id}/reject")
    assert resp.status_code == 200, resp.text
    old = await _memory(old_id)
    assert old.status == "active"
    assert "superseded_at" not in (old.properties or {})
    assert old_id in await _ids(question, as_of=datetime.now(UTC))


@skip_on_db_error
async def test_a_merged_duplicate_is_stamped_but_not_ended(client):
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    word = f"quillon{uuid.uuid4().hex[:6]}"
    a_id = await _seed(f"{word} deploy freeze on Fridays")
    b_id = await _seed(f"{word} no deploys on Friday")
    async with async_session() as s:
        ap = Approval(
            tenant_id=TENANT,
            kind="merge",
            source="test",
            title="Merge test pair",
            detail="test",
            status="pending",
            payload={"memory_id_a": a_id, "memory_id_b": b_id},
        )
        s.add(ap)
        await s.commit()
        ap_id = str(ap.id)

    resp = await client.post(f"/api/v1/approvals/{ap_id}/approve")
    assert resp.status_code == 200, resp.text
    a, b = await _memory(a_id), await _memory(b_id)
    loser, winner = (b, a) if b.status == "superseded" else (a, b)
    assert loser.status == "superseded"
    assert _stamp(loser)
    assert loser.properties.get("merged_into") == str(winner.id)
    # A duplicate was never untrue: no end of valid time.
    assert loser.valid_until is None
    assert "superseded_at" not in (winner.properties or {})


@skip_on_db_error
async def test_memory_manager_supersede_stamps_the_old_row():
    from life_graph.core.memory_manager import MemoryManager
    from life_graph.core.tenant import tenant_scope
    from life_graph.storage.postgres import PostgresMemoryStore

    _word, old_id, new_id = await _pair()
    mgr = MemoryManager(
        store=PostgresMemoryStore(), extractor=None, tagger=None, contradiction_detector=None
    )
    with tenant_scope(TENANT):
        await mgr.supersede(old_id, new_id, "test")
    old, new = await _memory(old_id), await _memory(new_id)
    assert old.status == "superseded"
    assert str(old.superseded_by) == new_id
    assert str(new.supersedes) == old_id
    assert _stamp(old)
    # The existing properties survive the stamp.
    assert "superseded_at" not in (new.properties or {})
    assert new.properties.get("saved_by") == "owner"


@skip_on_db_error
async def test_a_micro_consolidation_duplicate_keeps_its_properties_an_object():
    """The dedup note is merged into the properties object. It used to be cast
    from a JSON string, which made the properties a JSON array."""
    from sqlalchemy import update

    from life_graph.models.db import Memory
    from life_graph.services.memory.micro_consolidation import _with_merged_note
    from life_graph.storage.database import async_session

    winner = await _seed("quillon kept wording")
    dup = await _seed("quillon same wording", properties={"slot": "city"})
    async with async_session() as s:
        await s.execute(
            update(Memory)
            .where(Memory.id == uuid.UUID(dup))
            .values(status="superseded", properties=_with_merged_note(winner))
        )
        await s.commit()
    row = await _memory(dup)
    assert isinstance(row.properties, dict), row.properties
    assert row.properties["slot"] == "city"
    assert row.properties["merged_into"] == winner
    assert _stamp(row)


@skip_on_db_error
async def test_deny_stamps_the_old_row_not_its_replacement():
    from life_graph.core.tenant import tenant_scope
    from life_graph.storage.postgres import PostgresMemoryStore

    old_id = await _seed("quillon denied fact", properties={"slot": "city"})
    with tenant_scope(TENANT):
        old, replacement = await PostgresMemoryStore().deny(
            uuid.UUID(old_id), replacement_content="quillon corrected fact"
        )
    assert _stamp(old)
    assert old.properties.get("slot") == "city"
    assert replacement is not None
    assert "superseded_at" not in (replacement.properties or {})
    assert replacement.properties.get("slot") == "city"


@skip_on_db_error
async def test_undo_on_jarvis_leaves_a_merged_duplicate_folded_away(client):
    """A near-duplicate merged into the saved memory is not an earlier value:
    undoing the save must not bring it back as a second active copy."""
    from sqlalchemy import update

    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    word, dup_id, saved_id = await _pair()
    async with async_session() as s:
        await s.execute(
            update(Memory)
            .where(Memory.id == uuid.UUID(dup_id))
            .values(
                status="superseded",
                superseded_by=uuid.UUID(saved_id),
                properties={"merged_into": saved_id},
            )
        )
        await s.commit()

    resp = await client.post(f"/api/v1/jarvis/memories/{saved_id}/undo")
    assert resp.status_code == 200, resp.text
    dup = await _memory(dup_id)
    assert dup.status == "superseded" and str(dup.superseded_by) == saved_id
