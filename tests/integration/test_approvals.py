"""Integration tests for the unified Approvals API.

Covers:
- GET /api/v1/approvals (list; envelope; ?status=all)
- POST /api/v1/approvals/{id}/approve|reject (transitions, 409 on re-resolve, 404)
- tenant isolation

Defensive per house convention: accept 500 when the DB is unreachable, but
never 422 for a valid request. See docs/specs/approvals-feed.md.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = "test_approvals_tenant"
OTHER_TENANT = "test_approvals_other"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "approvals-test-user"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


async def _seed_approval(tenant: str = TENANT, *, kind: str = "merge") -> str:
    """Insert a pending approval directly and return its id (string)."""
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as session:
        row = Approval(
            tenant_id=tenant,
            kind=kind,
            source="test",
            title="Merge two near-duplicate memories",
            detail="test · seeded",
            status="pending",
        )
        session.add(row)
        await session.commit()
        return str(row.id)


class TestListApprovals:
    @skip_on_db_error
    async def test_list_returns_envelope(self, client: AsyncClient):
        resp = await client.get("/api/v1/approvals")
        assert resp.status_code in (200, 500), resp.text
        if resp.status_code == 200:
            body = resp.json()
            assert "data" in body
            assert isinstance(body["data"], list)

    @skip_on_db_error
    async def test_list_status_all_is_valid(self, client: AsyncClient):
        # A valid query param must never 422.
        resp = await client.get("/api/v1/approvals", params={"status": "all"})
        assert resp.status_code in (200, 500)


class TestResolve:
    @skip_on_db_error
    async def test_approve_unknown_id_404(self, client: AsyncClient):
        resp = await client.post(f"/api/v1/approvals/{uuid.uuid4()}/approve")
        assert resp.status_code in (404, 500)

    @skip_on_db_error
    async def test_approve_malformed_id_not_found(self, client: AsyncClient):
        resp = await client.post("/api/v1/approvals/not-a-uuid/approve")
        assert resp.status_code in (404, 500)

    @skip_on_db_error
    async def test_approve_then_conflict(self, client: AsyncClient):
        approval_id = await _seed_approval()

        first = await client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            json={"resolved_by": "tester"},
        )
        assert first.status_code in (200, 500), first.text
        if first.status_code == 500:
            return
        assert first.json()["data"]["status"] == "approved"

        # Re-resolving an already-resolved item conflicts.
        second = await client.post(f"/api/v1/approvals/{approval_id}/approve")
        assert second.status_code == 409

    @skip_on_db_error
    async def test_reject_transitions(self, client: AsyncClient):
        approval_id = await _seed_approval()
        resp = await client.post(f"/api/v1/approvals/{approval_id}/reject")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.json()["data"]["status"] == "rejected"

    @skip_on_db_error
    async def test_tenant_isolation(self, client: AsyncClient):
        # Seed under OTHER_TENANT; the default-tenant client must not resolve it.
        approval_id = await _seed_approval(OTHER_TENANT)
        resp = await client.post(f"/api/v1/approvals/{approval_id}/approve")
        assert resp.status_code in (404, 500)
