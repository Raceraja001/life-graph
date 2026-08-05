"""In-process chat session bus for streaming persona/delegation events.

Persona execution and the SSE endpoint run in the same process (ProcessManager
uses asyncio.create_task), so a per-session asyncio.Queue registry is enough —
no Redis. The stream key is the task tree's ``root_task_id`` (shared by a jarvis
task and all its delegated children). A short retained buffer lets a subscriber
that connects just after spawn still receive the earliest events.

For multi-replica infra later, swap the queue registry for Redis pub/sub on
channel ``stream:{tenant_id}:{root_task_id}`` — same publish/subscribe surface.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_END = {"type": "__end__"}
_BUFFER_MAX = 200


class ChatStreamBus:
    def __init__(self, buffer_max: int = _BUFFER_MAX) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=buffer_max))
        self._closed: set[str] = set()

    def publish(self, stream_key: str, event: dict) -> None:
        self._buffers[stream_key].append(event)
        for q in list(self._subscribers.get(stream_key, [])):
            q.put_nowait(event)

    def close(self, stream_key: str) -> None:
        """Signal end-of-stream to all current + future subscribers."""
        self._closed.add(stream_key)
        self._buffers[stream_key].append(_END)
        for q in list(self._subscribers.get(stream_key, [])):
            q.put_nowait(_END)

    def buffer_len(self, stream_key: str) -> int:
        return len(self._buffers.get(stream_key, ()))

    def discard(self, stream_key: str) -> None:
        """Free buffered/closed state for a key that has no active subscriber.

        Every persona task publishes to the bus, but only an SSE-streamed
        task ever gets a subscriber to drain it -- tasks spawned via
        `/route`, cron, watchers, etc. have no subscriber and would leak a
        `_buffers[stream_key]` deque forever without this. Call it once a
        task tree is done producing events.

        A no-op when a subscriber IS attached (the streamed path): the
        endpoint's own `close()` plus each subscriber's `finally`-block
        cleanup already reclaim that state once they've drained it, and
        dropping it out from under a live subscriber would lose events it
        hasn't read yet.
        """
        if self._subscribers.get(stream_key):
            return
        self._buffers.pop(stream_key, None)
        self._closed.discard(stream_key)
        self._subscribers.pop(stream_key, None)

    async def subscribe(self, stream_key: str) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue()
        # Replay anything already buffered (events fired before we subscribed).
        for ev in list(self._buffers.get(stream_key, ())):
            q.put_nowait(ev)
        # If stream is already closed, signal end-of-stream so late subscribers
        # terminate promptly instead of blocking forever.
        if stream_key in self._closed:
            q.put_nowait(_END)
        self._subscribers[stream_key].append(q)
        try:
            while True:
                ev = await q.get()
                if ev is _END:
                    return
                yield ev
        finally:
            subs = self._subscribers.get(stream_key)
            if subs and q in subs:
                subs.remove(q)
            if not subs and stream_key in self._closed:
                self._buffers.pop(stream_key, None)
                self._subscribers.pop(stream_key, None)


_bus: ChatStreamBus | None = None


def get_chat_stream_bus() -> ChatStreamBus:
    global _bus
    if _bus is None:
        _bus = ChatStreamBus()
    return _bus


def map_bus_event(raw: dict, seen_children: set[str]) -> dict | None:
    """Map one raw bus event to a chat-protocol event, or None to drop it.

    seen_children is caller-owned mutable state tracking which child task_ids
    have already emitted their delegation_start. A child whose first streamed
    event is `done` (no prior token) needs both delegation_start and child_done;
    that case returns the compound marker ``delegation_start+done`` for the
    caller (the SSE endpoint) to expand into two frames.
    """
    depth = raw.get("depth", 0)
    persona = raw.get("agent_name", "")
    child_id = raw.get("task_id", "")
    event = raw.get("event", {})
    etype = event.get("type")

    if depth == 0:
        if etype in ("error", "partial_error"):
            return {"type": "error", "message": event.get("error") or event.get("message", "error")}
        if etype == "token":
            return {"type": "assistant_delta", "text": event.get("content", "")}
        if etype == "done":
            return {"type": "done"}
        return None  # tool_call/tool_result/usage on the top-level task are dropped

    # depth >= 1 : a delegated child
    if etype in ("error", "partial_error"):
        # Non-fatal: the delegation architecture continues past a child failure
        # (Jarvis keeps running and still synthesizes a real answer), so this
        # must NOT be mapped to the same `error` type the endpoint treats as
        # stream-ending. `child_error` marks just that one step as failed.
        return {
            "type": "child_error",
            "child_id": child_id,
            "persona": persona,
            "message": event.get("error") or event.get("message", "error"),
        }
    if etype == "token":
        if child_id not in seen_children:
            seen_children.add(child_id)
            return {"type": "delegation_start", "child_id": child_id, "persona": persona}
        return {
            "type": "child_delta",
            "child_id": child_id,
            "persona": persona,
            "text": event.get("content", ""),
        }
    if etype == "done":
        if child_id not in seen_children:
            seen_children.add(child_id)
            return {"type": "delegation_start+done", "child_id": child_id, "persona": persona}
        return {"type": "child_done", "child_id": child_id, "persona": persona}
    return None
