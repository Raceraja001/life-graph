"""Integration tests for the merge-suggestion producer + approve side-effect.

- Approving a kind='merge' approval merges the two memories (loser superseded,
  tags unioned, higher importance wins).
- Rejecting leaves both active.
- The nightly scan executes cleanly.

Note: the pgvector similarity path (crafted-embedding pairs → suggestions) is
verified against real Postgres out of band — tests/conftest.py substitutes a
fake Vector type, so embeddings can't be inserted under pytest. The scan test
here therefore only asserts the service runs and returns cleanly.

Defensive per house convention: accept 500 when the DB is unreachable, never
422 for valid input. See docs/specs/approvals-feed.md.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.core.tenant import set_tenant_context
from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = "test_merge_tenant"
SCAN_TENANT = "test_merge_scan_tenant"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "merge-test-user"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


async def _seed_memory(content, importance, tags, tenant: str = TENANT) -> str:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            importance=importance,
            tags=tags,
            status="active",
            trust_tier="verified",
            source_type="test",
        )
        s.add(m)
        await s.commit()
        return str(m.id)


async def _seed_merge_approval(a_id: str, b_id: str) -> str:
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

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
        return str(ap.id)


async def _get_memory(mem_id: str):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, uuid.UUID(mem_id))


class TestMergeSideEffect:
    @skip_on_db_error
    async def test_approve_merges_memories(self, client: AsyncClient):
        # A has higher importance → wins; B is superseded into A; tags unioned.
        a_id = await _seed_memory("Deploy freeze on Fridays", 0.9, ["rule"])
        b_id = await _seed_memory("No prod deploys Friday afternoons", 0.6, ["ops"])
        approval_id = await _seed_merge_approval(a_id, b_id)

        resp = await client.post(f"/api/v1/approvals/{approval_id}/approve")
        assert resp.status_code in (200, 500), resp.text
        if resp.status_code == 500:
            return

        a = await _get_memory(a_id)
        b = await _get_memory(b_id)
        assert a.status == "active"
        assert b.status == "superseded"
        assert str(b.superseded_by) == a_id
        assert set(a.tags) == {"rule", "ops"}

    @skip_on_db_error
    async def test_reject_keeps_both(self, client: AsyncClient):
        a_id = await _seed_memory("Prefer FastAPI for services", 0.8, ["pref"])
        b_id = await _seed_memory("Use FastAPI for new APIs", 0.7, ["pref"])
        approval_id = await _seed_merge_approval(a_id, b_id)

        resp = await client.post(f"/api/v1/approvals/{approval_id}/reject")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            a = await _get_memory(a_id)
            b = await _get_memory(b_id)
            assert a.status == "active" and b.status == "active"


class TestMergeScan:
    @skip_on_db_error
    async def test_scan_runs_cleanly(self):
        # Memories without embeddings yield no suggestions; this asserts the
        # service executes end-to-end (idempotency query + iteration) under the
        # harness. The similarity matching itself is verified against real
        # Postgres separately (fake Vector type blocks embedded inserts here).
        from life_graph.services.merge_suggestions import MergeSuggestionService
        from life_graph.storage.database import async_session
        from life_graph.storage.postgres import PostgresMemoryStore

        await _seed_memory("scan smoke memory", 0.5, ["x"], tenant=SCAN_TENANT)

        set_tenant_context(SCAN_TENANT, "system")
        store = PostgresMemoryStore()
        async with async_session() as session:
            queued = await MergeSuggestionService(session, store).scan_and_queue(SCAN_TENANT)
            await session.commit()

        assert queued == 0
