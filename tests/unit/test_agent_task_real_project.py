"""_run_action's agent_task branch must resolve a real Project (by the
well-known AMBIENT_REPO_PROJECT_NAME) and pass ITS uuid to dispatch_task —
while auto_action.project_id (the DB column, "ambient") never changes.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.selectable import Select

from life_graph.autonomy.pipeline.service import AutoFixService
from life_graph.drivers.base import DriverResult


class _FakeResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one(self):
        return self._obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeSession:
    def __init__(self, box, project_id=None):
        self._box = box
        self._project_id = project_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def commit(self):
        pass

    async def execute(self, stmt):
        if isinstance(stmt, Update):
            action = self._box["action"]
            for key, value in stmt.compile().params.items():
                if hasattr(action, key):
                    setattr(action, key, value)
            return _FakeResult(action)
        if isinstance(stmt, Select):
            return _FakeResult(self._project_id)
        return _FakeResult(None)


def make_auto_action(*, project_id: str = "ambient"):
    return MagicMock(
        id="a1", tenant_id="t1", kind="agent_task",
        instruction="fix the flaky test", action_command=None,
        action_name="cody_fix", agent_id="cody", project_id=project_id,
        risk_level="moderate",
    )


@pytest.mark.asyncio
async def test_resolve_repo_project_id_returns_none_when_unregistered():
    box = {"action": make_auto_action()}
    svc = AutoFixService(
        session_factory=lambda: _FakeSession(box, project_id=None),
        audit_service=MagicMock(log_auto_execute=AsyncMock()),
        approval_service=MagicMock(),
    )

    result = await svc._resolve_repo_project_id("t1")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_repo_project_id_returns_the_real_uuid_when_registered():
    real_id = uuid.uuid4()
    box = {"action": make_auto_action()}
    svc = AutoFixService(
        session_factory=lambda: _FakeSession(box, project_id=real_id),
        audit_service=MagicMock(log_auto_execute=AsyncMock()),
        approval_service=MagicMock(),
    )

    result = await svc._resolve_repo_project_id("t1")

    assert result == str(real_id)


@pytest.mark.asyncio
async def test_run_action_agent_task_passes_real_project_and_isolation_to_dispatch(monkeypatch):
    real_id = uuid.uuid4()
    box = {"action": make_auto_action(project_id="ambient")}
    dispatcher = MagicMock()
    dispatcher.dispatch_task = AsyncMock(
        return_value=DriverResult(success=True, output="done", cost_usd=0.1)
    )
    svc = AutoFixService(
        session_factory=lambda: _FakeSession(box, project_id=real_id),
        audit_service=MagicMock(log_auto_execute=AsyncMock()),
        approval_service=MagicMock(),
        dispatcher=dispatcher,
    )

    await svc._run_action("t1", box["action"], timeout_seconds=60)

    kwargs = dispatcher.dispatch_task.call_args.kwargs
    assert kwargs["project_id"] == str(real_id)
    assert kwargs["isolate_workdir"] is True
    assert kwargs["verify_chain"] == ["build_ok_diff", "lint_clean_diff"]
    # the AutoAction's OWN project_id column is untouched
    assert box["action"].project_id == "ambient"
