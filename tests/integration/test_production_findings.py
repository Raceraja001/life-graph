"""Production failures become fix tasks, once: the post-deploy smoke check
(with rollback) and the monitor endpoint's service, against real rows.
"""

from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import skip_on_db_error


@pytest.fixture
def tenant():
    return f"prod_{uuid.uuid4().hex[:8]}"


async def _project(tenant, tmp_path, **meta):
    from life_graph.models.db import Project
    from life_graph.storage.database import async_session

    pid = uuid.uuid4()
    async with async_session() as s:
        s.add(
            Project(
                id=pid,
                tenant_id=tenant,
                name=f"app-{pid.hex[:6]}",
                path=str(tmp_path),
                scan_metadata=meta,
            )
        )
        await s.commit()
    return pid


async def _tasks(tenant):
    from sqlalchemy import select

    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return (
            (await s.execute(select(AgentTask).where(AgentTask.tenant_id == tenant)))
            .scalars()
            .all()
        )


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_reported_failure_queues_one_fix_task_and_dedupes_the_repeat(tenant, tmp_path):
    from life_graph.services.production_findings import file_fix_task
    from life_graph.storage.database import async_session

    pid = await _project(tenant, tmp_path, fix_persona="code-fixer-opencode")
    project = {
        "id": str(pid),
        "name": "app",
        "path": str(tmp_path),
        "scan_metadata": {"fix_persona": "code-fixer-opencode"},
    }

    first = await file_fix_task(
        async_session,
        tenant,
        project,
        kind="uptime",
        title="GET /api/todos returns 500",
        detail="HTTP 500",
    )
    again = await file_fix_task(
        async_session,
        tenant,
        project,
        kind="uptime",
        title="GET /api/todos returns 500",
        detail="HTTP 500 again",
    )

    assert "queued" in first and again == {
        "deduplicated": first["queued"],
        "finding_key": first["finding_key"],
    }
    (task,) = await _tasks(tenant)
    assert task.status == "queued"
    assert task.assigned_agent == "code-fixer-opencode"
    assert task.properties["origin"] == "production"
    assert task.properties["run_mode"] == "queue"
    assert "returns 500" in task.instructions and "test that would" in task.instructions


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_failing_smoke_check_rolls_back_and_files_a_fix(tenant, tmp_path):
    from life_graph.models.db import Approval
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    pid = await _project(tenant, tmp_path)
    async with async_session() as s:
        appr = Approval(
            tenant_id=tenant,
            kind="driver_deploy",
            title="Deploy app @ abc12345",
            status="pending",
            source="driver_deploy",
            source_ref=str(uuid.uuid4()),
            payload={
                "project_id": str(pid),
                "repo_path": str(tmp_path),
                "merge_commit": "abc12345",
                "deploy_command": "echo deployed > deployed.txt",
                "smoke_command": "echo smoke broke; exit 3",
                "rollback_command": "rm deployed.txt && echo rolled",
            },
        )
        s.add(appr)
        await s.commit()
        appr_id = str(appr.id)

    from life_graph.tools._guards import confine_to

    # Deploy commands only run inside the permitted project roots.
    async with async_session() as s:
        with confine_to(tmp_path):
            await ApprovalService(s).resolve(tenant, appr_id, "approve", resolved_by="test")
        await s.commit()
        done = await s.get(Approval, uuid.UUID(appr_id))

    assert done.status == "approved"
    assert done.payload["smoke"]["exit"] == 3
    assert done.payload["rollback"]["exit"] == 0
    assert not (tmp_path / "deployed.txt").exists()  # rolled back
    assert "smoke check FAILED (exit 3); rolled back; fix task" in done.resolution_note
    (task,) = await _tasks(tenant)
    assert task.properties["finding_kind"] == "post_deploy_smoke"
    assert "smoke broke" in task.instructions
