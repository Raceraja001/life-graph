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


@pytest.fixture(autouse=True)
def _autonomy_not_paused():
    """These tests exercise real execution, not the kill-switch itself
    (see test_kill_switch.py) -- keep _run_action's guard a no-op here."""
    with patch(
        "life_graph.autonomy.kill_switch.is_autonomy_paused", AsyncMock(return_value=False)
    ):
        yield


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


def _make_service(action, level_service=None):
    """Build a bare AutoFixService with just the collaborators execute_pending needs."""
    svc = AutoFixService.__new__(AutoFixService)
    svc._session_factory = lambda: _FakeSession(action)
    svc._executor = MagicMock()
    svc._executor.execute = AsyncMock(
        return_value=ExecutionResult(exit_code=0, stdout="ok", stderr="", duration_ms=12.0)
    )
    svc._audit_service = AsyncMock()
    svc._level_service = level_service
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


@pytest.mark.asyncio
async def test_execute_pending_records_level_action_on_success():
    """L0 projects queue every action, so execute_pending is the ONLY path that
    runs an L0 project's approved actions. Without a record_action call here,
    an L0 project's safe_count can never reach the L1 promotion threshold and
    nothing ever becomes auto-executable."""
    action = _fake_pending_action()
    level_service = AsyncMock()
    svc = _make_service(action, level_service=level_service)

    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock()
        await svc.execute_pending("t1", "a1")

    level_service.record_action.assert_awaited_once_with(
        "t1", "ambient", "moderate", True,
    )


@pytest.mark.asyncio
async def test_execute_pending_records_level_action_on_failure():
    action = _fake_pending_action()
    level_service = AsyncMock()
    svc = _make_service(action, level_service=level_service)
    svc._executor.execute = AsyncMock(
        return_value=ExecutionResult(exit_code=1, stdout="", stderr="boom", duration_ms=5.0)
    )

    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock()
        await svc.execute_pending("t1", "a1")

    level_service.record_action.assert_awaited_once_with(
        "t1", "ambient", "moderate", False,
    )


@pytest.mark.asyncio
async def test_execute_pending_skips_level_service_when_absent():
    """No level_service injected (e.g. some deployments) must not raise."""
    action = _fake_pending_action()
    svc = _make_service(action, level_service=None)

    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock()
        resp = await svc.execute_pending("t1", "a1")

    assert resp.status == "success"


@pytest.mark.asyncio
async def test_execute_pending_emits_completed_after_record_action():
    """The AUTONOMOUS_ACTION_COMPLETED emit must observably happen AFTER
    record_action — matching _auto_execute's pre-refactor ordering (the
    refactor must not silently reorder side effects observers rely on)."""
    action = _fake_pending_action()
    level_service = AsyncMock()
    call_order = []
    level_service.record_action = AsyncMock(
        side_effect=lambda *a, **kw: call_order.append("record_action")
    )
    svc = _make_service(action, level_service=level_service)

    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock(side_effect=lambda *a, **kw: call_order.append("emit"))
        await svc.execute_pending("t1", "a1")

    assert call_order == ["record_action", "emit"]


@pytest.mark.asyncio
async def test_auto_execute_emits_completed_after_record_action():
    """Same ordering guarantee for the classify-time route, to prove the
    _run_action extraction didn't change _auto_execute's observable order."""
    from life_graph.autonomy.pipeline.service import AutoFixService as _Svc

    action = _fake_pending_action()
    level_service = AsyncMock()
    call_order = []
    level_service.record_action = AsyncMock(
        side_effect=lambda *a, **kw: call_order.append("record_action")
    )
    svc = _make_service(action, level_service=level_service)

    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock(side_effect=lambda *a, **kw: call_order.append("emit"))
        await _Svc._auto_execute(svc, "t1", action, rule=None, timeout_seconds=60)

    assert call_order == ["record_action", "emit"]
