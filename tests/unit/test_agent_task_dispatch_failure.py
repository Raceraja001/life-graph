"""Unit tests for Phase B2 Task 4: dispatch-failure robustness.

Unlike ``CommandExecutor`` (which never raises), ``TaskDispatcher.
dispatch_task`` CAN raise — a ``DispatchError`` on a WIP-limit hit, or any
other driver/orchestrator error. This must not propagate out of
``_run_action`` (or, via ``execute_pending``, out to the unified-feed
approval flow in ``services/approvals.py::_apply_autonomous_action``) —
it must instead land as an ordinary ``status="failure"`` ``AutoAction`` row
with ``error_message`` set, going through the exact same persist/
``_emit_completed`` path as any other failure.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.dml import Update

from life_graph.autonomy.pipeline.schemas import AutoActionResponse
from life_graph.autonomy.pipeline.service import AutoFixService
from life_graph.drivers.dispatcher import DispatchError
from life_graph.models.db import Approval
from life_graph.services.approvals import ApprovalService


class _FakeResult:
    """Stand-in for a SQLAlchemy Result — both scalar accessors return the row."""

    def __init__(self, obj):
        self._obj = obj

    def scalar_one(self):
        return self._obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeSession:
    """Async-context-manager session backed by a single-row box.

    Mirrors ``tests/unit/test_agent_task_execution.py``'s ``_FakeSession``:
    each test in this module only ever touches one ``AutoAction``, so WHERE
    clauses are ignored — UPDATE statements apply to (and SELECTs return)
    whatever row is currently in the box.
    """

    def __init__(self, box):
        self._box = box

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def commit(self):
        pass

    async def execute(self, stmt):
        action = self._box["action"]
        if isinstance(stmt, Update):
            for key, value in stmt.compile().params.items():
                if hasattr(action, key):
                    setattr(action, key, value)
        return _FakeResult(action)


def make_auto_action(
    *,
    kind: str = "agent_task",
    instruction: str | None = "X",
    action_command: str | None = None,
    agent_id: str = "cody",
    project_id: str = "ambient",
):
    """Build a bare object with the attributes ``_run_action`` reads/writes."""
    return MagicMock(
        id="a1",
        tenant_id="t1",
        kind=kind,
        instruction=instruction,
        action_command=action_command,
        action_name="cody_fix" if kind == "agent_task" else "restart",
        agent_id=agent_id,
        project_id=project_id,
        risk_level="moderate",
        started_at=None,
        completed_at=None,
        exit_code=None,
        stdout=None,
        stderr=None,
        error_message=None,
        duration_ms=None,
        status="pending",
    )


@pytest.fixture
def agent_task_service_raising():
    """``AutoFixService`` wired to a dispatcher whose ``dispatch_task`` raises
    ``DispatchError`` (e.g. a WIP-limit hit)."""
    box: dict = {"action": None}
    session = _FakeSession(box)

    disp = MagicMock()
    disp.dispatch_task = AsyncMock(side_effect=DispatchError("wip limit exceeded"))

    svc = AutoFixService.__new__(AutoFixService)
    svc._session_factory = lambda: session
    svc._executor = MagicMock()
    svc._audit_service = AsyncMock()
    svc._level_service = None
    svc._project_locks = {}
    svc._dispatcher = disp

    real_run_action = AutoFixService._run_action

    async def _run_action_seeding(self, tenant_id, auto_action, timeout_seconds=60):
        box["action"] = auto_action
        return await real_run_action(self, tenant_id, auto_action, timeout_seconds)

    svc._run_action = _run_action_seeding.__get__(svc, AutoFixService)

    return svc, disp


@pytest.fixture
def agent_task_execute_pending_raising():
    """``AutoFixService.execute_pending`` on an approved agent_task action
    whose dispatch raises — must return a failure response, not raise."""
    action = make_auto_action()
    action.id = "auto-1"
    action.status = "pending"
    action.approval_id = None
    action.rollback_command = None
    action.trigger_type = "manual"
    action.trigger_detail = "cody_fix"
    action.created_at = datetime.now(UTC)
    box = {"action": action}
    session = _FakeSession(box)

    disp = MagicMock()
    disp.dispatch_task = AsyncMock(side_effect=DispatchError("wip limit exceeded"))

    svc = AutoFixService.__new__(AutoFixService)
    svc._session_factory = lambda: session
    svc._executor = MagicMock()
    svc._audit_service = AsyncMock()
    svc._level_service = None
    svc._project_locks = {}
    svc._dispatcher = disp

    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock()
        yield svc


@pytest.mark.asyncio
async def test_dispatch_raise_marks_failed_not_wedged(agent_task_service_raising):
    svc, disp = agent_task_service_raising  # disp.dispatch_task raises DispatchError("wip limit")
    auto = make_auto_action(kind="agent_task", instruction="X", action_command=None, agent_id="cody")
    # must NOT raise out of _run_action
    await svc._run_action("t1", auto, timeout_seconds=60)
    assert auto.status == "failure"
    assert "wip limit" in (auto.error_message or "")
    assert auto.exit_code == 1
    assert "wip limit" in (auto.stderr or "")


@pytest.mark.asyncio
async def test_dispatch_generic_exception_also_marks_failed_not_wedged(agent_task_service_raising):
    """Non-DispatchError exceptions (unexpected driver/orchestrator errors)
    hit the broad backstop and are handled identically."""
    svc, disp = agent_task_service_raising
    disp.dispatch_task = AsyncMock(side_effect=RuntimeError("orchestrator crashed"))
    auto = make_auto_action(kind="agent_task", instruction="X", action_command=None, agent_id="cody")

    await svc._run_action("t1", auto, timeout_seconds=60)

    assert auto.status == "failure"
    assert "orchestrator crashed" in (auto.error_message or "")


@pytest.mark.asyncio
async def test_execute_pending_agent_task_dispatch_raise_does_not_propagate(
    agent_task_execute_pending_raising,
):
    svc = agent_task_execute_pending_raising
    # execute_pending on an approved agent_task whose dispatch raises -> returns a
    # failure response, no exception
    resp = await svc.execute_pending("t1", "auto-1")
    assert resp.status == "failure"
    assert resp.error_message is not None
    assert "wip limit" in resp.error_message


# ── services/approvals.py: unified feed row still resolves ─────────────


class _FakeApprovalSession:
    """Stands in for an ``AsyncSession``: ``get`` returns the seeded row."""

    def __init__(self, appr: Approval) -> None:
        self._appr = appr
        self.flushed = False

    async def get(self, model, pk):
        assert str(pk) == str(self._appr.id)
        return self._appr

    async def flush(self):
        self.flushed = True


def _autonomous_action_approval(**overrides) -> Approval:
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id="t1",
        kind="autonomous_action",
        title="agent task: fix failing test X",
        detail="Fix failing test X",
        status="pending",
        source="autonomy",
        source_ref="aq-1",
        payload={
            "auto_action_id": "ac-1",
            "approval_id": "aq-1",
            "risk_level": "moderate",
        },
        priority=90,
    )
    defaults.update(overrides)
    return Approval(**defaults)


def _failure_auto_action_response() -> AutoActionResponse:
    return AutoActionResponse(
        id="ac-1",
        tenant_id="t1",
        agent_id="cody",
        project_id="ambient",
        action_name="cody_fix",
        action_command="",
        trigger_type="manual",
        trigger_detail="cody_fix",
        risk_level="moderate",
        status="failure",
        exit_code=1,
        stdout="",
        stderr="wip limit exceeded",
        error_message="wip limit exceeded",
        duration_ms=0,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_approve_resolves_feed_row_even_when_agent_task_execution_fails(monkeypatch):
    """execute_pending no longer raises for a dispatch failure — it returns a
    failure-status response. The generic Approval row (the user approved it;
    it ran; it failed) must still be marked resolved."""
    appr = _autonomous_action_approval()
    session = _FakeApprovalSession(appr)
    service = ApprovalService(session)

    fake_autonomy_approvals = AsyncMock()
    fake_autofix = AsyncMock()
    fake_autofix.execute_pending = AsyncMock(return_value=_failure_auto_action_response())
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: fake_autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: fake_autofix)

    result = await service.resolve("t1", str(appr.id), "approve", resolved_by="user-1")

    fake_autofix.execute_pending.assert_awaited_once_with("t1", "ac-1")
    assert result["status"] == "approved"  # feed row resolved despite the failed execution
    assert session.flushed is True
