"""Parallel plans ("teams"): workers on their own branches, one integration task.

docs/specs/agent-drivers.md, "Phase 4b". Off by default
(``driver_team_max_parallel = 1``: plans fan out exactly as before, one task
at a time, each merged before the next starts). With it above 1, an approved
plan whose Tasks declare file scopes (``Files: a.py, src/**``) becomes a team:

1. **Workers** -- one dev task per plan task, queued. Tasks whose scopes
   overlap an earlier task's get ``depends_on`` on it (and start from its
   change, committed); the rest run at once, at most ``max_parallel`` per plan
   (and within the project's WIP limit and the runner's concurrency). Each
   worker ends on its own ``lg/task-*`` branch with **no approval and no PR**
   (branch hand-off). A task with no declared scope overlaps everything.
2. **Integration** -- one more dev task, ``depends_on`` every worker: it starts
   from all the workers' changes applied with ``git apply --3way`` (conflict
   markers left for the agent), runs the normal verifier chain with every
   criterion the spec binds, and files the plan's **single** ``driver_pr``
   approval. Nothing approves or merges on its own.
3. **Failure** -- any worker failing (or being cancelled) cancels the rest and
   the integration task, and the team is ``failed`` (the owner is told once);
   re-approving the plan starts a new team.

The group row (``dev_task_groups``, kind ``team``) and the tasks' properties
are the state; :func:`reconcile` (the runner's loop) moves the team along, so
a restart resumes it. Rebuilt from race-app's ``automation/team/**`` (the
owner's code); the plan comes from the existing plan task, not a separate lead
agent.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.drivers.plan_spec import parse_task_files
from life_graph.models.db import AgentTask, DevTaskGroup
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev.team_scope import overlap_dependencies, parallel_waves

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

KIND = "team"
ACTIVE = ("running", "integrating")
_BROKEN = frozenset({"failed", "cancelled", "timeout"})
_OPEN = frozenset({"queued", "running", "parked"})
_APPROVAL_STAGES = frozenset({"awaiting_pr", "pr_open", "awaiting_merge", "merged"})


def team_mode(items: list[str]) -> bool:
    """Whether an approved plan with these tasks runs as a team."""
    return (
        int(settings.driver_team_max_parallel) > 1
        and len(items) >= 2
        and any(parse_task_files(i) for i in items)
    )


def worker_instruction(
    instruction: str, spec: str, item: str, index: int, count: int, files: list[str]
) -> str:
    """What one worker is asked to do."""
    scope = ", ".join(files) if files else "(not declared)"
    return (
        f"{instruction}\n\n"
        "--- APPROVED PLAN (full spec, for context) ---\n"
        f"{spec}\n\n"
        f"--- YOUR TASK ({index} of {count}) ---\n"
        f"{item}\n\n"
        "You are one of several workers doing this plan in parallel, each in its own "
        f"worktree. Change only what your task needs (your declared files: {scope}); "
        "the other tasks are someone else's, and every worker's change is integrated "
        "afterwards."
    )


def integration_instruction(instruction: str, spec: str, count: int) -> str:
    """What the integration task is asked to do."""
    return (
        f"{instruction}\n\n"
        "--- APPROVED PLAN (full spec, for context) ---\n"
        f"{spec}\n\n"
        "--- YOUR TASK: INTEGRATE ---\n"
        f"The plan's {count} tasks were done in parallel by separate workers, each on its "
        "own branch. Their changes are applied to this worktree (listed below). Make them "
        "one working change: resolve every conflict, fix what does not fit together, and "
        "make every acceptance criterion of the plan pass."
    )


async def fan_out(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    *,
    plan_task_id: str | None,
    project: dict[str, Any],
    persona_name: str,
    instruction: str,
    spec: str,
    items: list[str],
    cited: list[list[str]],
    defined: list[str],
    criteria_block,
    bound_tests,
) -> dict[str, Any]:
    """Queue the team for an approved plan; ``{group_id, worker_ids, integration_task_id}``.

    *cited* is each item's criteria; *criteria_block(ids)* and
    *bound_tests(ids)* render a task's criteria and their tests (the plan
    approval's own helpers, services/approvals.py).
    """

    group_id = uuid.uuid4()
    scopes = [parse_task_files(i) for i in items]
    deps = overlap_dependencies(scopes)
    max_parallel = max(1, int(settings.driver_team_max_parallel))
    count = len(items)
    async with session_factory() as session:
        session.add(
            DevTaskGroup(
                id=group_id,
                tenant_id=tenant_id,
                kind=KIND,
                project_id=uuid.UUID(project["id"]),
                status="running",
                title=(instruction.strip().splitlines() or ["Plan"])[0][:200],
                source_ref=plan_task_id,
                properties={
                    "max_parallel": max_parallel,
                    "scopes": scopes,
                    "waves": parallel_waves(scopes),
                    "worker_ids": [],
                    "integration_task_id": None,
                },
            )
        )
        await session.commit()

    common = {
        "plan_task_id": plan_task_id,
        "plan_group_id": str(group_id),
        "plan_task_count": count,
    }
    ids: list[str] = []
    for i, item in enumerate(items):
        depends_on = [ids[j] for j in deps[i]]
        task = await dev_tasks.create_dev_task(
            session_factory,
            tenant_id,
            instruction=worker_instruction(instruction, spec, item, i + 1, count, scopes[i])
            + criteria_block(cited[i]),
            project=project,
            persona_name=persona_name,
            task_type="code_change",
            start=False,
            depends_on=depends_on or None,
            properties={
                **common,
                "origin": "team_worker",
                "team_role": "worker",
                "plan_task_index": i + 1,
                "team_files": scopes[i],
                "team_max_parallel": max_parallel,
                "seed_from": depends_on,
                "acceptance_criteria": cited[i],
                "acceptance_tests": bound_tests(cited[i]),
            },
        )
        ids.append(str(task["id"]))
    integration = await dev_tasks.create_dev_task(
        session_factory,
        tenant_id,
        instruction=integration_instruction(instruction, spec, count) + criteria_block(defined),
        project=project,
        persona_name=persona_name,
        task_type="code_change",
        start=False,
        depends_on=ids,
        properties={
            **common,
            "origin": "team_integration",
            "team_role": "integration",
            "plan_task_index": count + 1,
            "seed_from": ids,
            "acceptance_criteria": defined,
            "acceptance_tests": bound_tests(defined),
        },
    )
    async with session_factory() as session:
        group = await session.get(DevTaskGroup, group_id)
        if group is not None:
            group.properties = {
                **(group.properties or {}),
                "worker_ids": ids,
                "integration_task_id": str(integration["id"]),
            }
            await session.commit()
    await _emit(
        "TEAM_STARTED",
        {
            "tenant_id": tenant_id,
            "group_id": str(group_id),
            "plan_task_id": plan_task_id,
            "workers": len(ids),
            "max_parallel": max_parallel,
        },
    )
    return {
        "group_id": str(group_id),
        "worker_ids": ids,
        "integration_task_id": str(integration["id"]),
        "max_parallel": max_parallel,
    }


async def _emit(name: str, payload: dict[str, Any]) -> None:

    await dev_tasks._emit_bus(name, payload)


def decide(
    status: str, workers: list[tuple[str, str]], integration: tuple[str, str] | None
) -> tuple[str, str | None]:
    """The team's next status and why: pure (``workers`` = ``(id, status)``,
    ``integration`` = ``(status, stage)``)."""
    for wid, wstatus in workers:
        if wstatus in _BROKEN:
            return "failed", f"worker {wid[:8]} {wstatus}"
    if integration is None:
        return status, None
    istatus, istage = integration
    if istage in _APPROVAL_STAGES:
        return "awaiting_approval", None
    if istatus in _BROKEN or istage in ("pr_rejected", "closed"):
        return "failed", f"integration {istatus if istatus in _BROKEN else istage}"
    if istatus == "running" and status == "running":
        return "integrating", None
    if istatus == "completed":
        return "awaiting_approval", None
    return status, None


async def reconcile(session_factory: async_sessionmaker[AsyncSession]) -> list[dict[str, Any]]:
    """Move every active team along; the changes made (the runner's loop).

    Install-wide like the claim; every task query is filtered by the group's
    tenant. A failing worker cancels the rest of its team.
    """

    changes: list[dict[str, Any]] = []
    to_cancel: list[tuple[str, str]] = []
    async with session_factory() as session:
        groups = (
            (
                await session.execute(
                    select(DevTaskGroup)
                    .where(DevTaskGroup.kind == KIND, DevTaskGroup.status.in_(ACTIVE))
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        for group in groups:
            rows = (
                (
                    await session.execute(
                        select(AgentTask).where(
                            AgentTask.tenant_id == group.tenant_id,
                            dev_tasks._kind_filter(),
                            AgentTask.properties["plan_group_id"].astext == str(group.id),
                        )
                    )
                )
                .scalars()
                .all()
            )
            workers = [r for r in rows if (r.properties or {}).get("team_role") == "worker"]
            integ = next(
                (r for r in rows if (r.properties or {}).get("team_role") == "integration"), None
            )
            istate = None
            if integ is not None:
                approvals = await dev_tasks._approvals_by_task(
                    session, group.tenant_id, [str(integ.id)]
                )
                istate = (integ.status, dev_tasks._stage(integ, approvals.get(str(integ.id), [])))
            new, why = decide(group.status, [(str(w.id), w.status) for w in workers], istate)
            if new == group.status:
                continue
            props = dict(group.properties or {})
            props.setdefault("history", []).append(
                {
                    "status": new,
                    "at": datetime.now(UTC).isoformat(),
                    **({"why": why} if why else {}),
                }
            )
            if why:
                props["reason"] = why
            group.properties = props
            group.status = new
            if new == "failed":
                to_cancel.extend((group.tenant_id, str(r.id)) for r in rows if r.status in _OPEN)
            changes.append(
                {
                    "tenant_id": group.tenant_id,
                    "group_id": str(group.id),
                    "plan_task_id": group.source_ref,
                    "status": new,
                    "reason": why,
                    "integration_task_id": str(integ.id) if integ is not None else None,
                }
            )
        await session.commit()

    for tenant_id, task_id in to_cancel:
        try:
            await dev_tasks.request_cancel(session_factory, tenant_id, task_id)
        except Exception:
            logger.warning("Could not cancel team task %s", task_id, exc_info=True)
    for change in changes:
        event = {
            "failed": "TEAM_FAILED",
            "integrating": "TEAM_INTEGRATING",
            "awaiting_approval": "TEAM_AWAITING_APPROVAL",
        }.get(change["status"])
        if event:
            await _emit(event, change)
        if change["status"] == "failed":
            await _notify_failed(change)
    return changes


async def _notify_failed(change: dict[str, Any]) -> None:
    """Tell the owner once: the "needs your attention" channel (push + Telegram)."""

    try:
        await event_bus.emit(
            EventType.APPROVAL_FILED,
            {
                "tenant_id": change["tenant_id"],
                "kind": "plan_stopped",
                "title": "Parallel plan failed",
                "detail": (
                    f"The plan's team stopped ({change.get('reason')}); its other tasks were "
                    "cancelled. Re-dispatch, then re-approve the plan to try again."
                ),
            },
            source="dev_tasks",
        )
    except Exception:
        logger.warning("Could not send the team-failed notification", exc_info=True)


async def team_view(
    session: AsyncSession, tenant_id: str, children: list[AgentTask], approvals: dict
) -> dict[str, Any] | None:
    """The team of a plan, for ``GET /kernel/drivers/plans/{id}``; None if it had none."""

    team_rows = [c for c in children if (c.properties or {}).get("team_role")]
    if not team_rows:
        return None
    group_id = (team_rows[0].properties or {}).get("plan_group_id")
    group = None
    try:
        group = await session.get(DevTaskGroup, uuid.UUID(str(group_id)))
    except (ValueError, TypeError):
        group = None
    if group is not None and group.tenant_id != tenant_id:
        group = None

    def row(t: AgentTask) -> dict[str, Any]:
        props = t.properties or {}
        meta = (t.result or {}).get("metadata") or {}
        return {
            "task_id": str(t.id),
            "index": props.get("plan_task_index"),
            "title": t.title,
            "files": list(props.get("team_files") or []),
            "depends_on": list(props.get("depends_on") or []),
            "status": t.status,
            "stage": dev_tasks._stage(t, approvals.get(str(t.id), [])),
            "waiting": props.get("dependency_wait") if props.get("deps_pending") else None,
            "branch": meta.get("landed_branch"),
            "handoff": meta.get("handoff"),
            "error": t.error,
        }

    workers = sorted(
        (c for c in team_rows if (c.properties or {}).get("team_role") == "worker"),
        key=lambda c: (c.properties or {}).get("plan_task_index") or 0,
    )
    integ = next(
        (c for c in team_rows if (c.properties or {}).get("team_role") == "integration"), None
    )
    gprops = (group.properties if group is not None else {}) or {}
    return {
        "group_id": str(group_id),
        "status": group.status if group is not None else None,
        "reason": gprops.get("reason"),
        "max_parallel": gprops.get("max_parallel"),
        "waves": gprops.get("waves"),
        "workers": [row(w) for w in workers],
        "integration": row(integ) if integ is not None else None,
    }
