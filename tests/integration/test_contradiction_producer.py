"""Integration tests for the contradiction producer's approve/reject side-effect.

Ingest auto-supersedes contradictions and (additively) queues a
kind='contradiction' approval. Approving confirms it (no-op); rejecting UNDOES
the supersede — restoring the old memory to active and clearing the chain.

Defensive per house convention: accept 500 when the DB is unreachable, never
422 for valid input. See docs/specs/approvals-feed.md.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = "test_contradiction_tenant"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "contra-test-user"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


async def _seed_superseded_pair() -> tuple[str, str]:
    """Create old→new in the exact superseded state ingest would produce."""
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    uniq = uuid.uuid4().hex[:8]
    async with async_session() as s:
        new = Memory(
            content=f"switched to green tea {uniq}",
            tenant_id=TENANT,
            content_hash=hashlib.sha256(f"new{uniq}".encode()).hexdigest(),
            importance=0.7,
            tags=["pref"],
            status="active",
            trust_tier="verified",
            source_type="test",
        )
        old = Memory(
            content=f"likes filter coffee {uniq}",
            tenant_id=TENANT,
            content_hash=hashlib.sha256(f"old{uniq}".encode()).hexdigest(),
            importance=0.6,
            tags=["pref"],
            status="active",
            trust_tier="verified",
            source_type="test",
        )
        s.add(new)
        s.add(old)
        await s.commit()
        old.status = "superseded"
        old.superseded_by = new.id
        new.supersedes = old.id
        await s.commit()
        return str(old.id), str(new.id)


async def _seed_contradiction_approval(old_id: str, new_id: str) -> str:
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as s:
        ap = Approval(
            tenant_id=TENANT,
            kind="contradiction",
            source="test",
            title="Review a resolved contradiction",
            detail="test",
            status="pending",
            payload={"memory_id_old": old_id, "memory_id_new": new_id},
        )
        s.add(ap)
        await s.commit()
        return str(ap.id)


async def _get_memory(mem_id: str):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, uuid.UUID(mem_id))


class TestContradictionSideEffect:
    @skip_on_db_error
    async def test_reject_undoes_supersede(self, client: AsyncClient):
        old_id, new_id = await _seed_superseded_pair()
        approval_id = await _seed_contradiction_approval(old_id, new_id)

        resp = await client.post(f"/api/v1/approvals/{approval_id}/reject")
        assert resp.status_code in (200, 500), resp.text
        if resp.status_code == 500:
            return

        old = await _get_memory(old_id)
        new = await _get_memory(new_id)
        assert old.status == "active"
        assert old.superseded_by is None
        assert new.supersedes is None

    @skip_on_db_error
    async def test_approve_is_noop(self, client: AsyncClient):
        old_id, new_id = await _seed_superseded_pair()
        approval_id = await _seed_contradiction_approval(old_id, new_id)

        resp = await client.post(f"/api/v1/approvals/{approval_id}/approve")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            old = await _get_memory(old_id)
            assert old.status == "superseded"  # confirm — unchanged
