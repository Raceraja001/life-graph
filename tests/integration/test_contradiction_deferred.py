"""Integration tests: a pending memory supersedes nothing until the owner agrees.

Review 2026-10-22: ingest used to mark the old memory superseded while the
new one was still pending, and rejecting the new memory never restored it.
Now the supersede is recorded on a contradiction approval
(``payload.applied`` False) and applied when the owner approves the new
memory or the approval; rejecting either leaves the old memory active.

Embeddings may not be writable under pytest (tests/conftest.py fakes the
Vector type when pgvector is missing), so the ingest test hands
MemoryManager its candidate pool directly instead of relying on pgvector.
"""

from __future__ import annotations

import hashlib
import uuid
from types import SimpleNamespace

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = "test_contradiction_deferred_tenant"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "contra-deferred-user"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


def _row(content: str, status: str):
    from life_graph.models.db import Memory

    return Memory(
        content=content,
        tenant_id=TENANT,
        content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
        importance=0.6,
        tags=["preference"],
        status=status,
        trust_tier="verified",
        source_type="test",
    )


async def _seed_suspected_pair() -> tuple[str, str, str]:
    """Active old memory, pending new one, and the deferred approval ingest queues."""
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    uniq = uuid.uuid4().hex[:8]
    async with async_session() as s:
        old = _row(f"I prefer PostgreSQL {uniq}", "active")
        new = _row(f"I prefer MongoDB {uniq}", "pending")
        s.add_all([old, new])
        await s.flush()
        ap = Approval(
            tenant_id=TENANT,
            kind="contradiction",
            source="judgment",
            source_ref=f"{old.id}|{new.id}",
            title="Review a suspected contradiction",
            detail="test",
            status="pending",
            payload={"memory_id_old": str(old.id), "memory_id_new": str(new.id), "applied": False},
        )
        s.add(ap)
        await s.commit()
        return str(old.id), str(new.id), str(ap.id)


async def _get(model, row_id: str):
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(model, uuid.UUID(row_id))


async def _memory(row_id: str):
    from life_graph.models.db import Memory

    return await _get(Memory, row_id)


async def _approval(row_id: str):
    from life_graph.models.db import Approval

    return await _get(Approval, row_id)


class TestDeferredSupersede:
    @skip_on_db_error
    async def test_approving_new_memory_applies_supersede_and_keeps_it_undoable(
        self, client: AsyncClient
    ):
        old_id, new_id, ap_id = await _seed_suspected_pair()

        resp = await client.post(f"/api/v1/memories/{new_id}/approve")
        assert resp.status_code == 200, resp.text

        old, new, ap = await _memory(old_id), await _memory(new_id), await _approval(ap_id)
        assert new.status == "active"
        assert old.status == "superseded"
        assert str(old.superseded_by) == new_id
        assert str(new.supersedes) == old_id
        assert ap.status == "pending"  # still reviewable
        assert ap.payload["applied"] is True

        # ...and rejecting the approval undoes it, as before.
        resp = await client.post(f"/api/v1/approvals/{ap_id}/reject")
        assert resp.status_code == 200, resp.text
        old = await _memory(old_id)
        assert old.status == "active"
        assert old.superseded_by is None

    @skip_on_db_error
    async def test_rejecting_new_memory_leaves_old_active(self, client: AsyncClient):
        old_id, new_id, ap_id = await _seed_suspected_pair()

        resp = await client.post(f"/api/v1/memories/{new_id}/reject")
        assert resp.status_code == 200, resp.text

        old, ap = await _memory(old_id), await _approval(ap_id)
        assert old.status == "active"
        assert old.superseded_by is None
        assert ap.status == "rejected"  # moot review item closed

    @skip_on_db_error
    async def test_approving_contradiction_applies_supersede_and_activates_new(
        self, client: AsyncClient
    ):
        old_id, new_id, ap_id = await _seed_suspected_pair()

        resp = await client.post(f"/api/v1/approvals/{ap_id}/approve")
        assert resp.status_code == 200, resp.text

        old, new = await _memory(old_id), await _memory(new_id)
        assert old.status == "superseded"
        assert str(old.superseded_by) == new_id
        assert new.status == "active"

    @skip_on_db_error
    async def test_rejecting_contradiction_leaves_both_as_they_were(self, client: AsyncClient):
        old_id, new_id, ap_id = await _seed_suspected_pair()

        resp = await client.post(f"/api/v1/approvals/{ap_id}/reject")
        assert resp.status_code == 200, resp.text

        old, new = await _memory(old_id), await _memory(new_id)
        assert old.status == "active"
        assert new.status == "pending"
        # A later approve of the new memory must not supersede: the owner
        # already said these do not conflict.
        resp = await client.post(f"/api/v1/memories/{new_id}/approve")
        assert resp.status_code == 200, resp.text
        assert (await _memory(old_id)).status == "active"


class TestIngestDefers:
    @skip_on_db_error
    async def test_pending_fact_leaves_old_memory_active(self):
        from sqlalchemy import select

        from life_graph.core.memory_manager import MemoryManager
        from life_graph.core.tenant import tenant_scope
        from life_graph.extraction.rules import ExtractedFact
        from life_graph.models.db import Approval, Memory
        from life_graph.services.contradiction import ContradictionDetector
        from life_graph.storage.database import async_session
        from life_graph.storage.postgres import PostgresMemoryStore

        uniq = uuid.uuid4().hex[:8]
        async with async_session() as s:
            old = _row(f"I prefer PostgreSQL {uniq}", "active")
            s.add(old)
            await s.commit()
            old_id = str(old.id)

        from life_graph.models.db import _EMBED_DIM

        emb = [0.1] * _EMBED_DIM  # the column's width, in case real pgvector binds it
        candidate = SimpleNamespace(
            id=old.id, content=old.content, status="active", properties={}, embedding=emb
        )
        store = PostgresMemoryStore()

        async def candidates(embedding, limit=15):
            return [(candidate, 0.8)]

        store.find_similarity_candidates = candidates  # type: ignore[method-assign]
        mgr = MemoryManager(
            store=store,
            extractor=None,  # type: ignore[arg-type]
            tagger=SimpleNamespace(score=lambda c, ctx: (0.5, "medium")),  # type: ignore[arg-type]
            contradiction_detector=ContradictionDetector(store),
        )
        fact = ExtractedFact(
            content=f"I prefer MongoDB {uniq}x", fact_type="preference", confidence=0.8
        )

        with tenant_scope(TENANT):
            new = await mgr._process_fact(fact, context=None, source="test", embedding=emb)

        assert new.status == "pending"
        assert (await _memory(old_id)).status == "active"
        async with async_session() as s:
            ap = (
                await s.execute(
                    select(Approval).where(
                        Approval.tenant_id == TENANT,
                        Approval.source_ref == f"{old_id}|{new.id}",
                    )
                )
            ).scalar_one()
            stored = await s.get(Memory, new.id)
        assert ap.payload["applied"] is False
        assert ap.title == "Review a suspected contradiction"
        assert stored.properties["contradictions"][0]["existing_id"] == old_id
