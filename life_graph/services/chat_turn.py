"""One chat turn with a persona: the checks, then the stream (audit M16).

Every chat route runs its turn here: /kernel/chat/stream (the dashboard),
/jarvis/chat and /jarvis/turns/{id}/regenerate (the phone). The waited-for
turn (api/jarvis.py ``_answer``) uses the session and history helpers. Moved
out of api/kernel.py on 2026-11-25; what each route sends is pinned by
tests/integration/test_chat_turn_parity.py.

A refusal raises ChatTurnError with the HTTP status the route answers.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from life_graph.core.run_taint import TAINT_INPUT_KEY
from life_graph.core.trust import with_shared
from life_graph.services.chat_stream import get_chat_stream_bus, map_bus_event

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Seconds of bus idleness after which the SSE stream emits a `: heartbeat`
# comment to keep proxies/load-balancers from dropping an idle connection.
# Module-level so tests can monkeypatch it to a tiny value and exercise the
# heartbeat/idle-gap path without waiting the full production interval.
CHAT_STREAM_HEARTBEAT_SECONDS = 15.0

#: The stream's response headers: no caching or proxy buffering, kept open.
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


class ChatTurnError(Exception):
    """A turn refused before it starts, with the HTTP status a route answers."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ChatStreamRequest(BaseModel):
    """Request body for a streaming persona chat turn."""

    message: str = Field(
        default="",
        description=(
            "User message to send to the persona. Required, except with `regenerates`, "
            "whose turn supplies it (anything sent here is then ignored)."
        ),
    )
    target_agent: str = Field(default="jarvis", description="Persona to converse with")
    project_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Conversation to continue. Omit on the first turn: one is created and its id "
            "comes back on the `start` event, to send with every later turn so the persona "
            "sees what was already said."
        ),
    )
    shared: str | None = Field(
        default=None,
        max_length=8000,
        description=(
            "Text the user shared from another app (a share sheet, words read from an "
            "image). Someone else wrote it: the persona sees it fenced as information, "
            "and only `message` counts as the user's own words."
        ),
    )
    client_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]{8,64}$",
        description=(
            "The phone app's id for this message, stored in the task's input so a resend "
            "can be recognised (api/jarvis.py)."
        ),
    )
    temporary: bool = Field(
        default=False,
        description=(
            "A temporary chat: local model only, nothing captured or saved, never listed "
            "or summarised, purged a day after its last message "
            "(docs/specs/web-chat-wave1.md F5). Set on the first turn; the conversation "
            "keeps it."
        ),
    )
    regenerates: uuid.UUID | None = Field(
        default=None,
        description=(
            "Re-run this turn, the conversation's latest, keeping both versions "
            "(docs/specs/web-chat-wave1.md F6). Its own message is asked again with the "
            "history before it; the new turn records `regenerates`, and later turns see "
            "only the newest completed version."
        ),
    )
    model: Literal["local", "cloud"] | None = Field(
        default=None,
        description=(
            "With `regenerates`: ask again on the local model or in the cloud, as if the "
            "message began `local:` or `cloud:` (services/lead.py). A temporary chat "
            "stays local whichever is asked."
        ),
    )

    @model_validator(mode="after")
    def _message_or_regenerates(self) -> ChatStreamRequest:
        if self.regenerates is None and not self.message:
            raise ValueError("message is required")
        if self.model is not None and self.regenerates is None:
            raise ValueError("model is only for regenerates")
        return self


# How many earlier turns a persona is given. Each turn is a user message and a
# reply, so this is CHAT_HISTORY_TURNS * 2 messages — enough for a conversation
# to hold together, bounded so a long thread cannot grow past the context
# window of a local model and start silently dropping the system prompt.
CHAT_HISTORY_TURNS = 10


async def start_chat_session(
    tenant_id: str, target_agent: str, message: str, *, temporary: bool = False
) -> uuid.UUID:
    """Open a conversation and return its id.

    `user_message` is the opening message and is not updated afterwards — the
    column records how the conversation began, and the turns themselves live in
    agent_tasks.
    """
    from life_graph.models.db import AgentSession
    from life_graph.storage.database import async_session

    async with async_session() as session:
        row = AgentSession(
            tenant_id=tenant_id,
            user_message=message,
            routed_to=target_agent,
            status="active",
            context={"temporary": True} if temporary else {},
        )
        session.add(row)
        await session.commit()
        return row.id


