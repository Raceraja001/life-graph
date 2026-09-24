"""Dev tasks: the dashboard's "do X in project Y" path.

The dispatcher is faked — these pin the task record, background run, status
and stage reporting, validation, restart recovery and WIP accounting around
it. The real dispatch pipeline has its own tests.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = f"dev_tasks_{uuid.uuid4().hex[:8]}"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "dev-task-test"}


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS
    ) as c:
        yield c


@pytest_asyncio.fixture
async def project(monkeypatch):
    from life_graph.api.dependencies import get_persona_service, get_project_registry
    from life_graph.config import settings

    monkeypatch.setattr(settings, "tool_fs_roots", str(Path.cwd()))
    await get_persona_service().seed_builtins(TENANT)
    return await get_project_registry().register(
        TENANT, {"name": f"proj-{uuid.uuid4().hex[:6]}", "path": str(Path.cwd())}
    )


@pytest.fixture
def fake_dispatch(monkeypatch):
    from life_graph.drivers.base import DriverResult
    from life_graph.drivers.dispatcher import TaskDispatcher

    calls = []

    async def dispatch_task(self, **kwargs):
        calls.append(kwargs)
        return DriverResult(
            success=True,
            output="Changed one line.",
            cost_usd=0.05,
            duration_ms=1200,
            metadata={"landed_branch": f"lg/task-{kwargs['task_id'][:8]}"},
        )

    monkeypatch.setattr(TaskDispatcher, "dispatch_task", dispatch_task)
    return calls


async def _drain():
    from life_graph.services import dev_tasks

    await asyncio.gather(*list(dev_tasks._background))


async def _start(client, project, instruction="Fix the typo in README", **extra):
    resp = await client.post(
        "/api/v1/kernel/drivers/tasks",
        json={"instruction": instruction, "project_id": project["id"], **extra},
    )
    return resp


@pytest.mark.asyncio
@skip_on_db_error
async def test_task_runs_in_background_and_reports_branch(client, project, fake_dispatch):
    resp = await _start(client, project)
    assert resp.status_code == 202, resp.text
    created = resp.json()["data"]
    assert created["status"] == "queued"
    assert created["persona"] == "code-fixer"

    await _drain()
    (call,) = fake_dispatch
    assert call["isolate_workdir"] is True
    assert call["interactive"] is True
    assert call["task_id"] == created["id"]

    got = (await client.get(f"/api/v1/kernel/drivers/tasks/{created['id']}")).json()["data"]
    assert got["status"] == "completed"
    assert got["stage"] == "landed"
    assert got["branch"] == f"lg/task-{created['id'][:8]}"
    assert got["cost_usd"] == 0.05
    assert got["verification"] == []

    listed = (await client.get("/api/v1/kernel/drivers/tasks")).json()["data"]
    assert listed[0]["id"] == created["id"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_stage_follows_pr_and_merge_approvals(client, project, fake_dispatch):
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    created = (await _start(client, project, "Add a helper")).json()["data"]
    await _drain()

    async with async_session() as s:
        s.add(
            Approval(
                tenant_id=TENANT,
                kind="driver_pr",
                title="Open PR",
                status="approved",
                source="driver",
                source_ref=created["id"],
                payload={"pr_url": "https://github.com/me/r/pull/5"},
            )
        )
        s.add(
            Approval(
                tenant_id=TENANT,
                kind="driver_merge",
                title="Merge PR #5",
                status="pending",
                source="driver_merge",
                source_ref=created["id"],
                payload={},
            )
        )
        await s.commit()

    got = (await client.get(f"/api/v1/kernel/drivers/tasks/{created['id']}")).json()["data"]
    assert got["stage"] == "awaiting_merge"
    assert got["pr_url"].endswith("/pull/5")


@pytest.mark.asyncio
@skip_on_db_error
async def test_failed_dispatch_is_recorded(client, project, monkeypatch):
    from life_graph.drivers.dispatcher import DispatchError, TaskDispatcher

    async def boom(self, **kwargs):
        raise DispatchError("Project WIP limit reached (2/2)")

    monkeypatch.setattr(TaskDispatcher, "dispatch_task", boom)
    created = (await _start(client, project, "Do something")).json()["data"]
    await _drain()
    got = (await client.get(f"/api/v1/kernel/drivers/tasks/{created['id']}")).json()["data"]
    assert (got["status"], got["stage"]) == ("failed", "failed")
    assert "WIP limit" in got["error"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_validation(client, project):
    bad_project = await client.post(
        "/api/v1/kernel/drivers/tasks",
        json={"instruction": "Do something", "project_id": str(uuid.uuid4())},
    )
    assert bad_project.status_code == 404
    no_driver = await _start(client, project, "Do something", persona_name="rex")
    assert no_driver.status_code == 400
    assert "no driver" in no_driver.json()["detail"]


# ── driver_stats: merge rate/timing per (persona, project) ──────


@pytest.mark.asyncio
@skip_on_db_error
async def test_stats_group_by_persona_and_project(client, project, fake_dispatch):
    """Answers "is this actually working" — one row per persona+project, not
    a task-by-task list someone has to read and tally by hand."""
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    merged = (await _start(client, project, "Fix the bug")).json()["data"]
    landed = (await _start(client, project, "Add a feature")).json()["data"]
    await _drain()

    async with async_session() as s:
        s.add(
            Approval(
                tenant_id=TENANT,
                kind="driver_merge",
                title="Merge PR",
                status="approved",
                source="driver_merge",
                source_ref=merged["id"],
                payload={},
            )
        )
        await s.commit()

    stats = (await client.get("/api/v1/kernel/drivers/tasks/stats")).json()["data"]
    row = next(r for r in stats if r["project_id"] == project["id"])
    assert row["persona"] == "code-fixer"
    assert row["total"] == 2
    assert row["merged"] == 1
    assert row["in_flight"] == 0
    assert row["merge_rate"] == pytest.approx(0.5)
    assert row["avg_duration_ms"] == 1200  # fake_dispatch's fixed duration
    assert row["avg_cost_usd"] == pytest.approx(0.05)
    assert landed["id"]  # the second task exists; just not merged


@pytest.mark.asyncio
@skip_on_db_error
async def test_stats_excludes_in_flight_tasks_from_merge_rate(client, project, fake_dispatch):
    """A task still queued/running hasn't succeeded OR failed yet — counting
    it against the merge rate would understate a driver that just has one
    slow task in flight, not a bad record."""
    await _start(client, project, "Still going")  # never drained: stays "queued"

    stats = (await client.get("/api/v1/kernel/drivers/tasks/stats")).json()["data"]
    row = next(r for r in stats if r["project_id"] == project["id"])
    assert row["total"] == 1
    assert row["in_flight"] == 1
    assert row["merge_rate"] is None  # nothing settled yet — not 0%, not 100%
    await _drain()  # let the background task finish before the fixture tears down


@pytest.mark.asyncio
@skip_on_db_error
async def test_restart_marks_abandoned_tasks_failed(project):
    from life_graph.models.db import AgentTask
    from life_graph.services import dev_tasks
    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = AgentTask(
            tenant_id=TENANT,
            agent_name=dev_tasks.AGENT_NAME,
            status="running",
            properties={"kind": dev_tasks.KIND},
        )
        s.add(row)
        await s.commit()
        row_id = row.id

    assert await dev_tasks.fail_interrupted(async_session) >= 1
    async with async_session() as s:
        row = await s.get(AgentTask, row_id)
        assert row.status == "failed"
        assert "restarted" in row.error


@pytest.mark.asyncio
@skip_on_db_error
async def test_wip_limit_does_not_count_the_task_itself(project):
    from life_graph.drivers.dispatcher import MAX_WIP_PER_PROJECT, DispatchError, TaskDispatcher
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    pid = uuid.UUID(project["id"])
    async with async_session() as s:
        rows = [
            AgentTask(tenant_id=TENANT, agent_name="x", status="running", project_id=pid)
            for _ in range(MAX_WIP_PER_PROJECT)
        ]
        s.add_all(rows)
        await s.commit()
        own = rows[-1].id

        dispatcher = TaskDispatcher(session_factory=async_session)
        with pytest.raises(DispatchError, match="WIP"):
            await dispatcher._check_wip_limits(TENANT, pid, s)
        # The dispatching task's own running row is not other work in progress.
        await dispatcher._check_wip_limits(TENANT, pid, s, exclude_task_id=str(own))
        for r in rows:
            await s.delete(r)
        await s.commit()


@pytest.mark.asyncio
@skip_on_db_error
async def test_verification_surfaces_the_failing_checks_evidence(project):
    """The detail behind a generic "Verification failed" error -- which
    verifier failed and why -- should be readable from the task itself,
    not require a hand-run query against VerificationRun."""
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.models.db import AgentTask
    from life_graph.services import dev_tasks
    from life_graph.services.verifiers import VerifierResult
    from life_graph.storage.database import async_session

    task_id = uuid.uuid4()
    async with async_session() as s:
        s.add(
            AgentTask(
                id=task_id,
                tenant_id=TENANT,
                agent_name=dev_tasks.AGENT_NAME,
                title="Fix the flaky test",
                instructions="Fix it",
                status="completed",
                properties={"kind": dev_tasks.KIND, "project_name": project["name"]},
            )
        )
        await s.commit()

        dispatcher = TaskDispatcher(session_factory=async_session)
        attempt1 = [VerifierResult("build_ok_diff", True, {"checked": 2})]
        attempt2 = [
            VerifierResult("build_ok_diff", True, {"checked": 2}),
            VerifierResult("tests_pass", False, {"stdout": "1 failed, 2 passed", "returncode": 1}),
        ]
        await dispatcher._record_verification(TENANT, str(task_id), 1, attempt1, s)
        await dispatcher._record_verification(TENANT, str(task_id), 2, attempt2, s)
        await s.commit()

        data = await dev_tasks.get_dev_task(s, TENANT, str(task_id))

    assert [r["attempt"] for r in data["verification"]] == [1, 2]
    assert data["verification"][0]["passed"] is True
    second = data["verification"][1]
    assert second["passed"] is False
    failing = next(r for r in second["results"] if not r["passed"])
    assert failing["verifier"] == "tests_pass"
    assert "1 failed" in failing["evidence"]["stdout"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_verification_is_empty_for_a_task_with_no_runs(project):
    from life_graph.models.db import AgentTask
    from life_graph.services import dev_tasks
    from life_graph.storage.database import async_session

    task_id = uuid.uuid4()
    async with async_session() as s:
        s.add(
            AgentTask(
                id=task_id,
                tenant_id=TENANT,
                agent_name=dev_tasks.AGENT_NAME,
                title="No verification yet",
                instructions="...",
                status="queued",
                properties={"kind": dev_tasks.KIND, "project_name": project["name"]},
            )
        )
        await s.commit()
        data = await dev_tasks.get_dev_task(s, TENANT, str(task_id))

    assert data["verification"] == []
