"""WorkflowEngine against the real database: create → run → complete → advance → cancel.

Found after #303 fixed the GET route: the engine itself still filtered on
``WorkflowStepRun.run_id`` / ``.step_key`` (not columns; the run link is
``workflow_run_id`` and the key is on ``WorkflowStep``), started steps with
``step.agent_name`` / ``step.config`` and a keyword call ``create_task`` does
not take, wrote ``step_run.task_id`` instead of ``agent_task_id``, and set
``run.error``, which has no column. No step could start, none could be
completed, and a cancel lost its reason.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"wfeng_{uuid.uuid4().hex[:8]}"


def _engine():
    from life_graph.services.delegation import DelegationEngine
    from life_graph.services.workflow_engine import WorkflowEngine
    from life_graph.storage.database import async_session

    return WorkflowEngine(async_session, DelegationEngine(async_session))


async def _steps(run_id: uuid.UUID) -> dict[str, object]:
    from life_graph.models.db import WorkflowStep, WorkflowStepRun
    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = (
            await s.execute(
                select(WorkflowStepRun, WorkflowStep.step_key)
                .join(WorkflowStep, WorkflowStep.id == WorkflowStepRun.workflow_step_id)
                .where(WorkflowStepRun.workflow_run_id == run_id)
            )
        ).all()
    return {key: sr for sr, key in rows}


async def _run(run_id: uuid.UUID):
    from life_graph.models.db import WorkflowRun
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(WorkflowRun, run_id)


async def _task(task_id: uuid.UUID):
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(AgentTask, task_id)


def _definition() -> dict:
    return {
        "name": f"build then test {uuid.uuid4().hex[:6]}",
        "steps": [
            {"step_key": "build", "agent_name": "scribe", "config": {"input": {"x": 1}}},
            {"step_key": "test", "agent_name": "scribe", "depends_on": ["build"]},
        ],
    }


@pytest.mark.asyncio
@skip_on_db_error
async def test_run_starts_root_step_as_an_agent_task():
    engine = _engine()
    wf = await engine.create_workflow(TENANT, _definition())
    run = await engine.start_run(wf.id, TENANT)

    steps = await _steps(run.id)
    assert steps["build"].status == "running", steps["build"].error
    assert steps["build"].agent_task_id is not None
    assert steps["test"].status == "pending"

    task = await _task(steps["build"].agent_task_id)
    assert task.tenant_id == TENANT
    assert task.agent_name == "scribe"
    assert task.priority == "normal"
    assert task.properties["step_key"] == "build"
    assert task.properties["input"] == {"x": 1}
    assert task.properties["workflow_run_id"] == str(run.id)


@pytest.mark.asyncio
@skip_on_db_error
async def test_complete_advances_then_completes_the_run():
    engine = _engine()
    wf = await engine.create_workflow(TENANT, _definition())
    run = await engine.start_run(wf.id, TENANT)

    await engine.on_step_completed(run.id, "build", TENANT, output={"ok": True})
    steps = await _steps(run.id)
    assert steps["build"].status == "completed"
    assert steps["build"].output == {"ok": True}
    assert steps["test"].status == "running"
    assert steps["test"].agent_task_id is not None

    await engine.on_step_completed(run.id, "test", TENANT, output={"passed": True})
    done = await _run(run.id)
    assert done.status == "completed"
    assert done.completed_at is not None
    assert done.output_summary == {
        "build": {"status": "completed", "output": {"ok": True}},
        "test": {"status": "completed", "output": {"passed": True}},
    }


@pytest.mark.asyncio
@skip_on_db_error
async def test_cancel_cancels_open_steps_and_keeps_the_reason():
    engine = _engine()
    wf = await engine.create_workflow(TENANT, _definition())
    run = await engine.start_run(wf.id, TENANT)
    await engine.on_step_completed(run.id, "build", TENANT, output={})

    await engine.cancel_run(run.id, TENANT, reason="owner stopped it")

    steps = await _steps(run.id)
    assert steps["build"].status == "completed"  # terminal steps are left alone
    assert steps["test"].status == "cancelled"
    assert steps["test"].error == "owner stopped it"
    cancelled = await _run(run.id)
    assert cancelled.status == "cancelled"
    assert (cancelled.properties or {}).get("error") == "owner stopped it"


@pytest.mark.asyncio
@skip_on_db_error
async def test_failed_step_aborts_the_run():
    engine = _engine()
    wf = await engine.create_workflow(TENANT, _definition())
    run = await engine.start_run(wf.id, TENANT)

    await engine.on_step_completed(run.id, "build", TENANT, status="failed", error="boom")

    steps = await _steps(run.id)
    assert steps["build"].status == "failed"
    assert steps["test"].status == "cancelled"
    failed = await _run(run.id)
    assert failed.status == "failed"
    assert "boom" in failed.properties["error"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_other_tenant_cannot_complete_or_cancel():
    engine = _engine()
    wf = await engine.create_workflow(TENANT, _definition())
    run = await engine.start_run(wf.id, TENANT)

    await engine.on_step_completed(run.id, "build", "someone-else", output={})
    await engine.cancel_run(run.id, "someone-else")

    steps = await _steps(run.id)
    assert steps["build"].status == "running"
    assert (await _run(run.id)).status == "running"