async def session_is_temporary(tenant_id: str, session_id: uuid.UUID | None) -> bool:
    """True when the conversation was opened as a temporary chat."""
    if session_id is None:
        return False
    from life_graph.models.db import AgentSession
    from life_graph.storage.database import async_session

    try:
        async with async_session() as session:
            row = await session.get(AgentSession, session_id)
    except Exception:  # noqa: BLE001
        # No database, no turn: the spawn and any capture need it too.
        import logging

        logging.getLogger(__name__).warning(
            "Could not read whether a chat is temporary", exc_info=True
        )
        return False
    return bool(
        row is not None
        and row.tenant_id == tenant_id
        and (row.context or {}).get("temporary") is True
    )


async def load_chat_history(
    tenant_id: str, session_id: uuid.UUID, *, excluding: uuid.UUID | None = None
) -> list[dict[str, str]]:
    """Earlier turns of this conversation, oldest first.

    Rebuilt from the agent_tasks rows each turn already writes rather than from
    anything the client sends: the transcript the persona is shown is then the
    one that actually happened, and a caller cannot put words in its mouth by
    editing the history it posts back.

    Only completed tasks with a reply count. A turn that failed, timed out, or
    was cancelled mid-answer left no answer, and feeding its empty string back
    as an assistant message teaches the model that saying nothing is a valid
    reply.

    A turn a completed regeneration replaced is left out, so the persona sees
    only the version the owner kept (services/chat_history.py); `excluding` is
    the turn being regenerated now, whose earlier versions stay out too.
    """
    from life_graph.models.db import AgentTask
    from life_graph.services.chat_history import superseded_by, versions_of
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(AgentTask)
                    .where(
                        AgentTask.tenant_id == tenant_id,
                        AgentTask.session_id == session_id,
                        AgentTask.parent_task_id.is_(None),
                    )
                    # Newest first, then reversed: the cut has to keep the most
                    # recent turns, and ordering ascending with a LIMIT would
                    # hand back the oldest ones instead.
                    .order_by(AgentTask.created_at.desc())
                    # Every status, so a regeneration chain through a failed
                    # version is seen; room for what is dropped below.
                    .limit(CHAT_HISTORY_TURNS * 3)
                )
            )
            .scalars()
            .all()
        )

    rows = list(reversed(rows))
    skip = set(superseded_by(rows))
    if excluding is not None:
        skip |= versions_of(rows, excluding)
    kept = [t for t in rows if t.status == "completed" and str(t.id) not in skip]
    kept = kept[-CHAT_HISTORY_TURNS:]
    history: list[dict[str, str]] = []
    for task in kept:
        asked = (task.input or {}).get("message")
        answered = (task.result or {}).get("response")
        if not asked or not answered:
            continue
        history.append({"role": "user", "content": asked})
        history.append({"role": "assistant", "content": answered})
    return history


#: A turn still being answered cannot be regenerated yet.
_REGENERABLE = {"completed", "failed", "timeout", "cancelled"}


