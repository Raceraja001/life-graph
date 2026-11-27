"""Dev-task dependencies: hold a task until the tasks it depends on finished.

docs/specs/agent-drivers.md, "Phase 4b". A dev task created with
``depends_on`` (dev-task ids of the same tenant) is ``queued`` with
``properties.deps_pending``; the claim skips it. The runner's loop
(:func:`release_dependencies`, before every fill, so on each wake-up or at most
every 60 s) looks at every held task:

* every dependency reached a **work-finished** stage -- its change waits for
  approval (``awaiting_pr``), its PR is open or merged, or it handed off on a
  branch (``landed``; a team worker) -- and the automation gate (kill switch,
  subscription share, Governor: services/dev/automation_gate.py) allows it:
  the hold is lifted and the task runs like any queued task;
* a dependency **failed** (failed / cancelled / timed out, its PR rejected or
  closed, or its row is gone): the task is cancelled with the reason
  ("Dependency <id> failed"), which in turn cancels whatever depends on it;
* otherwise it keeps waiting (``properties.dependency_wait`` says on what).

Unknown ids, another tenant's ids and cycles are refused at creation
(:class:`DependencyError`, 422). The rows are the only state, so a restart
loses nothing. Rebuilt from race-app's ``providers/local/dependencies.ts``
(the owner's code).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.models.db import AgentTask
from life_graph.services.dev import task_events
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev.automation_gate import blockers

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

MAX_DEPENDENCIES = 20
# Bounds the cycle walk over existing tasks' own dependencies.
_MAX_GRAPH_NODES = 500
_SCAN_LIMIT = 200

#: Stages at which a dependency's work is finished: waiting on approval, PR
#: open or merged, or handed off on its branch.
DONE_STAGES = frozenset({"awaiting_pr", "pr_open", "awaiting_merge", "merged", "landed"})
BROKEN_STATUSES = frozenset({"failed", "cancelled", "timeout"})
BROKEN_STAGES = frozenset({"pr_rejected", "closed"})


class DependencyError(ValueError):
    """``depends_on`` refused: ``code`` is ``invalid`` | ``unknown`` | ``cyclic``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def dependency_state(status: str | None, stage: str | None) -> str:
    """``done`` | ``broken`` | ``wait`` for one dependency (``None`` = row gone)."""
    if status is None:
        return "broken"
    if stage in DONE_STAGES:
        return "done"
    if status in BROKEN_STATUSES or stage in BROKEN_STAGES:
        return "broken"
    if status == "completed":
        # Finished with nothing to approve and no branch (e.g. a non-code
        # task): its work is done.
        return "done"
    return "wait"


def evaluate(
    depends_on: list[str], states: dict[str, tuple[str, str] | None]
) -> tuple[str, str | None, list[str]]:
    """``(decision, broken_id, still_waiting_on)`` for one held task.

    *states* maps a dependency id to ``(status, stage)``, or None when its row
    is gone. ``decision`` is ``ready`` | ``broken`` | ``wait``.
    """
    waiting: list[str] = []
    for dep in depends_on:
        state = states.get(dep)
        verdict = dependency_state(*(state or (None, None)))
        if verdict == "broken":
            return "broken", dep, []
        if verdict == "wait":
            waiting.append(dep)
    return ("wait" if waiting else "ready"), None, waiting


def find_cycle(graph: dict[str, list[str]], start: list[str], new_id: str | None = None):
    """A dependency cycle reachable from *start*, as a list of ids, or None.

    *graph* maps a task id to the ids it depends on. *new_id* is the task
    being created (its own id in its dependencies is a cycle of one).
    """
    if new_id is not None and new_id in start:
        return [new_id, new_id]
    color: dict[str, int] = {}
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = 1
        path.append(node)
        for nxt in graph.get(node, []):
            if nxt == new_id:
                return [*path, nxt]
            if color.get(nxt) == 1:
                return [*path[path.index(nxt) :], nxt]
            if color.get(nxt) is None:
                found = visit(nxt)
                if found:
                    return found
        path.pop()
        color[node] = 2
        return None

    for node in start:
        if color.get(node) is None:
            found = visit(node)
            if found:
                return found
    return None


