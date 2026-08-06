# tests/integration/test_action_roles_agent_task_e2e.py
"""End-to-end test for the B2 agent_task pipeline (mock-only, no DB, no real agent).

Drives every hop the real pipeline takes for one proposed ``agent_task`` action,
mirroring ``tests/integration/test_action_roles_end_to_end.py`` (B1) for style and
``tests/unit/test_agent_task_routing.py`` / ``tests/unit/test_agent_task_dispatch_failure.py``
for the fake-session conventions used to drive ``AutoFixService`` without a live DB:

  1. cody proposes an agent_task -> ``ActionProposalBridge.process_result()`` parses
     it and dispatches into ``AutoFixService.process()`` (mocked) with
     ``kind="agent_task"`` + the instruction text.
  2. ``AutoFixService.process()`` with the safety classifier mocked to recommend
     AUTO_EXECUTE -> B2-D2's override still forces ``queued_for_approval`` for an
     agent_task request (never auto), mirroring ``test_agent_task_routing.py``.
  3. The user approves the unified feed row -> ``ApprovalService.resolve()`` (which
     calls ``_apply_autonomous_action`` internally, Task 7) -> ``execute_pending``
     reaches a MOCKED ``TaskDispatcher.dispatch_task``, which returns a successful
     ``DriverResult`` -> the ``AutoAction`` ends ``status="success"`` and the feed
     row resolves to ``approved``.
  4. Same approve path, but ``dispatch_task`` raises ``DispatchError`` -> the
     ``AutoAction`` ends ``status="failure"``, the feed row still resolves, and no
     exception propagates out of the approve path (Task 4/7 robustness).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.dml import Update

from life_graph.autonomy.pipeline.schemas import AutoActionResponse, AutoFixRequest, AutoFixResponse
from life_graph.autonomy.pipeline.service import DEFAULT_AGENT_TASK_COST_CAP, AutoFixService
from life_graph.autonomy.safety.classifier import ClassificationResult, Recommendation, RiskLevel
from life_graph.drivers.base import DriverResult
from life_graph.drivers.dispatcher import DispatchError
from life_graph.models.db import Approval
from life_graph.services.action_proposal_bridge import AMBIENT_PROJECT_ID, ActionProposalBridge
from life_graph.services.approvals import ApprovalService

TENANT = "test_action_roles_agent_task_e2e_tenant"

AGENT_TASK_PROPOSAL_RESULT = (
    "Inspected recent CI runs.\n"
    '[{"name":"fix_flaky_test","kind":"agent_task",'
    '"instruction":"Investigate and fix the flaky test_worker_retry test",'
    '"rationale":"test has failed 3 times this week"}]'
)


# ── Step 1: cody proposal (agent_task) -> AutoFixService.process ───────────


@pytest.mark.asyncio
async def test_proposal_bridge_dispatches_agent_task_autofix_request():
    """A proposed agent_task item -> exactly one AutoFixService.process call
    carrying kind="agent_task" and the raw instruction text."""

    def _response(routing: str = "queued_for_approval") -> AutoFixResponse:
        action = AutoActionResponse(
            id="action-1",
            tenant_id=TENANT,
            agent_id="cody",
            project_id=AMBIENT_PROJECT_ID,
            action_name="fix_flaky_test",
            action_command="",
            trigger_type="manual",
            trigger_detail="test has failed 3 times this week",
            risk_level="moderate",
            status="pending",
            created_at=datetime.now(UTC),
        )
        return AutoFixResponse(action=action, routing=routing, message=f"Action {routing}")

    autofix = AsyncMock()
    autofix.process = AsyncMock(return_value=_response())
    notifications = AsyncMock()

    bridge = ActionProposalBridge(autofix_service=autofix, notification_engine=notifications)
    dispatched = await bridge.process_result(TENANT, "cody", "task-1", AGENT_TASK_PROPOSAL_RESULT)

    assert dispatched == 1
    autofix.process.assert_awaited_once()
    call_tenant, call_request = autofix.process.await_args.args
    assert call_tenant == TENANT
    assert isinstance(call_request, AutoFixRequest)
    assert call_request.agent_id == "cody"
    assert call_request.project_id == AMBIENT_PROJECT_ID
    assert call_request.action_type == "fix_flaky_test"
    assert call_request.kind == "agent_task"
    assert call_request.instruction == "Investigate and fix the flaky test_worker_retry test"
    assert call_request.command is None
    notifications.create.assert_not_awaited()  # a parseable proposal never falls back to advisory


# ── Step 2: process() routing — agent_task always queues (B2-D2) ───────────


class _RoutingFakeResult:
    """Stand-in for a SQLAlchemy Result — both scalar accessors return the row."""

    def __init__(self, obj):
        self._obj = obj

    def scalar_one(self):
        return self._obj

    def scalar_one_or_none(self):
        return self._obj


class _RoutingFakeSession:
    """Async-context-manager session backed by a single-row box.

    Mirrors ``tests/unit/test_agent_task_routing.py``'s ``_FakeSession``: this
    test only ever creates one ``AutoAction``, so WHERE clauses are ignored —
    UPDATE statements are applied to (and SELECTs return) whatever row is
    currently in the box.
    """

    def __init__(self, box):
        self._box = box

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    def add(self, obj):
        self._box["action"] = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def execute(self, stmt):
        action = self._box["action"]
        if isinstance(stmt, Update):
            for key, value in stmt.compile().params.items():
                if hasattr(action, key):
                    setattr(action, key, value)
        return _RoutingFakeResult(action)


@pytest.mark.asyncio
async def test_process_agent_task_always_queues_even_when_classifier_says_auto():
    """Mirrors test_agent_task_routing.py: the classifier recommends
    AUTO_EXECUTE, but B2-D2's override still forces queued_for_approval for
    an agent_task request — never auto, as part of the full E2E file."""
    box: dict = {"action": None}
    session = _RoutingFakeSession(box)

    svc = AutoFixService.__new__(AutoFixService)
    svc._session_factory = lambda: session
    svc._executor = MagicMock()
    svc._executor.execute = AsyncMock()
    svc._audit_service = AsyncMock()
    svc._approval_service = AsyncMock()
    svc._approval_service.create = AsyncMock(return_value=MagicMock(id="appr-1"))
    svc._level_service = None
    svc._project_locks = {}
    svc._dispatcher = AsyncMock()

    classification = ClassificationResult(
        risk_level=RiskLevel.SAFE,
        recommendation=Recommendation.AUTO_EXECUTE,
        matched_rule=None,
        trust_score=1.0,
        autonomy_level="L1",
        reasoning={},
    )
    fake_classifier = MagicMock()
    fake_classifier.classify = AsyncMock(return_value=classification)

    with (
        patch(
            "life_graph.autonomy.safety.classifier.ActionClassifier",
            return_value=fake_classifier,
        ),
        patch("life_graph.autonomy.pipeline.service.shadow_service") as shadow_mock,
        patch("life_graph.autonomy.pipeline.service.event_bus") as bus_mock,
    ):
        shadow_mock.intercept = AsyncMock(return_value=MagicMock(shadow=False, enrollment_id=None))
        bus_mock.emit = AsyncMock()

        req = AutoFixRequest(
            agent_id="cody",
            project_id=AMBIENT_PROJECT_ID,
            action_type="fix_flaky_test",
            kind="agent_task",
            instruction="Investigate and fix the flaky test_worker_retry test",
        )
        resp = await svc.process(TENANT, req)

    assert resp.routing == "queued_for_approval"  # never auto, no matter what the classifier said
    svc._executor.execute.assert_not_called()
    svc._dispatcher.dispatch_task.assert_not_called()  # not dispatched yet — only queued
    saved = box["action"]
    assert saved.kind == "agent_task"
    assert saved.instruction == "Investigate and fix the flaky test_worker_retry test"
    approval_data = svc._approval_service.create.call_args.kwargs["data"]
    assert approval_data["kind"] == "agent_task"
    assert approval_data["instruction"] == "Investigate and fix the flaky test_worker_retry test"


# ── Steps 3 & 4: approve -> execute_pending -> TaskDispatcher.dispatch_task ─


class _DispatchFakeResult:
    """Stand-in for a SQLAlchemy Result — both scalar accessors return the row."""

    def __init__(self, obj):
        self._obj = obj

    def scalar_one(self):
        return self._obj

    def scalar_one_or_none(self):
        return self._obj


class _DispatchFakeSession:
    """Async-context-manager session backed by a single-row box.

    Mirrors ``tests/unit/test_agent_task_dispatch_failure.py``'s
    ``_FakeSession``: ``execute_pending`` only ever touches one ``AutoAction``,
    so WHERE clauses are ignored — UPDATE statements apply to (and SELECTs
    return) whatever row is currently in the box.
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
        return _DispatchFakeResult(action)


