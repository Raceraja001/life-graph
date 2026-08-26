"""Telegram notification delivery against a real database.

The unit tests fake ``_resolve_chats``; these exercise the real one, because
which chats a notification reaches is a tenant boundary enforced by a query,
not by a branch. Also covers the NotificationEngine dispatch branch, which the
spec flags as easy to forget — registering the channel class is necessary but
not sufficient.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import delete

from life_graph.models.db import TelegramBinding
from life_graph.storage.database import async_session
from life_graph.watchers.channels.telegram_channel import TelegramChannel
from life_graph.watchers.notification_engine import NotificationEngine
from tests.integration.conftest import skip_on_db_error

TENANT = "test_tgchan_tenant"
OTHER_TENANT = "test_tgchan_other"


class FakeClient:
    def __init__(self):
        self.configured = True
        self.sent: list[tuple[int, str, bool]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send_message(self, chat_id, text, *, disable_notification=False, **kw):
        self.sent.append((chat_id, text, disable_notification))
        return [{"message_id": 1}]


async def _bind(chat_id: int, tenant: str, *, active: bool = True) -> None:
    async with async_session() as session:
        session.add(
            TelegramBinding(tenant_id=tenant, chat_id=chat_id, chat_type="private", active=active)
        )
        await session.commit()


@pytest_asyncio.fixture
async def clean_slate():
    async def _wipe():
        async with async_session() as session:
            await session.execute(
                delete(TelegramBinding).where(TelegramBinding.tenant_id.in_([TENANT, OTHER_TENANT]))
            )
            await session.commit()

    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
@skip_on_db_error
async def test_resolves_every_active_binding_for_the_tenant(clean_slate):
    await _bind(6410001, TENANT)
    await _bind(6410002, TENANT)
    client = FakeClient()
    ok = await TelegramChannel(client_factory=lambda: client).send(
        {}, TENANT, "critical", "Disk full"
    )
    assert ok is True
    assert sorted(c for c, _, _ in client.sent) == [6410001, 6410002]


@pytest.mark.asyncio
@skip_on_db_error
async def test_never_sends_to_another_tenants_chat(clean_slate):
    """The whole point of the binding table: one tenant's alert cannot leak."""
    await _bind(6410003, TENANT)
    await _bind(6410004, OTHER_TENANT)
    client = FakeClient()
    await TelegramChannel(client_factory=lambda: client).send({}, TENANT, "critical", "Secret")
    assert [c for c, _, _ in client.sent] == [6410003]


@pytest.mark.asyncio
@skip_on_db_error
async def test_revoked_bindings_stop_receiving(clean_slate):
    """Revoking sets active=False rather than deleting; delivery must honour it."""
    await _bind(6410005, TENANT, active=False)
    client = FakeClient()
    assert (
        await TelegramChannel(client_factory=lambda: client).send({}, TENANT, "critical", "X")
        is False
    )
    assert client.sent == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_tenant_with_no_binding_gets_nothing(clean_slate):
    client = FakeClient()
    assert (
        await TelegramChannel(client_factory=lambda: client).send({}, TENANT, "info", "X") is False
    )


@pytest.mark.asyncio
@skip_on_db_error
async def test_engine_dispatches_telegram_with_the_tenant(clean_slate):
    """Guards the `elif channel_type == 'telegram'` branch in NotificationEngine.send.

    Registering the class in _ensure_channels() is not enough — without the
    dispatch branch this falls through to 'Unsupported channel type' and the
    notification is silently dropped.
    """
    await _bind(6410006, TENANT)
    client = FakeClient()
    engine = NotificationEngine()
    await engine._ensure_channels()
    engine._channels["telegram"] = TelegramChannel(client_factory=lambda: client)

    ok = await engine.send(
        TENANT,
        "telegram",
        {"severity": "critical", "title": "Budget exceeded", "watcher_name": "cost_watcher"},
        config={},
    )
    assert ok is True
    assert client.sent and client.sent[0][0] == 6410006
    assert "Budget exceeded" in client.sent[0][1]


@pytest.mark.asyncio
@skip_on_db_error
async def test_engine_renders_dict_details_without_crashing(clean_slate):
    """WatchEvent.details is JSONB and genuinely holds dicts as well as strings."""
    await _bind(6410007, TENANT)
    client = FakeClient()
    engine = NotificationEngine()
    await engine._ensure_channels()
    engine._channels["telegram"] = TelegramChannel(client_factory=lambda: client)

    ok = await engine.send(
        TENANT,
        "telegram",
        {"severity": "info", "title": "T", "details": {"spend": 91.2}, "watcher_name": "w"},
        config={},
    )
    assert ok is True
    assert "spend" in client.sent[0][1]
