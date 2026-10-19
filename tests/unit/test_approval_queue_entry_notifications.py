"""The OLDER approval system (ApprovalQueueEntry -- second-opinion dissent,
verification-unavailable/failed escalations) must notify too, same as the
newer Approval-table producers (driver_pr/merge/plan/deploy).
"""

from __future__ import annotations

import pytest

from life_graph.core.events import Event, EventType, event_bus
from life_graph.drivers.dispatcher import TaskDispatcher
from life_graph.services.verifiers import VerifierResult


class _FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


@pytest.fixture
def captured():
    events: list[Event] = []

    async def _capture(event: Event) -> None:
        events.append(event)

    event_bus.subscribe(EventType.APPROVAL_FILED, _capture)
    try:
        yield events
    finally:
        event_bus.unsubscribe(EventType.APPROVAL_FILED, _capture)


@pytest.mark.asyncio
async def test_dissent_entry_notifies(captured):
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=event_bus)
    session = _FakeSession()

    await disp._create_dissent_approval_entry(
        "t1", "task-123", "local", "looks like a correctness bug", session
    )

    assert len(session.added) == 1
    assert len(captured) == 1
    assert captured[0].payload["tenant_id"] == "t1"
    assert captured[0].payload["kind"] == "driver_second_opinion_dissent"
    assert "correctness bug" in captured[0].payload["detail"]


@pytest.mark.asyncio
async def test_verification_unavailable_entry_notifies(captured):
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=event_bus)
    session = _FakeSession()
    results = [VerifierResult("no_vulnerable_deps_in_diff", False, {}, inconclusive=True)]

    await disp._create_approval_entry("t1", "task-456", "local", results, session)

    assert len(captured) == 1
    assert captured[0].payload["kind"] == "driver_verification_unavailable"
    assert "no_vulnerable_deps_in_diff" in captured[0].payload["detail"]


@pytest.mark.asyncio
async def test_verification_failed_entry_notifies(captured):
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=event_bus)
    session = _FakeSession()
    results = [VerifierResult("tests_pass", False, {})]

    await disp._create_approval_entry("t1", "task-789", "local", results, session)

    assert len(captured) == 1
    assert captured[0].payload["kind"] == "driver_verification_failed"
    assert "tests_pass" in captured[0].payload["detail"]