class _FakeApprovalSession:
    """Stands in for an ``AsyncSession``: ``get`` returns the seeded feed row."""

    def __init__(self, appr: Approval) -> None:
        self._appr = appr
        self.flushed = False

    async def get(self, model, pk):
        assert str(pk) == str(self._appr.id)
        return self._appr

    async def flush(self):
        self.flushed = True


def _make_pending_agent_task_auto_action():
    """Build a bare object with the attributes ``_run_action``/``execute_pending`` read/write."""
    return MagicMock(
        id="auto-1",
        tenant_id=TENANT,
        kind="agent_task",
        instruction="Investigate and fix the flaky test_worker_retry test",
        action_command=None,
        action_name="fix_flaky_test",
        agent_id="cody",
        project_id=AMBIENT_PROJECT_ID,
        risk_level="moderate",
        status="pending",
        approval_id=None,
        rollback_command=None,
        trigger_type="manual",
        trigger_detail="fix_flaky_test",
        started_at=None,
        completed_at=None,
        exit_code=None,
        stdout=None,
        stderr=None,
        error_message=None,
        duration_ms=None,
        created_at=datetime.now(UTC),
    )


def _feed_row(appr_id: uuid.UUID, status: str = "pending") -> Approval:
    return Approval(
        id=appr_id,
        tenant_id=TENANT,
        kind="autonomous_action",
        source="autonomy",
        source_ref="aq-1",
        title="agent task: fix_flaky_test",
        detail="Investigate and fix the flaky test_worker_retry test",
        status=status,
        payload={
            "approval_id": "aq-1",
            "auto_action_id": "auto-1",
            "risk_level": "moderate",
        },
        priority=90,
    )


