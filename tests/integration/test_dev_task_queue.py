"""Queued dev tasks: nightly queueing rules, claiming, restart and running."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"dev_queue_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def project(monkeypatch):
    from life_graph.api.dependencies import get_persona_service, get_project_registry
    from life_graph.config import settings

    monkeypatch.setattr(settings, "tool_fs_roots", str(Path.cwd()))
    await get_persona_service().seed_builtins(TENANT)
    proj = await get_project_registry().register(
        TENANT,
        {"name": f"proj-{uuid.uuid4().hex[:6]}", "path": str(Path.cwd())},
    )
    proj["scan_metadata"] = {"nightly_max_tasks": 2}
    return proj


def _finding(i):
    from life_graph.services.dev_suggestions import Finding

    return Finding(
        kind="todo", key=f"k{i}-{uuid.uuid4().hex[:6]}", title=f"t{i}", instruction=f"Fix item {i}"
    )


async def _tasks(project_id):
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return (
            (
                await s.execute(
                    select(AgentTask)
                    .where(
                        AgentTask.tenant_id == TENANT, AgentTask.project_id == uuid.UUID(project_id)
                    )
                    .order_by(AgentTask.created_at)
                )
            )
            .scalars()
            .all()
        )


@pytest.mark.asyncio
@skip_on_db_error
async def test_queue_respects_cap_seen_keys_and_open_tasks(project):
    from life_graph.services.dev_suggestions import queue_suggestions
    from life_graph.storage.database import async_session

    findings = [_finding(i) for i in range(4)]
    first = await queue_suggestions(async_session, TENANT, project, findings)
    assert first["queued"] == 2
    rows = await _tasks(project["id"])
    assert all(r.status == "queued" for r in rows)
    assert all(
        r.properties["run_mode"] == "queue" and r.properties["origin"] == "nightly" for r in rows
    )
    assert all(r.assigned_agent == "code-fixer-local" for r in rows)

    # Two nightly tasks still open: nothing more tonight, even with new findings.
    second = await queue_suggestions(async_session, TENANT, project, findings + [_finding(9)])
    assert (second["queued"], second["open_before"]) == (0, 2)


@pytest.mark.asyncio
@skip_on_db_error
async def test_same_finding_is_not_suggested_twice(project):
    from life_graph.services.dev_suggestions import queue_suggestions
    from life_graph.storage.database import async_session

    f = _finding(1)
    await queue_suggestions(async_session, TENANT, project, [f])
    for r in await _tasks(project["id"]):  # settle it, freeing the cap
        async with async_session() as s:
            row = await s.get(type(r), r.id)
            row.status = "failed"
            await s.commit()
    again = await queue_suggestions(async_session, TENANT, project, [f])
    assert again["queued"] == 0


@pytest.mark.asyncio
@skip_on_db_error
async def test_claim_restart_and_run(project, monkeypatch):
    from life_graph.drivers.base import DriverResult
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.models.db import AgentTask
    from life_graph.services import dev_tasks
    from life_graph.storage.database import async_session

    queued = await dev_tasks.create_dev_task(
        async_session,
        TENANT,
        instruction="Fix item A",
        project=project,
        persona_name="code-fixer-local",
        start=False,
        properties={"origin": "nightly"},
    )
    # An immediate-mode task left queued by a crashed process is re-queued
    # into queue mode (it runs once more instead of failing)...
    async with async_session() as s:
        stale = AgentTask(
            tenant_id=TENANT,
            agent_name=dev_tasks.AGENT_NAME,
            status="queued",
            project_id=uuid.UUID(project["id"]),
            properties={"kind": dev_tasks.KIND},
        )
        s.add(stale)
        await s.commit()
        stale_id = stale.id
    await dev_tasks.fail_interrupted(async_session)
    async with async_session() as s:
        stale_row = await s.get(AgentTask, stale_id)
        assert stale_row.status == "queued"
        assert stale_row.properties["run_mode"] == dev_tasks.QUEUE_MODE
        # ...but a queue-mode task is still waiting its turn.
        assert (await s.get(AgentTask, uuid.UUID(queued["id"]))).status == "queued"

    calls = []

    async def fake_dispatch(self, **kw):
        calls.append(kw)
        return DriverResult(success=True, output="fixed")

    monkeypatch.setattr(TaskDispatcher, "dispatch_task", fake_dispatch)

    claimed = await dev_tasks.claim_next_queued(async_session)
    while claimed is not None and str(claimed.id) != queued["id"]:  # other tenants' rows
        claimed = await dev_tasks.claim_next_queued(async_session)
    assert claimed is not None and claimed.status == "running"
    await dev_tasks._run(
        async_session,
        claimed.tenant_id,
        str(claimed.id),
        claimed.instructions,
        str(claimed.project_id),
        claimed.assigned_agent,
        claimed.task_type,
        interactive=False,
    )
    (call,) = calls
    assert call["interactive"] is False  # unattended work is budget-governed
    assert call["persona_name"] == "code-fixer-local"
    async with async_session() as s:
        assert (await s.get(AgentTask, claimed.id)).status == "completed"


async def test_a_started_task_requeued_by_a_restart_stays_interactive(project, monkeypatch):
    """A task someone started keeps that status when an API restart re-queues
    it: task eda04c34 (2026-10-17) was re-queued, run as unattended work and
    denied by the budget. Unattended (nightly) work stays budget-governed."""
    from life_graph.drivers.base import DriverResult
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.models.db import AgentTask
    from life_graph.services import dev_tasks
    from life_graph.storage.database import async_session

    async def not_now(*_a, **_k):  # the restart happens before it runs
        return None

    real_run = dev_tasks._run
    monkeypatch.setattr(dev_tasks, "_run", not_now)
    started = await dev_tasks.create_dev_task(
        async_session,
        TENANT,
        instruction="Fix item B",
        project=project,
        persona_name="code-fixer-opencode",
    )
    nightly = await dev_tasks.create_dev_task(
        async_session,
        TENANT,
        instruction="Fix item C",
        project=project,
        persona_name="code-fixer-local",
        start=False,
        properties={"origin": "nightly"},
    )
    async with async_session() as s:
        row = await s.get(AgentTask, uuid.UUID(started["id"]))
        row.status = "running"  # it was mid-run when the API went down
        await s.commit()
    await dev_tasks.fail_interrupted(async_session)
    monkeypatch.setattr(dev_tasks, "_run", real_run)

    calls = {}

    async def fake_dispatch(self, **kw):
        calls[kw["task_id"]] = kw["interactive"]
        return DriverResult(success=True, output="fixed")

    monkeypatch.setattr(TaskDispatcher, "dispatch_task", fake_dispatch)
    wanted = {started["id"], nightly["id"]}
    while wanted - calls.keys():
        claimed = await dev_tasks.claim_next_queued(async_session)
        assert claimed is not None
        if str(claimed.id) in wanted:
            await dev_tasks.run_claimed(async_session, claimed)
    assert calls[started["id"]] is True
    assert calls[nightly["id"]] is False


async def test_a_queued_plan_still_runs_as_a_plan(project, monkeypatch):
    """POST /tasks with queue=true hands work to the queue runner; a queued
    plan must keep its spec_first and its no_diff_in_plan check."""
    from life_graph.drivers.base import DriverResult
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.services import dev_tasks
    from life_graph.storage.database import async_session

    queued = await dev_tasks.create_dev_task(
        async_session,
        TENANT,
        instruction="Plan item D",
        project=project,
        persona_name="code-fixer-local",
        task_type="plan",
        start=False,
        spec_first=True,
        verify_chain=["no_diff_in_plan"],
    )
    calls = {}

    async def fake_dispatch(self, **kw):
        calls[kw["task_id"]] = kw
        return DriverResult(success=True, output="## Spec\n...")

    monkeypatch.setattr(TaskDispatcher, "dispatch_task", fake_dispatch)
    while queued["id"] not in calls:
        claimed = await dev_tasks.claim_next_queued(async_session)
        assert claimed is not None
        if str(claimed.id) == queued["id"]:
            await dev_tasks.run_claimed(async_session, claimed)
    kw = calls[queued["id"]]
    assert kw["spec_first"] is True
    assert kw["verify_chain"] == ["no_diff_in_plan"]
    assert kw["task_type"] == "plan"
    assert kw["interactive"] is False


async def _claim_ours(task_id):
    """Claim until our task comes up or nothing more is runnable."""
    from life_graph.services import dev_tasks
    from life_graph.storage.database import async_session

    for _ in range(200):
        claimed = await dev_tasks.claim_next_queued(async_session)
        if claimed is None or str(claimed.id) == task_id:
            return claimed
    return None


async def test_while_the_user_is_active_a_nightly_task_goes_to_the_cloud(project, monkeypatch):
    from life_graph.drivers.base import DriverResult
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.models.db import AgentTask
    from life_graph.services import compute_router, dev_tasks
    from life_graph.storage.database import async_session

    async def active(_factory, _tenant):
        return compute_router.Snapshot(
            active="voice 2 min ago", local_hours=True, free_gb=30.0, cloud=("openrouter/m:free",)
        )

    monkeypatch.setattr(compute_router, "snapshot", active)
    queued = await dev_tasks.create_dev_task(
        async_session,
        TENANT,
        instruction="Fix item E",
        project=project,
        persona_name="code-fixer-local",
        start=False,
        properties={"origin": "nightly"},
    )
    claimed = await _claim_ours(queued["id"])
    assert claimed is not None
    assert claimed.assigned_agent == compute_router.CLOUD_PERSONA
    assert claimed.properties["route"] == "cloud"
    assert claimed.properties["routed_from"] == "code-fixer-local"
    assert "voice 2 min ago" in claimed.status_history[-1]["note"]

    async def rate_limited(self, **kw):
        assert kw["persona_name"] == compute_router.CLOUD_PERSONA
        return DriverResult(
            success=False,
            error="All models are currently unavailable. Please try again shortly.",
            metadata={"stop_reason": "error"},
        )

    benched = []

    async def cool(seconds=None):
        benched.append(seconds)

    monkeypatch.setattr(TaskDispatcher, "dispatch_task", rate_limited)
    monkeypatch.setattr(compute_router, "cool_cloud_route", cool)
    await dev_tasks.run_claimed(async_session, claimed)
    async with async_session() as s:
        row = await s.get(AgentTask, claimed.id)
        assert row.status == "queued"  # back for the GPU, not failed
        assert row.assigned_agent == "code-fixer-local"
        assert row.properties["cloud_requeues"] == 1
        row.status = "cancelled"  # don't leave it for later tests' claims
        await s.commit()
    assert benched == [None]


async def test_while_the_user_is_active_without_a_cloud_model_it_waits(project, monkeypatch):
    from life_graph.models.db import AgentTask
    from life_graph.services import compute_router, dev_tasks
    from life_graph.storage.database import async_session

    async def active(_factory, _tenant):
        return compute_router.Snapshot(
            active="switch says active", local_hours=True, free_gb=30.0, cloud=()
        )

    monkeypatch.setattr(compute_router, "snapshot", active)
    queued = await dev_tasks.create_dev_task(
        async_session,
        TENANT,
        instruction="Fix item F",
        project=project,
        persona_name="code-fixer-local",
        start=False,
        properties={"origin": "nightly"},
    )
    assert await _claim_ours(queued["id"]) is None
    async with async_session() as s:
        row = await s.get(AgentTask, uuid.UUID(queued["id"]))
        assert (row.status, row.assigned_agent) == ("queued", "code-fixer-local")
        # Settle it so later tests' claims aren't held up by it.
        row.status = "cancelled"
        await s.commit()
