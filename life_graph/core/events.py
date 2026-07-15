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
import json
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

    # ── OS Kernel Events ──────────────────────────────────
    TASK_SPAWNED = "kernel:task:spawned"
    TASK_COMPLETED = "kernel:task:completed"
    TASK_FAILED = "kernel:task:failed"
    TASK_CANCELLED = "kernel:task:cancelled"
    TASK_TIMEOUT = "kernel:task:timeout"

    # ── Scheduler Events ─────────────────────────────────
    SCHEDULE_FIRED = "kernel:schedule:fired"
    SCHEDULE_DISABLED = "kernel:schedule:disabled"

    # ── Project Events ───────────────────────────────────
    PROJECT_REGISTERED = "kernel:project:registered"
    PROJECT_SCANNED = "kernel:project:scanned"

    # ── Notification Events ──────────────────────────────
    NOTIFICATION_CREATED = "kernel:notification:created"

    # ── Personal AI Events ───────────────────────────────────
    PREFERENCE_CREATED = "preference:created"
    PREFERENCE_UPDATED = "preference:updated"
    PREFERENCE_CHALLENGED = "preference:challenged"
    EVIDENCE_ADDED = "evidence:added"
    RESEARCH_COMPLETED = "research:completed"

    # ── Watcher Events ───────────────────────────────────
    WATCHER_COMPLETED = "watcher:completed"
    WATCHER_FAILED = "watcher:failed"

    # ── Agent Network Events ─────────────────────────────
    TASK_DELEGATED = "agent:task:delegated"
    TASK_AGENT_COMPLETED = "agent:task:completed"
    TASK_AGENT_FAILED = "agent:task:failed"
    TASK_CHILDREN_COMPLETE = "agent:task:children_complete"
    TASK_CHILD_FAILED = "agent:task:child_failed"
    TASK_HANDOFF = "agent:task:handoff"
    TASK_AGENT_CANCELLED = "agent:task:cancelled"
    MESSAGE_SENT = "agent:message:sent"
    MESSAGE_READ = "agent:message:read"
    WORKFLOW_STARTED = "agent:workflow:started"
    WORKFLOW_COMPLETED = "agent:workflow:completed"
    WORKFLOW_FAILED = "agent:workflow:failed"
    WORKFLOW_STEP_COMPLETED = "agent:workflow:step_completed"
    SYNC_COMPLETED = "agent:sync:completed"
    SYNC_FAILED = "agent:sync:failed"
    CONTEXT_SHARED = "agent:context:shared"

    # ── Autonomous AI Events ─────────────────────────────
    AUTONOMOUS_ACTION_COMPLETED = "autonomy:action:completed"
    AUTONOMOUS_ACTION_PENDING = "autonomy:action:pending"
    SHADOW_RECORDED = "autonomy:shadow:recorded"
    SHADOW_GRADUATED = "autonomy:shadow:graduated"

    # ── Capture Spine Events ─────────────────────────────────
    CAPTURE_RECEIVED = "capture:received"
    CORRECTION_RECORDED = "capture:correction:recorded"
    DECISION_CANDIDATE = "capture:decision:candidate"
    PROCEDURE_CANDIDATE = "capture:procedure:candidate"
    INTERVIEW_ASKED = "capture:interview:asked"
    INTERVIEW_ANSWERED = "capture:interview:answered"
    BRIEF_COMPOSED = "capture:brief:composed"

    # ── Judgment Engine Events ────────────────────────────────
    DECISION_RECORDED = "judgment:decision:recorded"
    DECISION_SUPERSEDED = "judgment:decision:superseded"
    PREDICTION_CREATED = "judgment:prediction:created"
    PREDICTION_RESOLVED = "judgment:prediction:resolved"
    CALIBRATION_UPDATED = "judgment:calibration:updated"
    DECISION_CHALLENGED = "judgment:decision:challenged"
    BIAS_DETECTED = "judgment:bias:detected"

    # ── Agent Driver Events ──────────────────────────────────
    DRIVER_DISPATCHED = "driver:dispatched"
    DRIVER_RESULT = "driver:result"
    VERIFICATION_PASSED = "driver:verification:passed"
    VERIFICATION_FAILED = "driver:verification:failed"
    SECOND_OPINION_DISSENT = "driver:second_opinion:dissent"
    TASK_BOUNCED = "driver:task:bounced"
    PIPELINE_TASK_ORIGINATED = "driver:pipeline:task_originated"


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


# ── Redis Bridge ─────────────────────────────────────────────


def _json_serializer(obj: Any) -> str:
    """JSON serializer that handles datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class RedisBridge:
    """Bridge that publishes EventBus events to Redis pub/sub channels.

    Each event is published to ``events:{tenant_id}:{event_type}``
    where tenant_id comes from the current tenant context or defaults
    to 'system'.
    """

    async def publish(self, event: Event) -> None:
        """Publish an event to Redis.

        Uses ``get_current_tenant_id()`` if available, falls back to 'system'.
        Serializes the event to JSON, handling datetime with isoformat.
        """
        # Import here to avoid circular imports at module level
        from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
        from life_graph.storage.redis import get_redis

        tenant_id = "system"
        if has_tenant_context():
            try:
                tenant_id = get_current_tenant_id()
            except RuntimeError:
                pass

        channel = f"events:{tenant_id}:{event.type.value}"
        data = json.dumps(
            {
                "type": event.type.value,
                "payload": event.payload,
                "timestamp": event.timestamp.isoformat(),
                "source": event.source,
            },
            default=_json_serializer,
        )

        r = get_redis()
        if r is None:
            logger.debug("Redis unavailable — skipping bridge publish for %s", channel)
            return

        try:
            await r.publish(channel, data)
            logger.debug("Published event to Redis channel %s", channel)
        except Exception:
            logger.warning("Failed to publish event to Redis channel %s", channel, exc_info=True)


# Module-level bridge instance
_redis_bridge = RedisBridge()


async def _bridge_handler(event: Event) -> None:
    """EventBus handler that forwards events to the Redis bridge."""
    await _redis_bridge.publish(event)


def enable_redis_bridge() -> None:
    """Enable the Redis bridge by subscribing it to the global event bus.

    Call this during application startup after Redis has been initialized.
    Events will be forwarded to Redis pub/sub channels for cross-instance
    communication.
    """
    event_bus.subscribe_all(_bridge_handler)
    logger.info("Redis bridge enabled — events will be published to Redis")