async def regeneration(tenant_id: str, body: ChatStreamRequest) -> ChatStreamRequest:
    """The request for re-running ``body.regenerates``, from that turn's own words.

    404 unless it is this tenant's top-level turn; 409 unless it is its
    conversation's latest turn and has finished. The message and any shared
    text are the turn's (what was asked is not the client's to rewrite), the
    conversation is the turn's, and the phone's client_id is not carried: this
    is a new turn, not a resend.
    """
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as session:
        turn = await session.get(AgentTask, body.regenerates)
        if (
            turn is None
            or turn.tenant_id != tenant_id
            or turn.parent_task_id is not None
            or turn.session_id is None
        ):
            raise ChatTurnError(404, "turn not found")
        latest = (
            await session.execute(
                select(AgentTask.id)
                .where(
                    AgentTask.tenant_id == tenant_id,
                    AgentTask.session_id == turn.session_id,
                    AgentTask.parent_task_id.is_(None),
                )
                .order_by(AgentTask.created_at.desc(), AgentTask.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if body.session_id is not None and body.session_id != turn.session_id:
        raise ChatTurnError(409, "That turn is in another conversation.")
    if latest != turn.id:
        raise ChatTurnError(409, "Only the latest reply can be regenerated.")
    if turn.status not in _REGENERABLE:
        raise ChatTurnError(409, "That reply is still being written.")
    asked = turn.input or {}
    message = asked.get("owner_message", asked.get("message"))
    if not message:
        raise ChatTurnError(409, "That turn has no message to ask again.")
    if body.model is not None:
        from life_graph.services.lead import _SWITCH

        # The owner's choice replaces any switch the words began with.
        message = f"{body.model}: {_SWITCH.sub('', message, count=1)}"
    return body.model_copy(
        update={
            "message": message,
            "shared": asked.get("shared"),
            "session_id": turn.session_id,
            "client_id": None,
        }
    )


async def prepare_turn(tenant_id: str, body: ChatStreamRequest, personas: Any) -> ChatStreamRequest:
    """The turn to run: a known persona; a regeneration's own words; a
    temporary chat only from its start and only with Jarvis. ChatTurnError
    (404, 409, 400) otherwise."""
    persona = await personas.get_by_name(tenant_id, body.target_agent)
    if persona is None:
        raise ChatTurnError(
            status_code=404,
            detail=f"Unknown persona: {body.target_agent!r}",
        )
    if body.regenerates is not None:
        body = await regeneration(tenant_id, body)
    if (
        body.temporary
        and body.session_id is not None
        and not await session_is_temporary(tenant_id, body.session_id)
    ):
        # Its earlier turns are already kept; half a temporary chat would promise
        # what it cannot keep.
        raise ChatTurnError(
            status_code=409,
            detail="A chat becomes temporary only when it starts: open a new one.",
        )
    from life_graph.services.lead import LEAD

    if body.target_agent != LEAD and (
        body.temporary or await session_is_temporary(tenant_id, body.session_id)
    ):
        # Only the lead's model is chosen per message, so only it can be held
        # local; a later turn (or a regeneration) of a temporary chat too.
        raise ChatTurnError(
            status_code=400,
            detail="A temporary chat is with Jarvis only.",
        )
    return body


async def _turn_input(tenant_id: str, body: ChatStreamRequest) -> tuple[uuid.UUID, dict[str, Any]]:
    """The turn's conversation (opened here on a first turn) and the spawn's input."""
    # A conversation needs a row to hang its turns off, and the first
    # turn of a new one does not have it yet. Creating it here rather
    # than making the client call /route first keeps a plain chat a
    # single request, and the id goes back on `start` so the next turn
    # can name the conversation it belongs to.
    session_id = body.session_id
    temporary = body.temporary
    if session_id is None:
        session_id = await start_chat_session(
            tenant_id, body.target_agent, body.message, temporary=temporary
        )
        history: list[dict[str, str]] = []
    else:
        history = await load_chat_history(tenant_id, session_id, excluding=body.regenerates)
        # Once temporary, always: a later turn cannot switch it off.
        temporary = temporary or await session_is_temporary(tenant_id, session_id)

    input_data: dict[str, Any] = {"message": body.message, "history": history}
    if body.regenerates is not None:
        input_data["regenerates"] = str(body.regenerates)
    if temporary:
        input_data["temporary"] = True
    if body.shared and body.shared.strip():
        # The model reads both; the owner's typed words stay apart, so
        # memory_save's "did the owner ask" reads only them
        # (tools/memory_search.py _owner_message).
        input_data.update(
            message=with_shared(body.message, body.shared),
            owner_message=body.message,
            shared=body.shared,
            # Someone else wrote it: the run starts as if it had read
            # an email, so the text cannot save, forget or delegate in
            # the owner's name (core/run_taint.py; owner's call
            # 2026-10-25, second review).
            **{TAINT_INPUT_KEY: True},
        )
    if body.client_id:
        input_data["client_id"] = body.client_id
    return session_id, input_data


async def stream_turn(tenant_id: str, body: ChatStreamRequest, pm: Any) -> AsyncIterator[str]:
    """Spawn the turn and yield its SSE frames until the top-level done or error.

    Chat protocol events: start, assistant_delta{text},
    delegation_start{child_id,persona}, child_delta{child_id,persona,text},
    child_done{child_id,persona}, done{}, error{message}.
    """
    bus = get_chat_stream_bus()

    def sse(obj: dict) -> str:
        return f"data: {json.dumps(obj)}\n\n"

    # pm.spawn() (AgentTask insert + TASK_SPAWNED emit) now runs as the
    # first thing INSIDE the generator rather than before this function
    # returns its StreamingResponse — Starlette sends response headers
    # as soon as that Response object is returned, before ever pulling
    # the first item from this generator, so moving the DB work here
    # means the client's connection opens right after the (cached)
    # persona lookup instead of waiting on this insert too.
    try:
        session_id, input_data = await _turn_input(tenant_id, body)
        spawn = await pm.spawn(
            tenant_id=tenant_id,
            agent_name=body.target_agent,
            input_data=input_data,
            task_name=f"chat:{body.target_agent}",
            session_id=session_id,
            project_id=body.project_id,
        )
    except Exception as exc:
        yield sse({"type": "error", "message": str(exc)})
        return
    task_id = spawn["task_id"]  # == root_task_id for a top-level task

    yield sse(
        {
            "type": "start",
            "task_id": task_id,
            "persona": body.target_agent,
            "session_id": str(session_id),
        }
    )
    seen: set[str] = set()
    it = bus.subscribe(task_id).__aiter__()
    # A delegated child waiting on a slow model can leave the bus idle for
    # well over a minute; without a periodic keep-alive, proxies/load-
    # balancers time out and drop the connection. `: heartbeat` is an SSE
    # comment line -- ignored by any spec-compliant client (ours only
    # parses "data: " lines).
    #
    # The heartbeat MUST NOT cancel the underlying `__anext__()` wait. We
    # keep a single persistent `pending` future and poll it with
    # `asyncio.wait(..., timeout=...)`, which -- unlike `asyncio.wait_for`
    # -- does NOT cancel the future when the timeout fires. So the subscribe
    # generator's `await q.get()` survives every heartbeat and no events are
    # lost. (`wait_for` would cancel it, throwing CancelledError into the
    # generator, running its `finally` to unregister the subscriber, and
    # silently ending the stream at the first >heartbeat idle gap.)
    pending = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(it.__anext__())
            done_set, _ = await asyncio.wait({pending}, timeout=CHAT_STREAM_HEARTBEAT_SECONDS)
            if not done_set:
                yield ": heartbeat\n\n"
                continue
            try:
                raw = pending.result()
            except StopAsyncIteration:
                pending = None
                break
            pending = None

            mapped = map_bus_event(raw, seen)
            if mapped is None:
                continue
            if mapped["type"] == "delegation_start+done":
                yield sse(
                    {
                        "type": "delegation_start",
                        "child_id": mapped["child_id"],
                        "persona": mapped["persona"],
                    }
                )
                yield sse(
                    {
                        "type": "child_done",
                        "child_id": mapped["child_id"],
                        "persona": mapped["persona"],
                    }
                )
                continue
            yield sse(mapped)
            # Only a TOP-LEVEL (depth-0) done/error ends the stream. A delegated
            # child's error surfaces to the client as the non-fatal `child_error`
            # chat event (mapped by map_bus_event, never "error" for depth>=1),
            # since the delegation architecture continues past child failures
            # (tools/delegate.py, services/delegation.py default
            # on_child_failure="continue") — Jarvis keeps running and the
            # client should keep receiving events up to the real top-level done.
            # `child_error` is neither "done" nor "error" so this check never
            # breaks the stream on it, by construction.
            if mapped["type"] in ("done", "error") and raw.get("depth", 0) == 0:
                break
    finally:
        # Cancel any in-flight `__anext__()` and let it settle before we
        # aclose() the generator -- awaiting a closing generator that still
        # has a pending anext would raise "already running".
        if pending is not None:
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await pending
        bus.close(task_id)
        await it.aclose()
