"""Async event bus for the Life Graph plugin architecture (T-079).

Provides a lightweight pub-sub event system with async handlers.
All handlers execute concurrently via ``asyncio.gather`` and failures
in individual handlers are logged but never propagate to the emitter.

Usage::

    from life_graph.core.events import event_bus, EventType

    async def on_memory_created(event):
        print(f"New memory: {event.payload}")

    event_bus.subscribe(EventType.MEMORY_CREATED, on_memory_created)
    await event_bus.emit(EventType.MEMORY_CREATED, {"id": "abc"})
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """All event types emitted within the Life Graph system."""

    MEMORY_CREATED = "memory:created"
    MEMORY_RETRIEVED = "memory:retrieved"
    MEMORY_UPDATED = "memory:updated"
    MEMORY_DELETED = "memory:deleted"
    SESSION_START = "session:start"
    SESSION_END = "session:end"
    INTENTION_TRIGGERED = "intention:triggered"
    CONTRADICTION_DETECTED = "contradiction:detected"
    VOICE_TRANSCRIBED = "voice:transcribed"
    IMAGE_PROCESSED = "image:processed"
    DOCUMENT_IMPORTED = "document:imported"


@dataclass
class Event:
    """An event emitted by the system.

    Attributes:
        type: The event type enum value.
        payload: Arbitrary data associated with the event.
        timestamp: UTC timestamp of when the event was created.
        source: Identifier for the subsystem that emitted the event.
    """

    type: EventType
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "system"


# Handler type: an async callable that accepts a single Event argument.
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Pub-sub event bus with async handlers.

    Handlers are invoked concurrently for each emitted event.
    Errors in individual handlers are caught and logged so that
    one failing handler never blocks or crashes the rest of the system.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register *handler* to be called whenever *event_type* is emitted."""
        self._handlers.setdefault(event_type, []).append(handler)
        logger.debug("Subscribed %s to %s", handler.__qualname__, event_type.value)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Register *handler* to be called for **every** event type."""
        self._global_handlers.append(handler)
        logger.debug("Subscribed %s to ALL events", handler.__qualname__)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove *handler* from *event_type* subscriptions.

        Silently ignores handlers that are not currently subscribed.
        """
        handlers = self._handlers.get(event_type, [])
        try:
            handlers.remove(handler)
            logger.debug("Unsubscribed %s from %s", handler.__qualname__, event_type.value)
        except ValueError:
            pass

    async def emit(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        source: str = "system",
    ) -> None:
        """Emit an event to all subscribed handlers (fire-and-forget).

        Creates an :class:`Event`, gathers all matching handlers, and
        invokes them concurrently.  Any handler that raises is logged
        at ERROR level but does not affect other handlers.

        Args:
            event_type: The type of event to emit.
            payload: Event data dictionary.
            source: Identifier for the emitting subsystem.
        """
        event = Event(type=event_type, payload=payload, source=source)

        handlers: list[EventHandler] = list(self._global_handlers)
        handlers.extend(self._handlers.get(event_type, []))

        if not handlers:
            return

        results = await asyncio.gather(
            *(self._safe_invoke(h, event) for h in handlers),
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error(
                    "Event handler %s failed for %s: %s",
                    handlers[i].__qualname__,
                    event_type.value,
                    result,
                    exc_info=result,
                )

    @staticmethod
    async def _safe_invoke(handler: EventHandler, event: Event) -> None:
        """Invoke a single handler, allowing exceptions to propagate to gather."""
        await handler(event)


# ── Built-in debug logging handler ────────────────────────────

async def _debug_log_handler(event: Event) -> None:
    """Log every event at DEBUG level."""
    logger.debug(
        "Event %s from %s: %s",
        event.type.value,
        event.source,
        event.payload,
    )


# ── Global singleton ─────────────────────────────────────────

event_bus = EventBus()
event_bus.subscribe_all(_debug_log_handler)
