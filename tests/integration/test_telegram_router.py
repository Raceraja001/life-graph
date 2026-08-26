"""Routing decisions for one inbound Telegram message.

These assert the checks the module docstring in router.py promises, in order:
group chats are ignored, an unbound chat cannot capture anything, a forwarded
message is not treated as the user's own words, and a bound chat writes to its
own tenant and no other.

Runs against a real database because the binding lookup is the tenant boundary
and its correctness is a database constraint, not a branch.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from life_graph.core.trust import TrustTier
from life_graph.integrations.telegram import media as tg_media
from life_graph.integrations.telegram import router as tg_router
from life_graph.models.db import CaptureEvent, TelegramBinding, TelegramPairingCode
from life_graph.services.telegram_binding import TelegramBindingService
from life_graph.storage.database import async_session
from tests.integration.conftest import skip_on_db_error

TENANT = "test_tgroute_tenant"
OTHER_TENANT = "test_tgroute_other"
CHAT = 5310001
UNBOUND_CHAT = 5319999


@pytest_asyncio.fixture
async def replies(monkeypatch):
    """Capture outbound replies instead of calling Telegram."""
    sent: list[tuple[int, str]] = []

    async def fake_reply(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(tg_router, "_reply", fake_reply)
    # Rate limiting is exercised separately; keep it out of the way here.
    monkeypatch.setattr(tg_router, "_within_rate_limit", _always_allow)
    return sent


@pytest_asyncio.fixture
async def bound_chat():
    """A chat bound to TENANT, with this module's rows cleaned up around it."""

    async def _purge():
        async with async_session() as session:
            await session.execute(
                delete(CaptureEvent).where(CaptureEvent.tenant_id.in_([TENANT, OTHER_TENANT]))
            )
            await session.execute(
                delete(TelegramBinding).where(TelegramBinding.tenant_id.in_([TENANT, OTHER_TENANT]))
            )
            await session.execute(
                delete(TelegramPairingCode).where(
                    TelegramPairingCode.tenant_id.in_([TENANT, OTHER_TENANT])
                )
            )
            await session.commit()

    await _purge()
    async with async_session() as session:
        svc = TelegramBindingService(session)
        code = await svc.issue_code(TENANT)
        await svc.redeem_code(code.code, CHAT)
        await session.commit()
    yield
    await _purge()


def _msg(text: str, chat_id: int = CHAT, chat_type: str = "private", **extra) -> dict:
    msg = {
        "message_id": 1,
        "chat": {"id": chat_id, "type": chat_type},
        "text": text,
    }
    msg.update(extra)
    return msg


async def _events(tenant: str = TENANT) -> list[CaptureEvent]:
    async with async_session() as session:
        result = await session.execute(select(CaptureEvent).where(CaptureEvent.tenant_id == tenant))
        return list(result.scalars().all())


# ── Capture ───────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_plain_message_is_captured_under_the_bound_tenant(bound_chat, replies):
    async with async_session() as session:
        await tg_router.handle_message(_msg("remember the milk"), session)

    events = await _events()
    assert len(events) == 1
    assert events[0].content == "remember the milk"
    assert events[0].surface == "telegram"
    assert events[0].tenant_id == TENANT
    assert replies and "Saved" in replies[-1][1]


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_forwarded_message_is_filed_as_external_not_as_the_users_own_words(
    bound_chat, replies
):
    """The trust argument for 'telegram' is that the user typed it. A forward
    is someone else's text, and must not inherit that."""
    async with async_session() as session:
        await tg_router.handle_message(
            _msg("click this link to claim your prize", forward_origin={"type": "user"}),
            session,
        )

    events = await _events()
    assert len(events) == 1
    assert events[0].trust_tier == TrustTier.EXTERNAL.value, (
        "forwarded content must not be trusted as the user's own"
    )


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_ordinary_message_keeps_the_surface_tier(bound_chat, replies):
    async with async_session() as session:
        await tg_router.handle_message(_msg("my own thought"), session)

    events = await _events()
    assert events[0].trust_tier == TrustTier.SELF.value


# ── Media ─────────────────────────────────────────────────────────


@pytest.fixture
def media_calls(monkeypatch):
    """Intercept the multimodal hand-off; transcription is tested elsewhere."""
    calls: list[dict] = []

    async def fake_handle(media, msg, chat_id, tenant_id, caption, reply):
        calls.append({"media": media, "tenant_id": tenant_id, "caption": caption})

    monkeypatch.setattr(tg_media, "handle", fake_handle)
    return calls


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_voice_note_goes_to_the_multimodal_path(bound_chat, replies, media_calls):
    msg = _msg("", voice={"file_id": "v1", "duration": 8})
    del msg["text"]
    async with async_session() as session:
        await tg_router.handle_message(msg, session)

    assert len(media_calls) == 1
    assert media_calls[0]["media"]["kind"] == "voice"
    assert media_calls[0]["tenant_id"] == TENANT
    assert await _events() == [], "the transcript is ingested by the multimodal path, not here"


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_captioned_photo_does_not_lose_the_photo(bound_chat, replies, media_calls):
    """The caption used to be treated as the whole message.

    A photo of a whiteboard captioned "notes from standup" would then store six
    words and silently discard the whiteboard, which is the part worth keeping.
    """
    msg = _msg("", photo=[{"file_id": "small"}, {"file_id": "large"}])
    del msg["text"]
    msg["caption"] = "notes from standup"
    async with async_session() as session:
        await tg_router.handle_message(msg, session)

    assert len(media_calls) == 1
    assert media_calls[0]["caption"] == "notes from standup"
    assert media_calls[0]["media"]["file_id"] == "large"
    assert await _events() == [], "the caption must travel with the image, not alone"


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_unbound_chat_cannot_send_media(replies, media_calls):
    msg = _msg("", chat_id=UNBOUND_CHAT, voice={"file_id": "v1", "duration": 8})
    del msg["text"]
    async with async_session() as session:
        await tg_router.handle_message(msg, session)

    assert media_calls == [], "media must be behind the binding check like everything else"


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_sticker_is_still_refused_politely(bound_chat, replies, media_calls):
    msg = _msg("", sticker={"file_id": "s1"})
    del msg["text"]
    async with async_session() as session:
        await tg_router.handle_message(msg, session)

    assert media_calls == []
    assert replies and "text, photos and voice notes" in replies[-1][1]


