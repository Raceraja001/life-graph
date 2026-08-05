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
