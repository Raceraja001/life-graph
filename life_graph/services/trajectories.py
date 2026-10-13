"""Trajectory recorder: persists every step of a dev-agent driver run.

Subscribes to ``driver:steps`` (emitted by the dispatcher once per attempt)
and writes one ``agent_run_steps`` row per step, so a run can be replayed in
order and studied later: what the agent read, what it ran, what came back,
where it went wrong.

Two things happen here and nowhere else, so no caller can skip them:
- **redaction**: tool results routinely contain file contents, which can
  include secrets (a read of ``.env``); every step's content goes through
  services/redaction.py before it is stored.
- **size cap**: one step's content is cut to ``trajectory_step_max_chars``
  (a whole-file read can be megabytes); ``properties.original_chars`` keeps
  the real length so an analysis can still see that the output was huge.

Recording is best-effort: a failure is logged and never fails the task.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.config import settings
from life_graph.core.events import Event, EventBus, EventType, event_bus
from life_graph.models.db import AgentRunStep
from life_graph.services.redaction import redact

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _parse_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def to_rows(
    tenant_id: str, task_id: uuid.UUID, driver: str, attempt: int, steps: list[dict]
) -> list[AgentRunStep]:
    """Redact, cap and shape a driver's steps into rows (no I/O)."""
    cap = settings.trajectory_step_max_chars
    rows = []
    for i, step in enumerate(steps, start=1):
        content = redact(str(step.get("content") or ""))
        props: dict[str, Any] = {}
        if len(content) > cap:
            props["original_chars"] = len(content)
            content = content[:cap]
        for key in ("ref", "is_error"):
            if step.get(key) is not None:
                props[key] = step[key]
        rows.append(
            AgentRunStep(
                tenant_id=tenant_id,
                task_id=task_id,
                attempt=attempt,
                seq=int(step.get("seq") or i),
                driver=driver,
                kind=str(step.get("kind") or "unknown")[:32],
                tool=(str(step["tool"])[:128] if step.get("tool") else None),
                content=content,
                properties=props,
                step_at=_parse_at(step.get("at")),
            )
        )
    return rows


async def list_steps(session: AsyncSession, tenant_id: str, task_id: uuid.UUID) -> list[dict]:
    """A task's recorded steps, every attempt, in order."""
    rows = (
        (
            await session.execute(
                select(AgentRunStep)
                .where(AgentRunStep.tenant_id == tenant_id, AgentRunStep.task_id == task_id)
                .order_by(AgentRunStep.attempt, AgentRunStep.seq)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "attempt": r.attempt,
            "seq": r.seq,
            "driver": r.driver,
            "kind": r.kind,
            "tool": r.tool,
            "content": r.content,
            "properties": r.properties or {},
            "at": r.step_at.isoformat() if r.step_at else None,
        }
        for r in rows
    ]


class TrajectoryRecorder:
    """Writes ``driver:steps`` events to ``agent_run_steps``."""

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus or event_bus
        self._subscribed = False

    def subscribe(self) -> None:
        if self._subscribed:
            return
        self._bus.subscribe(EventType.DRIVER_STEPS, self._on_steps)
        self._subscribed = True

    def unsubscribe(self) -> None:
        if not self._subscribed:
            return
        self._bus.unsubscribe(EventType.DRIVER_STEPS, self._on_steps)
        self._subscribed = False

    async def _on_steps(self, event: Event) -> None:
        data = event.payload or {}
        steps = data.get("steps") or []
        if not steps or not data.get("tenant_id") or not data.get("task_id"):
            return
        from life_graph.storage.database import async_session

        try:
            rows = to_rows(
                str(data["tenant_id"]),
                uuid.UUID(str(data["task_id"])),
                str(data.get("driver") or "unknown"),
                int(data.get("attempt") or 1),
                steps,
            )
            async with async_session() as session:
                session.add_all(rows)
                await session.commit()
        except Exception:
            logger.warning(
                "Could not record %d step(s) for task %s",
                len(steps),
                data.get("task_id"),
                exc_info=True,
            )


trajectory_recorder = TrajectoryRecorder()