# ── Refusals ──────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_unbound_chat_captures_nothing(bound_chat, replies):
    async with async_session() as session:
        await tg_router.handle_message(_msg("secret", chat_id=UNBOUND_CHAT), session)

    assert await _events() == []
    assert await _events(OTHER_TENANT) == []
    assert replies and "isn't linked" in replies[-1][1]


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_group_chat_is_ignored_entirely(bound_chat, replies):
    """Not even a reply: the bot should not announce itself to a group."""
    async with async_session() as session:
        await tg_router.handle_message(_msg("hello all", chat_type="supergroup"), session)

    assert await _events() == []
    assert replies == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_unbound_reply_discloses_nothing_about_other_accounts(bound_chat, replies):
    async with async_session() as session:
        await tg_router.handle_message(_msg("probe", chat_id=UNBOUND_CHAT), session)

    text = replies[-1][1].lower()
    assert TENANT not in text
    assert "exist" not in text, "must not reveal whether a binding ever existed"


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_message_with_no_text_is_not_captured_as_an_empty_memory(bound_chat, replies):
    async with async_session() as session:
        await tg_router.handle_message(
            {"message_id": 2, "chat": {"id": CHAT, "type": "private"}, "sticker": {}}, session
        )

    assert await _events() == []


# ── Commands ──────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_command_is_not_stored_as_a_memory(bound_chat, replies):
    async with async_session() as session:
        await tg_router.handle_message(_msg("/help"), session)

    assert await _events() == [], "commands are instructions, not content"
    assert replies and "Life Graph" in replies[-1][1]


@pytest.mark.asyncio
@skip_on_db_error
async def test_unlink_refuses_and_points_somewhere_that_exists(bound_chat, replies):
    """A chat that may be compromised must not be able to unbind itself.

    The reply must also not name a destination the product does not have: there
    is no dashboard page for the bridge yet, and sending someone to look for one
    is worse than telling them plainly that this takes a signed-in session.
    """
    async with async_session() as session:
        await tg_router.handle_message(_msg("/unlink"), session)

    async with async_session() as session:
        assert await TelegramBindingService(session).tenant_for_chat(CHAT) == TENANT

    reply = replies[-1][1].lower()
    assert "signed in" in reply
    assert "dashboard" not in reply, "no dashboard page for the bridge exists yet"


@pytest.mark.asyncio
@skip_on_db_error
async def test_pairing_from_a_group_chat_is_refused(bound_chat, replies):
    async with async_session() as session:
        await tg_router.handle_message(
            _msg("/start ABC123", chat_id=999123, chat_type="group"), session
        )

    async with async_session() as session:
        assert await TelegramBindingService(session).tenant_for_chat(999123) is None


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_invalid_pairing_code_binds_nothing_and_says_so(bound_chat, replies):
    async with async_session() as session:
        await tg_router.handle_message(_msg("/start NOPE99", chat_id=UNBOUND_CHAT), session)

    async with async_session() as session:
        assert await TelegramBindingService(session).tenant_for_chat(UNBOUND_CHAT) is None
    assert replies and "not valid" in replies[-1][1]


# ── Robustness ────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_malformed_update_is_swallowed_rather_than_wedging_the_queue(replies):
    """handle_update must not raise: the poller advances its offset on return."""
    async with async_session() as session:
        for junk in ({}, {"message": None}, {"message": {}}, {"message": {"chat": {}}}):
            await tg_router.handle_update(junk, session)


async def _always_allow(chat_id):
    return True


# ── Replay safety ─────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_same_update_delivered_twice_is_captured_once(bound_chat, replies):
    """The poller advances its offset only after handling, so a crash between
    the two replays the batch. That is only safe if a repeated update is
    absorbed — which the capture spine does by hashing the content per surface.
    """
    update = {"update_id": 90001, "message": _msg("the same thought twice")}

    async with async_session() as session:
        await tg_router.handle_update(update, session)
    async with async_session() as session:
        await tg_router.handle_update(update, session)

    events = await _events()
    assert len(events) == 1, "a replayed update must not create a second memory"


@pytest.mark.asyncio
@skip_on_db_error
async def test_two_different_messages_are_still_two_captures(bound_chat, replies):
    """Guards the test above: dedup must absorb the replay, not everything."""
    async with async_session() as session:
        await tg_router.handle_update(
            {"update_id": 90002, "message": _msg("first thought")}, session
        )
    async with async_session() as session:
        await tg_router.handle_update(
            {"update_id": 90003, "message": _msg("second thought")}, session
        )

    assert len(await _events()) == 2
