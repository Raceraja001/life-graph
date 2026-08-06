# tests/integration/test_action_roles_end_to_end.py
"""End-to-end test for the B1 autonomous-action-roles pipeline (mock-only, no DB).

Drives every hop the real pipeline takes for one proposed action, mirroring the
mocking conventions of tests/unit/test_autonomous_approvals_producer.py (fake
session queue) and tests/integration/test_ambient_event_wiring.py (direct
handler invocation rather than a live event bus):

  1. ops proposes an action -> ``ActionProposalBridge.process_result()`` parses
     it and dispatches into ``AutoFixService.process()`` (mocked to route it to
     approval, as the classifier would for a moderate/dangerous action).
  2. The autonomy engine's ``AUTONOMOUS_ACTION_PENDING`` event ->
     ``AutonomousApprovalProducer`` creates a Notification + a generic
     ``Approval`` feed row (mocked session/engine/push).
  3. The user approves that generic ``Approval`` row ->
     ``ApprovalService._apply_autonomous_action`` (Task 7) resolves the
     autonomy-side approval and executes the action via ``execute_pending``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from life_graph.autonomy.pipeline.schemas import AutoActionResponse, AutoFixRequest, AutoFixResponse
from life_graph.core.events import Event, EventType
from life_graph.models.db import Approval
from life_graph.services.action_proposal_bridge import AMBIENT_PROJECT_ID, ActionProposalBridge
from life_graph.services.autonomous_approvals import AutonomousApprovalProducer

TENANT = "test_action_roles_e2e_tenant"

PROPOSAL_RESULT = (
    "Inspected the system.\n"
    '[{"name":"restart_worker","command":"systemctl restart worker",'
    '"rationale":"worker looked stuck"}]'
)


def _autofix_response(routing: str = "queued_for_approval") -> AutoFixResponse:
    action = AutoActionResponse(
        id="action-1",
        tenant_id=TENANT,
        agent_id="ops",
        project_id=AMBIENT_PROJECT_ID,
        action_name="restart_worker",
        action_command="systemctl restart worker",
        trigger_type="manual",
        trigger_detail="worker looked stuck",
        risk_level="moderate",
        status="pending",
        created_at=datetime.now(UTC),
    )
    return AutoFixResponse(action=action, routing=routing, message=f"Action {routing}")


# ── Fakes shared by the producer step (same shape as
#    tests/unit/test_autonomous_approvals_producer.py) ─────────────────────


class _Row:
    """A plain attribute bag standing in for an ORM row."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeSession:
    """Returns queued results in order, one per ``execute`` call; records inserts."""

    def __init__(self, results):
        self._results = list(results)
        self.added: list = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, stmt):
        return _FakeResult(self._results.pop(0))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


# ── Step 1: ops proposal -> AutoFixService.process ─────────────────────────


@pytest.mark.asyncio
async def test_proposal_bridge_dispatches_one_autofix_request():
    """One proposed action -> exactly one AutoFixService.process call with the
    right AutoFixRequest fields (agent_id, project_id="ambient", action_type,
    command)."""
    autofix = AsyncMock()
    autofix.process = AsyncMock(return_value=_autofix_response())
    notifications = AsyncMock()

    bridge = ActionProposalBridge(autofix_service=autofix, notification_engine=notifications)
    dispatched = await bridge.process_result(TENANT, "ops", "task-1", PROPOSAL_RESULT)

    assert dispatched == 1
    autofix.process.assert_awaited_once()
    call_tenant, call_request = autofix.process.await_args.args
    assert call_tenant == TENANT
    assert isinstance(call_request, AutoFixRequest)
    assert call_request.agent_id == "ops"
    assert call_request.project_id == "ambient"
    assert call_request.action_type == "restart_worker"
    assert call_request.command == "systemctl restart worker"
    notifications.create.assert_not_awaited()  # a parseable proposal never falls back to advisory


# ── Step 2: AUTONOMOUS_ACTION_PENDING -> notification + Approval feed row ──


