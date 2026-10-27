"""Jarvis for the phone app (docs/design/12_android_app_plan.md, Phase 1).

Every method here is open to a paired device's token (api/device_access.py,
``DEVICE_PATH_PREFIX``); beyond them it opens only the reviewed allowlist
there. The contract is the app's (life-graph-android docs/PLAN.md):

* ``POST /jarvis/chat`` streams ``{type: token, content}`` events, then
  ``{type: done, conversation_id, route}`` or ``{type: error, message}``.
  It is the dashboard's chat stream (api/kernel.py) with Jarvis as the persona,
  in the app's simpler event shapes. The body is ``{message, shared?,
  conversation_id?}``: ``message`` is what the owner typed, ``shared`` text
  they shared from another app, which Jarvis treats as someone else's words.
  Memory events: ``{type: saved, id, content, pending}`` and
  ``{type: forgotten, id, content}``.
* ``GET /jarvis/conversations`` and ``.../{id}/messages``.
* ``POST /jarvis/voice``: audio in, transcribed on this machine only, answered
  by Jarvis in the same conversation, the reply spoken back as mp3.
* ``POST /jarvis/warm``: the app opened; load the local model in the background.

v3 (docs/PLAN-v3.md): notifications carry ``kind`` and ``actions``, and
``POST /jarvis/notifications/{id}/action`` takes one
(services/notification_actions.py); ``GET /jarvis/brief/latest`` speaks the
newest brief; ``GET /jarvis/reminders`` and ``.../{id}/cancel``. Jarvis's
reminder_set reaches the chat as ``{type: reminded, id, text, at}`` and the
voice reply as ``reminded``.

v4 (docs/PLAN-v4.md, S1): ``GET /jarvis/today`` is the whole Today screen in
one call (services/jarvis_today.py), each part failing on its own; ``POST
/jarvis/bills/{item_id}/paid`` is its "Mark paid". ``GET /jarvis/app/latest``
and ``.../app/download/{file}`` offer the newest APK from ``app_release_dir``.

v4 S2: ``GET /jarvis/plan`` (services/jarvis_plan.py); ``GET
/jarvis/memory/overview``, ``.../memory/search`` and ``/jarvis/entities/{id}``
(services/jarvis_memory.py); ``GET /jarvis/contacts`` and ``.../mail/waiting``
(services/jarvis_inbox.py). The chat stream gains ``{type: card, card}``
events built from tool results (services/jarvis_cards.py), and the voice
reply a ``cards`` list.

Where Jarvis ran (``route``: personal = this PC's model, general = a cloud
model without the personal tools) comes from services/lead.py.

Idempotent sends: chat and voice take an optional ``client_id`` (8-64 of
``[A-Za-z0-9_-]``), the phone outbox's id for one message. WorkManager can
cancel a send the PC already received and send it again; a request whose
client_id matches a top-level Jarvis turn of the last day spawns and captures
nothing new: a finished turn is replayed (chat: ``saved``/``reminded``, one
``token``, ``done``; voice: the stored reply, spoken again), a running one is
waited for and then replayed, and a failed one is run again.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.lead import LEAD
from life_graph.storage.database import async_session

router = APIRouter(prefix="/jarvis", tags=["jarvis"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024
_TERMINAL = {"completed", "failed", "timeout", "cancelled"}
#: A turn that ended in one of these is run again when its message is resent.
_RETRY = {"failed", "timeout", "cancelled"}
#: The phone outbox's id for one message (the app's contract).
CLIENT_ID_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"
_CLIENT_ID = re.compile(CLIENT_ID_PATTERN)
#: How long a resent message is recognised by its client_id.
CLIENT_ID_WINDOW = timedelta(hours=24)
#: Between looks at a turn being waited for.
_POLL_SECONDS = 1.0
_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: uuid.UUID | None = None
    # The phone outbox's id for this message: a resend with the same id
    # replays the turn instead of asking Jarvis twice.
    client_id: str | None = Field(None, pattern=CLIENT_ID_PATTERN)
    # Text the owner shared into the chat from another app (the share sheet, or
    # /jarvis/read-image's words). Someone else wrote it: Jarvis sees it fenced
    # as information (core/trust.py with_shared), it is captured as EXTERNAL,
    # and only `message` counts as the owner asking for anything.
    shared: str | None = Field(None, max_length=8000)
    # A temporary chat (docs/specs/web-chat-wave1.md F5): local only, nothing
    # captured; set on the first turn, kept by the conversation.
    temporary: bool = False


async def _own_conversation(tenant_id: str, conversation_id: uuid.UUID | None) -> None:
    """404 unless the conversation is this tenant's chat with Jarvis."""
    if conversation_id is None:
        return
    from life_graph.models.db import AgentSession

    async with async_session() as session:
        row = await session.get(AgentSession, conversation_id)
    if row is None or row.tenant_id != tenant_id or row.routed_to != LEAD:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")


def _app_event(event: dict, state: dict) -> dict | None:
    """One dashboard chat event in the app's shape, or None to drop it."""
    kind = event.get("type")
    if kind == "start":
        state["conversation_id"] = event.get("session_id")
        return None
    if kind == "route":
        state["route"] = event.get("kind")
        return None
    if kind == "assistant_delta":
        return {"type": "token", "content": event.get("text", "")}
    if kind == "done":
        return {
            "type": "done",
            "conversation_id": state.get("conversation_id"),
            "route": state.get("route"),
        }
    if kind == "error":
        return {"type": "error", "message": event.get("message") or "Something went wrong."}
    if kind == "tool_result" and event.get("name") == "memory_save":
        # What Jarvis just remembered, so the app can show it with an Undo.
        return _saved_event(event.get("result"))
    if kind == "tool_result" and event.get("name") == "memory_forget":
        # What Jarvis just forgot, so a wrong forget does not go unnoticed.
        return _forgotten_event(event.get("result"))
    if kind == "tool_result" and event.get("name") == "reminder_set":
        # The reminder just set, so the app can show it with a Cancel.
        return _reminded_event(event.get("result"))
    return None  # other tool calls, delegations: not shown on the phone


def _reminded_event(result: object) -> dict | None:
    try:
        out = json.loads(str(result or ""))
    except ValueError:
        return None
    if not isinstance(out, dict) or out.get("reminded") is not True or not out.get("id"):
        return None
    return {
        "type": "reminded",
        "id": str(out["id"]),
        "text": str(out.get("text") or ""),
        "at": str(out.get("at") or ""),
    }


def _forgotten_event(result: object) -> dict | None:
    try:
        out = json.loads(str(result or ""))
    except ValueError:
        return None
    if not isinstance(out, dict) or out.get("forgotten") is not True or not out.get("id"):
        return None
    return {"type": "forgotten", "id": str(out["id"]), "content": str(out.get("content") or "")}


