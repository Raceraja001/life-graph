"""GET /workflows/{id}/runs/{run_id} reads the real step-run columns.

Found by mypy (audit M11): the route filtered on ``WorkflowStepRun.run_id``
and read ``sr.step_key`` / ``sr.task_id`` / ``run.error``, none of which exist
on the models (the columns are ``workflow_run_id``, ``agent_task_id``, and the
step key lives on ``WorkflowStep``). Building the query raised AttributeError,
so the endpoint answered 500 for every run that existed.

No database: the session is faked, and the step query it receives is compiled
for PostgreSQL so the test still checks what SQL would run.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

import life_graph.storage.database as database
from life_graph.api import agent_workflows
from life_graph.core.tenant import tenant_scope

TENANT = "test-workflow-run-detail"


class _Result:
    def __init__(self, *, one: Any = None, rows: list[Any] | None = None) -> None:
        self._one = one
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._one

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(self, results: list[_Result]) -> None:
        self._results = list(results)
        self.statements: list[Any] = []

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def execute(self, stmt: Any) -> _Result:
        self.statements.append(stmt)
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_get_run_returns_steps_from_the_real_columns(monkeypatch):
    workflow_id, run_id, task_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    started = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
    run = SimpleNamespace(
        id=run_id,
        workflow_id=workflow_id,
        status="failed",
        trigger="manual",
        triggered_by="owner",
        input_params={"x": 1},
        output_summary=None,
        properties={"error": "step lint failed"},
        started_at=started,
        completed_at=None,
    )
    step_run = SimpleNamespace(
        id=uuid.uuid4(),
        status="failed",
        output=None,
        error="boom",
        agent_task_id=task_id,
        started_at=started,
        completed_at=None,
    )
    session = _FakeSession([_Result(one=run), _Result(rows=[(step_run, "lint")])])
    monkeypatch.setattr(database, "async_session", lambda: session)

    with tenant_scope(TENANT):
        response = await agent_workflows.get_run(workflow_id, run_id, engine=None)

    data = response["data"]
    assert data["id"] == str(run_id)
    assert data["error"] == "step lint failed"
    assert data["steps"] == [
        {
            "id": str(step_run.id),
            "step_key": "lint",
            "status": "failed",
            "output": None,
            "error": "boom",
            "task_id": str(task_id),
            "started_at": started.isoformat(),
            "completed_at": None,
        }
    ]

    step_sql = str(session.statements[1].compile(dialect=postgresql.dialect()))
    assert "workflow_step_runs.workflow_run_id = " in step_sql
    assert "JOIN workflow_steps ON workflow_steps.id = workflow_step_runs.workflow_step_id" in (
        step_sql
    )
