"""AutonomousApprovalProducer — bridges AUTONOMOUS_ACTION_PENDING to a notification +
push + the unified Approval feed row."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from life_graph.core.events import Event, EventType
from life_graph.models.db import Approval
from life_graph.services.autonomous_approvals import AutonomousApprovalProducer


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


def _pending_event(approval_id="a1", action_id="ac1", project_id="p1", risk_level="dangerous"):
    return Event(
        type=EventType.AUTONOMOUS_ACTION_PENDING,
        payload={
            "action_id": action_id,
            "approval_id": approval_id,
            "project_id": project_id,
            "risk_level": risk_level,
        },
    )


def _approval_entry(risk="dangerous", kind="command", instruction=None):
    return _Row(
        id="a1",
        tenant_id="t1",
        agent_id="ag1",
        action_name="rm-old-logs",
        action_command="rm -rf /var/log/old",
        kind=kind,
        instruction=instruction,
        risk_level=risk,
        category="pipeline",
        status="pending",
        priority=100,
        trigger_detail="log dir over quota",
    )


def _auto_action(risk="dangerous", kind="command", instruction=None, command="rm -rf /var/log/old"):
    return _Row(
        id="ac1",
        tenant_id="t1",
        agent_id="ag1",
        action_name="rm-old-logs",
        action_command=command,
        kind=kind,
        instruction=instruction,
        risk_level=risk,
        project_id="p1",
        status="pending",
        trigger_detail="log dir over quota",
    )


def _make_producer():
    producer = AutonomousApprovalProducer()
    producer._notification_engine = AsyncMock()
    producer._push_service = AsyncMock()
    return producer


@pytest.mark.asyncio
async def test_dangerous_action_notifies_critical_and_pushes_once(monkeypatch):
    session = _FakeSession([_approval_entry(), _auto_action(), None])
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    await producer._on_pending(_pending_event(risk_level="dangerous"))

    producer._notification_engine.create.assert_awaited_once()
    _, kwargs = producer._notification_engine.create.call_args
    assert kwargs["priority"] == "critical"
    producer._push_service.send_to_tenant.assert_awaited_once()


@pytest.mark.asyncio
async def test_moderate_action_notifies_important(monkeypatch):
    session = _FakeSession([_approval_entry("moderate"), _auto_action("moderate"), None])
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    await producer._on_pending(_pending_event(risk_level="moderate"))

    _, kwargs = producer._notification_engine.create.call_args
    assert kwargs["priority"] == "important"


@pytest.mark.asyncio
async def test_inserts_approval_feed_row(monkeypatch):
    session = _FakeSession([_approval_entry(), _auto_action(), None])
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    await producer._on_pending(_pending_event())

    assert len(session.added) == 1
    row = session.added[0]
    assert isinstance(row, Approval)
    assert row.kind == "autonomous_action"
    assert row.source == "autonomy"
    assert row.source_ref == "a1"
    assert row.tenant_id == "t1"
    assert row.title == "dangerous action: rm-old-logs"  # feed title matches the plan text
    assert row.payload["approval_id"] == "a1"
    assert row.payload["auto_action_id"] == "ac1"
    assert row.payload["kind"] == "command"
    assert "instruction" not in row.payload
    assert row.priority == 90  # dangerous
    assert session.committed is True


@pytest.mark.asyncio
async def test_agent_task_payload_carries_kind_and_instruction(monkeypatch):
    """agent_task entries mirror kind + the natural-language instruction into the
    unified Approval feed's payload, so the client can render it without a shell
    command (Task 7)."""
    session = _FakeSession(
        [
            _approval_entry(kind="agent_task", instruction="Refactor the auth module for clarity"),
            _auto_action(
                kind="agent_task",
                instruction="Refactor the auth module for clarity",
                command=None,
            ),
            None,
        ]
    )
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    await producer._on_pending(_pending_event())

    assert len(session.added) == 1
    row = session.added[0]
    assert row.payload["kind"] == "agent_task"
    assert row.payload["instruction"] == "Refactor the auth module for clarity"

    # The push/in-app notification body must use the instruction, not the (always
    # None for agent_task) command — must never literally read "None" (fix review).
    _, kwargs = producer._notification_engine.create.call_args
    assert "None" not in kwargs["body"]
    assert "Refactor the auth module for clarity" in kwargs["body"]


@pytest.mark.asyncio
async def test_agent_task_with_no_instruction_falls_back_to_action_name_in_body(monkeypatch):
    """Defensive case: even if an agent_task row somehow has neither command nor
    instruction, the notification body falls back to the action name rather than
    stringifying None."""
    session = _FakeSession(
        [
            _approval_entry(kind="agent_task", instruction=None),
            _auto_action(kind="agent_task", instruction=None, command=None),
            None,
        ]
    )
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    await producer._on_pending(_pending_event())

    _, kwargs = producer._notification_engine.create.call_args
    assert "None" not in kwargs["body"]
    assert "rm-old-logs" in kwargs["body"]  # falls back to action_name


@pytest.mark.asyncio
async def test_notification_title_differs_from_feed_title(monkeypatch):
    """The push/notification title stays the fuller 'needs approval' wording; only
    the generic Approval feed-row title is trimmed to match the plan text."""
    session = _FakeSession([_approval_entry(), _auto_action(), None])
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    await producer._on_pending(_pending_event())

    notify_title = producer._notification_engine.create.call_args.args[1]
    assert notify_title == "dangerous action needs approval: rm-old-logs"
    assert session.added[0].title == "dangerous action: rm-old-logs"


@pytest.mark.asyncio
async def test_idempotent_skips_duplicate_insert(monkeypatch):
    existing = _Row(id="existing-uuid")
    session = _FakeSession([_approval_entry(), _auto_action(), existing])
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    await producer._on_pending(_pending_event())

    assert session.added == []
    assert session.committed is False


@pytest.mark.asyncio
async def test_push_failure_does_not_propagate(monkeypatch):
    session = _FakeSession([_approval_entry(), _auto_action(), None])
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    producer._push_service.send_to_tenant.side_effect = RuntimeError("push boom")

    await producer._on_pending(_pending_event())  # must not raise

    assert len(session.added) == 1  # feed row still inserted despite push failure


@pytest.mark.asyncio
async def test_notify_failure_does_not_propagate(monkeypatch):
    session = _FakeSession([_approval_entry(), _auto_action(), None])
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    producer._notification_engine.create.side_effect = RuntimeError("notify boom")

    await producer._on_pending(_pending_event())  # must not raise

    producer._push_service.send_to_tenant.assert_awaited_once()
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_agent_task_feed_row_detail_falls_back_to_instruction(monkeypatch):
    """Final-review Minor #7: Approval.detail was always None for agent_task
    (it was fed the always-None action_command)."""
    session = _FakeSession(
        [
            _approval_entry(kind="agent_task", instruction="Refactor the auth module"),
            _auto_action(kind="agent_task", instruction="Refactor the auth module", command=None),
            None,
        ]
    )
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    await producer._on_pending(_pending_event())

    assert session.added[0].detail == "Refactor the auth module"


@pytest.mark.asyncio
async def test_row_missing_the_b2_columns_still_gets_a_feed_row(monkeypatch):
    """Final-review Important #6: a single broad try/except meant one bad
    attribute cost the queued action its notification AND its feed row, leaving
    it invisible in /m/approvals forever. Task 1's kind/instruction columns
    tripped exactly this. Rows that predate (or drift from) the current schema
    must degrade a field, not the whole event."""
    stale_entry = _Row(
        id="a1",
        tenant_id="t1",
        agent_id="ag1",
        action_name="rm-old-logs",
        action_command="rm -rf /var/log/old",
        risk_level="dangerous",
        trigger_detail="log dir over quota",
    )  # note: no `kind`, no `instruction`
    stale_action = _Row(
        id="ac1",
        tenant_id="t1",
        agent_id="ag1",
        action_name="rm-old-logs",
        action_command="rm -rf /var/log/old",
        risk_level="dangerous",
        project_id="p1",
        trigger_detail="log dir over quota",
    )
    session = _FakeSession([stale_entry, stale_action, None])
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    await producer._on_pending(_pending_event())

    producer._notification_engine.create.assert_awaited_once()
    assert len(session.added) == 1
    assert session.added[0].payload["kind"] == "command"  # sane default


@pytest.mark.asyncio
async def test_missing_approval_entry_returns_without_error(monkeypatch):
    session = _FakeSession([None])
    monkeypatch.setattr("life_graph.services.autonomous_approvals.async_session", lambda: session)

    producer = _make_producer()
    await producer._on_pending(_pending_event())

    producer._notification_engine.create.assert_not_awaited()
    producer._push_service.send_to_tenant.assert_not_awaited()
    assert session.added == []


@pytest.mark.asyncio
async def test_subscribe_is_idempotent(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "life_graph.services.autonomous_approvals.event_bus.subscribe",
        lambda event_type, handler: calls.append((event_type, handler)),
    )

    producer = AutonomousApprovalProducer()
    producer.subscribe()
    producer.subscribe()

    assert len(calls) == 1
    assert calls[0][0] == EventType.AUTONOMOUS_ACTION_PENDING
