"""continue_task: continue a finished dev task in its own session and worktree.

docs/specs/agent-drivers.md, "Phase 3b part 2". What race-app's PR-feedback
loop and "request changes" call (``POST /kernel/drivers/tasks/{id}/continue``,
owner only). Rebuilt from race-app's ``providers/local/engine-control.ts``.

This only decides and queues: the task goes back to ``queued`` (start now,
interactive -- the owner asked) with ``properties.continue_request``; the
dev-task runner then runs :meth:`TaskDispatcher.continue_dispatch` in the task's
kept worktree with ``driver.resume`` on the same session and account, and the
normal verify/land chain follows. One runner, one lock, one cancel path.

Refusals (:class:`ContinueError`, each with an HTTP status):

* ``continue_disabled`` 409 -- ``driver_continue_enabled`` is off;
* ``not_found`` 404 -- no such dev task for this tenant;
* ``busy`` 409 -- queued, running or parked: continue it once it finished;
* ``not_continuable`` 409 -- cancelled, or its PR is already merged/closed;
* ``no_session`` 409 -- the run left no CLI session (or the kept record is gone);
* ``no_workdir`` 409 -- the kept worktree was removed or is no longer intact;
* ``resume_unsupported`` 409 -- its driver cannot resume a session;
* ``paused`` 409 -- the kill switch is on.

In each case nothing changes; a fresh task with the feedback is the fallback.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.autonomy.kill_switch import autonomy_stopped
from life_graph.config import settings
from life_graph.drivers.registry import driver_registry
from life_graph.drivers.workdir import worktree_intact
from life_graph.models.db import AgentTask
from life_graph.services.dev import task_events
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev.runner import notify_runner

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

MAX_FEEDBACK_CHARS = 8000
MAX_REASON_CHARS = 200
_BUSY = frozenset({"queued", "running", "parked"})
_CONTINUABLE = frozenset({"completed", "failed", "timeout"})
_FINISHED_STAGES = frozenset({"merged", "closed"})


class ContinueError(Exception):
    """continue_task refused; ``code`` names why, ``http_status`` for the API."""

    def __init__(self, code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


async def continue_task(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    task_id: str,
    feedback: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Queue *task_id* to continue in its own session with *feedback*.

    Returns the task as :func:`~life_graph.services.dev.tasks.serialize` shows
    it (status ``queued``). Raises :class:`ContinueError`.
    """
    if not settings.driver_continue_enabled:
        raise ContinueError(
            "continue_disabled", "Continuing tasks is off (driver_continue_enabled=false)"
        )
    feedback = (feedback or "").strip()[:MAX_FEEDBACK_CHARS]
    if not feedback:
        raise ContinueError("no_feedback", "Feedback is required", 422)
    reason = ((reason or "feedback").strip() or "feedback")[:MAX_REASON_CHARS]
    try:
        pk = uuid.UUID(str(task_id))
    except ValueError:
        raise ContinueError("not_found", "Dev task not found", 404) from None

    async with session_factory() as session:
        task = (
            await session.execute(
                select(AgentTask)
                .where(
                    AgentTask.id == pk,
                    AgentTask.tenant_id == tenant_id,
                    dev_tasks._kind_filter(),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if task is None:
            raise ContinueError("not_found", "Dev task not found", 404)
        record, approvals = await _check_continuable(session, tenant_id, task)
        if await autonomy_stopped(tenant_id):
            raise ContinueError("paused", "Autonomy is paused (kill switch); resume it first")

        now = datetime.now(UTC)
        props = dict(task.properties or {})
        props["continue_request"] = {
            "feedback": feedback,
            "reason": reason,
            "requested_at": now.isoformat(),
        }
        props["start_now"] = True
        props["interactive"] = True
        props.pop("park", None)
        task.properties = props
        task.status = "queued"
        task.error = None
        task.started_at = None
        task.completed_at = None
        task.status_history = dev_tasks._history(task, "queued", f"continuing: {reason}")
        await session.commit()
        data = dev_tasks.serialize(task, approvals)

    task_events.emit(
        tenant_id, str(pk), "status", "queued",
        data={"continue": True, "reason": reason, "round": int(record.get("rounds") or 0) + 1},
        source="api",
    )  # fmt: skip
    await dev_tasks._emit_bus(
        "TASK_CONTINUED",
        {"tenant_id": tenant_id, "task_id": str(pk), "reason": reason,
         "driver": record.get("driver")},
    )  # fmt: skip
    await notify_runner()
    return data


async def _check_continuable(
    session: AsyncSession, tenant_id: str, task: AgentTask
) -> tuple[dict, list]:
    """``(continuation record, approvals)`` or a :class:`ContinueError`."""
    pk = task.id
    if task.status in _BUSY:
        raise ContinueError("busy", f"Dev task is {task.status}; continue it once it has finished")
    if task.status not in _CONTINUABLE:
        raise ContinueError("not_continuable", f"Cannot continue a {task.status} dev task")
    approvals = (await dev_tasks._approvals_by_task(session, tenant_id, [str(pk)])).get(str(pk), [])
    stage = dev_tasks._stage(task, approvals)
    if stage in _FINISHED_STAGES:
        raise ContinueError(
            "not_continuable", f"The task's PR is already {stage}; start a new task"
        )
    record = (task.properties or {}).get("continuation")
    if not isinstance(record, dict) or not record.get("session_id"):
        raise ContinueError("no_session", "This task left no agent session to continue")
    worktree, origin = record.get("worktree"), record.get("origin")
    if not worktree or not origin or not Path(worktree).is_dir():
        raise ContinueError("no_workdir", "This task's worktree is gone; start a new task")
    if not worktree_intact(Path(worktree), origin):
        raise ContinueError("no_workdir", "This task's worktree is no longer intact")
    driver = driver_registry.get(record.get("driver") or "")
    if driver is None or not getattr(driver, "supports_resume", False):
        raise ContinueError(
            "resume_unsupported", f"Driver {record.get('driver')!r} cannot resume a session"
        )
    return record, approvals