def _saved_event(result: object) -> dict | None:
    try:
        out = json.loads(str(result or ""))
    except ValueError:
        return None
    if not isinstance(out, dict) or out.get("saved") is not True or not out.get("id"):
        return None
    return {
        "type": "saved",
        "id": str(out["id"]),
        "content": str(out.get("content") or ""),
        "pending": "status" in out,
    }


async def _capture(
    tenant_id: str,
    text: str,
    kind: str,
    conversation_id: uuid.UUID | None,
    *,
    trust_tier: str | None = None,
    client_id: str | None = None,
) -> None:
    """The owner's own words to Jarvis, to the capture spine: memory is learnt from them.

    Extraction (services/capture_processors.py) keeps only lasting facts, on
    the local model; "remember that…" becomes an active memory at once.
    Text the owner shared from elsewhere passes ``trust_tier="external"``: what
    is learnt from it is marked untrusted and waits for review.
    Best-effort: a failed capture never fails the conversation.
    """
    import logging

    from life_graph.core.events import event_bus
    from life_graph.services.capture import CaptureService

    try:
        async with async_session() as session:
            await CaptureService(session, event_bus).ingest(
                tenant_id=tenant_id,
                surface="jarvis_app",
                content=text[:8000],
                properties={
                    "input": kind,
                    "conversation_id": str(conversation_id) if conversation_id else None,
                    **({"client_id": client_id} if client_id else {}),
                },
                trust_tier=trust_tier,
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        # Never the text: it is personal.
        logging.getLogger(__name__).warning("Jarvis capture failed: %s", exc)


@router.post("/chat", summary="Talk to Jarvis; the reply streams back (SSE)")
async def chat(body: ChatRequest):
    tenant_id = get_current_tenant_id()
    await _own_conversation(tenant_id, body.conversation_id)
    prior = await _turn_for(tenant_id, body.client_id) if body.client_id else None
    if prior is not None and prior.status not in _RETRY:
        # A resend of a message already received: replay it, never ask twice.
        return StreamingResponse(
            _replay_chat(tenant_id, prior, body),
            media_type="text/event-stream",
            headers=_SSE_HEADERS,
        )
    conversation_id = body.conversation_id
    from life_graph.api.kernel import session_is_temporary

    # A temporary chat teaches memory nothing: its words are never captured.
    temporary = body.temporary or await session_is_temporary(tenant_id, conversation_id)
    if prior is None:
        if not temporary:
            await _capture_chat(tenant_id, body)
    elif conversation_id is None:
        # A failed turn run again: its words were captured the first time, and
        # it goes on in the conversation that turn opened.
        conversation_id = prior.session_id
    inner = await _start_chat(body, conversation_id)
    return StreamingResponse(
        _app_frames(inner, tenant_id), media_type="text/event-stream", headers=dict(inner.headers)
    )


async def _capture_chat(tenant_id: str, body: ChatRequest) -> None:
    from life_graph.core.trust import TrustTier

    await _capture(tenant_id, body.message, "text", body.conversation_id, client_id=body.client_id)
    if body.shared and body.shared.strip():
        await _capture(
            tenant_id,
            body.shared,
            "shared",
            body.conversation_id,
            trust_tier=TrustTier.EXTERNAL,
            client_id=body.client_id,
        )


async def _start_chat(body: ChatRequest, conversation_id: uuid.UUID | None):
    """The dashboard's chat stream (api/kernel.py) for one turn with Jarvis."""
    from life_graph.api.dependencies import get_persona_service, get_process_manager
    from life_graph.api.kernel import ChatStreamRequest, chat_stream

    return await chat_stream(
        ChatStreamRequest(
            message=body.message,
            target_agent=LEAD,
            session_id=conversation_id,
            shared=body.shared,
            client_id=body.client_id,
            temporary=body.temporary,
        ),
        pm=get_process_manager(),
        personas=get_persona_service(),
    )


async def _app_frames(inner, tenant_id: str | None = None):
    """The dashboard stream's frames, in the app's event shapes, each tool
    result's answer cards after its own event (services/jarvis_cards.py)."""
    state: dict = {}
    async for chunk in inner.body_iterator:
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        for frame in text.split("\n\n"):
            if frame.startswith(":"):
                yield frame + "\n\n"  # heartbeat
                continue
            if not frame.startswith("data: "):
                continue
            try:
                event = json.loads(frame[6:])
            except ValueError:
                continue
            out = _app_event(event, state)
            if out is not None:
                yield f"data: {json.dumps(out)}\n\n"
            for card in await _card_events(event, state, tenant_id):
                yield f"data: {json.dumps(card)}\n\n"


async def _local_only(state: dict, tenant_id: str | None) -> set[str] | None:
    """The tenant's local_only account names, read once per stream (None: unknown)."""
    from life_graph.services import jarvis_cards

    if "local_only" not in state:
        state["local_only"] = (
            await jarvis_cards.local_only_accounts(tenant_id) if tenant_id else None
        )
    return state["local_only"]


async def _card_events(event: dict, state: dict, tenant_id: str | None) -> list[dict]:
    """``{type: card, card}`` for each card a tool result makes; none otherwise."""
    from life_graph.services import jarvis_cards

    name = event.get("name")
    if event.get("type") != "tool_result" or name not in jarvis_cards.CARD_TOOLS:
        return []
    local_only = await _local_only(state, tenant_id)
    return [
        {"type": "card", "card": c}
        for c in jarvis_cards.cards_for(name, event.get("result"), local_only)
    ]


async def _turn_for(tenant_id: str, client_id: str):
    """The newest top-level Jarvis turn sent under *client_id* in the last
    CLIENT_ID_WINDOW, or None. Small without an index: one tenant's day."""
    from life_graph.models.db import AgentTask

    since = datetime.now(UTC) - CLIENT_ID_WINDOW
    async with async_session() as session:
        return (
            (
                await session.execute(
                    select(AgentTask)
                    .where(
                        AgentTask.tenant_id == tenant_id,
                        AgentTask.agent_name == LEAD,
                        AgentTask.parent_task_id.is_(None),
                        AgentTask.created_at >= since,
                        AgentTask.input["client_id"].astext == client_id,
                    )
                    .order_by(AgentTask.created_at.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )


async def _polls(tenant_id: str, task_id: object):
    """The task, every _POLL_SECONDS, until it ends or the voice path's timeout
    (telegram_ask_timeout_seconds) passes; the last one yielded is where it got to."""
    from life_graph.api.dependencies import get_process_manager
    from life_graph.config import settings

    pm = get_process_manager()
    deadline = time.monotonic() + settings.telegram_ask_timeout_seconds
    while True:
        task = await pm.get_task(tenant_id, str(task_id))
        yield task
        if (task is not None and task.status in _TERMINAL) or time.monotonic() >= deadline:
            return
        await asyncio.sleep(_POLL_SECONDS)


async def _settled(tenant_id: str, task_id: object):
    """The task once it has ended, or as it was when the wait ran out (None if lost)."""
    task = None
    async for latest in _polls(tenant_id, task_id):
        task = latest
    return task


async def _replay_chat(tenant_id: str, prior, body: ChatRequest):
    """A resent message's turn as the app's events, from what it stored.

    Still running: waited for, with heartbeats so the stream stays open.
    Failed meanwhile: run again, which is what the phone's resend wants.
    """
    from life_graph.api.kernel import CHAT_STREAM_HEARTBEAT_SECONDS

    task, beat = prior, time.monotonic()
    if prior.status not in _TERMINAL:
        async for latest in _polls(tenant_id, prior.id):
            task = latest
            if time.monotonic() - beat >= CHAT_STREAM_HEARTBEAT_SECONDS:
                beat = time.monotonic()
                yield ": heartbeat\n\n"
    if task is not None and task.status == "completed":
        for event in await _replayed_events(tenant_id, task):
            yield f"data: {json.dumps(event)}\n\n"
        return
    if task is not None and task.status in _RETRY:
        inner = await _start_chat(body, body.conversation_id or task.session_id)
        async for frame in _app_frames(inner, tenant_id):
            yield frame
        return
    state = task.status if task is not None else "lost"
    failed = {"type": "error", "message": f"Jarvis could not finish ({state})."}
    yield f"data: {json.dumps(failed)}\n\n"


async def _replayed_events(tenant_id: str, task) -> list[dict]:
    """A finished turn as the stream showed it: what it saved and reminded
    (still standing), its reply as one token, then done."""
    turn = await _turn_result(tenant_id, task)
    events = [{"type": "saved", **s} for s in turn["saved"]]
    events += [{"type": "reminded", **r} for r in turn["reminded"]]
    events.append({"type": "token", "content": turn["reply"]})
    events.append(
        {"type": "done", "conversation_id": turn["conversation_id"], "route": turn["route"]}
    )
    return events


_warming: set = set()  # keeps the background tasks referenced until they finish


@router.post(
    "/warm", status_code=status.HTTP_202_ACCEPTED, summary="Get Jarvis's local model ready"
)
async def warm():
    """The app opened: load the local model now, so the first question is not a cold start.

    Returns at once; the load (~15 s on this machine) runs in the background.
    """
    import asyncio

    from life_graph.config import settings
    from life_graph.services import lead, local_runtime

    task = asyncio.create_task(local_runtime.warm(lead.local_model(), settings.lm_embedding_model))
    _warming.add(task)
    task.add_done_callback(_warming.discard)
    return success_response(data={"warming": True})


@router.get("/conversations", summary="Your conversations with Jarvis, newest first")
async def conversations(limit: int = 50):
    from life_graph.models.db import AgentSession, AgentTask

    tenant_id = get_current_tenant_id()
    last = (
        select(AgentTask.session_id, func.max(AgentTask.created_at).label("at"))
        .where(AgentTask.tenant_id == tenant_id, AgentTask.parent_task_id.is_(None))
        .group_by(AgentTask.session_id)
        .subquery()
    )
    async with async_session() as session:
        rows = (
            await session.execute(
                select(AgentSession, last.c.at)
                .outerjoin(last, last.c.session_id == AgentSession.id)
                .where(
                    AgentSession.tenant_id == tenant_id,
                    AgentSession.routed_to == LEAD,
                    # Temporary chats are never listed (F5).
                    AgentSession.context["temporary"].as_boolean().is_not(True),
                )
                .order_by(func.coalesce(last.c.at, AgentSession.created_at).desc())
                .limit(max(1, min(limit, 200)))
            )
        ).all()
    return success_response(
        data=[
            {
                "id": str(s.id),
                "title": " ".join((s.user_message or "").split())[:80],
                "updated_at": (at or s.created_at).isoformat(),
            }
            for s, at in rows
        ]
    )


@router.get("/conversations/{conversation_id}/messages", summary="One conversation, oldest first")
async def messages(conversation_id: uuid.UUID):
    from life_graph.models.db import AgentTask

    tenant_id = get_current_tenant_id()
    await _own_conversation(tenant_id, conversation_id)
    async with async_session() as session:
        tasks = (
            (
                await session.execute(
                    select(AgentTask)
                    .where(
                        AgentTask.tenant_id == tenant_id,
                        AgentTask.session_id == conversation_id,
                        AgentTask.parent_task_id.is_(None),
                    )
                    .order_by(AgentTask.created_at)
                    .limit(400)
                )
            )
            .scalars()
            .all()
        )
    saved = await _saved_by_task(tenant_id, [t.id for t in tasks])
    out = []
    for t in tasks:
        when = t.created_at.isoformat() if t.created_at else None
        inp = t.input or {}
        # A turn with shared text: the owner's typed words, and what they shared.
        asked = inp.get("owner_message", inp.get("message"))
        if asked:
            turn = {"role": "user", "content": asked, "created_at": when}
            if inp.get("shared"):
                turn["shared"] = inp["shared"]
            out.append(turn)
        answered = (t.result or {}).get("response")
        if answered:
            done = t.completed_at.isoformat() if getattr(t, "completed_at", None) else when
            out.append(
                {
                    "role": "assistant",
                    "content": answered,
                    "created_at": done,
                    # What Jarvis saved in that turn, for the app's Saved lines (still undoable).
                    "saved": saved.get(str(t.id), []),
                }
            )
    return success_response(data=out)


async def _saved_by_task(tenant_id: str, task_ids: list) -> dict[str, list[dict]]:
    """Memories memory_save stored in each of these runs and not since taken back, by task id."""
    from life_graph.models.db import Memory

    if not task_ids:
        return {}
    key = Memory.properties["task_id"].astext
    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.tenant_id == tenant_id,
                        key.in_([str(i) for i in task_ids]),
                        Memory.status.in_(("active", "pending")),
                    )
                    .order_by(Memory.created_at)
                )
            )
            .scalars()
            .all()
        )
    out: dict[str, list[dict]] = {}
    for m in rows:
        out.setdefault(str((m.properties or {}).get("task_id")), []).append(
            {"id": str(m.id), "content": m.content, "pending": m.status == "pending"}
        )
    return out


