"""Management API for the Telegram bridge.

Four operations, all scoped to the calling tenant: mint a pairing code, list
the chats that redeemed one, revoke a chat, and report whether the bridge is
actually running.

The pairing code is the whole security story. An inbound Telegram update
carries a chat id and nothing else, so a chat becomes a tenant's only by
redeeming a code that an authenticated caller asked for here. That is why
``/pair`` is the only write and why revocation lives here too: undoing a
binding must require proof of identity that a message in the chat cannot give.

``/status`` is the odd one out. The poller runs in the ARQ worker process, not
in the API process serving this request, so there is no object to ask — it
reports what the poller published to Redis. See :func:`poller_state`.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select

from life_graph.api.openapi_examples import (
    TELEGRAM_BINDING_LIST,
    TELEGRAM_PAIR_CREATED,
    TELEGRAM_STATUS,
)
from life_graph.api.responses import success_response
from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.integrations.telegram.client import TelegramClient
from life_graph.integrations.telegram.poller import (
    HEARTBEAT_KEY,
    LAST_UPDATE_KEY,
    LEASE_KEY,
)
from life_graph.models.db import TelegramBinding
from life_graph.services.telegram_binding import TelegramBindingService
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/telegram", tags=["telegram"])

# The bot's @handle never changes for a given token, and the pairing screen
# needs it on every load to tell the user which bot to open. Cached per process
# so a dashboard visit is not a round trip to Telegram.
_bot_username_cache: str | None = None


@router.post(
    "/pair",
    status_code=status.HTTP_201_CREATED,
    summary="Mint a pairing code for a Telegram chat",
    responses=TELEGRAM_PAIR_CREATED,
)
async def create_pairing_code(tenant_id: str = Depends(get_current_tenant_id)):
    """Issue a short-lived, single-use code to send to the bot as ``/start <code>``.

    Codes are not listed anywhere and cannot be retrieved after this response —
    losing one costs a second call, whereas making them readable later would
    turn any read of this API into a way to bind a chat.
    """
    async with async_session() as session:
        code = await TelegramBindingService(session).issue_code(tenant_id)
        await session.commit()
        payload = {
            "code": code.code,
            "expires_at": code.expires_at.isoformat(),
            "bot_username": await _bot_username(),
        }
    return success_response(data=payload)


@router.get(
    "/bindings",
    summary="List the Telegram chats linked to this tenant",
    responses=TELEGRAM_BINDING_LIST,
)
async def list_bindings(tenant_id: str = Depends(get_current_tenant_id)):
    """Active bindings, newest first. Revoked ones are not shown."""
    async with async_session() as session:
        bindings = await TelegramBindingService(session).list_bindings(tenant_id)
    return success_response(data=[_as_dict(b) for b in bindings])


@router.delete(
    "/bindings/{binding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a Telegram binding",
    response_class=Response,
)
async def revoke_binding(binding_id: uuid.UUID, tenant_id: str = Depends(get_current_tenant_id)):
    """Disconnect one chat. The chat can pair again with a fresh code.

    A binding belonging to another tenant is reported as missing rather than
    forbidden: the id is the only thing the caller supplied, and confirming
    that it exists would leak that some other tenant has it.
    """
    async with async_session() as session:
        revoked = await TelegramBindingService(session).revoke(tenant_id, binding_id)
        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Telegram binding {binding_id} not found",
            )
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/status",
    summary="Report whether the Telegram bridge is running",
    responses=TELEGRAM_STATUS,
)
async def bridge_status(tenant_id: str = Depends(get_current_tenant_id)):
    """Whether the bridge is configured, whether it is polling, and since when.

    A bridge that stops polling fails silently by design — messages queue on
    Telegram's side and the user simply never gets a reply — so this endpoint
    exists to make that visible.
    """
    async with async_session() as session:
        bound = await session.scalar(
            select(func.count())
            .select_from(TelegramBinding)
            .where(
                TelegramBinding.tenant_id == tenant_id,
                TelegramBinding.active.is_(True),
            )
        )

    state = await poller_state()
    return success_response(
        data={
            "configured": bool(settings.telegram_bot_token),
            "bound_chats": int(bound or 0),
            **state,
        }
    )


# ── Helpers ───────────────────────────────────────────────────────


def _as_dict(binding: TelegramBinding) -> dict:
    return {
        "id": str(binding.id),
        "chat_id": binding.chat_id,
        "chat_type": binding.chat_type,
        "username": binding.username,
        "bound_at": binding.bound_at.isoformat() if binding.bound_at else None,
        "last_seen_at": binding.last_seen_at.isoformat() if binding.last_seen_at else None,
    }


async def poller_state() -> dict:
    """Derive the poller's state from what it published to Redis.

    The poller runs in the ARQ worker; this code runs in the API process. There
    is no in-process object to inspect, and inspecting the one that exists here
    would report ``stopped`` forever — the API never starts a poller.

    So the answer comes from three keys the poller writes:

    * the lease, held by whichever instance is leading;
    * a heartbeat, rewritten every completed poll cycle and expiring with the
      lease, so a wedged leader stops looking alive;
    * the timestamp of the last batch that actually contained something.

    ``standby`` is never returned from here. A standby poller writes nothing —
    it is by definition the instance that failed to take the lease — so from
    outside the worker there is no way to tell a standby from an absence, and
    claiming otherwise would be a guess. The value stays in the vocabulary
    because the worker's own ``poller.status`` does distinguish it.
    """
    if not settings.telegram_bot_token:
        return {"poller": "disabled", "last_poll_at": None, "last_update_at": None}

    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        # No Redis means no way to know, and "stopped" would be a claim rather
        # than an observation — the poller may well be running fine.
        return {"poller": "unknown", "last_poll_at": None, "last_update_at": None}

    try:
        lease = await redis.get(LEASE_KEY)
        heartbeat = await redis.get(HEARTBEAT_KEY)
        last_update = await redis.get(LAST_UPDATE_KEY)
    except Exception:
        logger.warning("telegram: could not read poller state from Redis", exc_info=True)
        return {"poller": "unknown", "last_poll_at": None, "last_update_at": None}

    return {
        "poller": "leading" if lease else "stopped",
        "last_poll_at": _text(heartbeat),
        "last_update_at": _text(last_update),
    }


def _text(value: object) -> str | None:
    """Redis may hand back bytes or str depending on the client's decoding."""
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else str(value)


async def _bot_username() -> str | None:
    """The bot's @handle, or ``None`` when it cannot be determined.

    Never raises: the pairing code is what matters, and a missing handle makes
    the dashboard's instructions less convenient rather than wrong.
    """
    global _bot_username_cache
    if _bot_username_cache is not None:
        return _bot_username_cache
    if not settings.telegram_bot_token:
        return None
    try:
        async with TelegramClient() as client:
            me = await client.get_me()
    except Exception:  # noqa: BLE001 - see docstring: never fail the pairing call
        logger.warning("telegram: getMe failed while issuing a pairing code", exc_info=True)
        return None
    _bot_username_cache = me.get("username")
    return _bot_username_cache