@pytest.mark.asyncio
async def test_approve_dispatches_agent_task_and_ends_success(monkeypatch):
    """Approving the unified feed row runs execute_pending, which reaches a
    mocked TaskDispatcher.dispatch_task with the right kwargs; a successful
    DriverResult ends the AutoAction success and resolves the feed row."""
    auto_action = _make_pending_agent_task_auto_action()
    box: dict = {"action": auto_action}
    autofix_session = _DispatchFakeSession(box)

    disp = MagicMock()
    disp.dispatch_task = AsyncMock(
        return_value=DriverResult(success=True, output="fixed it", cost_usd=0.02, duration_ms=4200)
    )

    autofix = AutoFixService.__new__(AutoFixService)
    autofix._session_factory = lambda: autofix_session
    autofix._executor = MagicMock()
    autofix._audit_service = AsyncMock()
    autofix._level_service = None
    autofix._project_locks = {}
    autofix._dispatcher = disp

    autonomy_approvals = AsyncMock()
    autonomy_approvals.resolve = AsyncMock(return_value=MagicMock(id="aq-1"))
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: autofix)

    appr_id = uuid.uuid4()
    appr = _feed_row(appr_id)
    feed_service = ApprovalService(session=_FakeApprovalSession(appr))

    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock()
        result = await feed_service.resolve(TENANT, str(appr_id), "approve", resolved_by="tester")

    disp.dispatch_task.assert_awaited_once()
    _, kwargs = disp.dispatch_task.await_args
    assert kwargs["tenant_id"] == TENANT
    assert kwargs["task_id"] == "auto-1"
    assert kwargs["instruction"] == "Investigate and fix the flaky test_worker_retry test"
    assert kwargs["persona_name"] == "cody"
    assert kwargs["verify_chain"] == ["build_ok_diff", "lint_clean_diff"]
    assert kwargs["interactive"] is False
    assert kwargs["cost_cap_usd"] == DEFAULT_AGENT_TASK_COST_CAP

    assert auto_action.status == "success"
    assert auto_action.exit_code == 0

    autonomy_approvals.resolve.assert_awaited_once_with(
        tenant_id=TENANT,
        approval_id="aq-1",
        decision="approve",
        note=None,
        resolved_by="tester",
    )
    assert appr.status == "approved"
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_dispatch_failure_ends_failure_but_still_resolves(monkeypatch):
    """Same approve path, but dispatch_task raises DispatchError: the
    AutoAction ends failure, the feed row still resolves, and nothing
    propagates out of the approve path."""
    auto_action = _make_pending_agent_task_auto_action()
    box: dict = {"action": auto_action}
    autofix_session = _DispatchFakeSession(box)

    disp = MagicMock()
    disp.dispatch_task = AsyncMock(side_effect=DispatchError("wip limit exceeded"))

    autofix = AutoFixService.__new__(AutoFixService)
    autofix._session_factory = lambda: autofix_session
    autofix._executor = MagicMock()
    autofix._audit_service = AsyncMock()
    autofix._level_service = None
    autofix._project_locks = {}
    autofix._dispatcher = disp

    autonomy_approvals = AsyncMock()
    autonomy_approvals.resolve = AsyncMock(return_value=MagicMock(id="aq-1"))
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: autofix)

    appr_id = uuid.uuid4()
    appr = _feed_row(appr_id)
    feed_service = ApprovalService(session=_FakeApprovalSession(appr))

    with patch("life_graph.autonomy.pipeline.service.event_bus") as bus:
        bus.emit = AsyncMock()
        # must NOT raise
        result = await feed_service.resolve(TENANT, str(appr_id), "approve", resolved_by="tester")

    disp.dispatch_task.assert_awaited_once()
    assert auto_action.status == "failure"
    assert auto_action.exit_code == 1
    assert "wip limit exceeded" in (auto_action.error_message or "")

    assert appr.status == "approved"  # a failed-but-completed agent_task is still resolved
    assert result["status"] == "approved"
