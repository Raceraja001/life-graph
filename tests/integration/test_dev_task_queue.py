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
    # An immediate-mode task left queued by a crashed process is abandoned...
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
        assert (await s.get(AgentTask, stale_id)).status == "failed"
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
