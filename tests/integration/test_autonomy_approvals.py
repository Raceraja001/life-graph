"""Integration tests for the reconciled Era-8 autonomy approval queue.

The queue (`approval_queue` table / `ApprovalQueueEntry`) was rebuilt against its
real model. Resolving an entry flips its status and updates the linked
`AutoAction` (reverse FK `AutoAction.approval_id`).

Every status is asserted exactly: ``skip_on_db_error`` skips when no
database is reachable, so a 500 is always a failure. See
docs/specs/era8-autonomy-reconciliation.md. The statuses below are today's
master behaviour for a dev-mode (owner) caller; the autonomy trust-boundary
work may add 403s for non-owners but should not change these.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import assert_ok, skip_on_db_error

TENANT = "test_autonomy_approvals_tenant"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "autonomy-test-user"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


async def _seed_action_with_approval() -> tuple[str, str]:
    """Create a pending ApprovalQueueEntry + an AutoAction linked to it."""
    from life_graph.autonomy.models import ApprovalQueueEntry, AutoAction
    from life_graph.storage.database import async_session

    uniq = uuid.uuid4().hex[:8]
    async with async_session() as s:
        approval = ApprovalQueueEntry(
            tenant_id=TENANT,
            agent_id="agent-x",
            action_name=f"restart_service_{uniq}",
            action_command="systemctl restart svc",
            risk_level="moderate",
            category="pipeline",
            trigger_type="manual",
            trigger_detail="needs a human ok",
            status="pending",
        )
        s.add(approval)
        await s.commit()
        action = AutoAction(
            tenant_id=TENANT,
            agent_id="agent-x",
            action_name=f"restart_service_{uniq}",
            action_command="systemctl restart svc",
            trigger_type="manual",
            trigger_detail="needs a human ok",
            risk_level="moderate",
            status="pending",
            approval_id=approval.id,
        )
        s.add(action)
        await s.commit()
        return str(approval.id), str(action.id)


async def _get(model_name: str, pk: str):
    from life_graph.autonomy import models as m
    from life_graph.storage.database import async_session

    model = getattr(m, model_name)
    async with async_session() as s:
        return await s.get(model, pk)


class TestApprovalQueue:
    @skip_on_db_error
    async def test_list_never_422(self, client: AsyncClient):
        resp = await client.get("/api/v1/autonomy/approvals")
        body = assert_ok(resp, 200)
        assert "data" in body
        assert isinstance(body["data"], list)

    @skip_on_db_error
    async def test_resolve_approve_updates_linked_action(self, client: AsyncClient):
        approval_id, action_id = await _seed_action_with_approval()

        resp = await client.post(
            f"/api/v1/autonomy/approvals/{approval_id}/resolve",
            json={"decision": "approve", "resolved_by": "tester"},
        )
        assert_ok(resp, 200)

        approval = await _get("ApprovalQueueEntry", approval_id)
        action = await _get("AutoAction", action_id)
        assert approval.status == "approved"
        # Who resolved is the server's view of the caller (api/approval_identity.py),
        # never the body's claim; the claim survives only as a note.
        assert approval.resolved_by != "tester"
        assert approval.resolved_by.startswith(("owner", "service-key"))
        assert "(client said: tester)" in (approval.resolution_note or "")
        # auto_actions has no 'approved' status; approve clears it back to pending.
        assert action.status == "pending"

    @skip_on_db_error
    async def test_resolve_reject_updates_linked_action(self, client: AsyncClient):
        approval_id, action_id = await _seed_action_with_approval()

        resp = await client.post(
            f"/api/v1/autonomy/approvals/{approval_id}/resolve",
            json={"decision": "reject", "resolved_by": "tester", "note": "no"},
        )
        assert_ok(resp, 200)

        approval = await _get("ApprovalQueueEntry", approval_id)
        action = await _get("AutoAction", action_id)
        assert approval.status == "rejected"
        # reject marks the linked action 'skipped' (ck_aa_status).
        assert action.status == "skipped"

    @skip_on_db_error
    async def test_double_resolve_is_guarded(self, client: AsyncClient):
        approval_id, _ = await _seed_action_with_approval()

        first = await client.post(
            f"/api/v1/autonomy/approvals/{approval_id}/resolve",
            json={"decision": "approve", "resolved_by": "tester"},
        )
        assert_ok(first, 200)
        again = await client.post(
            f"/api/v1/autonomy/approvals/{approval_id}/resolve",
            json={"decision": "approve", "resolved_by": "tester"},
        )
        # Already-resolved → ValueError → 404 (never a double side-effect).
        assert again.status_code == 404, again.text

    @skip_on_db_error
    async def test_resolve_missing_returns_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/v1/autonomy/approvals/{uuid.uuid4()}/resolve",
            json={"decision": "approve", "resolved_by": "tester"},
        )
        assert resp.status_code == 404, resp.text
