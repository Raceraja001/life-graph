"""Dev tasks — "do X in project Y", submitted from the dashboard.

Each task is an ``AgentTask`` row (``properties.kind == "dev_task"``) run in
the background through :meth:`TaskDispatcher.dispatch_task`: isolated
worktree, sandboxed verification, landing on an ``lg/task-*`` branch, and the
``driver_pr`` / ``driver_merge`` approvals that follow. The row is what the
dashboard polls; the approvals carry the PR and merge state.

Runs happen in the API process, not the ARQ worker: drivers are registered in
the API lifespan, and a dispatch plus one bounce can outlast the worker's job
timeout, whose automatic retry would re-run a coding agent. The cost of an
in-process run is that an API restart abandons it —
:func:`fail_interrupted` marks those rows failed at startup instead of
leaving them "running" forever (which would also hold a WIP slot).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update

from life_graph.models.db import AgentTask, Approval

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

KIND = "dev_task"
AGENT_NAME = "dev_task"

# Strong references: asyncio keeps only weak ones to running tasks.
_background: set[asyncio.Task] = set()


def _kind_filter():
    return AgentTask.properties["kind"].astext == KIND


def _history(task: AgentTask, status: str, note: str | None = None) -> list:
    entry = {"status": status, "at": datetime.now(UTC).isoformat()}
    if note:
        entry["note"] = note[:500]
    return [*(task.status_history or []), entry]


async def create_dev_task(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    *,
    instruction: str,
    project: dict[str, Any],
    persona_name: str,
    task_type: str = "code_change",
) -> dict[str, Any]:
    """Record a dev task and start it in the background."""
    task_id = uuid.uuid4()
    title = instruction.strip().splitlines()[0][:200] if instruction.strip() else "Dev task"
    async with session_factory() as session:
        task = AgentTask(
            id=task_id,
            tenant_id=tenant_id,
            agent_name=AGENT_NAME,
            task_name=title,
            title=title,
            instructions=instruction,
            task_type=task_type,
            assigned_agent=persona_name,
            project_id=uuid.UUID(project["id"]),
            status="queued",
            input={"instruction": instruction, "persona": persona_name, "project": project["name"]},
            properties={"kind": KIND, "project_name": project["name"]},
            tags=[KIND],
            status_history=[{"status": "queued", "at": datetime.now(UTC).isoformat()}],
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        data = serialize(task, [])

    bg = asyncio.create_task(
        _run(
            session_factory,
            tenant_id,
            str(task_id),
            instruction,
            project["id"],
            persona_name,
            task_type,
        )
    )
    _background.add(bg)
    bg.add_done_callback(_background.discard)
    return data


async def _run(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    task_id: str,
    instruction: str,
    project_id: str,
    persona_name: str,
    task_type: str,
) -> None:
    from life_graph.core.events import event_bus
    from life_graph.core.tenant import set_tenant_context
    from life_graph.drivers.dispatcher import TaskDispatcher

    set_tenant_context(tenant_id)
    pk = uuid.UUID(task_id)
    async with session_factory() as session:
        task = await session.get(AgentTask, pk)
        task.status = "running"
        task.started_at = datetime.now(UTC)
        task.status_history = _history(task, "running")
        await session.commit()

    status, error, result_data = "failed", None, {}
    try:
        dispatcher = TaskDispatcher(session_factory=session_factory, event_bus=event_bus)
        async with session_factory() as session:
            result = await dispatcher.dispatch_task(
                tenant_id=tenant_id,
                task_id=task_id,
                instruction=instruction,
                task_type=task_type,
                project_id=project_id,
                session=session,
                persona_name=persona_name,
                interactive=True,  # user-started: the governor must not block it
                isolate_workdir=True,
            )
            await session.commit()
        status = "completed" if result.success else "failed"
        error = result.error
        result_data = {
            "success": result.success,
            "output": (result.output or "")[:8000],
            "cost_usd": result.cost_usd,
            "duration_ms": result.duration_ms,
            "metadata": result.metadata or {},
        }
    except Exception as exc:  # DispatchError (WIP, no driver) or a crash
        logger.warning("Dev task %s failed to dispatch: %s", task_id, exc, exc_info=True)
        error = str(exc)[:2000]

    async with session_factory() as session:
        task = await session.get(AgentTask, pk)
        task.status = status
        task.error = error
        task.result = result_data
        task.completed_at = datetime.now(UTC)
        task.status_history = _history(task, status, error)
        await session.commit()


async def list_dev_tasks(session: AsyncSession, tenant_id: str, limit: int = 50) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(AgentTask)
                .where(AgentTask.tenant_id == tenant_id, _kind_filter())
                .order_by(AgentTask.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    approvals = await _approvals_by_task(session, tenant_id, [str(r.id) for r in rows])
    return [serialize(r, approvals.get(str(r.id), [])) for r in rows]


async def get_dev_task(session: AsyncSession, tenant_id: str, task_id: str) -> dict | None:
    try:
        pk = uuid.UUID(task_id)
    except ValueError:
        return None
    task = await session.get(AgentTask, pk)
    if task is None or task.tenant_id != tenant_id or (task.properties or {}).get("kind") != KIND:
        return None
    approvals = await _approvals_by_task(session, tenant_id, [task_id])
    return serialize(task, approvals.get(task_id, []))


async def _approvals_by_task(
    session: AsyncSession, tenant_id: str, task_ids: list[str]
) -> dict[str, list[Approval]]:
    if not task_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(Approval).where(
                    Approval.tenant_id == tenant_id,
                    Approval.source_ref.in_(task_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    out: dict[str, list[Approval]] = {}
    for a in rows:
        out.setdefault(a.source_ref, []).append(a)
    return out


def _stage(task: AgentTask, approvals: list[Approval]) -> str:
    """One word for where the task is in the pipeline, for the UI."""
    by_kind = {a.kind: a for a in approvals}
    merge, pr = by_kind.get("driver_merge"), by_kind.get("driver_pr")
    if merge is not None:
        return {"approved": "merged", "rejected": "pr_open"}.get(merge.status, "awaiting_merge")
    if pr is not None:
        return {"approved": "pr_open", "rejected": "pr_rejected"}.get(pr.status, "awaiting_pr")
    if task.status in ("queued", "running"):
        return task.status
    if (task.result or {}).get("metadata", {}).get("landed_branch"):
        return "landed"  # verified branch, but no PR approval was filed
    if (task.result or {}).get("metadata", {}).get("needs_human") or any(
        a.status == "pending" for a in approvals
    ):
        return "needs_review"
    return task.status


def serialize(task: AgentTask, approvals: list[Approval]) -> dict[str, Any]:
    result = task.result or {}
    metadata = result.get("metadata") or {}
    pr = next((a for a in approvals if a.kind == "driver_pr"), None)
    merge = next((a for a in approvals if a.kind == "driver_merge"), None)
    return {
        "id": str(task.id),
        "title": task.title,
        "instruction": task.instructions,
        "project_id": str(task.project_id) if task.project_id else None,
        "project_name": (task.properties or {}).get("project_name"),
        "persona": task.assigned_agent,
        "status": task.status,
        "stage": _stage(task, approvals),
        "error": task.error,
        "output": result.get("output"),
        "cost_usd": result.get("cost_usd"),
        "duration_ms": result.get("duration_ms"),
        "branch": metadata.get("landed_branch"),
        "pr_url": (pr.payload or {}).get("pr_url") if pr else None,
        "merge_commit": (merge.payload or {}).get("merge_commit") if merge else None,
        "approvals": [
            {"id": str(a.id), "kind": a.kind, "status": a.status, "title": a.title}
            for a in approvals
        ],
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


async def fail_interrupted(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Mark dev tasks left queued/running by a previous process as failed."""
    async with session_factory() as session:
        result = await session.execute(
            update(AgentTask)
            .where(_kind_filter(), AgentTask.status.in_(["queued", "running"]))
            .values(
                status="failed",
                error="Interrupted: the API restarted while this task was running",
                completed_at=datetime.now(UTC),
            )
        )
        await session.commit()
        return result.rowcount or 0
