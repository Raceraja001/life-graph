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


class TestConcurrentResolve:
    """H4 (audit 2026-11-19): two resolves of one item at once run its side
    effect once. ``resolve()`` locks the row (FOR UPDATE NOWAIT) before it
    checks the status, so the second is told 409 instead of running it again."""

    @skip_on_db_error
    async def test_two_approvals_at_once_run_the_side_effect_once(self, client, monkeypatch):
        import asyncio

        from life_graph.services.approvals import ApprovalService

        approval_id = await _seed_approval()
        calls = []

        async def slow_merge(self, tenant_id, appr, approve):
            calls.append(str(appr.id))
            await asyncio.sleep(0.5)  # a merge or deploy still running

        monkeypatch.setattr(ApprovalService, "_apply_merge", slow_merge)

        url = f"/api/v1/approvals/{approval_id}/approve"
        first, second = await asyncio.gather(client.post(url), client.post(url))

        codes = sorted([first.status_code, second.status_code])
        assert codes == [200, 409], (first.text, second.text)
        assert calls == [approval_id]

    @skip_on_db_error
    async def test_a_held_row_is_409_and_pending_again_after_a_rollback(self, client):
        from sqlalchemy import select

        from life_graph.models.db import Approval
        from life_graph.storage.database import async_session

        approval_id = await _seed_approval()
        url = f"/api/v1/approvals/{approval_id}/approve"
        async with async_session() as holder:
            await holder.execute(
                select(Approval).where(Approval.id == uuid.UUID(approval_id)).with_for_update()
            )
            busy = await client.post(url)
            assert busy.status_code == 409, busy.text
            assert "being resolved" in busy.text
            await holder.rollback()  # e.g. the first approve's side effect failed

        done = await client.post(url)
        assert done.status_code == 200, done.text
        assert done.json()["data"]["status"] == "approved"

    @skip_on_db_error
    async def test_the_auto_merge_sweep_skips_a_row_being_resolved(self, monkeypatch):
        from sqlalchemy import select

        from life_graph.models.db import Approval
        from life_graph.services import approvals
        from life_graph.storage.database import async_session

        async with async_session() as session:
            row = Approval(
                tenant_id=TENANT,
                kind="driver_merge",
                source="test",
                title="Merge test PR",
                status="pending",
                payload={"auto_merge": True, "driver": "local"},
            )
            session.add(row)
            await session.commit()
            mine = row.id

        seen = []

        async def record(self, appr, driver_name, project_id, auto_merge):
            seen.append(appr.id)

        monkeypatch.setattr(approvals.ApprovalService, "maybe_auto_merge", record)

        async with async_session() as holder:
            await holder.execute(select(Approval).where(Approval.id == mine).with_for_update())
            await approvals.retry_auto_merges(async_session)
            assert mine not in seen
            await holder.rollback()

        await approvals.retry_auto_merges(async_session)
        assert mine in seen
