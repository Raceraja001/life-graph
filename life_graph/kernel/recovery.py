"""Close out kernel tasks a dead process left behind (audit M2).

ProcessManager runs every chat turn, persona run and scheduled task as an
asyncio task inside the process that spawned it: the API, or the ARQ worker.
When that process dies (a crash, a kill, a release), the task dies with it,
but its ``agent_tasks`` row stays ``queued`` or ``running`` for ever. Nothing
else would ever finish it, and a client polling or resending that turn
sees a reply "still being written".

Dev tasks have their own recovery (services/dev/tasks.py ``fail_interrupted``),
run only by the dev-task runner. This is the same idea for the rest.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

from life_graph.config import settings
from life_graph.models.db import AgentTask

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

#: The error a recovered task is left with.
INTERRUPTED_ERROR = "interrupted (process restarted)"

#: Added to a task's own timeout before it counts as abandoned. Generous on
#: purpose: a queued task's wait for a concurrency slot is not under its
#: timeout, so a live but very busy process can hold one queued past it.
DEFAULT_MARGIN_SECONDS = 3600

# Dev tasks: agent_name and properties.kind as services/dev/tasks.py writes
# them (AGENT_NAME, KIND). Spelled out here so the kernel does not import
# the dev service.
_DEV_TASK = "dev_task"


async def fail_interrupted_kernel_tasks(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime | None = None,
    margin_seconds: int = DEFAULT_MARGIN_SECONDS,
) -> int:
    """Mark abandoned kernel tasks failed. Returns how many.

    A task counts as abandoned when it is ``queued`` or ``running`` and older
    than its own timeout plus ``margin_seconds``. Age is measured from
    ``started_at``, or ``created_at`` for a task that never started, and the
    timeout is the row's ``timeout_seconds`` (the kernel default when it is 0).
    Each one becomes ``failed`` with the error :data:`INTERRUPTED_ERROR`, a
    ``completed_at`` and a ``status_history`` entry saying so.

    Safe to run while other processes are working. The API and the ARQ worker
    both spawn kernel tasks against the same database, and neither knows what
    the other is running, so this never asks. It relies on age instead: a live
    run is cut off by ``asyncio.timeout(timeout_seconds)`` in
    ``ProcessManager._execute_task``, so a running row older than its timeout
    plus the margin cannot still be running anywhere. A queued row waits for
    a concurrency slot outside that timeout, which is what the hour of margin
    is for. A run that is still alive is never touched.

    Only rows ProcessManager.spawn made are touched:

    * not dev tasks (``agent_name`` or ``properties.kind`` ``dev_task``),
      which their runner recovers;
    * only rows whose ``status_history`` is empty. spawn never writes one.
      The task board (services/delegation.py) and agent messages
      (services/agent_messaging.py) always do, and their queued rows are
      work waiting for someone, not runs that died.
    """
    now = now or datetime.now(UTC)
    timeout = func.coalesce(
        func.nullif(AgentTask.timeout_seconds, 0), settings.kernel_default_timeout
    )
    since = func.coalesce(AgentTask.started_at, AgentTask.created_at)
    # make_interval(years, months, weeks, days, hours, mins, secs)
    deadline = since + func.make_interval(0, 0, 0, 0, 0, 0, timeout + margin_seconds)
    stmt = (
        select(AgentTask)
        .where(
            AgentTask.status.in_(("queued", "running")),
            AgentTask.agent_name != _DEV_TASK,
            or_(
                AgentTask.properties["kind"].astext.is_(None),
                AgentTask.properties["kind"].astext != _DEV_TASK,
            ),
            func.jsonb_array_length(AgentTask.status_history) == 0,
            deadline < now,
        )
        # Two processes starting at once must not both close the same rows.
        .with_for_update(skip_locked=True)
    )
    async with session_factory() as session:
        rows = (await session.execute(stmt)).scalars().all()
        for task in rows:
            was = task.status
            task.status = "failed"
            task.error = INTERRUPTED_ERROR
            task.completed_at = now
            task.updated_at = now
            task.status_history = [
                *(task.status_history or []),
                {
                    "status": "failed",
                    "at": now.isoformat(),
                    "note": f"was {was} when its process stopped; failed at startup",
                },
            ]
        await session.commit()
    if rows:
        logger.warning(
            "Marked %d interrupted kernel task(s) failed: %s",
            len(rows),
            ", ".join(f"{t.id!s:.8}" for t in rows[:20]),
        )
    return len(rows)
