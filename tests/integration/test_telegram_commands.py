"""Command routing through the real router, against a real database.

The unit tests cover each command's decisions in isolation. These cover the
two things only the router can guarantee: that a command runs under the right
tenant, and that nothing leaves for Telegram unredacted.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import delete

from life_graph.core.tenant import get_current_tenant_id
from life_graph.integrations.telegram import commands as tg_commands
from life_graph.integrations.telegram import router as tg_router
from life_graph.models.db import TelegramBinding
from life_graph.storage.database import async_session
from tests.integration.conftest import skip_on_db_error

TENANT = "test_tgcmd_tenant"
OTHER_TENANT = "test_tgcmd_other"
CHAT = 7710001
OTHER_CHAT = 7710002


async def _bind(chat_id: int, tenant: str) -> None:
    async with async_session() as session:
        session.add(
            TelegramBinding(tenant_id=tenant, chat_id=chat_id, chat_type="private", active=True)
        )
        await session.commit()


@pytest_asyncio.fixture
async def bound(monkeypatch):
    async def _wipe():
        async with async_session() as session:
            await session.execute(
                delete(TelegramBinding).where(TelegramBinding.tenant_id.in_([TENANT, OTHER_TENANT]))
            )
            await session.commit()

    await _wipe()
    await _bind(CHAT, TENANT)
    await _bind(OTHER_CHAT, OTHER_TENANT)

    sent: list[tuple[int, str]] = []

    async def fake_reply(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(tg_router, "_reply", fake_reply)

    async def always_allow(_chat_id):
        return True

    monkeypatch.setattr(tg_router, "_within_rate_limit", always_allow)
    yield sent
    await _wipe()


def _update(chat_id: int, text: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_command_runs_under_the_chats_own_tenant(bound, monkeypatch):
    """The storage layer reads the tenant from a contextvar, not an argument."""
    seen: list[str] = []

    async def spy(chat_id, tenant_id, text, session, reply):
        seen.append(get_current_tenant_id())

    monkeypatch.setattr(tg_commands, "handle", spy)

    async with async_session() as session:
        await tg_router.handle_update(_update(CHAT, "/pending"), session)
        await tg_router.handle_update(_update(OTHER_CHAT, "/pending"), session)

    assert seen == [TENANT, OTHER_TENANT]


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_tenant_does_not_leak_into_the_next_update(bound, monkeypatch):
    """Both chats are handled in one asyncio task, so one context.

    Asserts the context is left exactly as it was found rather than asserting
    it is empty: this suite shares a task with everything else pytest has run,
    so "empty" is not a property this test can rely on — and demanding it would
    make the test pass or fail on unrelated ordering.
    """
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context

    before = get_current_tenant_id() if has_tenant_context() else None

    async def spy(chat_id, tenant_id, text, session, reply):
        # Proves the scope really is active while the command runs, so the
        # "unchanged after" assertion below is about restoration, not a no-op.
        assert get_current_tenant_id() == tenant_id

    monkeypatch.setattr(tg_commands, "handle", spy)

    async with async_session() as session:
        await tg_router.handle_update(_update(CHAT, "/pending"), session)
        await tg_router.handle_update(_update(OTHER_CHAT, "/pending"), session)

    after = get_current_tenant_id() if has_tenant_context() else None
    assert after == before
    assert after not in (TENANT, OTHER_TENANT)


@pytest.mark.asyncio
@skip_on_db_error
async def test_pending_reaches_the_command_module(bound):
    async with async_session() as session:
        await tg_router.handle_update(_update(CHAT, "/pending"), session)
    assert bound, "the command produced no reply"
    assert "waiting" in bound[0][1].lower()


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_unbound_chat_cannot_run_commands(bound):
    async with async_session() as session:
        await tg_router.handle_update(_update(7719999, "/pending"), session)
    assert len(bound) == 1
    assert "isn't linked" in bound[0][1]


@pytest.mark.asyncio
@skip_on_db_error
async def test_every_outbound_message_is_redacted(monkeypatch):
    """Telegram keeps chat history indefinitely; a leaked key cannot be recalled."""
    sent: list[str] = []

    class FakeClient:
        configured = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def send_message(self, chat_id, text, **kw):
            sent.append(text)
            return [{"message_id": 1}]

    monkeypatch.setattr(tg_router, "TelegramClient", FakeClient)
    await tg_router._reply(CHAT, "here it is: api_key=sk-abcdef1234567890abcdef1234567890")

    assert sent
    assert "sk-abcdef1234567890abcdef1234567890" not in sent[0]
    assert "REDACTED" in sent[0]
