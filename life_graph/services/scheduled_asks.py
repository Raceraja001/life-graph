"""Jarvis acts on its own: asks the owner set once in chat (web-chat-wave1 F1).

"Every Monday at 9, summarise my week" becomes a kernel ``ScheduledJob`` for
jarvis (``properties.origin == "chat"``) through the ``ask_schedule`` tool
(tools/schedules.py). When it fires (workers/tasks.py tick_scheduled_jobs) it
runs as the owner's own message, on the local model (the ``personal:``
switch, services/lead.py), as a new turn of the chat it was set in; when that
turn completes a ``Notification`` carries the answer to the phone and the web.

Only the owner's words make one: the tool refuses on a run that read outside
content unless the owner's typed message asks for something recurring.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from life_graph.core.events import Event, EventType, event_bus

logger = logging.getLogger(__name__)

ORIGIN = "chat"
SOURCE_TYPE = "scheduled_ask"
MAX_ACTIVE = 20
MAX_ASK_CHARS = 500
NOTIFY_BODY_CHARS = 600


class AskError(ValueError):
    """Why an ask cannot be set, in words for the owner."""


async def active_count(session_factory, tenant_id: str) -> int:
    from life_graph.models.db import ScheduledJob

    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(ScheduledJob)
                .where(
                    ScheduledJob.tenant_id == tenant_id,
                    ScheduledJob.is_active.is_(True),
                    ScheduledJob.properties["origin"].astext == ORIGIN,
                )
            )
            or 0
        )


async def create(
    scheduler: Any,
    session_factory,
    tenant_id: str,
    *,
    ask: str,
    when: str,
    tz: str,
    session_id: str | None,
) -> dict[str, Any]:
    """Store one ask; the job dict back. Raises AskError when it cannot."""
    from life_graph.services.recurrence import parse_recurrence

    words = " ".join(ask.split())
    if len(words) < 3:
        raise AskError("What should I do each time? Ask the user.")
    if len(words) > MAX_ASK_CHARS:
        raise AskError(f"Too long: keep the ask under {MAX_ASK_CHARS} characters.")
    cron = parse_recurrence(when, tz)
    if cron is None:
        raise AskError(
            f"I could not read {when!r} as a repeating time. Ask the user, e.g."
            " 'every Monday at 9' or 'every day at 7 pm'."
        )
    if await active_count(session_factory, tenant_id) >= MAX_ACTIVE:
        raise AskError(f"There are already {MAX_ACTIVE} asks running; pause or remove one first.")
    return await scheduler.create(
        tenant_id,
        {
            "name": f"ask-{uuid.uuid4().hex[:12]}",
            "description": words,
            "cron_expression": cron,
            "agent_name": "jarvis",
            "input": {},
            "properties": {
                "origin": ORIGIN,
                "ask": words,
                "when": " ".join(when.split()),
                "session_id": session_id,
                "tz": tz,
            },
        },
    )


def is_ask(job: dict[str, Any]) -> bool:
    return (job.get("properties") or {}).get("origin") == ORIGIN


def turn_input(job: dict[str, Any]) -> tuple[dict[str, Any], uuid.UUID | None]:
    """What a firing ask runs: the owner's words, local, and the chat it belongs to."""
    props = job.get("properties") or {}
    session_id = None
    if props.get("session_id"):
        try:
            session_id = uuid.UUID(str(props["session_id"]))
        except ValueError:
            session_id = None
    data = {
        # The owner's own words, kept local whatever they say (services/lead.py).
        "message": f"personal: {props.get('ask') or job.get('description') or ''}",
        "history": [],
        "scheduled_ask_id": str(job["id"]),
        "origin": "scheduled",
    }
    return data, session_id


def as_listed(job: dict[str, Any], last_reply: str | None = None) -> dict[str, Any]:
    props = job.get("properties") or {}
    return {
        "id": str(job["id"]),
        "ask": props.get("ask") or job.get("description"),
        "when": props.get("when"),
        "cron": job.get("cron_expression"),
        "active": bool(job.get("is_active")),
        "next_run_at": job.get("next_run_at"),
        "last_run_at": job.get("last_run_at"),
        "last_run_status": job.get("last_run_status"),
        "last_reply": last_reply,
        "session_id": props.get("session_id"),
    }


async def notify_result(session_factory, tenant_id: str, task_id: str) -> bool:
    """A finished ask's answer as a Notification; False when the task is not an ask."""
    from life_graph.models.db import AgentTask, Notification

    async with session_factory() as session:
        task = await session.get(AgentTask, uuid.UUID(task_id))
        if task is None or task.tenant_id != tenant_id:
            return False
        ask_id = (task.input or {}).get("scheduled_ask_id")
        reply = str((task.result or {}).get("response") or "").strip()
        if not ask_id or not reply:
            return False
        ask = str((task.input or {}).get("message") or "").removeprefix("personal: ")
        now = datetime.now(UTC)
        session.add(
            Notification(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                priority="info",
                title=f"Jarvis: {ask}"[:500],
                body=reply[:NOTIFY_BODY_CHARS],
                extra_metadata={
                    "kind": SOURCE_TYPE,
                    "ask_id": ask_id,
                    "task_id": task_id,
                    "conversation_id": str(task.session_id) if task.session_id else None,
                },
                source_type=SOURCE_TYPE,
                source_id=task.id,
                # The phone polls for these, as for due notifications.
                is_delivered=True,
                delivered_at=now,
            )
        )
        await session.commit()
    return True


class ScheduledAskResults:
    """TASK_COMPLETED → a Notification for each finished ask. Subscribed in the
    worker, where scheduled jarvis turns run (workers/settings.py)."""

    def __init__(self) -> None:
        self._subscribed = False

    def subscribe(self) -> None:
        if self._subscribed:
            return
        event_bus.subscribe(EventType.TASK_COMPLETED, self._on_completed)
        self._subscribed = True

    async def _on_completed(self, event: Event) -> None:
        data = event.payload
        if (
            data.get("agent_name") != "jarvis"
            or not data.get("tenant_id")
            or not data.get("task_id")
        ):
            return
        from life_graph.storage.database import async_session

        try:
            await notify_result(async_session, data["tenant_id"], data["task_id"])
        except Exception:  # never break task completion
            logger.warning("Scheduled ask notification failed", exc_info=True)


scheduled_ask_results = ScheduledAskResults()
