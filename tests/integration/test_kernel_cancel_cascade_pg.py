"""POST /kernel/tasks/{id}/cancel against the real database (Phase 2 M2).

The kernel cancel used to stop only the one task: its delegated children
(rows with parent_task_id) stayed queued or running, kept their live
capabilities, and an in-process child run went on. Now the whole open tree
is cancelled, revoked, and each run this process holds is stopped.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import assert_ok, skip_on_db_error

TENANT = f"kcancel_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": TENANT, "X-User-ID": "tester"},
    ) as c:
        yield c


async def _task(task_id):
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(AgentTask, task_id)


@pytest.mark.asyncio
@skip_on_db_error
async def test_kernel_cancel_stops_queued_and_running_children(client, monkeypatch):
    from life_graph.api.dependencies import get_process_manager
    from life_graph.autonomy.approvals.capability import CapabilityStore
    from life_graph.services.delegation import DelegationEngine
    from life_graph.storage.database import async_session

    store = CapabilityStore()
    monkeypatch.setattr("life_graph.autonomy.approvals.capability.capability_store", store)
    engine = DelegationEngine(async_session)

    parent = await engine.create_task(TENANT, {"agent_name": "jarvis", "task_name": "parent"})
    await engine.update_task(TENANT, parent.id, {"status": "running"})
    queued = await engine.create_child_task(
        TENANT, parent.id, {"agent_name": "scout", "task_name": "queued child"}
    )
    running = await engine.create_child_task(
        TENANT, parent.id, {"agent_name": "coder", "task_name": "running child"}
    )
    await engine.update_task(TENANT, running.id, {"status": "running"})
    grandchild = await engine.create_child_task(
        TENANT, running.id, {"agent_name": "scout", "task_name": "grandchild"}
    )

    caps = {
        tid: store.issue(
            tenant_id=TENANT,
            action_types=["transfer_money"],
            target_origins=["owner"],
            task_id=str(tid),
        ).capability_id
        for tid in (parent.id, queued.id, running.id, grandchild.id)
    }

    # The running child's run, held by this process's ProcessManager.
    pm = get_process_manager()
    child_run = asyncio.create_task(asyncio.sleep(3600))
    pm._running[running.id] = child_run
    try:
        r = await client.post(f"/api/v1/kernel/tasks/{parent.id}/cancel")
        data = assert_ok(r, 200)["data"]
        await asyncio.sleep(0)
    finally:
        pm._running.pop(running.id, None)
        child_run.cancel()

    assert data["status"] == "cancelled"
    assert data["cancelled_descendants"] == 3
    assert data["stopped_in_process"] == 1
    assert child_run.cancelled()

    assert (await _task(parent.id)).status == "cancelled"
    for tid in (queued.id, running.id, grandchild.id):
        row = await _task(tid)
        assert row.status == "cancelled", (row.task_name, row.status)
        assert row.cancel_reason == f"Parent {parent.id} cancelled"
    for tid, cap in caps.items():
        assert store.get(cap).revoked is True, tid


@pytest.mark.asyncio
@skip_on_db_error
async def test_kernel_cancel_still_answers_409_for_a_finished_task(client):
    from life_graph.services.delegation import DelegationEngine
    from life_graph.storage.database import async_session

    engine = DelegationEngine(async_session)
    done = await engine.create_task(TENANT, {"agent_name": "jarvis", "task_name": "done"})
    await engine.update_task(TENANT, done.id, {"status": "completed"})

    r = await client.post(f"/api/v1/kernel/tasks/{done.id}/cancel")
    assert r.status_code == 409, r.text
