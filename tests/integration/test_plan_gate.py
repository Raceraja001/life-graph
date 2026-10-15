"""A fanned-out plan task only starts once the task before it is merged, and
a predecessor that can no longer merge stops the rest of the plan (with one
notification), instead of later tasks running on code missing its change.

claim_next_queued is global across tenants by design, and the test database
can hold other queued rows, so tests drain the queue and assert only on the
tasks they created.
"""

from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"plan_gate_{uuid.uuid4().hex[:8]}"


async def _project():
    from life_graph.models.db import Project
    from life_graph.storage.database import async_session

    pid = uuid.uuid4()
    async with async_session() as s:
        s.add(Project(id=pid, tenant_id=TENANT, name=f"p-{pid.hex[:6]}", path="/tmp/x"))
        await s.commit()
    return pid


async def _plan_tasks(count, project_id, *, first_status="queued"):
    """A plan group of `count` queued tasks; returns their ids in order."""
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    group = str(uuid.uuid4())
    ids = []
    async with async_session() as s:
        for i in range(1, count + 1):
            tid = uuid.uuid4()
            s.add(AgentTask(
                id=tid, tenant_id=TENANT, agent_name="dev_task", task_name=f"t{i}",
                title=f"task {i}", instructions="do it", task_type="code_change",
                assigned_agent="code-fixer-local", project_id=project_id,
                status=first_status if i == 1 else "queued",
                properties={
                    "kind": "dev_task", "run_mode": "queue", "plan_group_id": group,
                    "plan_task_index": i, "plan_task_count": count,
                },
            ))
            await s.flush()  # created_at strictly in plan order
            ids.append(tid)
        await s.commit()
    return ids


async def _drain():
    """Claim until nothing is runnable; return the ids that were claimed."""
    from life_graph.services.dev_tasks import claim_next_queued
    from life_graph.storage.database import async_session

    claimed = []
    for _ in range(200):
        task = await claim_next_queued(async_session)
        if task is None:
            break
        claimed.append(task.id)
    return claimed


async def _status(task_id):
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        t = await s.get(AgentTask, task_id)
        return t.status, t.error


async def _add_approval(task_id, kind, status="pending", payload=None):
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as s:
        s.add(Approval(
            tenant_id=TENANT, kind=kind, title=kind, status=status,
            source="driver" if kind == "driver_pr" else "driver_merge",
            source_ref=str(task_id), payload=payload or {},
        ))
        await s.commit()


@pytest.fixture
def plan_stopped_events():
    from life_graph.core.events import Event, EventType, event_bus

    seen: list[Event] = []

    async def _capture(event):
        if event.payload.get("kind") == "plan_stopped":
            seen.append(event)

    event_bus.subscribe(EventType.APPROVAL_FILED, _capture)
    try:
        yield seen
    finally:
        event_bus.unsubscribe(EventType.APPROVAL_FILED, _capture)


@pytest.mark.asyncio
@skip_on_db_error
async def test_first_task_runs_but_the_second_waits_for_its_merge():
    t1, t2 = await _plan_tasks(2, await _project())

    claimed = await _drain()

    assert t1 in claimed
    assert t2 not in claimed
    assert (await _status(t2))[0] == "queued"


@pytest.mark.asyncio
@skip_on_db_error
async def test_second_waits_while_the_first_awaits_pr_approval():
    t1, t2 = await _plan_tasks(2, await _project(), first_status="completed")
    await _add_approval(t1, "driver_pr")  # stage: awaiting_pr

    assert t2 not in await _drain()
    assert (await _status(t2))[0] == "queued"


@pytest.mark.asyncio
@skip_on_db_error
async def test_second_runs_once_the_first_is_merged():
    t1, t2 = await _plan_tasks(2, await _project(), first_status="completed")
    await _add_approval(t1, "driver_pr", status="approved")
    await _add_approval(t1, "driver_merge", status="approved")  # stage: merged

    assert t2 in await _drain()


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_failed_task_stops_the_rest_of_the_plan_and_notifies_once(plan_stopped_events):
    t1, t2, t3 = await _plan_tasks(3, await _project(), first_status="failed")

    claimed = await _drain()

    assert t2 not in claimed and t3 not in claimed
    for tid in (t2, t3):
        status, error = await _status(tid)
        assert status == "failed"
        assert error.startswith("Not run:")
    mine = [e for e in plan_stopped_events if e.payload["tenant_id"] == TENANT]
    assert len(mine) == 1, "one notification at the real failure, not one per stopped task"
    assert "task 1" in mine[0].payload["detail"].lower()


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_waiting_plan_does_not_starve_other_queued_work():
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    project = await _project()
    _t1, t2 = await _plan_tasks(2, project, first_status="completed")
    await _add_approval(_t1, "driver_pr")  # t2 must wait
    other = uuid.uuid4()
    async with async_session() as s:
        s.add(AgentTask(
            id=other, tenant_id=TENANT, agent_name="dev_task", task_name="nightly",
            title="nightly", instructions="lint", task_type="code_change",
            assigned_agent="code-fixer-local", project_id=project, status="queued",
            properties={"kind": "dev_task", "run_mode": "queue"},
        ))
        await s.commit()

    claimed = await _drain()

    assert other in claimed
    assert t2 not in claimed