def normalize(depends_on: list[Any] | None) -> list[str]:
    """Canonical UUID strings, de-duplicated in order; :class:`DependencyError` if bad."""
    out: list[str] = []
    for raw in depends_on or []:
        try:
            value = str(uuid.UUID(str(raw)))
        except ValueError:
            raise DependencyError("invalid", f"{raw!r} is not a dev task id") from None
        if value not in out:
            out.append(value)
    if len(out) > MAX_DEPENDENCIES:
        raise DependencyError("invalid", f"At most {MAX_DEPENDENCIES} dependencies")
    return out


async def validate_dependencies(
    session: AsyncSession,
    tenant_id: str,
    depends_on: list[Any] | None,
    *,
    new_id: str | None = None,
) -> list[str]:
    """The checked ``depends_on`` for a new task of *tenant_id*.

    Every id must be a dev task of this tenant (another tenant's id reads as
    unknown); the dependencies' own dependencies are walked for a cycle.
    """

    ids = normalize(depends_on)
    if not ids:
        return []
    graph: dict[str, list[str]] = {}
    frontier = list(ids)
    first = True
    while frontier and len(graph) < _MAX_GRAPH_NODES:
        rows = (
            (
                await session.execute(
                    select(AgentTask).where(
                        AgentTask.tenant_id == tenant_id,
                        dev_tasks._kind_filter(),
                        AgentTask.id.in_([uuid.UUID(i) for i in frontier]),
                    )
                )
            )
            .scalars()
            .all()
        )
        found = {str(r.id): r for r in rows}
        if first:
            missing = [i for i in ids if i not in found]
            if missing:
                raise DependencyError("unknown", f"Unknown dev task(s): {', '.join(missing)}")
            first = False
        nxt: list[str] = []
        for tid, row in found.items():
            deps = [str(d) for d in ((row.properties or {}).get("depends_on") or [])]
            graph[tid] = deps
            nxt.extend(d for d in deps if d not in graph and d not in nxt)
        frontier = nxt
    cycle = find_cycle(graph, ids, new_id)
    if cycle:
        raise DependencyError("cyclic", "Dependency cycle: " + " -> ".join(c[:8] for c in cycle))
    return ids


def hold_properties(depends_on: list[str]) -> dict[str, Any]:
    """What a new held task carries."""
    return {
        "depends_on": list(depends_on),
        "deps_pending": True,
        "dependency_wait": {
            "waiting_on": list(depends_on),
            "since": datetime.now(UTC).isoformat(),
        },
    }


def _gate_driver(task: AgentTask) -> str | None:

    props = task.properties or {}
    return props.get("driver_pin") or dev_tasks._pinned_driver(task.assigned_agent)


async def _dependency_states(
    session: AsyncSession, tenant_id: str, tasks: list[AgentTask]
) -> dict[str, tuple[str, str]]:
    """``{dependency id: (status, stage)}`` for the held *tasks* of one tenant."""

    dep_ids = sorted(
        {str(d) for t in tasks for d in ((t.properties or {}).get("depends_on") or [])}
    )
    if not dep_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(AgentTask).where(
                    AgentTask.tenant_id == tenant_id,
                    dev_tasks._kind_filter(),
                    AgentTask.id.in_([uuid.UUID(d) for d in dep_ids]),
                )
            )
        )
        .scalars()
        .all()
    )
    approvals = await dev_tasks._approvals_by_task(session, tenant_id, [str(r.id) for r in rows])
    return {str(r.id): (r.status, dev_tasks._stage(r, approvals.get(str(r.id), []))) for r in rows}


def _cancel_held(task: AgentTask, broken: str, how: str, now: datetime) -> None:

    note = f"Dependency {broken} failed ({how})"
    props = dict(task.properties or {})
    props.pop("deps_pending", None)
    props["dependency_failed"] = {"task_id": broken, "stage": how}
    task.properties = props
    task.status = "cancelled"
    task.error = note
    task.completed_at = now
    task.status_history = dev_tasks._history(task, "cancelled", note)