async def _answer(
    tenant_id: str,
    question: str,
    conversation_id: uuid.UUID | None,
    *,
    client_id: str | None = None,
) -> dict:
    """One Jarvis turn, waited for: {reply, conversation_id, route, saved, reminded}."""
    from life_graph.api.dependencies import get_process_manager
    from life_graph.api.kernel import _load_chat_history, _start_chat_session

    pm = get_process_manager()
    if conversation_id is None:
        conversation_id = await _start_chat_session(tenant_id, LEAD, question)
        history: list[dict[str, str]] = []
    else:
        history = await _load_chat_history(tenant_id, conversation_id)
    input_data: dict = {"message": question, "history": history}
    if client_id:
        input_data["client_id"] = client_id
    spawn = await pm.spawn(
        tenant_id=tenant_id,
        agent_name=LEAD,
        input_data=input_data,
        task_name=f"voice:{LEAD}",
        session_id=conversation_id,
        max_retries=0,
    )
    async with _tool_results(str(spawn["task_id"])) as results:
        task = await _settled(tenant_id, spawn["task_id"])
    if task is None or task.status != "completed":
        state = task.status if task is not None else "lost"
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, f"Jarvis could not finish ({state}).")
    return await _turn_result(tenant_id, task, await _cards(tenant_id, results))


