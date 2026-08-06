"""Unit tests for AutoFixService.execute_pending — the execute-on-approval gap.

Today, approving an autonomy approval flips the linked AutoAction to
status="pending" and nothing runs it. execute_pending is the missing public
method that actually executes an approved/pending AutoAction by id, reusing
the same run+persist+audit+emit core (_run_action) as the classify-time
auto-execute path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.dml import Update

from life_graph.autonomy.pipeline.executor import ExecutionResult
from life_graph.autonomy.pipeline.service import AutoFixService


class _FakeResult:
    """Stand-in for a SQLAlchemy Result — both scalar accessors return the action."""

    def __init__(self, action):
        self._action = action

    def scalar_one_or_none(self):
        return self._action

    def scalar_one(self):
        return self._action


class _FakeSession:
    """Async-context-manager session whose .execute() always resolves to the action."""

    def __init__(self, action):
        self._action = action

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, stmt):
        # Mimic the real UPDATE's effect on the row so status/exit_code/etc.
        # assertions can observe what _run_action persisted.
        if isinstance(stmt, Update):
            for key, value in stmt.compile().params.items():
                if hasattr(self._action, key):
                    setattr(self._action, key, value)
        return _FakeResult(self._action)

    async def commit(self):
        pass


def _make_service(action):
    """Build a bare AutoFixService with just the collaborators execute_pending needs."""
    svc = AutoFixService.__new__(AutoFixService)
    svc._session_factory = lambda: _FakeSession(action)
    svc._executor = MagicMock()
    svc._executor.execute = AsyncMock(
        return_value=ExecutionResult(exit_code=0, stdout="ok", stderr="", duration_ms=12.0)
    )
    svc._audit_service = AsyncMock()
    svc._level_service = None
    svc._project_locks = {}
    return svc


def _fake_pending_action():
    return MagicMock(
        id="a1",
        tenant_id="t1",
        status="pending",
        action_command="echo hi",
        action_name="restart",
        rollback_command=None,
        trigger_type="manual",
        trigger_detail="restart",
        project_id="ambient",
        agent_id="ops",
        risk_level="moderate",
        approval_id=None,
        started_at=None,
        completed_at=None,
        created_at=datetime.now(UTC),
        exit_code=None,
        stdout=None,
        stderr=None,
        error_message=None,
        duration_ms=None,
    )


@pytest.mark.asyncio
async def test_execute_pending_runs_command_and_marks_success():
    action = _fake_pending_action()
    svc = _make_service(action)

    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock()
        resp = await svc.execute_pending("t1", "a1")

    svc._executor.execute.assert_awaited_once()
    assert action.status == "success"
    assert action.exit_code == 0
    svc._audit_service.log_auto_execute.assert_awaited_once()
    bus.emit.assert_awaited()  # AUTONOMOUS_ACTION_COMPLETED
    assert resp.status == "success"
    assert resp.id == "a1"


@pytest.mark.asyncio
async def test_execute_pending_marks_failure_on_nonzero_exit():
    action = _fake_pending_action()
    svc = _make_service(action)
    svc._executor.execute = AsyncMock(
        return_value=ExecutionResult(exit_code=1, stdout="", stderr="boom", duration_ms=5.0)
    )

    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock()
        resp = await svc.execute_pending("t1", "a1")

    assert action.status == "failure"
    assert resp.status == "failure"


@pytest.mark.asyncio
async def test_execute_pending_raises_when_action_not_found():
    svc = _make_service(None)

    with pytest.raises(ValueError, match="not found"):
        await svc.execute_pending("t1", "missing")

    svc._executor.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_pending_raises_when_status_not_pending():
    action = _fake_pending_action()
    action.status = "success"
    svc = _make_service(action)

    with pytest.raises(ValueError, match="status"):
        await svc.execute_pending("t1", "a1")

    svc._executor.execute.assert_not_awaited()
