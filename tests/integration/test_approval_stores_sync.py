"""The autonomy queue and its copies in the unified feed agree (audit H9), on Postgres.

An autonomy action waiting for approval lives in ``approval_queue`` and is
copied into ``approvals`` (``kind="autonomous_action"``,
services/autonomous_approvals.py). Before 2026-11-20 nothing on the queue side
touched the copy: it stayed pending after the queue resolved, and a later
Reject on it was reported as success over an approved action. These tests
drive both stores against the real schema, including the row locks.

Nothing here runs a host command: the one test that executes an action does so
for a tenant with no TenantConfig row, which the kill switch treats as paused
(autonomy/kill_switch.py), and the seeded command ("true") carries no pin
either, so the action is recorded as blocked before anything runs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = "test_approval_stores_sync"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "stores-sync-test"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


async def _seed(
    *,
    queue_status: str = "pending",
    action_status: str = "pending",
    expires_at: datetime | None = None,
    created_at: datetime | None = None,
) -> tuple[str, str, str]:
    """A queue entry, its AutoAction and its feed copy. Returns their ids."""
    from life_graph.autonomy.models import ApprovalQueueEntry, AutoAction
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    uniq = uuid.uuid4().hex[:8]
    async with async_session() as s:
        entry = ApprovalQueueEntry(
            tenant_id=TENANT,
            agent_id="ops",
            action_name=f"noop_{uniq}",
            action_command="true",
            risk_level="moderate",
            category="pipeline",
            trigger_type="manual",
            trigger_detail="stores sync test",
            status=queue_status,
            expires_at=expires_at,
            **({"created_at": created_at} if created_at else {}),
        )
        s.add(entry)
        await s.commit()
        action = AutoAction(
            tenant_id=TENANT,
            agent_id="ops",
            action_name=f"noop_{uniq}",
            action_command="true",
            project_id="ambient",  # AutoFixRequest requires one; levels bookkeeping needs it
            trigger_type="manual",
            trigger_detail="stores sync test",
            risk_level="moderate",
            status=action_status,
            approval_id=entry.id,
        )
        s.add(action)
        copy = Approval(
            tenant_id=TENANT,
            kind="autonomous_action",
            source="autonomy",
            source_ref=str(entry.id),
            title=f"moderate action: noop_{uniq}",
            detail="true",
            payload={"auto_action_id": "", "approval_id": str(entry.id), "kind": "command"},
            priority=50,
        )
        s.add(copy)
        await s.commit()
        copy.payload = {**copy.payload, "auto_action_id": str(action.id)}
        await s.commit()
        return str(entry.id), str(action.id), str(copy.id)


async def _rows(entry_id: str, action_id: str, copy_id: str):
    from life_graph.autonomy.models import ApprovalQueueEntry, AutoAction
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return (
            await s.get(ApprovalQueueEntry, entry_id),
            await s.get(AutoAction, action_id),
            await s.get(Approval, uuid.UUID(copy_id)),
        )


def _queue():
    from life_graph.runtime import get_approval_service

    return get_approval_service()


@skip_on_db_error
async def test_a_queue_reject_closes_the_copy_in_the_same_transaction():
    entry_id, action_id, copy_id = await _seed()

    await _queue().resolve(TENANT, entry_id, "reject", "not now", "owner")

    entry, action, copy = await _rows(entry_id, action_id, copy_id)
    assert (entry.status, action.status, copy.status) == ("rejected", "skipped", "rejected")
    assert copy.resolved_by == "owner"
    assert copy.resolution_note.startswith("Resolved in autonomy queue (rejected)")


@skip_on_db_error
async def test_stale_entries_close_their_copies():
    old = datetime.now(UTC) - timedelta(days=30)
    entry_id, action_id, copy_id = await _seed(created_at=old)

    assert await _queue().expire_stale(14) >= 1

    entry, action, copy = await _rows(entry_id, action_id, copy_id)
    assert (entry.status, action.status, copy.status) == ("stale", "skipped", "rejected")


@skip_on_db_error
async def test_a_passed_notify_before_window_approves_nothing():
    past = datetime.now(UTC) - timedelta(minutes=1)
    entry_id, action_id, copy_id = await _seed(expires_at=past)

    assert await _queue().check_expirations() >= 1

    entry, action, copy = await _rows(entry_id, action_id, copy_id)
    assert entry.status == "pending" and entry.expires_at is None
    assert action.status == "pending" and copy.status == "pending"


@skip_on_db_error
async def test_the_queue_waits_for_a_copy_the_feed_holds():
    """The feed locks its row first, then resolves the queue; the queue side
    takes the same order, and backs off at once (SKIP LOCKED) instead of
    deadlocking or overwriting the feed's decision."""
    from sqlalchemy import select

    from life_graph.autonomy.approvals.service import QueueConflictError
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    entry_id, action_id, copy_id = await _seed()
    async with async_session() as holder:
        await holder.execute(
            select(Approval).where(Approval.id == uuid.UUID(copy_id)).with_for_update()
        )
        with pytest.raises(QueueConflictError):
            await _queue().resolve(TENANT, entry_id, "reject", None, "owner")
        await holder.rollback()

    entry, _, copy = await _rows(entry_id, action_id, copy_id)
    assert entry.status == "pending" and copy.status == "pending"


@skip_on_db_error
async def test_rejecting_a_copy_the_queue_already_approved_is_409(client: AsyncClient):
    """The audit's scenario: queue approved (the old timeout did this), copy
    left pending, owner taps Reject on the copy."""
    entry_id, action_id, copy_id = await _seed(queue_status="approved")

    resp = await client.post(f"/api/v1/approvals/{copy_id}/reject", json={"note": "no"})

    assert resp.status_code == 409, resp.text
    assert "autonomy queue" in resp.json()["detail"]
    _, action, copy = await _rows(entry_id, action_id, copy_id)
    assert copy.status == "pending" and action.status == "pending"


@skip_on_db_error
async def test_approving_in_the_queue_runs_the_action_through_its_copy(client: AsyncClient):
    """It used to mark the entry approved and run nothing. Now it goes through
    the copy: both stores approved, the action taken off ``pending`` (here
    blocked by the kill switch, since this tenant has no TenantConfig)."""
    entry_id, action_id, copy_id = await _seed()

    resp = await client.post(
        f"/api/v1/autonomy/approvals/{entry_id}/resolve", json={"decision": "approve"}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == {"id": entry_id, "status": "approved"}
    entry, action, copy = await _rows(entry_id, action_id, copy_id)
    assert entry.status == "approved" and copy.status == "approved"
    assert copy.payload["execution"]["state"] == "done"
    # Refused before running, by the kill switch (no TenantConfig) or, if the
    # tenant is provisioned, by the command pin this seeded action lacks.
    assert action.status == "failure" and action.error_message
    assert action.stdout is None


@skip_on_db_error
async def test_reconcile_closes_drifted_copies_but_keeps_a_runnable_one():
    rejected = await _seed(queue_status="rejected", action_status="skipped")
    ran = await _seed(queue_status="approved", action_status="success")
    runnable = await _seed(queue_status="approved", action_status="pending")

    assert await _queue().reconcile_feed_copies() >= 2

    assert (await _rows(*rejected))[2].status == "rejected"
    assert (await _rows(*ran))[2].status == "approved"
    assert (await _rows(*runnable))[2].status == "pending"  # approving it runs it
