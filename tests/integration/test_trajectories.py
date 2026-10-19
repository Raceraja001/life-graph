"""The trajectory recorder stores a driver:steps event as agent_run_steps
rows, and reading them back is ordered by attempt then step, and scoped to
the tenant.
"""

from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import skip_on_db_error


async def _task(tenant: str) -> uuid.UUID:
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    tid = uuid.uuid4()
    async with async_session() as s:
        s.add(
            AgentTask(
                id=tid,
                tenant_id=tenant,
                agent_name="dev_task",
                task_name="t",
                status="completed",
                properties={"kind": "dev_task"},
            )
        )
        await s.commit()
    return tid


@pytest.mark.asyncio
@skip_on_db_error
async def test_steps_are_recorded_and_read_back_in_order_for_their_tenant_only():
    from life_graph.core.events import Event, EventType
    from life_graph.services.trajectories import TrajectoryRecorder, list_steps
    from life_graph.storage.database import async_session

    tenant = f"traj_{uuid.uuid4().hex[:8]}"
    task_id = await _task(tenant)
    recorder = TrajectoryRecorder()

    def _event(attempt, steps):
        return Event(
            type=EventType.DRIVER_STEPS,
            payload={
                "tenant_id": tenant,
                "task_id": str(task_id),
                "driver": "claude_code",
                "attempt": attempt,
                "steps": steps,
            },
        )

    # The bounce (attempt 2) is recorded first here on purpose: order on read
    # comes from attempt/seq, not insertion.
    await recorder._on_steps(_event(2, [{"seq": 1, "kind": "text", "content": "fixed it"}]))
    await recorder._on_steps(
        _event(
            1,
            [
                {
                    "seq": 1,
                    "kind": "tool_call",
                    "tool": "Read",
                    "content": "{}",
                    "ref": "a",
                    "at": "2026-10-13T09:40:32.579Z",
                },
                {
                    "seq": 2,
                    "kind": "tool_result",
                    "tool": "Read",
                    "content": "TOKEN=abcdefgh12345678",
                    "ref": "a",
                },
            ],
        )
    )

    async with async_session() as s:
        mine = await list_steps(s, tenant, task_id)
        other = await list_steps(s, "someone-else", task_id)

    assert [(r["attempt"], r["seq"], r["kind"]) for r in mine] == [
        (1, 1, "tool_call"),
        (1, 2, "tool_result"),
        (2, 1, "text"),
    ]
    assert mine[0]["at"].startswith("2026-10-13T09:40:32")
    assert "abcdefgh12345678" not in mine[1]["content"]
    assert other == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_opted_out_tenant_has_no_steps_recorded(monkeypatch):
    from life_graph.config import settings
    from life_graph.core.events import Event, EventType
    from life_graph.services.trajectories import TrajectoryRecorder, list_steps
    from life_graph.storage.database import async_session

    tenant = f"optout_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(settings, "trajectory_opt_out_tenants", f"someone,{tenant}")
    task_id = await _task(tenant)

    await TrajectoryRecorder()._on_steps(
        Event(
            type=EventType.DRIVER_STEPS,
            payload={
                "tenant_id": tenant,
                "task_id": str(task_id),
                "driver": "local",
                "attempt": 1,
                "steps": [{"seq": 1, "kind": "text", "content": "private"}],
            },
        )
    )

    async with async_session() as s:
        assert await list_steps(s, tenant, task_id) == []
