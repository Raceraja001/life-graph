"""Dispatch for one inbound Telegram message.

This is the security-relevant half of the bridge. Every message arrives with a
chat id and no authentication, so the order of checks here matters:

1. Private chats only. A group chat can contain anyone.
2. ``/start`` is the only thing an *unbound* chat may do. Everything else from
   an unknown chat is refused without disclosing whether the bot is in use.
3. A bound chat is rate limited, so a compromised or runaway client cannot
   flood the capture spine.
4. Plain text goes to the capture spine under the tenant the binding names.

Everything after the binding check runs inside a ``tenant_scope`` so that the
storage layer — which reads the tenant from a contextvar rather than taking it
as an argument — cannot serve one chat from another chat's tenant. The poller
handles every chat sequentially in one asyncio task, so an unrestored contextvar
would persist into the next update.

Command handling lives in :mod:`commands`; this module keeps the security
ordering and owns the one outbound path, so that redaction is applied in a
single place rather than per-handler.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.config import settings
from life_graph.core.events import event_bus
from life_graph.core.redaction import redact_secrets
from life_graph.core.tenant import tenant_scope
from life_graph.core.trust import TrustTier
from life_graph.integrations.telegram import commands as tg_commands
from life_graph.integrations.telegram.client import TelegramClient, TelegramError
from life_graph.services.capture import CaptureService
from life_graph.services.telegram_binding import PairingError, TelegramBindingService

logger = logging.getLogger(__name__)

# Telegram caps a message at 4096 chars, so this is a backstop for captions and
# concatenations rather than a real limit — it keeps one message from becoming
# an outsized memory.
MAX_CAPTURE_CHARS = 10_000

_RATE_KEY = "telegram:rate:{chat_id}"

_UNBOUND_REPLY = (
    "This chat isn't linked to an account.\n\n"
    "Generate a pairing code from your Life Graph dashboard, then send:\n"
    "/start <code>"
)

_HELP = (
    "Life Graph\n\n"
    "Send any message to save it as a memory.\n\n"
    "/help — this message\n"
    "/recall <query> — search your memories\n"
    "/pending — items awaiting your decision\n"
    "/unlink — disconnect this chat"
)


async def handle_update(update: dict[str, Any], session: AsyncSession) -> None:
    """Entry point for one ``getUpdates`` item. Never raises for bad input.

    The poller advances its offset on return, so swallowing a malformed update
    is deliberate: one unparseable message must not wedge the queue forever.
    """
    message = update.get("message")
    if not isinstance(message, dict):
        return  # Not a message — edits, reactions and the rest are not subscribed.
    try:
        await handle_message(message, session)
    except TelegramError as exc:
        # Failing to reply is not a reason to reprocess the message.
        logger.warning("telegram: could not reply — %s", exc.description)


async def handle_message(msg: dict[str, Any], session: AsyncSession) -> None:
    """Route one message. See the module docstring for the order of checks."""
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    if chat.get("type") != "private":
        # v1 is private chats only. Silence rather than an explanation: the bot
        # should not announce itself to a group it was added to.
        return

    text = (msg.get("text") or msg.get("caption") or "").strip()
    service = TelegramBindingService(session)

    if text.startswith("/start"):
        await _handle_start(chat, text, service, session)
        return

    tenant_id = await service.tenant_for_chat(chat_id)
    if tenant_id is None:
        # Same reply whether or not a binding ever existed — it discloses
        # nothing to someone who guessed at the bot.
        await _reply(chat_id, _UNBOUND_REPLY)
        return

    if not await _within_rate_limit(chat_id):
        logger.warning("telegram: rate limit hit for chat %s", chat_id)
        await _reply(chat_id, "Slow down a moment — too many messages. Try again shortly.")
        return

    await service.touch(chat_id)

    # Past this point the message has a tenant, so give the storage layer one.
    with tenant_scope(tenant_id, "telegram"):
        if text.startswith("/"):
            await _handle_command(chat_id, tenant_id, text, session)
            return

        if not text:
            # A sticker, photo without a caption, or voice note. Phase 5 routes
            # these through the multimodal path; until then, say so rather than
            # dropping them silently.
            await _reply(chat_id, "I can only read text messages so far.")
            return

        await _capture(msg, chat_id, tenant_id, text, session)


# ── Pairing ───────────────────────────────────────────────────────


async def _handle_start(
    chat: dict[str, Any], text: str, service: TelegramBindingService, session: AsyncSession
) -> None:
    chat_id = chat["id"]
    parts = text.split(maxsplit=1)
    code = parts[1].strip() if len(parts) > 1 else ""

    if not code:
        await _reply(
            chat_id,
            "Welcome to Life Graph.\n\n"
            "Generate a pairing code from your dashboard, then send:\n"
            "/start <code>",
        )
        return

    try:
        binding = await service.redeem_code(
            code,
            chat_id,
            chat_type=chat.get("type", "private"),
            username=chat.get("username"),
        )
    except PairingError as exc:
        await session.rollback()
        # PairingError messages are written to be shown to the user and are
        # deliberately uniform across "wrong", "expired" and "already used".
        await _reply(chat_id, str(exc))
        return

    await session.commit()
    logger.info("telegram: chat %s bound to tenant %s", chat_id, binding.tenant_id)
    await _reply(chat_id, "Linked. Send me anything and I'll remember it.\n\n" + _HELP)


# ── Capture ───────────────────────────────────────────────────────


async def _capture(
    msg: dict[str, Any],
    chat_id: int,
    tenant_id: str,
    text: str,
    session: AsyncSession,
) -> None:
    """Hand a plain message to the capture spine under the bound tenant."""
    # A forwarded message is somebody else's words. The "telegram" surface is
    # trusted because the user paired the chat and is typing into it; that
    # argument does not extend to content they merely relayed, so the tier is
    # set explicitly here rather than derived from the surface.
    forwarded = bool(
        msg.get("forward_origin") or msg.get("forward_from") or msg.get("forward_date")
    )
    tier = TrustTier.EXTERNAL if forwarded else None

    svc = CaptureService(session, event_bus)
    await svc.ingest(
        tenant_id=tenant_id,
        surface="telegram",
        content=text[:MAX_CAPTURE_CHARS],
        modality="text",
        trust_tier=tier,
        properties={
            "chat_id": chat_id,
            "message_id": msg.get("message_id"),
            "forwarded": forwarded,
        },
    )
    await session.commit()

    await _reply(
        chat_id,
        "Saved — from a forwarded message, so it's filed as external." if forwarded else "Saved.",
    )


# ── Commands ──────────────────────────────────────────────────────


async def _handle_command(chat_id: int, tenant_id: str, text: str, session: AsyncSession) -> None:
    command = text.split()[0].lower().lstrip("/").split("@")[0]

    if command == "help":
        await _reply(chat_id, _HELP)
        return
    if command == "unlink":
        await _reply(
            chat_id,
            "Unlink this chat from the dashboard's integrations page. "
            "Doing it there proves it's you.",
        )
        return
    if command in {"recall", "pending", "approve", "reject", "yes", "confirm"}:
        await tg_commands.handle(chat_id, tenant_id, text, session, _reply)
        return

    await _reply(chat_id, f"Unknown command: /{command}\n\n{_HELP}")


# ── Helpers ───────────────────────────────────────────────────────


async def _reply(chat_id: int, text: str) -> None:
    """Best-effort reply. A failure to reply must not fail the message.

    Every outbound message is redacted here rather than in each handler:
    Telegram retains chat history on its own servers indefinitely and ordinary
    cloud chats are not end-to-end encrypted, so a recalled memory containing
    an API key would otherwise be copied somewhere we cannot delete it. One
    choke point means a new command cannot forget to do it.
    """
    async with TelegramClient() as client:
        if not client.configured:
            return
        await client.send_message(chat_id, redact_secrets(text))


async def _within_rate_limit(chat_id: int) -> bool:
    """Fixed-window counter per chat, per minute.

    Fails *open* when Redis is down. The limit protects the capture spine from
    a runaway client; it is not an authorisation control, and the binding check
    above already ran. Refusing the user's own messages because a cache is
    unavailable would be the worse failure.
    """
    from life_graph.storage.redis import get_redis

    limit = settings.telegram_rate_limit_per_min
    if limit <= 0:
        return True

    redis = get_redis()
    if redis is None:
        return True

    try:
        key = _RATE_KEY.format(chat_id=chat_id)
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)
        return int(count) <= limit
    except Exception:  # noqa: BLE001 - see docstring: degrade open, never lock the user out
        logger.warning("telegram: rate limit check failed, allowing through", exc_info=True)
        return True
