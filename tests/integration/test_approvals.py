"""Integration tests for the unified Approvals API.

Covers:
- GET /api/v1/approvals (list; envelope; ?status=all)
- POST /api/v1/approvals/{id}/approve|reject (transitions, 409 on re-resolve, 404)
- tenant isolation

Every status is asserted exactly: ``skip_on_db_error`` skips when no
database is reachable, so a 500 is always a failure. See
docs/specs/approvals-feed.md. The resolve expectations (200 for a dev-mode
caller naming ``resolved_by`` in the body) are today's master behaviour; the
approvals-identity work may change who is recorded, not these statuses.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import assert_ok, skip_on_db_error

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
        body = assert_ok(resp, 200)
        assert "data" in body
        assert isinstance(body["data"], list)

    @skip_on_db_error
    async def test_list_status_all_is_valid(self, client: AsyncClient):
        # A valid query param must never 422.
        resp = await client.get("/api/v1/approvals", params={"status": "all"})
        assert_ok(resp, 200)


class TestResolve:
    @skip_on_db_error
    async def test_approve_unknown_id_404(self, client: AsyncClient):
        resp = await client.post(f"/api/v1/approvals/{uuid.uuid4()}/approve")
        assert resp.status_code == 404, resp.text

    @skip_on_db_error
    async def test_approve_malformed_id_not_found(self, client: AsyncClient):
        resp = await client.post("/api/v1/approvals/not-a-uuid/approve")
        assert resp.status_code == 404, resp.text

    @skip_on_db_error
    async def test_approve_then_conflict(self, client: AsyncClient):
        approval_id = await _seed_approval()

        first = await client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            json={"resolved_by": "tester"},
        )
        assert assert_ok(first, 200)["data"]["status"] == "approved"

        # Re-resolving an already-resolved item conflicts.
        second = await client.post(f"/api/v1/approvals/{approval_id}/approve")
        assert second.status_code == 409, second.text

    @skip_on_db_error
    async def test_reject_transitions(self, client: AsyncClient):
        approval_id = await _seed_approval()
        resp = await client.post(f"/api/v1/approvals/{approval_id}/reject")
        assert assert_ok(resp, 200)["data"]["status"] == "rejected"

    @skip_on_db_error
    async def test_tenant_isolation(self, client: AsyncClient):
        # Seed under OTHER_TENANT; the default-tenant client must not resolve it.
        approval_id = await _seed_approval(OTHER_TENANT)
        resp = await client.post(f"/api/v1/approvals/{approval_id}/approve")
        assert resp.status_code == 404, resp.text


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


async def _row(approval_id: str):
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as session:
        return await session.get(Approval, uuid.UUID(approval_id))


class TestApprovedActionsRunAtMostOnce:
    """P0 (2026-11-20): a durable execution claim is committed before an
    external side effect runs, so a crash between the effect and the commit
    leaves evidence instead of a plain pending row that runs it again."""

    @skip_on_db_error
    async def test_a_crash_after_the_side_effect_does_not_run_it_again(self, client, monkeypatch):
        from life_graph.services.approvals import ApprovalService
        from life_graph.storage.database import async_session

        approval_id = await _seed_approval(kind="driver_deploy")
        calls = []

        async def deploy(self, appr, approve):
            calls.append(appr.id)

        monkeypatch.setattr(ApprovalService, "_apply_driver_deploy", deploy)

        # The API process: the deploy ran, then it died before committing.
        async with async_session() as dying:
            await ApprovalService(dying).resolve(TENANT, approval_id, "approve")
            await dying.rollback()

        row = await _row(approval_id)
        assert row.status == "pending"
        assert row.payload["execution"]["state"] == "started"

        again = await client.post(f"/api/v1/approvals/{approval_id}/approve")
        assert again.status_code == 409, again.text
        assert "being applied" in again.text
        assert len(calls) == 1

    @skip_on_db_error
    async def test_two_approvals_of_a_deploy_at_once_deploy_once(self, client, monkeypatch):
        import asyncio

        from life_graph.services.approvals import ApprovalService

        approval_id = await _seed_approval(kind="driver_deploy")
        calls = []

        async def slow_deploy(self, appr, approve):
            calls.append(str(appr.id))
            await asyncio.sleep(0.5)

        monkeypatch.setattr(ApprovalService, "_apply_driver_deploy", slow_deploy)

        url = f"/api/v1/approvals/{approval_id}/approve"
        results = await asyncio.gather(*(client.post(url) for _ in range(3)))

        codes = sorted(r.status_code for r in results)
        assert codes == [200, 409, 409], [r.text for r in results]
        assert calls == [approval_id]
        row = await _row(approval_id)
        assert row.status == "approved" and row.payload["execution"]["state"] == "done"

    @skip_on_db_error
    async def test_the_side_effect_runs_with_the_claim_committed_and_no_lock_held(
        self, monkeypatch
    ):
        """No transaction holds the row lock through a deploy: another
        connection can lock the row at once, and already sees the claim. The
        effect's own transaction (it reads before the command runs) is exempt
        from the idle timeout, so a slow deploy can still record its outcome."""
        from sqlalchemy import select, text

        from life_graph.models.db import Approval
        from life_graph.services.approvals import ApprovalService
        from life_graph.storage.database import async_session

        approval_id = await _seed_approval(kind="driver_deploy")
        seen = {}

        async def look(self, appr, approve):
            async with async_session() as other:
                row = (
                    await other.execute(
                        select(Approval).where(Approval.id == appr.id).with_for_update(nowait=True)
                    )
                ).scalar_one()
                seen["state"] = row.payload["execution"]["state"]
                await other.rollback()
            seen["idle"] = (
                await self.session.execute(text("SHOW idle_in_transaction_session_timeout"))
            ).scalar()

        monkeypatch.setattr(ApprovalService, "_apply_driver_deploy", look)

        async with async_session() as session:
            await ApprovalService(session).resolve(TENANT, approval_id, "approve")
            await session.commit()

        assert seen == {"state": "started", "idle": "0"}

    @skip_on_db_error
    async def test_a_manual_approve_during_an_auto_merge_retry_is_refused(
        self, client, monkeypatch
    ):
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
            mine = str(row.id)

        merges = []
        manual = {}

        async def sweep_merge(self, appr, *_a):
            if str(appr.id) != mine:
                return
            merges.append("sweep")
            resp = await client.post(f"/api/v1/approvals/{mine}/approve")
            manual["code"], manual["text"] = resp.status_code, resp.text
            appr.status = "approved"

        async def manual_merge(self, appr, approve):
            merges.append("manual")

        monkeypatch.setattr(approvals.ApprovalService, "maybe_auto_merge", sweep_merge)
        monkeypatch.setattr(approvals.ApprovalService, "_apply_driver_merge", manual_merge)

        await approvals.retry_auto_merges(async_session)

        assert manual["code"] == 409, manual["text"]
        assert merges == ["sweep"]
        assert (await _row(mine)).payload["execution"]["state"] == "done"

    @skip_on_db_error
    async def test_a_stale_claim_is_flagged_and_needs_an_explicit_retry(self, client, monkeypatch):
        from datetime import UTC, datetime, timedelta

        from life_graph.models.db import Approval
        from life_graph.services import approvals
        from life_graph.storage.database import async_session

        started = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
        async with async_session() as session:
            row = Approval(
                tenant_id=TENANT,
                kind="driver_deploy",
                source="test",
                title="Deploy test",
                status="pending",
                payload={"execution": {"state": "started", "started_at": started, "attempt": 1}},
            )
            session.add(row)
            await session.commit()
            mine = str(row.id)

        calls = []

        async def deploy(self, appr, approve):
            calls.append(appr.id)

        monkeypatch.setattr(approvals.ApprovalService, "_apply_driver_deploy", deploy)

        assert await approvals.flag_stale_claims(async_session) >= 1
        assert (await _row(mine)).payload["execution"]["state"] == "unknown"

        url = f"/api/v1/approvals/{mine}/approve"
        plain = await client.post(url)
        assert plain.status_code == 409, plain.text
        assert "retry" in plain.text
        assert calls == []

        retried = await client.post(url, json={"retry": True})
        assert retried.status_code == 200, retried.text
        assert len(calls) == 1
        execution = (await _row(mine)).payload["execution"]
        assert execution["state"] == "done" and execution["attempt"] == 2
