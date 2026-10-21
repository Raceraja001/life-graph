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
    return None  # tool calls, delegations: not shown on the phone


@router.post("/chat", summary="Talk to Jarvis; the reply streams back (SSE)")
async def chat(body: ChatRequest):
    from life_graph.api.dependencies import get_persona_service, get_process_manager
    from life_graph.api.kernel import ChatStreamRequest, chat_stream

    tenant_id = get_current_tenant_id()
    await _own_conversation(tenant_id, body.conversation_id)
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
    out = []
    for t in tasks:
        when = t.created_at.isoformat() if t.created_at else None
        asked = (t.input or {}).get("message")
        if asked:
            out.append({"role": "user", "content": asked, "created_at": when})
        answered = (t.result or {}).get("response")
        if answered:
            done = t.completed_at.isoformat() if getattr(t, "completed_at", None) else when
            out.append({"role": "assistant", "content": answered, "created_at": done})
    return success_response(data=out)


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
    }


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
    turn = await _answer(tenant_id, heard["transcript"], conv)
    spoken = await speak(turn["reply"]) if turn["reply"] else None
    return success_response(
        data={
            "heard": heard["transcript"],
            **turn,
            "audio_base64": base64.b64encode(spoken).decode() if spoken else None,
        }
    )