@contextlib.asynccontextmanager
async def _tool_results(stream_key: str):
    """The run's own tool results, ``[(name, result)]``, heard on the chat
    stream bus while the block runs: nothing stores them, and the voice
    reply's cards are built from them as the chat's are.

    Subscribing registers at once (ChatStreamBus.subscribe), and what the run
    published before is replayed. A voice run has no stream consumer to
    close the stream, so the listener is stopped and the key freed here.
    """
    from life_graph.services.chat_stream import get_chat_stream_bus
    from life_graph.services.jarvis_cards import CARD_TOOLS

    bus = get_chat_stream_bus()
    events = bus.subscribe(stream_key)
    results: list[tuple[str, str]] = []

    async def listen() -> None:
        async for raw in events:
            ev = raw.get("event") or {}
            # The run's own calls, not a delegated child's: as the chat shows.
            top = raw.get("depth", 0) == 0 and ev.get("type") == "tool_result"
            if top and ev.get("name") in CARD_TOOLS:
                results.append((ev["name"], str(ev.get("result") or "")))

    listener = asyncio.create_task(listen())
    try:
        yield results
    finally:
        await asyncio.sleep(0)  # what was published last is heard first
        listener.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener
        bus.discard(stream_key)


async def _cards(tenant_id: str, results: list[tuple[str, str]]) -> list[dict]:
    from life_graph.services import jarvis_cards

    if not results:
        return []
    local_only = await jarvis_cards.local_only_accounts(tenant_id)
    return [c for name, result in results for c in jarvis_cards.cards_for(name, result, local_only)]


async def _turn_result(tenant_id: str, task, cards: list[dict] | None = None) -> dict:
    """A completed Jarvis turn as the app reads it. ``cards`` only for a turn
    just run: a replayed one's tool results are gone."""
    result = task.result or {}
    return {
        "reply": str(result.get("response") or "").strip(),
        "conversation_id": str(task.session_id) if task.session_id else None,
        "route": (result.get("route") or {}).get("kind"),
        "saved": await _saved_in(tenant_id, task.id),
        "reminded": await _reminded_in(tenant_id, task.id),
        "cards": cards or [],
    }


def _reminder_row(it) -> dict:
    """One reminder as the app reads it; ``at`` on the owner's clock."""
    from life_graph.connectors.tools import user_tz

    at = it.trigger_time.astimezone(user_tz()).isoformat() if it.trigger_time else None
    return {"id": str(it.id), "text": it.content, "at": at}


async def _reminded_in(tenant_id: str, task_id: object) -> list[dict]:
    """What reminder_set scheduled during one Jarvis run and is still pending
    (tools/reminders.py tags it with the run's task id)."""
    from life_graph.models.db import Intention

    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(Intention)
                    .where(
                        Intention.tenant_id == tenant_id,
                        Intention.trigger_type == "time",
                        Intention.status == "pending",
                        Intention.context_match["task_id"].astext == str(task_id),
                    )
                    .order_by(Intention.trigger_time)
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )
    return [_reminder_row(it) for it in rows]


async def _saved_in(tenant_id: str, task_id: object) -> list[dict]:
    """What memory_save stored during one Jarvis run (tools/memory_search.py tags it)
    and was not since taken back: a replayed turn must not offer Undo on an undone save."""
    from life_graph.models.db import Memory

    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.tenant_id == tenant_id,
                        Memory.properties["task_id"].astext == str(task_id),
                        Memory.status.in_(("active", "pending")),
                    )
                    .order_by(Memory.created_at)
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )
    return [{"id": str(m.id), "content": m.content, "pending": m.status == "pending"} for m in rows]


@router.post("/voice", summary="Speak to Jarvis: audio in, spoken reply out")
async def voice(
    audio: UploadFile = File(...),
    conversation_id: str | None = Form(None),
    client_id: str | None = Form(None),
):
    tenant_id = get_current_tenant_id()
    if client_id is not None and not _CLIENT_ID.fullmatch(client_id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "client_id must be 8-64 letters, digits, '-' or '_'.",
        )
    conv = None
    if conversation_id:
        try:
            conv = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found") from None
    await _own_conversation(tenant_id, conv)
    prior = await _turn_for(tenant_id, client_id) if client_id else None
    # The words as heard the first time: a resend is not transcribed again.
    heard = str((prior.input or {}).get("message") or "") if prior is not None else ""
    if prior is not None and prior.status not in _RETRY:
        # A resend of a message already received: its reply, not a second turn.
        task = prior if prior.status in _TERMINAL else await _settled(tenant_id, prior.id)
        if task is not None and task.status == "completed":
            return await _voice_reply(heard, await _turn_result(tenant_id, task))
        if task is None or task.status not in _RETRY:
            state = task.status if task is not None else "lost"
            raise HTTPException(
                status.HTTP_504_GATEWAY_TIMEOUT, f"Jarvis could not finish ({state})."
            )
    if prior is not None and conv is None:
        conv = prior.session_id  # a failed turn run again, in the conversation it opened
    if prior is None or not heard:
        heard = await _transcribe(audio)
        from life_graph.api.kernel import session_is_temporary

        # A retry's words were captured the first time; a temporary chat's never are.
        if prior is None and not await session_is_temporary(tenant_id, conv):
            await _capture(tenant_id, heard, "voice", conv, client_id=client_id)
    turn = await _answer(tenant_id, heard, conv, client_id=client_id)
    return await _voice_reply(heard, turn)


async def _voice_reply(heard: str, turn: dict):
    from life_graph.services.assistant_chat import speak

    spoken = await speak(turn["reply"]) if turn["reply"] else None
    return success_response(
        data={
            "heard": heard,
            **turn,
            "audio_base64": base64.b64encode(spoken).decode() if spoken else None,
        }
    )