def _note_wait(task: AgentTask, waiting: list[str], blocked: str | None) -> None:
    """Record what the hold waits on (only when it changed: no row churn)."""
    props = dict(task.properties or {})
    wait = dict(props.get("dependency_wait") or {})
    if wait.get("waiting_on") == waiting and wait.get("blocked") == blocked:
        return
    wait["waiting_on"] = waiting
    if blocked:
        wait["blocked"] = blocked
    else:
        wait.pop("blocked", None)
    props["dependency_wait"] = wait
    task.properties = props


def _release(task: AgentTask, now: datetime) -> None:

    props = dict(task.properties or {})
    props.pop("deps_pending", None)
    props.pop("dependency_wait", None)
    props["dependencies_met_at"] = now.isoformat()
    task.properties = props
    task.status_history = dev_tasks._history(task, "queued", "dependencies finished")


async def release_dependencies(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime | None = None,
    gate=None,
) -> dict[str, list[str]]:
    """Lift or cancel the holds whose dependencies settled; ``{released, cancelled}``.

    Install-wide like the claim (one runner per database); every query of the
    dependencies is filtered by the held task's own tenant. *gate* is
    :func:`automation_gate.blockers` (injectable for tests).
    """

    gate = gate or blockers
    now = now or datetime.now(UTC)
    released: list[tuple[str, str]] = []
    cancelled: list[tuple[str, str, str, str]] = []
    async with session_factory() as session:
        held = (
            (
                await session.execute(
                    select(AgentTask)
                    .where(
                        dev_tasks._kind_filter(),
                        AgentTask.status == "queued",
                        AgentTask.properties["deps_pending"].astext.is_not(None),
                    )
                    .order_by(AgentTask.created_at)
                    .limit(_SCAN_LIMIT)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        if not held:
            return {"released": [], "cancelled": []}
        by_tenant: dict[str, list[AgentTask]] = {}
        for task in held:
            by_tenant.setdefault(task.tenant_id, []).append(task)
        for tenant_id, tasks in by_tenant.items():
            states = await _dependency_states(session, tenant_id, tasks)
            for task in tasks:
                deps = [str(d) for d in (task.properties or {}).get("depends_on") or []]
                decision, broken, waiting = evaluate(deps, states)
                if decision == "broken":
                    state = states.get(broken or "")
                    how = state[1] if state else "gone"
                    _cancel_held(task, str(broken), how, now)
                    cancelled.append((str(task.id), tenant_id, str(broken), how))
                    continue
                if decision == "wait":
                    _note_wait(task, waiting, None)
                    continue
                reasons = await gate(
                    tenant_id,
                    driver=_gate_driver(task),
                    account_id=(task.properties or {}).get("account_pin"),
                )
                if reasons:
                    _note_wait(task, [], " ".join(reasons)[:300])
                    continue
                _release(task, now)
                released.append((str(task.id), tenant_id))
        await session.commit()

    for task_id, tenant_id in released:
        task_events.emit(
            tenant_id, task_id, "dependencies", "dependencies finished; starting",
            data={"met": True}, source="runner",
        )  # fmt: skip
        await dev_tasks._emit_bus(
            "TASK_DEPENDENCIES_MET", {"tenant_id": tenant_id, "task_id": task_id}
        )
    for task_id, tenant_id, dep, how in cancelled:
        task_events.emit(
            tenant_id, task_id, "status", "cancelled",
            data={"dependency_failed": dep, "stage": how}, source="runner",
        )  # fmt: skip
        await dev_tasks._emit_bus(
            "TASK_DEPENDENCY_FAILED",
            {"tenant_id": tenant_id, "task_id": task_id, "dependency": dep, "stage": how},
        )
    if released or cancelled:
        logger.info(
            "Dependencies: released %d held dev task(s), cancelled %d",
            len(released),
            len(cancelled),
        )
    return {"released": [r[0] for r in released], "cancelled": [c[0] for c in cancelled]}
