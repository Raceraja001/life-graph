"""Unit tests for the Telegram notification channel and brief delivery.

No network and no DB: the Bot API client and the session factory are both
faked, so these assert routing and formatting decisions rather than transport.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from life_graph.integrations.telegram.client import TelegramError
from life_graph.services.telegram_delivery import TelegramDeliveryHandler
from life_graph.watchers.channels.telegram_channel import TelegramChannel


class FakeClient:
    """Stands in for TelegramClient, recording sends."""

    def __init__(self, *, configured: bool = True, fail_on: set[int] | None = None):
        self.configured = configured
        self.sent: list[tuple[int, str, bool]] = []
        self._fail_on = fail_on or set()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send_message(self, chat_id, text, *, disable_notification=False, **kw):
        if chat_id in self._fail_on:
            raise TelegramError("chat not found", error_code=400)
        self.sent.append((chat_id, text, disable_notification))
        return [{"message_id": 1}]


def _channel(client: FakeClient, chats: list[int]) -> TelegramChannel:
    ch = TelegramChannel(client_factory=lambda: client)

    async def _resolve(config, tenant_id):
        return [int(config["chat_id"])] if config.get("chat_id") else chats

    ch._resolve_chats = _resolve  # type: ignore[method-assign]
    return ch


@pytest.mark.asyncio
async def test_sends_to_every_active_binding():
    client = FakeClient()
    ok = await _channel(client, [11, 22]).send({}, "t1", "critical", "Disk full")
    assert ok is True
    assert [c for c, _, _ in client.sent] == [11, 22]


@pytest.mark.asyncio
async def test_config_chat_id_overrides_the_bindings():
    client = FakeClient()
    await _channel(client, [11, 22]).send({"chat_id": "99"}, "t1", "info", "Hi")
    assert [c for c, _, _ in client.sent] == [99]


@pytest.mark.asyncio
async def test_no_paired_chat_is_a_clean_false_not_a_raise():
    client = FakeClient()
    assert await _channel(client, []).send({}, "t1", "critical", "Disk full") is False
    assert client.sent == []


@pytest.mark.asyncio
async def test_missing_bot_token_does_not_send():
    client = FakeClient(configured=False)
    assert await _channel(client, [11]).send({}, "t1", "critical", "X") is False
    assert client.sent == []


@pytest.mark.asyncio
async def test_one_dead_chat_does_not_stop_the_others():
    """A blocked chat must not silence a critical alert to the user's other devices."""
    client = FakeClient(fail_on={11})
    ok = await _channel(client, [11, 22]).send({}, "t1", "critical", "Disk full")
    assert ok is True
    assert [c for c, _, _ in client.sent] == [22]


@pytest.mark.asyncio
async def test_every_chat_failing_reports_failure():
    client = FakeClient(fail_on={11, 22})
    assert await _channel(client, [11, 22]).send({}, "t1", "critical", "X") is False


@pytest.mark.asyncio
async def test_info_is_silent_and_higher_severities_are_not():
    """The 03:00 brief must not buzz; an alert must."""
    client = FakeClient()
    ch = _channel(client, [11])
    await ch.send({}, "t1", "info", "Brief")
    await ch.send({}, "t1", "critical", "Alert")
    assert [silent for _, _, silent in client.sent] == [True, False]


@pytest.mark.asyncio
async def test_silent_config_overrides_severity():
    client = FakeClient()
    await _channel(client, [11]).send({"silent": True}, "t1", "critical", "Alert")
    assert client.sent[0][2] is True


@pytest.mark.asyncio
async def test_non_numeric_chat_id_in_config_sends_nowhere():
    client = FakeClient()
    ch = TelegramChannel(client_factory=lambda: client)
    assert await ch._resolve_chats({"chat_id": "not-a-number"}, "t1") == []


def test_format_is_plain_text_so_markdown_in_content_cannot_break_it():
    """Telegram 400s on unbalanced Markdown; plain text has no such failure."""
    text = TelegramChannel._format("critical", "cost_alert: *90%* of _budget_", None, None)
    assert "*90%*" in text and "_budget_" in text


def test_format_includes_severity_details_and_attribution():
    text = TelegramChannel._format("important", "Title", "Body here", "cost_watcher")
    assert text.startswith("🟠 Important Title")
    assert "Body here" in text
    assert text.endswith("— cost_watcher")


def test_format_omits_placeholder_watcher_names():
    for placeholder in ("unknown", "queued"):
        assert "—" not in TelegramChannel._format("info", "T", None, placeholder)


# ── Brief delivery ────────────────────────────────────────


class RecordingChannel:
    def __init__(self):
        self.calls: list[dict] = []

    async def send(self, **kwargs):
        self.calls.append(kwargs)
        return True


def _session_factory(row):
    @asynccontextmanager
    async def factory():
        class S:
            async def execute(self, *_a, **_k):
                return SimpleNamespace(scalar_one_or_none=lambda: row)

        yield S()

    return factory


@pytest.mark.asyncio
async def test_brief_delivery_sends_the_stored_body():
    channel = RecordingChannel()
    handler = TelegramDeliveryHandler(
        session_factory=_session_factory(SimpleNamespace(body="Three things today")),
        channel=channel,
    )
    await handler._on_brief(
        SimpleNamespace(
            payload={
                "tenant_id": "t1",
                "title": "Daily brief",
                "notification_id": "0f6c4b1e-0000-4000-8000-000000000000",
            }
        )
    )
    assert len(channel.calls) == 1
    assert channel.calls[0]["tenant_id"] == "t1"
    assert channel.calls[0]["details"] == "Three things today"
    # Silent tier: the brief cron fires at 03:00 UTC.
    assert channel.calls[0]["severity"] == "info"


@pytest.mark.asyncio
async def test_brief_delivery_ignores_events_without_a_tenant():
    channel = RecordingChannel()
    handler = TelegramDeliveryHandler(session_factory=_session_factory(None), channel=channel)
    await handler._on_brief(SimpleNamespace(payload={"title": "x"}))
    assert channel.calls == []


@pytest.mark.asyncio
async def test_brief_delivery_survives_a_send_failure():
    """Delivery must never propagate: the brief itself is already committed."""

    class Boom:
        async def send(self, **kwargs):
            raise RuntimeError("telegram down")

    handler = TelegramDeliveryHandler(session_factory=_session_factory(None), channel=Boom())
    await handler._on_brief(SimpleNamespace(payload={"tenant_id": "t1", "title": "x"}))


@pytest.mark.asyncio
async def test_subscribe_is_idempotent():
    handler = TelegramDeliveryHandler(session_factory=_session_factory(None))
    handler.subscribe()
    handler.subscribe()
    assert handler._subscribed is True