async def _transcribe(audio: UploadFile) -> str:
    """The recording's words, transcribed on this machine only."""
    from life_graph.api.multimodal import _get_multimodal_service

    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No audio received.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Recording is too long.")
    try:
        heard = await _get_multimodal_service().transcribe_only(
            data, audio.filename or "voice.m4a", local_only=True
        )
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "I couldn't hear anything."
        ) from None
    return heard["transcript"]


# ── v2: review memories, undo a save, read an image, notifications ──────────

#: Where a memory came from, in the owner's words (the app shows it).
_SOURCE_LABEL = {
    "cli": "Claude Code",
    "jarvis_app": "Jarvis",
    "explicit": "Jarvis",
    "voice": "voice",
    "telegram": "Telegram",
    "dashboard": "dashboard",
    "manual": "dashboard",
    "image": "an image",
    "interview_answer": "interview",
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _source(m) -> str:
    props = m.properties or {}
    for key in (props.get("surface"), m.source_type):
        if key in _SOURCE_LABEL:
            return _SOURCE_LABEL[key]
    return "Life Graph"


@router.get("/memories/pending", summary="Memories waiting for your review, newest first")
async def pending_memories(limit: int = 50):
    from life_graph.models.db import Memory

    tenant_id = get_current_tenant_id()
    where = (Memory.tenant_id == tenant_id, Memory.status == "pending")
    async with async_session() as session:
        total = await session.scalar(select(func.count()).select_from(Memory).where(*where))
        rows = (
            (
                await session.execute(
                    select(Memory)
                    .where(*where)
                    .order_by(Memory.created_at.desc())
                    .limit(max(1, min(limit, 200)))
                )
            )
            .scalars()
            .all()
        )
    return success_response(
        data={
            "memories": [
                {
                    "id": str(m.id),
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "source": _source(m),
                }
                for m in rows
            ],
            "total": int(total or 0),
        }
    )


async def _review(memory_id: uuid.UUID, action: str) -> dict:
    """Approve or reject through the dashboard's own transition (events, contradictions)."""
    from life_graph.api.dependencies import get_store
    from life_graph.api.memories import _transition

    row = await _transition(memory_id, action, get_store())
    return {"id": str(row.id), "status": row.status}


@router.post("/memories/{memory_id}/approve", summary="Keep a memory")
async def approve_memory(memory_id: uuid.UUID):
    return success_response(data=await _review(memory_id, "approve"))


@router.post("/memories/{memory_id}/reject", summary="Drop a memory")
async def reject_memory(memory_id: uuid.UUID):
    return success_response(data=await _review(memory_id, "reject"))


@router.post("/memories/{memory_id}/undo", summary="Take back a memory Jarvis just saved")
async def undo_save(memory_id: uuid.UUID):
    """Archives (never deletes) one memory Jarvis saved with memory_save."""
    from datetime import UTC, datetime

    from sqlalchemy import text

    tenant_id = get_current_tenant_id()
    note = json.dumps({"undone": {"at": datetime.now(UTC).isoformat(), "by": "owner"}})
    async with async_session() as session:
        row = (
            await session.execute(
                text(
                    "UPDATE memories SET status = 'archived', updated_at = NOW(),"
                    " properties = COALESCE(properties, '{}'::jsonb) || CAST(:note AS jsonb)"
                    " WHERE id = :id AND tenant_id = :t AND status IN ('active', 'pending')"
                    " AND properties->>'saved_by' = 'jarvis' RETURNING id"
                ),
                {"id": memory_id, "t": tenant_id, "note": note},
            )
        ).first()
        if row is not None:
            # A correction (memory_save replaces_id) superseded the old fact;
            # taking the correction back must not leave neither of them active.
            await session.execute(
                text(
                    "UPDATE memories SET status = 'active', superseded_by = NULL,"
                    " updated_at = NOW()"
                    " WHERE tenant_id = :t AND superseded_by = :id AND status = 'superseded'"
                ),
                {"id": memory_id, "t": tenant_id},
            )
        await session.commit()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nothing to undo.")
    return success_response(data={"id": str(memory_id), "status": "archived"})


def _image_format(data: bytes) -> str | None:
    """JPEG, PNG or WEBP by the file's own first bytes, whatever it claims to be."""
    if data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def _read_words(data: bytes, fmt: str) -> str:
    """Open *data* as *fmt* only (no other Pillow decoder is reachable), then OCR it.

    MultiModalService._ocr_image caps the pixel count before decoding.
    """
    import io

    from PIL import Image

    from life_graph.services.multimodal import MultiModalService

    with Image.open(io.BytesIO(data), formats=[fmt]):
        pass  # raises unless the bytes really are that format
    return MultiModalService._ocr_image(data)


@router.post("/read-image", summary="The words in an image, read on this PC; nothing is stored")
async def read_image(image: UploadFile = File(...)):
    """Security review 2026-10-24 (M3): the bytes must be a JPEG, PNG or WebP by
    their magic bytes and open as that format only; over 40M pixels is refused
    before decoding; OCR stops after OCR_TIMEOUT_SECONDS."""
    import asyncio

    from life_graph.services.multimodal import OCR_TIMEOUT_SECONDS

    if (image.content_type or "").lower() not in _IMAGE_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Send a JPEG, PNG or WebP.")
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No image received.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That image is too big.")
    fmt = _image_format(data)
    if fmt is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Send a JPEG, PNG or WebP.")
    try:
        # A backstop over tesseract's own timeout (which also kills it).
        words = await asyncio.wait_for(
            asyncio.to_thread(_read_words, data, fmt), timeout=OCR_TIMEOUT_SECONDS + 5
        )
    except ImportError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Reading images is not set up on the PC."
        ) from None
    except TimeoutError:
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT, "Reading that image took too long."
        ) from None
    except RuntimeError as exc:
        if "timeout" in str(exc).lower():  # pytesseract: "Tesseract process timeout"
            raise HTTPException(
                status.HTTP_504_GATEWAY_TIMEOUT, "Reading that image took too long."
            ) from None
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "I couldn't read that image."
        ) from None
    except Exception:  # noqa: BLE001 - corrupt, too many pixels, or not what it claims
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "I couldn't read that image."
        ) from None
    words = (words or "").strip()
    if not words:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No words found in that image.")
    return success_response(data={"text": words})


_PRIORITY = {
    "urgent": "urgent",
    "critical": "urgent",
    "important": "important",
    "high": "important",
}


#: How far before *after* GET /notifications looks again. created_at is stamped
#: when a row is built, not when its transaction commits, so a row committed a
#: moment late can carry a time the phone's cursor has already passed; without
#: the overlap it was never delivered (security review 2026-10-24, finding 7).
#: The app drops ids it has already shown, so the repeats are harmless.
NOTIFICATION_OVERLAP_SECONDS = 30


