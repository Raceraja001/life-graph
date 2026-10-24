"""Jarvis for the phone app (docs/design/12_android_app_plan.md, Phase 1).

The only endpoints a paired device's token opens (api/middleware.py,
``DEVICE_PATH_PREFIX``). The contract is the app's (life-graph-android
docs/PLAN.md):

* ``POST /jarvis/chat`` streams ``{type: token, content}`` events, then
  ``{type: done, conversation_id, route}`` or ``{type: error, message}``.
  It is the dashboard's chat stream (api/kernel.py) with Jarvis as the persona,
  in the app's simpler event shapes.
* ``GET /jarvis/conversations`` and ``.../{id}/messages``.
* ``POST /jarvis/voice``: audio in, transcribed on this machine only, answered
  by Jarvis in the same conversation, the reply spoken back as mp3.
* ``POST /jarvis/warm``: the app opened; load the local model in the background.

Where Jarvis ran (``route``: personal = this PC's model, general = a cloud
model without the personal tools) comes from services/lead.py.
"""

from __future__ import annotations

import base64
import json
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
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


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: uuid.UUID | None = None


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
    return None  # other tool calls, delegations: not shown on the phone


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


async def _capture(tenant_id: str, text: str, kind: str, conversation_id: uuid.UUID | None) -> None:
    """The owner's own words to Jarvis, to the capture spine: memory is learnt from them.

    Extraction (services/capture_processors.py) keeps only lasting facts, on
    the local model; "remember that…" becomes an active memory at once.
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
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        # Never the text: it is personal.
        logging.getLogger(__name__).warning("Jarvis capture failed: %s", exc)


@router.post("/chat", summary="Talk to Jarvis; the reply streams back (SSE)")
async def chat(body: ChatRequest):
    from life_graph.api.dependencies import get_persona_service, get_process_manager
    from life_graph.api.kernel import ChatStreamRequest, chat_stream

    tenant_id = get_current_tenant_id()
    await _own_conversation(tenant_id, body.conversation_id)
    await _capture(tenant_id, body.message, "text", body.conversation_id)
    inner = await chat_stream(
        ChatStreamRequest(message=body.message, target_agent=LEAD, session_id=body.conversation_id),
        pm=get_process_manager(),
        personas=get_persona_service(),
    )

    async def gen():
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

    return StreamingResponse(gen(), media_type="text/event-stream", headers=dict(inner.headers))


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
                .where(AgentSession.tenant_id == tenant_id, AgentSession.routed_to == LEAD)
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
        asked = (t.input or {}).get("message")
        if asked:
            out.append({"role": "user", "content": asked, "created_at": when})
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


async def _answer(tenant_id: str, question: str, conversation_id: uuid.UUID | None) -> dict:
    """One Jarvis turn, waited for: {reply, conversation_id, route}."""
    import asyncio

    from life_graph.api.dependencies import get_process_manager
    from life_graph.api.kernel import _load_chat_history, _start_chat_session
    from life_graph.config import settings

    pm = get_process_manager()
    if conversation_id is None:
        conversation_id = await _start_chat_session(tenant_id, LEAD, question)
        history: list[dict[str, str]] = []
    else:
        history = await _load_chat_history(tenant_id, conversation_id)
    spawn = await pm.spawn(
        tenant_id=tenant_id,
        agent_name=LEAD,
        input_data={"message": question, "history": history},
        task_name=f"voice:{LEAD}",
        session_id=conversation_id,
        max_retries=0,
    )
    waited, task = 0.0, None
    while waited < settings.telegram_ask_timeout_seconds:
        task = await pm.get_task(tenant_id, spawn["task_id"])
        if task is not None and task.status in _TERMINAL:
            break
        await asyncio.sleep(1.0)
        waited += 1.0
    if task is None or task.status != "completed":
        state = task.status if task is not None else "lost"
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, f"Jarvis could not finish ({state}).")
    result = task.result or {}
    return {
        "reply": str(result.get("response") or "").strip(),
        "conversation_id": str(conversation_id),
        "route": (result.get("route") or {}).get("kind"),
        "saved": await _saved_in(tenant_id, spawn["task_id"]),
    }


async def _saved_in(tenant_id: str, task_id: object) -> list[dict]:
    """What memory_save stored during one Jarvis run (tools/memory_search.py tags it)."""
    from life_graph.models.db import Memory

    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.tenant_id == tenant_id,
                        Memory.properties["task_id"].astext == str(task_id),
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
):
    from life_graph.api.multimodal import _get_multimodal_service
    from life_graph.services.assistant_chat import speak

    tenant_id = get_current_tenant_id()
    conv = None
    if conversation_id:
        try:
            conv = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found") from None
    await _own_conversation(tenant_id, conv)
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
    await _capture(tenant_id, heard["transcript"], "voice", conv)
    turn = await _answer(tenant_id, heard["transcript"], conv)
    spoken = await speak(turn["reply"]) if turn["reply"] else None
    return success_response(
        data={
            "heard": heard["transcript"],
            **turn,
            "audio_base64": base64.b64encode(spoken).decode() if spoken else None,
        }
    )


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


@router.post("/read-image", summary="The words in an image, read on this PC; nothing is stored")
async def read_image(image: UploadFile = File(...)):
    import asyncio

    from life_graph.services.multimodal import MultiModalService

    if (image.content_type or "").lower() not in _IMAGE_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Send a JPEG, PNG or WebP.")
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No image received.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That image is too big.")
    try:
        words = await asyncio.to_thread(MultiModalService._ocr_image, data)
    except ImportError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Reading images is not set up on the PC."
        ) from None
    except Exception:  # noqa: BLE001 - a corrupt or unreadable file
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


@router.get("/notifications", summary="What Jarvis has to tell you, oldest first")
async def notifications(after: str | None = None, limit: int = 20):
    """Notifications newer than *after* (ISO-8601), for the phone to post."""
    from datetime import UTC, datetime

    from life_graph.models.db import Notification

    tenant_id = get_current_tenant_id()
    query = select(Notification).where(Notification.tenant_id == tenant_id)
    if after:
        try:
            since = datetime.fromisoformat(after.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "after is not a date.") from None
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        query = query.where(Notification.created_at > since)
    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    query.order_by(Notification.created_at).limit(max(1, min(limit, 50)))
                )
            )
            .scalars()
            .all()
        )
    return success_response(
        data=[
            {
                "id": str(n.id),
                "title": n.title,
                "body": (n.body or "")[:2000],
                "priority": _PRIORITY.get((n.priority or "").lower(), "info"),
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in rows
        ]
    )