@pytest.mark.asyncio
async def test_pending_event_creates_notification_and_feed_row(monkeypatch):
    """Simulates the producer that bridges ``AUTONOMOUS_ACTION_PENDING`` into a
    Notification (pushed) + a generic ``Approval`` feed row, both mocked."""
    approval_entry = _Row(
        id="approval-1",
        tenant_id=TENANT,
        agent_id="ops",
        action_name="restart_worker",
        action_command="systemctl restart worker",
        risk_level="moderate",
        trigger_detail="worker looked stuck",
        kind="command",
        instruction=None,
    )
    auto_action = _Row(
        id="action-1",
        tenant_id=TENANT,
        agent_id="ops",
        action_name="restart_worker",
        action_command="systemctl restart worker",
        risk_level="moderate",
        trigger_detail="worker looked stuck",
        kind="command",
        instruction=None,
    )
    session = _FakeSession([approval_entry, auto_action, None])
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = AutonomousApprovalProducer()
    producer._notification_engine = AsyncMock()
    producer._push_service = AsyncMock()

    event = Event(
        type=EventType.AUTONOMOUS_ACTION_PENDING,
        payload={
            "action_id": "action-1",
            "approval_id": "approval-1",
            "project_id": AMBIENT_PROJECT_ID,
            "risk_level": "moderate",
        },
    )
    await producer._on_pending(event)

    producer._notification_engine.create.assert_awaited_once()
    producer._push_service.send_to_tenant.assert_awaited_once()
    assert session.committed is True
    assert len(session.added) == 1

    row = session.added[0]
    assert isinstance(row, Approval)
    assert row.kind == "autonomous_action"
    assert row.source == "autonomy"
    assert row.tenant_id == TENANT
    assert row.source_ref == "approval-1"
    assert row.payload["approval_id"] == "approval-1"
    assert row.payload["auto_action_id"] == "action-1"
    assert row.payload["risk_level"] == "moderate"


# ── Step 3: approve the feed row -> execute_pending ─────────────────────────


def _feed_row(status: str = "pending") -> Approval:
    return Approval(
        tenant_id=TENANT,
        kind="autonomous_action",
        source="autonomy",
        source_ref="approval-1",
        title="moderate action: restart_worker",
        detail="systemctl restart worker",
        status=status,
        payload={
            "approval_id": "approval-1",
            "auto_action_id": "action-1",
            "risk_level": "moderate",
        },
    )


@pytest.mark.asyncio
async def test_approve_feed_row_resolves_and_executes_pending_action(monkeypatch):
    """The Task 7 approve path resolves the autonomy-side approval and then
    calls ``execute_pending`` on the linked ``AutoAction``."""
    from life_graph.services.approvals import ApprovalService

    autonomy_approvals = AsyncMock()
    autonomy_approvals.resolve = AsyncMock(return_value=_Row(id="approval-1"))
    autofix = AsyncMock()
    autofix.execute_pending = AsyncMock(return_value=_autofix_response("auto_executed").action)

    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: autofix)

    service = ApprovalService(session=AsyncMock())
    appr = _feed_row()
    await service._apply_autonomous_action(TENANT, appr, True, "tester")

    autonomy_approvals.resolve.assert_awaited_once_with(
        tenant_id=TENANT,
        approval_id="approval-1",
        decision="approve",
        note=None,
        resolved_by="tester",
    )
    autofix.execute_pending.assert_awaited_once_with(TENANT, "action-1")


@pytest.mark.asyncio
async def test_reject_feed_row_never_executes(monkeypatch):
    """Rejecting the generic feed row must resolve the autonomy approval as
    'reject' and must NEVER call execute_pending."""
    from life_graph.services.approvals import ApprovalService

    autonomy_approvals = AsyncMock()
    autonomy_approvals.resolve = AsyncMock(return_value=_Row(id="approval-1"))
    autofix = AsyncMock()
    autofix.execute_pending = AsyncMock()

    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: autofix)

    service = ApprovalService(session=AsyncMock())
    appr = _feed_row()
    await service._apply_autonomous_action(TENANT, appr, False, "tester")

    autonomy_approvals.resolve.assert_awaited_once_with(
        tenant_id=TENANT,
        approval_id="approval-1",
        decision="reject",
        note=None,
        resolved_by="tester",
    )
    autofix.execute_pending.assert_not_awaited()