@router.get("/notifications", summary="What Jarvis has to tell you, oldest first")
async def notifications(after: str | None = None, limit: int = 20):
    """Notifications from *after* (ISO-8601) on, for the phone to post.

    The reply also repeats what was created in the NOTIFICATION_OVERLAP_SECONDS
    before *after*, so it can hold notifications the phone already has: the
    app de-duplicates by id. Those repeats come on top of *limit*, so a burst
    inside the overlap can never fill the page and stop the cursor moving.
    """
    from datetime import UTC, datetime, timedelta

    from life_graph.models.db import Notification

    tenant_id = get_current_tenant_id()
    query = select(Notification).where(Notification.tenant_id == tenant_id)
    page = max(1, min(limit, 50))
    overlap = None
    if after:
        try:
            since = datetime.fromisoformat(after.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "after is not a date.") from None
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        overlap = query.where(
            Notification.created_at > since - timedelta(seconds=NOTIFICATION_OVERLAP_SECONDS),
            Notification.created_at <= since,
        )
        query = query.where(Notification.created_at > since)
    async with async_session() as session:
        rows = []
        if overlap is not None:
            # Newest first, then put back in order: the late-committed rows the
            # overlap exists for sit just before *after*, and a burst over the
            # LIMIT, read ascending, would keep the oldest and drop exactly them.
            newest = (
                await session.execute(overlap.order_by(Notification.created_at.desc()).limit(50))
            ).scalars()
            rows = sorted(newest.all(), key=lambda n: n.created_at)
        rows += (
            (await session.execute(query.order_by(Notification.created_at).limit(page)))
            .scalars()
            .all()
        )
    return success_response(data=[_notification_row(n) for n in rows])


def _notification_row(n) -> dict:
    from life_graph.services.notification_actions import actions_for, kind_of

    meta = getattr(n, "extra_metadata", None) or {}
    kind = kind_of(getattr(n, "source_type", None), meta)
    return {
        "id": str(n.id),
        "title": n.title,
        "body": (n.body or "")[:2000],
        "priority": _PRIORITY.get((n.priority or "").lower(), "info"),
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "kind": kind,
        "actions": actions_for(kind, meta),
    }


# ── v3: act on notifications, the morning brief, reminders ──────────────────


class NotificationAction(BaseModel):
    action: str = Field(..., min_length=1, max_length=32)


