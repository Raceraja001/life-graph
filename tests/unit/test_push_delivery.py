"""PushDeliveryHandler — delivers the daily brief via Web Push on BRIEF_COMPOSED."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from life_graph.core.events import Event, EventType
from life_graph.services.push_delivery import PushDeliveryHandler


class _FakeNotification:
    def __init__(self, body):
        self.body = body


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeSession:
    def __init__(self, row):
        self._row = row

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, stmt):
        return _FakeResult(self._row)


def _brief_event(tenant_id="t1", title="Daily Brief — 2026-07-31", notif_id=None):
    notif_id = notif_id or str(uuid.uuid4())
    return Event(
        type=EventType.BRIEF_COMPOSED,
        payload={
            "notification_id": notif_id,
            "tenant_id": tenant_id,
            "title": title,
            "questions": 2,
            "held": 1,
        },
    )


@pytest.mark.asyncio
async def test_on_brief_fetches_body_and_sends_push(monkeypatch):
    row = _FakeNotification(body="You held 1 item. 2 questions await.")

    def session_factory():
        return _FakeSession(row)

    monkeypatch.setattr("life_graph.services.push_delivery.async_session", session_factory)

    handler = PushDeliveryHandler()
    handler._push.send_to_tenant = AsyncMock(return_value=1)

    event = _brief_event(tenant_id="t1", title="Daily Brief — 2026-07-31")
    await handler._on_brief(event)

    handler._push.send_to_tenant.assert_awaited_once_with(
        "t1", "Daily Brief — 2026-07-31", "You held 1 item. 2 questions await.", "/m"
    )


@pytest.mark.asyncio
async def test_on_brief_swallows_send_failure(monkeypatch):
    row = _FakeNotification(body="body text")

    def session_factory():
        return _FakeSession(row)

    monkeypatch.setattr("life_graph.services.push_delivery.async_session", session_factory)

    handler = PushDeliveryHandler()
    handler._push.send_to_tenant = AsyncMock(side_effect=RuntimeError("boom"))

    event = _brief_event()

    # Must not raise — delivery failure must never break the brief flow.
    await handler._on_brief(event)


@pytest.mark.asyncio
async def test_subscribe_is_idempotent(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "life_graph.services.push_delivery.event_bus.subscribe",
        lambda event_type, handler: calls.append((event_type, handler)),
    )

    handler = PushDeliveryHandler()
    handler.subscribe()
    handler.subscribe()

    assert len(calls) == 1
    assert calls[0][0] == EventType.BRIEF_COMPOSED
