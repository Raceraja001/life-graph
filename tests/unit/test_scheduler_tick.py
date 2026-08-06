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


def _make_scheduler_service(stored_input):
    """Build a bare SchedulerService with just enough patched to exercise fire_job."""
    from life_graph.kernel.scheduler import SchedulerService

    svc = SchedulerService.__new__(SchedulerService)  # bypass __init__
    pm = AsyncMock()
    pm.spawn = AsyncMock(return_value={"task_id": "tk", "status": "queued"})
    svc._process_manager = pm

    async def fake_get(tenant_id, job_id):
        return {
            "id": job_id,
            "name": "scout-daily",
            "agent_name": "scout",
            "is_active": True,
            "input": stored_input,
            "timeout_seconds": 600,
            "max_retries": 3,
        }

    svc.get_by_id = fake_get
    svc._record_run = AsyncMock()
    return svc, pm


@pytest.mark.asyncio
async def test_fire_job_uses_input_override_when_provided():
    stored_input = {"topics": ["x"]}
    svc, pm = _make_scheduler_service(stored_input)

    with patch("life_graph.kernel.scheduler.event_bus.emit", new=AsyncMock()):
        await svc.fire_job("t1", "j1", input_override={"message": "ENRICHED"})

    _, kwargs = pm.spawn.call_args
    assert kwargs["input_data"] == {"message": "ENRICHED"}


@pytest.mark.asyncio
async def test_fire_job_falls_back_to_stored_input_when_no_override():
    stored_input = {"topics": ["x"]}
    svc, pm = _make_scheduler_service(stored_input)

    with patch("life_graph.kernel.scheduler.event_bus.emit", new=AsyncMock()):
        await svc.fire_job("t1", "j1")

    _, kwargs = pm.spawn.call_args
    assert kwargs["input_data"] == stored_input