async def _own_notification(session, tenant_id: str, notification_id: str, *, lock: bool = False):
    """This tenant's notification, or 404 (an id that is not a UUID is unknown too)."""
    from life_graph.models.db import Notification

    try:
        ident = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found.") from None
    query = select(Notification).where(
        Notification.id == ident, Notification.tenant_id == tenant_id
    )
    if lock:
        query = query.with_for_update()  # two quick taps: the second sees the first
    row = (await session.execute(query)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found.")
    return row


@router.post("/notifications/{notification_id}/action", summary="Tap a notification's button")
async def notification_action(notification_id: str, body: NotificationAction):
    """Mark a bill paid, a reminder done, or snooze; the notification is then read.

    404 when the notification (or what it is about) is not yours; 409 when the
    button is not offered for it or was already used.
    """
    from life_graph.connectors.tools import user_tz
    from life_graph.services import notification_actions as na

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        row = await _own_notification(session, tenant_id, notification_id, lock=True)
        try:
            result = await na.perform(session, tenant_id, row, body.action, na.utcnow(), user_tz())
        except na.ActionRefusedError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
        except na.ActionNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
        await session.commit()
    return success_response(data={"id": str(row.id), "action": body.action, "result": result})


#: Spoken briefs by notification id, newest last: tapping Listen twice does not
#: synthesise twice. In-process and small; a restart just synthesises again.
_brief_audio: dict[str, bytes] = {}
BRIEF_AUDIO_CACHE = 4
#: How long the endpoint waits for speech before answering with the text only.
#: Under the phone's 30 s read timeout: on 2026-10-25, with the GPU held by a
#: dev task's model, speech took over 60 s and the phone got nothing at all.
BRIEF_AUDIO_WAIT_SECONDS = 20.0
_brief_speaking: dict[str, asyncio.Task] = {}  # brief id -> the synthesis in flight


async def _speak_brief(brief_id: str, text: str) -> bytes | None:
    from life_graph.services.assistant_chat import speak

    audio = await speak(text)
    if audio:  # a failure is not cached: speech may be back next time
        _brief_audio[brief_id] = audio
        while len(_brief_audio) > BRIEF_AUDIO_CACHE:
            _brief_audio.pop(next(iter(_brief_audio)))
    return audio


async def _brief_mp3(brief_id: str, text: str) -> bytes | None:
    """The spoken brief, or None if it is not ready within the wait.

    Synthesis carries on in the background either way, so the next tap plays it.
    """
    if brief_id in _brief_audio:
        return _brief_audio[brief_id]
    task = _brief_speaking.get(brief_id)
    if task is None or task.done():
        task = asyncio.create_task(_speak_brief(brief_id, text))
        _brief_speaking[brief_id] = task
        task.add_done_callback(lambda _t: _brief_speaking.pop(brief_id, None))
    try:
        return await asyncio.wait_for(asyncio.shield(task), BRIEF_AUDIO_WAIT_SECONDS)
    except TimeoutError:
        return None


@router.get("/brief/latest", summary="The newest daily brief, with its audio")
async def latest_brief():
    """The brief's text and the spoken brief as mp3 (null when speech is unavailable)."""
    from life_graph.models.db import Notification

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        row = (
            (
                await session.execute(
                    select(Notification)
                    .where(Notification.tenant_id == tenant_id, Notification.source_type == "brief")
                    .order_by(Notification.created_at.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No brief yet.")
    text = row.body or ""
    audio = await _brief_mp3(str(row.id), text) if text.strip() else None
    return success_response(
        data={
            "id": str(row.id),
            "title": row.title,
            "text": text,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "audio_base64": base64.b64encode(audio).decode() if audio else None,
        }
    )


@router.get("/reminders", summary="Your pending reminders, soonest first")
async def pending_reminders(limit: int = 100):
    from life_graph.models.db import Intention

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(Intention)
                    .where(
                        Intention.tenant_id == tenant_id,
                        Intention.trigger_type == "time",
                        Intention.status == "pending",
                        Intention.trigger_time.is_not(None),
                    )
                    .order_by(Intention.trigger_time)
                    .limit(max(1, min(limit, 200)))
                )
            )
            .scalars()
            .all()
        )
    return success_response(data=[{**_reminder_row(it), "status": "pending"} for it in rows])


@router.post("/reminders/{reminder_id}/cancel", summary="Cancel a reminder")
async def cancel_reminder(reminder_id: str):
    """Stored as ``dismissed`` (services/intentions.py's word for it), never deleted.

    Cancelling one already cancelled says so again; one already done is a 409.
    """
    from life_graph.models.db import Intention

    tenant_id = get_current_tenant_id()
    try:
        ident = uuid.UUID(reminder_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder not found.") from None
    async with async_session() as session:
        row = (
            await session.execute(
                select(Intention)
                .where(
                    Intention.id == ident,
                    Intention.tenant_id == tenant_id,
                    Intention.trigger_type == "time",
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder not found.")
        if row.status == "completed":
            raise HTTPException(status.HTTP_409_CONFLICT, "That reminder is already done.")
        if row.status == "pending":
            row.status = "dismissed"
            await session.commit()
    return success_response(data={"id": str(row.id), "status": "cancelled"})


# ── v4: the Today screen ────────────────────────────────────────────────────


@router.get("/today", summary="The Today screen in one call")
async def today():
    """Counts, insights, schedule, what is due, money, work, study and what
    Jarvis learnt (services/jarvis_today.py). A source that fails leaves its
    part null or empty; the call itself does not fail for it."""
    from life_graph.services.jarvis_today import today_screen

    return success_response(data=await today_screen(get_current_tenant_id()))


@router.post("/bills/{item_id}/paid", summary="Mark a bill from mail paid")
async def bill_paid(item_id: str):
    """The Today screen's "Mark paid": the bill on this email, and every other
    open email about the same bill (connectors/bills.mark_paid). Only "paid":
    the dashboard's dismiss and remind stay with the dashboard."""
    from life_graph.connectors.bills import mark_paid

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        marked = await mark_paid(session, tenant_id, item_id, datetime.now(UTC))
        if marked is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Bill not found.")
        await session.commit()
    return success_response(data={"id": item_id, "state": "paid", "marked": marked})


# ── v4 S2: Plan, Memory, contacts, mail ─────────────────────────────────────


@router.get("/plan", summary="The next days: events, what is due, reminders, to-dos")
async def plan(days: int = Query(7, ge=1, le=31)):
    """One row per day from today in the owner's time zone, empty days
    included (services/jarvis_plan.py). A source that fails leaves its kind
    empty; the call itself does not fail for it."""
    from life_graph.services import jarvis_plan

    return success_response(data=await jarvis_plan.plan(get_current_tenant_id(), days))


@router.get("/memory/overview", summary="What Jarvis remembers: counts, people, rules, days")
async def memory_overview():
    """Counts, the people, projects and things memories mention, the rules,
    the newest memories and the days (services/jarvis_memory.py). A part that
    fails is null or empty; the call itself does not fail for it."""
    from life_graph.services import jarvis_memory

    return success_response(data=await jarvis_memory.overview(get_current_tenant_id()))


@router.get("/memory/search", summary="Search what Jarvis remembers (active memories only)")
async def memory_search(q: str = "", limit: int = Query(30, ge=1, le=100)):
    """By meaning and by words (the store's hybrid search). A blank query is
    an empty list; 503 when the embedding service is down."""
    from life_graph.services import jarvis_memory

    try:
        return success_response(data=await jarvis_memory.search(q, limit))
    except jarvis_memory.SearchUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Search is not available right now."
        ) from None


@router.get("/entities/{entity_id}", summary="One person, project or thing, and what is known")
async def entity(entity_id: str):
    """404 when the id is not a UUID or not one of this tenant's entities."""
    from life_graph.services import jarvis_memory

    try:
        ident = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
    found = await jarvis_memory.entity_detail(get_current_tenant_id(), ident)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return success_response(data=found)


@router.get("/contacts", summary="Your contacts, or those matching q")
async def contacts(q: str = ""):
    """Every word of *q* in the name, an address or the organisation; a blank
    *q* lists them by name (services/jarvis_inbox.py)."""
    from life_graph.services import jarvis_inbox

    return success_response(data=await jarvis_inbox.contacts(get_current_tenant_id(), q))


@router.get("/mail/waiting", summary="Mail waiting on your reply, longest wait first")
async def mail_waiting():
    from life_graph.services import jarvis_inbox

    return success_response(data=await jarvis_inbox.mail_waiting(get_current_tenant_id()))


# ── v4: in-app update ───────────────────────────────────────────────────────

APK_MEDIA_TYPE = "application/vnd.android.package-archive"
#: An APK's name as the release script writes it: no path, no hidden file.
_APK_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.apk")


def _release() -> tuple[Path, dict] | None:
    """(the APK's path, latest.json) from ``app_release_dir``, or None when
    unset, unreadable, malformed, or naming a file that is not right there."""
    from life_graph.config import settings

    folder = (settings.app_release_dir or "").strip()
    if not folder:
        return None
    base = Path(folder).expanduser()
    try:
        meta = json.loads((base / "latest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    code, name, file, notes = (
        meta.get(k) for k in ("version_code", "version_name", "file", "notes")
    )
    if not (isinstance(code, int) and not isinstance(code, bool) and code > 0):
        return None
    if not isinstance(name, str) or not isinstance(file, str) or not _APK_NAME.fullmatch(file):
        return None
    if notes is not None and not isinstance(notes, str):
        return None
    apk = base / file
    try:
        # The name pattern already rules out a path; this also refuses a symlink out.
        if apk.resolve().parent != base.resolve() or not apk.is_file():
            return None
    except OSError:
        return None
    return apk, {"version_code": code, "version_name": name, "file": file, "notes": notes or ""}


@router.get("/app/latest", summary="The newest phone app the PC offers (404: none)")
async def app_latest():
    """The app compares ``version_code`` with its own and offers Update when newer."""
    found = _release()
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No app release here.")
    _apk, meta = found
    return success_response(
        data={
            "version_code": meta["version_code"],
            "version_name": meta["version_name"],
            "url": f"/api/v1/jarvis/app/download/{meta['file']}",
            "notes": meta["notes"],
        }
    )


@router.get("/app/download/{file}", summary="Download the phone app's APK")
async def app_download(file: str):
    """Only the file latest.json names: any other name, path or not, is a 404."""
    from fastapi.responses import FileResponse

    found = _release()
    if found is None or file != found[1]["file"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such app release.")
    return FileResponse(found[0], media_type=APK_MEDIA_TYPE, filename=file)


# ── Scheduled asks (docs/specs/web-chat-wave1.md F1) ─────────────────────


class AskUpdate(BaseModel):
    active: bool


async def _own_ask(tenant_id: str, ask_id: str) -> dict:
    """The tenant's scheduled ask, or 404 (other schedules are not asks)."""
    from life_graph.api.dependencies import get_scheduler_service
    from life_graph.services import scheduled_asks

    try:
        uuid.UUID(ask_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ask not found") from None
    job = await get_scheduler_service().get_by_id(tenant_id, ask_id)
    if (
        job is None
        or not scheduled_asks.is_ask(job)
        or (job.get("properties") or {}).get("removed")
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ask not found")
    return job


@router.get("/asks", summary="What Jarvis does on its own: your scheduled asks")
async def list_asks():
    from life_graph.api.dependencies import get_scheduler_service
    from life_graph.models.db import AgentTask
    from life_graph.services import scheduled_asks

    tenant_id = get_current_tenant_id()
    jobs, _ = await get_scheduler_service().list_all(tenant_id, include_inactive=True)
    asks = [
        j
        for j in jobs
        if scheduled_asks.is_ask(j) and not (j.get("properties") or {}).get("removed")
    ]
    last_ids = [uuid.UUID(j["last_run_task_id"]) for j in asks if j.get("last_run_task_id")]
    replies: dict[str, str] = {}
    if last_ids:
        async with async_session() as session:
            for task in (
                await session.execute(
                    select(AgentTask).where(
                        AgentTask.tenant_id == tenant_id, AgentTask.id.in_(last_ids)
                    )
                )
            ).scalars():
                replies[str(task.id)] = str((task.result or {}).get("response") or "")[:600]
    return success_response(
        data=[
            scheduled_asks.as_listed(j, replies.get(j.get("last_run_task_id") or ""))
            for j in sorted(asks, key=lambda j: (not j["is_active"], j.get("next_run_at") or ""))
        ]
    )


@router.patch("/asks/{ask_id}", summary="Pause or resume a scheduled ask")
async def update_ask(ask_id: str, body: AskUpdate):
    from life_graph.api.dependencies import get_scheduler_service
    from life_graph.services import scheduled_asks

    tenant_id = get_current_tenant_id()
    job = await _own_ask(tenant_id, ask_id)
    data: dict = {"is_active": body.active}
    if body.active:
        # From now: a paused ask does not run once for every time it missed.
        data["cron_expression"] = job["cron_expression"]
    updated = await get_scheduler_service().update(tenant_id, ask_id, data)
    return success_response(data=scheduled_asks.as_listed(updated or job))


@router.delete("/asks/{ask_id}", summary="Stop a scheduled ask for good")
async def delete_ask(ask_id: str):
    from life_graph.api.dependencies import get_scheduler_service

    tenant_id = get_current_tenant_id()
    job = await _own_ask(tenant_id, ask_id)
    props = {**(job.get("properties") or {}), "removed": True}
    await get_scheduler_service().update(
        tenant_id, ask_id, {"is_active": False, "properties": props}
    )
    return success_response(data={"id": ask_id, "removed": True})


# ── What shaped an answer (docs/specs/web-chat-wave1.md F3) ──────────────


class WrongMemory(BaseModel):
    note: str | None = Field(None, max_length=500)


async def _own_turn(tenant_id: str, task_id: uuid.UUID):
    from life_graph.models.db import AgentTask

    async with async_session() as session:
        task = await session.get(AgentTask, task_id)
    if task is None or task.tenant_id != tenant_id or task.parent_task_id is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "turn not found")
    return task


@router.get(
    "/turns/{task_id}/trace", summary="How one reply was made: memories, tools, where it ran"
)
async def turn_trace(task_id: uuid.UUID):
    from life_graph.services.turn_trace import summary_line

    task = await _own_turn(get_current_tenant_id(), task_id)
    trace = (task.result or {}).get("trace")
    if not trace:
        # A turn from before traces were kept, or one still running.
        return success_response(data={"task_id": str(task_id), "trace": None, "summary": None})
    return success_response(
        data={"task_id": str(task_id), "trace": trace, "summary": summary_line(trace)}
    )


@router.post(
    "/turns/{task_id}/memories/{memory_id}/wrong",
    summary="A memory this reply used is wrong: back to review, left out of answers",
)
async def memory_was_wrong(task_id: uuid.UUID, memory_id: uuid.UUID, body: WrongMemory):
    """Only a memory the turn actually used, and only an active one: it goes back
    to the review queue (pending, so recall leaves it out) with the owner's note.
    Never deleted; Keep in review restores it."""
    from sqlalchemy import text

    tenant_id = get_current_tenant_id()
    task = await _own_turn(tenant_id, task_id)
    used = {m.get("id") for m in ((task.result or {}).get("trace") or {}).get("memories") or []}
    if str(memory_id) not in used:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "this reply did not use that memory")
    note = json.dumps(
        {
            "disputed": {
                "at": datetime.now(UTC).isoformat(),
                "task_id": str(task_id),
                "note": (body.note or "").strip() or None,
            }
        }
    )
    async with async_session() as session:
        row = (
            await session.execute(
                text(
                    "UPDATE memories SET status = 'pending', updated_at = NOW(),"
                    " properties = COALESCE(properties, '{}'::jsonb) || CAST(:note AS jsonb)"
                    " WHERE id = :id AND tenant_id = :t AND status = 'active' RETURNING id"
                ),
                {"id": memory_id, "t": tenant_id, "note": note},
            )
        ).first()
        await session.commit()
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "that memory is not active any more")
    return success_response(data={"id": str(memory_id), "status": "pending"})


# ── Nudges from the owner's own words (docs/specs/web-chat-wave1.md F2) ──


class NudgeAction(BaseModel):
    action: str = Field(..., pattern="^(done|snooze_1d|drop)$")


@router.get("/nudges", summary="What you said you would do, still open")
async def open_nudges(limit: int = 50):
    from life_graph.models.db import Intention
    from life_graph.services import nudges

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(Intention)
                    .where(
                        Intention.tenant_id == tenant_id,
                        Intention.trigger_type == "nudge",
                        Intention.status.in_(nudges.OPEN),
                    )
                    .order_by(Intention.trigger_time)
                    .limit(max(1, min(limit, 200)))
                )
            )
            .scalars()
            .all()
        )
    return success_response(data=[nudges.as_listed(r) for r in rows])


@router.post(
    "/nudges/{nudge_id}", summary="Done, Tomorrow or Drop for something you said you would do"
)
async def act_on_nudge(nudge_id: str, body: NudgeAction):
    from life_graph.connectors.tools import user_tz
    from life_graph.services import notification_actions as na
    from life_graph.services import nudges

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        try:
            row = await nudges.act(
                session, tenant_id, nudge_id, body.action, na.utcnow(), user_tz()
            )
        except na.ActionRefusedError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "nudge not found")
        await session.commit()
        return success_response(data=nudges.as_listed(row))
