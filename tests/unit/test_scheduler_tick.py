"""Unit tests for the per-minute scheduler ticker cron task."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_tick_fires_each_due_job_and_isolates_failures():
    from life_graph.workers import tasks

    scheduler = AsyncMock()
    scheduler.get_due_jobs = AsyncMock(return_value=[
        {"id": "j1", "tenant_id": "t1", "agent_name": "scout"},
        {"id": "j2", "tenant_id": "t2", "agent_name": "admin"},
    ])
    # j1 raises, j2 must still fire
    scheduler.fire_job = AsyncMock(side_effect=[RuntimeError("boom"), {"task_id": "x"}])

    with patch.object(tasks, "get_scheduler_service", return_value=scheduler), \
         patch.object(tasks, "set_tenant_context") as set_ctx:
        out = await tasks.tick_scheduled_jobs({})

    assert scheduler.fire_job.await_count == 2
    assert out["fired"] == 1
    assert out["failed"] == 1
    set_ctx.assert_any_call("t1", "system")
    set_ctx.assert_any_call("t2", "system")
