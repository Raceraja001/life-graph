"""The night shift report against the database: stages, the gate's reasons,
failure causes, the API and the brief section."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"night_{uuid.uuid4().hex[:8]}"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "night-test"}


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


async def _task(title, status, *, props=None, error=None, approvals=()):
    from life_graph.models.db import AgentTask, Approval
    from life_graph.storage.database import async_session

    now = datetime.now(UTC)
    async with async_session() as s:
        task = AgentTask(
            id=uuid.uuid4(),
            tenant_id=TENANT,
            agent_name="dev_task",
            task_name=title,
            title=title,
            instructions=title,
            task_type="code_change",
            assigned_agent="code-fixer-local",
            status=status,
            error=error,
            properties={"kind": "dev_task", "project_name": "life-graph", **(props or {})},
            completed_at=None if status == "queued" else now - timedelta(hours=2),
            result={},
        )
        s.add(task)
        for kind, appr_status, payload in approvals:
            s.add(
                Approval(
                    tenant_id=TENANT,
                    kind=kind,
                    title=f"{kind} {title}",
                    # Keyed as the real ones are: driver_pr by "driver",
                    # driver_merge by "driver_merge" (approvals.file_merge_approval).
                    source="driver_merge" if kind == "driver_merge" else "driver",
                    source_ref=str(task.id),
                    status=appr_status,
                    resolved_at=now - timedelta(hours=1) if appr_status != "pending" else None,
                    payload={"task_id": str(task.id), "driver": "local", **payload},
                )
            )
        await s.commit()
        return str(task.id)


@pytest.mark.asyncio
@skip_on_db_error
async def test_report_api_and_brief(client):
    from life_graph.services import night_shift
    from life_graph.storage.database import async_session

    pr = "https://github.com/o/r/pull/9"
    await _task(
        "Write unit tests, in a new file tests/unit/test_a.py, for `fa` in life_graph/services/a.py",
        "completed",
        approvals=[
            ("driver_pr", "approved", {"pr_url": pr}),
            ("driver_merge", "approved", {"pr_url": pr, "merge_commit": "c" * 40}),
        ],
    )
    await _task(
        "Bump a dependency",
        "completed",
        approvals=[
            (
                "driver_pr",
                "pending",
                {
                    "change": {
                        "files": ["uv.lock"],
                        "lines": 4,
                        "kind": "code",
                        "protected": ["uv.lock"],
                        "review_reasons": ["touches protected paths: uv.lock"],
                    }
                },
            )
        ],
    )
    await _task(
        "Write unit tests, in a new file tests/unit/test_b.py, for `fb` in life_graph/services/b.py",
        "failed",
        error="ran out of tool rounds",
        props={"origin": "nightly", "escalated_to": "code-fixer-opencode"},
    )
    await _task("Fix later", "queued", props={"run_mode": "queue"})

    async with async_session() as s:
        rep = await night_shift.report(s, TENANT)
    assert [t["title"] for t in rep["merged"]] == ["tests for fa (services/a.py)"]
    assert rep["merged"][0]["pr_url"] == pr
    (waiting,) = rep["waiting"]
    assert waiting["reason"].startswith("needs review: touches protected paths: uv.lock")
    assert "no proof checks ran" in waiting["reason"]  # every reason the gate gave
    (failed,) = rep["failed"]
    assert failed["reason"].endswith("handed to OpenCode")
    assert rep["queued"] == 1

    api = await client.get("/api/v1/kernel/drivers/night-shift?hours=24")
    assert api.status_code == 200
    data = api.json()["data"]
    assert data["lines"][0] == "1 merged, 1 waiting for you, 1 failed, 1 queued"

    from life_graph.core.events import event_bus
    from life_graph.services.brief import BriefComposer

    composer = BriefComposer(async_session, event_bus)
    shift = await composer._night_shift_lines(TENANT, datetime.now(UTC) - timedelta(hours=24))
    assert shift == data["lines"]
