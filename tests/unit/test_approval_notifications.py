"""ApprovalNotificationHandler: a filed approval reaches push + Telegram,
and a failure in one channel never blocks the other.
"""

from __future__ import annotations

import pytest

from life_graph.core.events import Event, EventType
from life_graph.services.approval_notifications import ApprovalNotificationHandler


class _FakePush:
    def __init__(self, raise_on_send=False):
        self.calls = []
        self._raise = raise_on_send

    async def send_to_tenant(self, tenant_id, title, body, url):
        if self._raise:
            raise RuntimeError("push backend down")
        self.calls.append({"tenant_id": tenant_id, "title": title, "body": body, "url": url})


class _FakeChannel:
    def __init__(self, raise_on_send=False):
        self.calls = []
        self._raise = raise_on_send

    async def send(self, *, config, tenant_id, severity, title, details, watcher_name):
        if self._raise:
            raise RuntimeError("telegram backend down")
        self.calls.append(
            {"tenant_id": tenant_id, "severity": severity, "title": title, "details": details}
        )


def _event(payload: dict) -> Event:
    return Event(type=EventType.APPROVAL_FILED, payload=payload, source="test")


@pytest.mark.asyncio
async def test_sends_to_both_channels():
    push, channel = _FakePush(), _FakeChannel()
    handler = ApprovalNotificationHandler(push=push, channel=channel)

    await handler._on_approval_filed(
        _event({"tenant_id": "t1", "kind": "driver_pr", "title": "Open PR: fix x", "detail": "the diff..."})
    )

    assert push.calls == [
        {"tenant_id": "t1", "title": "Open PR: fix x", "body": "the diff...", "url": "/m/approvals"}
    ]
    assert channel.calls == [
        {"tenant_id": "t1", "severity": "important", "title": "Open PR: fix x", "details": "the diff..."}
    ]


@pytest.mark.asyncio
async def test_missing_tenant_id_is_a_noop():
    push, channel = _FakePush(), _FakeChannel()
    handler = ApprovalNotificationHandler(push=push, channel=channel)

    await handler._on_approval_filed(_event({"kind": "driver_pr", "title": "x", "detail": "y"}))

    assert push.calls == []
    assert channel.calls == []


@pytest.mark.asyncio
async def test_push_failure_does_not_block_telegram():
    push, channel = _FakePush(raise_on_send=True), _FakeChannel()
    handler = ApprovalNotificationHandler(push=push, channel=channel)

    await handler._on_approval_filed(_event({"tenant_id": "t1", "title": "x", "detail": "y"}))

    assert channel.calls  # still delivered despite push raising


@pytest.mark.asyncio
async def test_telegram_failure_does_not_block_push():
    push, channel = _FakePush(), _FakeChannel(raise_on_send=True)
    handler = ApprovalNotificationHandler(push=push, channel=channel)

    await handler._on_approval_filed(_event({"tenant_id": "t1", "title": "x", "detail": "y"}))

    assert push.calls  # still delivered despite telegram raising


@pytest.mark.asyncio
async def test_detail_truncated_for_a_push_message():
    push, channel = _FakePush(), _FakeChannel()
    handler = ApprovalNotificationHandler(push=push, channel=channel)
    long_detail = "x" * 5000

    await handler._on_approval_filed(
        _event({"tenant_id": "t1", "title": "x", "detail": long_detail})
    )

    assert len(push.calls[0]["body"]) == 500
    assert len(channel.calls[0]["details"]) == 500


def test_subscribe_is_idempotent():
    handler = ApprovalNotificationHandler(push=_FakePush(), channel=_FakeChannel())
    handler.subscribe()
    handler.subscribe()  # must not double-register
    assert handler._subscribed is True
