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

from sqlalchemy import and_, or_, select, text

from life_graph.models.db import AgentTask, Approval, VerificationRun

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import (
        AsyncConnection,
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
    )

logger = logging.getLogger(__name__)

KIND = "dev_task"
AGENT_NAME = "dev_task"
QUEUE_MODE = "queue"

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
    start: bool = True,
    properties: dict[str, Any] | None = None,
    spec_first: bool = False,
    verify_chain: list[str] | None = None,
) -> dict[str, Any]:
    """Record a dev task and start it in the background.

    With ``start=False`` the task is left ``queued`` for :func:`run_queue`
    (``properties.run_mode == "queue"``), which runs queued tasks one at a time
    — how nightly suggestions avoid starting several local-model runs at once.
    """
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
            properties={
                **(properties or {}),
                "kind": KIND,
                "project_name": project["name"],
                **({} if start else {"run_mode": QUEUE_MODE}),
                # A task started now was asked for by someone, so the Governor
                # never blocks it; kept so a re-queue after an API restart runs
                # it the same way (run_queue).
                "interactive": start,
            },
            tags=[KIND],
            status_history=[{"status": "queued", "at": datetime.now(UTC).isoformat()}],
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        data = serialize(task, [])

    if not start:
        return data

    bg = asyncio.create_task(
        _run(
            session_factory,
            tenant_id,
            str(task_id),
            instruction,
            project["id"],
            persona_name,
            task_type,
            spec_first=spec_first,
            verify_chain=verify_chain,
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
    interactive: bool = True,
    spec_first: bool = False,
    verify_chain: list[str] | None = None,
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
        # Read from the row, not passed in: a fanned-out plan task usually
        # reaches here via run_queue(), which only has the row to go on.
        acceptance_tests = list((task.properties or {}).get("acceptance_tests") or []) or None
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
                # A dashboard task is user-started, so the Governor must not block
                # it; queued (unattended) work is subject to the budget like any
                # other autonomous dispatch.
                interactive=interactive,
                isolate_workdir=True,
                spec_first=spec_first,
                verify_chain=verify_chain,
                acceptance_tests=acceptance_tests,
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


async def dev_task_stats(session: AsyncSession, tenant_id: str, limit: int = 2000) -> list[dict]:
    """Per (persona, project) merge rate and timing, aggregated from the same
    dev_task rows and the same :func:`_stage` logic the dashboard renders —
    so this always agrees with what ``/drivers`` shows, not a separate,
    driftable approximation of it. Answers "is this actually working" at a
    glance instead of scrolling task-by-task or reading logs.
    """
    tasks = await list_dev_tasks(session, tenant_id, limit=limit)
    groups: dict[tuple[str, str | None], list[dict]] = {}
    for t in tasks:
        groups.setdefault((t["persona"] or "?", t["project_id"]), []).append(t)

    out = []
    for (persona, project_id), rows in groups.items():
        in_flight = sum(1 for r in rows if r["stage"] in ("queued", "running"))
        merged = sum(1 for r in rows if r["stage"] == "merged")
        needs_review = sum(1 for r in rows if r["stage"] == "needs_review")
        settled = len(rows) - in_flight
        durations = [r["duration_ms"] for r in rows if r["duration_ms"] is not None]
        costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
        out.append(
            {
                "persona": persona,
                "project_id": project_id,
                "project_name": rows[0]["project_name"],
                "total": len(rows),
                "merged": merged,
                "needs_review": needs_review,
                "in_flight": in_flight,
                "merge_rate": round(merged / settled, 3) if settled else None,
                "avg_duration_ms": round(sum(durations) / len(durations)) if durations else None,
                "avg_cost_usd": round(sum(costs) / len(costs), 4) if costs else None,
            }
        )
    out.sort(key=lambda r: -r["total"])
    return out


async def auto_merge_status(session: AsyncSession, tenant_id: str) -> list[dict[str, Any]]:
    """For every (persona, project) pair with dev-task history: the exact
    trust-gate numbers auto_open_pr/auto_merge actually check.

    "Why isn't this auto-merging" used to mean hand-running /tasks/stats
    against a curl command and holding 80% in your head — this answers it
    directly: merge_rate, established, the threshold, whether the project
    opted in, and whether the gate is actually being met right now.

    Keyed on the persona's *driver* (dispatch_task and
    services.dev_outcomes.track_record both key trust by driver name, e.g.
    "local" or "claude_code" — not by persona name), resolved from each
    persona's static config. A persona pinned to "auto" driver selection has
    no single driver to report a track record for and is skipped — its
    trust is decided fresh per dispatch by the driver-selection cascade, not
    something a snapshot like this can summarize honestly.
    """
    from life_graph.drivers.dispatcher import AUTO_PR_MERGE_RATE
    from life_graph.kernel.personas import PersonaService
    from life_graph.kernel.project_registry import ProjectRegistry
    from life_graph.services.dev_outcomes import track_record
    from life_graph.storage.database import async_session

    stats = await dev_task_stats(session, tenant_id)
    personas, _ = await PersonaService(session_factory=async_session).list_all(
        tenant_id, include_inactive=True
    )
    driver_by_persona = {p["name"]: p["driver"] for p in personas}
    registry = ProjectRegistry(session_factory=async_session)

    project_cache: dict[str, dict[str, Any] | None] = {}
    out = []
    for row in stats:
        driver = driver_by_persona.get(row["persona"])
        if not driver or driver == "auto":
            continue
        project_id = row["project_id"]
        if project_id not in project_cache:
            project_cache[project_id] = (
                await registry.get_by_id(tenant_id, project_id) if project_id else None
            )
        meta = (project_cache[project_id] or {}).get("scan_metadata") or {}
        record = await track_record(session, tenant_id, driver, project_id)
        out.append(
            {
                "persona": row["persona"],
                "driver": driver,
                "project_id": project_id,
                "project_name": row["project_name"],
                "merged": record["merged"],
                "failed": record["failed"],
                "total": record["total"],
                "merge_rate": record["merge_rate"],
                "established": record["established"],
                "threshold": AUTO_PR_MERGE_RATE,
                "auto_open_pr": bool(meta.get("auto_open_pr")),
                "auto_merge": bool(meta.get("auto_merge")),
                "earning_auto_merge": bool(
                    record["established"] and (record["merge_rate"] or 0) >= AUTO_PR_MERGE_RATE
                ),
            }
        )
    out.sort(key=lambda r: -r["total"])
    return out


_AUDIT_MANIFEST_CANDIDATES = (
    "uv.lock",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements.txt",
)


def _pip_audit_declared(project_path: str) -> tuple[bool, str | None]:
    """Whether *project_path* declares pip-audit as a dependency anywhere
    ``no_vulnerable_deps_in_diff`` would look for it.

    A static file read, not a live check: actually building the project's
    sandbox venv (services.sandbox.prepare_env) to find out for certain
    means docker and real time, which is too expensive to spend on every
    registered project just to answer "is this configured yet". This
    answers the same question a human skimming the manifest would, which
    is what a dashboard glance needs.
    """
    from life_graph.tools._guards import ToolDeniedError, resolve_in_roots

    try:
        root = resolve_in_roots(project_path, tool_name="dependency audit readiness")
    except ToolDeniedError:
        return False, None
    for name in _AUDIT_MANIFEST_CANDIDATES:
        candidate = root / name
        try:
            if not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "pip-audit" in text or "pip_audit" in text:
            return True, name
    return False, None


async def dependency_audit_readiness(tenant_id: str) -> list[dict[str, Any]]:
    """For every active project: can no_vulnerable_deps_in_diff actually run
    for it, or would a dependency-manifest change there silently escalate to
    needs_human instead of being checked?

    The verifier itself already reports this correctly per-task (inconclusive,
    never a silent pass) — this answers it proactively, before anyone
    dispatches a task that touches a manifest and finds out the hard way.
    """
    from life_graph.kernel.project_registry import ProjectRegistry
    from life_graph.storage.database import async_session

    registry = ProjectRegistry(session_factory=async_session)
    projects, _ = await registry.list_all(tenant_id)

    out = []
    for p in projects:
        full = await registry.get_by_id(tenant_id, p["id"])
        path = (full or {}).get("path") or ""
        available, via = _pip_audit_declared(path) if path else (False, None)
        out.append(
            {
                "project_id": p["id"],
                "project_name": p["name"],
                "pip_audit_available": available,
                "checked_via": via,
            }
        )
    return out


async def get_dev_task(session: AsyncSession, tenant_id: str, task_id: str) -> dict | None:
    try:
        pk = uuid.UUID(task_id)
    except ValueError:
        return None
    task = await session.get(AgentTask, pk)
    if task is None or task.tenant_id != tenant_id or (task.properties or {}).get("kind") != KIND:
        return None
    approvals = await _approvals_by_task(session, tenant_id, [task_id])
    data = serialize(task, approvals.get(task_id, []))
    data["verification"] = await _verification_summary(session, tenant_id, pk)
    return data


async def _verification_summary(
    session: AsyncSession, tenant_id: str, task_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Every verifier-chain run for this task, oldest attempt first.

    This is the detail behind a generic "Verification failed" error — which
    verifier failed and its evidence (stdout tail, returncode, ...) — kept
    out of list_dev_tasks/serialize() because it's one extra query per task
    and only ever useful once you're already looking at a single stalled or
    needs_human task, not scanning a list of them.
    """
    rows = (
        (
            await session.execute(
                select(VerificationRun)
                .where(VerificationRun.tenant_id == tenant_id, VerificationRun.task_id == task_id)
                .order_by(VerificationRun.attempt)
            )
        )
        .scalars()
        .all()
    )
    return [{"attempt": r.attempt, "passed": r.passed, "results": r.results} for r in rows]


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
    outcome = (pr.payload or {}).get("outcome") if pr is not None else None
    if outcome == "merged":
        return "merged"
    if outcome == "closed":
        return "closed"
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


def driver_of(task: AgentTask) -> str | None:
    """Which driver ran the task: recorded since 2026-10-13, inferred before.

    Older rows never stored it, but each driver leaves its own metadata:
    claude_code a CLI ``session_id``, local an orchestrator ``tool_calls`` count.
    A run that failed before leaving either (a timeout, a budget refusal) falls
    back to the driver its persona pins.
    """
    metadata = (task.result or {}).get("metadata") or {}
    if metadata.get("driver"):
        return str(metadata["driver"])
    if "session_id" in metadata or "num_turns" in metadata:
        return "claude_code"
    if "tool_calls" in metadata:
        return "local"
    return _pinned_driver(task.assigned_agent)


def _pinned_driver(persona: str | None) -> str | None:
    """The driver a built-in persona pins (code-fixer -> claude_code, ...)."""
    from life_graph.kernel.personas import _BUILTIN_PERSONAS

    for p in _BUILTIN_PERSONAS:
        if p["name"] == persona and p.get("driver") not in (None, "auto"):
            return str(p["driver"])
    return None


def serialize(task: AgentTask, approvals: list[Approval]) -> dict[str, Any]:
    result = task.result or {}
    metadata = result.get("metadata") or {}
    props = task.properties or {}
    pr = next((a for a in approvals if a.kind == "driver_pr"), None)
    merge = next((a for a in approvals if a.kind == "driver_merge"), None)
    return {
        "id": str(task.id),
        "title": task.title,
        "instruction": task.instructions,
        "task_type": task.task_type,
        "project_id": str(task.project_id) if task.project_id else None,
        "project_name": props.get("project_name"),
        "persona": task.assigned_agent,
        "driver": driver_of(task),
        "model": metadata.get("model"),
        "num_turns": metadata.get("num_turns"),
        "origin": props.get("origin", "dashboard"),
        "plan_task_id": props.get("plan_task_id"),
        "plan_task_index": props.get("plan_task_index"),
        "plan_task_count": props.get("plan_task_count"),
        "status": task.status,
        "stage": _stage(task, approvals),
        "error": task.error,
        "output": result.get("output"),
        "cost_usd": result.get("cost_usd"),
        "duration_ms": result.get("duration_ms"),
        "branch": metadata.get("landed_branch"),
        "spec": metadata.get("spec"),
        "conformance": (task.properties or {}).get("conformance"),
        "pr_url": (pr.payload or {}).get("pr_url") if pr else None,
        "merge_commit": (merge.payload or {}).get("merge_commit") if merge else None,
        "approvals": [
            {
                "id": str(a.id),
                "kind": a.kind,
                "status": a.status,
                "title": a.title,
                # The reviewer's reasoning: why it was approved or rejected.
                "note": a.resolution_note,
                "resolved_by": a.resolved_by,
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            }
            for a in approvals
        ],
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


# One dev-task runner per database. Every API process used to run the queue
# and the startup recovery, so a preview server from another worktree (older
# code, same DB) claimed a plan's queued tasks and ran them without the merge
# gate, and its startup recovery would fail the real runner's in-flight task.
RUNNER_LOCK_KEY = 0x4C474456  # "LGDV"


async def acquire_runner_lock(engine: AsyncEngine) -> AsyncConnection | None:
    """Hold the dev-task runner lock on a dedicated connection, or return None.

    A Postgres session-level advisory lock: it lives as long as the returned
    connection, so the caller keeps it open for the process's lifetime and
    closes it on shutdown. None means another process is the runner.
    """
    conn = await engine.connect()
    try:
        got = (
            await conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": RUNNER_LOCK_KEY})
        ).scalar()
        # Session-level locks survive commit; committing keeps this connection
        # from sitting idle in a transaction for hours.
        await conn.commit()
    except BaseException:
        await conn.close()
        raise
    if not got:
        await conn.close()
        return None
    return conn


async def release_runner_lock(conn: AsyncConnection) -> None:
    """Release the lock, then hand the connection back.

    An explicit unlock, not just close(): close() returns the connection to
    the pool with its Postgres session -- and so the lock -- still alive.
    """
    try:
        await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": RUNNER_LOCK_KEY})
        await conn.commit()
    finally:
        await conn.close()


# A task cut short by a restart runs again once (from the start, in a fresh
# worktree) before it counts as failed: restarts are routine, and failing the
# task made a plan stop for a reason that had nothing to do with its work.
INTERRUPT_REQUEUES = 1
_INTERRUPTED = "Interrupted: the API restarted while this task was running"


async def fail_interrupted(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Recover dev tasks abandoned by a previous process.

    That is every ``running`` task, and ``queued`` tasks that were meant to
    start immediately (tasks queued for :func:`run_queue` are still waiting
    for their turn and are left alone). Each goes back on the queue once --
    ``run_mode`` becomes ``queue`` so :func:`run_queue` picks it up -- and
    is failed only when it was already re-queued before. Returns how many
    were failed.
    """
    abandoned_queued = and_(
        AgentTask.status == "queued",
        or_(
            AgentTask.properties["run_mode"].astext.is_(None),
            AgentTask.properties["run_mode"].astext != QUEUE_MODE,
        ),
    )
    failed = 0
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(AgentTask).where(
                        _kind_filter(), or_(AgentTask.status == "running", abandoned_queued)
                    )
                )
            )
            .scalars()
            .all()
        )
        now = datetime.now(UTC)
        for task in rows:
            props = dict(task.properties or {})
            done = int(props.get("interrupt_requeues") or 0)
            if done < INTERRUPT_REQUEUES:
                props["interrupt_requeues"] = done + 1
                props["run_mode"] = QUEUE_MODE
                task.properties = props
                task.status = "queued"
                task.started_at = None
                task.status_history = _history(task, "queued", "re-queued after an API restart")
                logger.warning("Re-queued dev task %s after an API restart", task.id)
            else:
                task.status = "failed"
                task.error = _INTERRUPTED
                task.completed_at = now
                failed += 1
        await session.commit()
    return failed


# ── Queue runner ─────────────────────────────────────────────

QUEUE_POLL_SECONDS = 60
_QUEUE_SCAN_LIMIT = 50

# A fanned-out plan task only starts once the task before it is merged.
# Each task's worktree is cut from the project checkout, so starting task 2
# while task 1 still sits on an unmerged lg/task-* branch would build it on
# code that doesn't have task 1's change -- "sequential" in name only.
_PLAN_PREDECESSOR_DONE = frozenset({"merged", "completed"})
# Stages a predecessor can't get out of without a person re-dispatching it:
# the rest of the plan is stopped rather than left waiting forever.
_PLAN_PREDECESSOR_DEAD = frozenset(
    {"closed", "pr_rejected", "failed", "cancelled", "needs_review", "landed"}
)


async def _plan_gate(session: AsyncSession, task: AgentTask) -> tuple[str, AgentTask | None, str]:
    """('ready' | 'wait' | 'blocked', predecessor, predecessor_stage)."""
    props = task.properties or {}
    group, index = props.get("plan_group_id"), props.get("plan_task_index")
    if not group or not isinstance(index, int) or index <= 1:
        return "ready", None, ""
    prev = (
        (
            await session.execute(
                select(AgentTask).where(
                    AgentTask.tenant_id == task.tenant_id,
                    _kind_filter(),
                    AgentTask.properties["plan_group_id"].astext == group,
                    AgentTask.properties["plan_task_index"].astext == str(index - 1),
                )
            )
        )
        .scalars()
        .first()
    )
    if prev is None:
        # The predecessor row is gone; waiting on it would wedge the plan.
        return "ready", None, ""
    approvals = await _approvals_by_task(session, task.tenant_id, [str(prev.id)])
    stage = _stage(prev, approvals.get(str(prev.id), []))
    if stage in _PLAN_PREDECESSOR_DONE:
        return "ready", prev, stage
    if stage in _PLAN_PREDECESSOR_DEAD:
        return "blocked", prev, stage
    return "wait", prev, stage


async def _notify_plan_stopped(task: AgentTask, prev: AgentTask, stage: str) -> None:
    """Tell the person a plan stopped -- once, at the task right after the failure."""
    from life_graph.core.events import EventType, event_bus

    props = task.properties or {}
    try:
        await event_bus.emit(
            # Reuses the "needs your attention" channel (push + Telegram): a
            # stopped plan isn't an approval, but it is waiting on a person.
            EventType.APPROVAL_FILED,
            {
                "tenant_id": task.tenant_id,
                "kind": "plan_stopped",
                "title": f"Plan stopped at task {props.get('plan_task_index')} of "
                f"{props.get('plan_task_count')}",
                "detail": (
                    f"Task {props.get('plan_task_index', 1) - 1} ({prev.title}) ended as "
                    f"'{stage}', so the remaining plan tasks were not run. Re-dispatch it, "
                    "then re-approve the plan to continue."
                ),
            },
            source="dev_tasks",
        )
    except Exception:
        logger.warning("Could not send the plan-stopped notification", exc_info=True)


async def claim_next_queued(session_factory: async_sessionmaker[AsyncSession]) -> AgentTask | None:
    """Atomically claim the oldest *runnable* queue-mode task (status -> running).

    A plan task whose predecessor isn't merged yet is skipped (it waits);
    one whose predecessor can no longer merge is marked failed, along with
    the rest of its plan as the scan reaches them.
    """
    stopped: list[tuple[AgentTask, AgentTask, str]] = []
    claimed: AgentTask | None = None
    async with session_factory() as session:
        candidates = (
            (
                await session.execute(
                    select(AgentTask)
                    .where(
                        _kind_filter(),
                        AgentTask.status == "queued",
                        AgentTask.properties["run_mode"].astext == QUEUE_MODE,
                    )
                    .order_by(AgentTask.created_at)
                    .limit(_QUEUE_SCAN_LIMIT)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        for task in candidates:
            gate, prev, stage = await _plan_gate(session, task)
            if gate == "wait":
                continue
            if gate == "blocked":
                props = task.properties or {}
                note = (
                    f"Not run: task {props.get('plan_task_index', 1) - 1} of this plan "
                    f"ended as '{stage}' and was never merged."
                )
                task.status = "failed"
                task.error = note
                task.completed_at = datetime.now(UTC)
                task.status_history = _history(task, "failed", note)
                task.properties = {**props, "plan_stopped": True}
                # Notify once: only where the real failure is, not again for
                # every later task that was stopped because of it.
                if not (prev.properties or {}).get("plan_stopped"):
                    stopped.append((task, prev, stage))
                continue
            task.status = "running"
            task.started_at = datetime.now(UTC)
            task.status_history = _history(task, "running", "claimed from queue")
            claimed = task
            break
        await session.commit()
        if claimed is not None:
            await session.refresh(claimed)
    for task, prev, stage in stopped:
        await _notify_plan_stopped(task, prev, stage)
    return claimed


async def run_claimed(session_factory: async_sessionmaker[AsyncSession], task: AgentTask) -> None:
    """Run one task :func:`claim_next_queued` returned."""
    await _run(
        session_factory,
        task.tenant_id,
        str(task.id),
        task.instructions or "",
        str(task.project_id),
        task.assigned_agent or "code-fixer-local",
        task.task_type or "code_change",
        # Queued work is unattended and under the budget. But a task someone
        # started that an API restart put back on the queue stays theirs:
        # before this, task eda04c34 (started from MCP) was re-queued and then
        # denied for "monthly budget exhausted" (2026-10-17).
        interactive=bool((task.properties or {}).get("interactive", False)),
    )


TASK_DIFF_MAX_CHARS = 200_000


async def task_diff(session: AsyncSession, tenant_id: str, task_id: str) -> dict | None:
    """A landed dev task's change, from its newest ``driver_pr`` approval, so a
    reviewer can read it without git (GET /kernel/drivers/tasks/{id}/diff).

    Returns None if no matching approval is found. Otherwise a dict with
    task_id, branch, base_commit, head_commit, files (changed paths), the
    diff text capped at :data:`TASK_DIFF_MAX_CHARS`, and ``truncated``.

    Written by the dev agent (OpenCode, task 90033c3e); its tests were not
    usable and were replaced.
    """
    from life_graph.services.github_pr import landed_diff

    # Find the newest Approval with kind "driver_pr" and matching payload.task_id
    result = await session.execute(
        select(Approval)
        .where(
            Approval.tenant_id == tenant_id,
            Approval.kind == "driver_pr",
            Approval.payload["task_id"].astext == task_id,
        )
        .order_by(Approval.created_at.desc())
        .limit(1)
    )

    approval = result.scalar_one_or_none()
    if approval is None:
        return None

    # Extract the required fields from the payload
    payload = approval.payload
    repo_path = payload["repo_path"]
    base_commit = payload["base_commit"]
    head_commit = payload["head_commit"]
    branch = payload["branch"]

    # Get the diff text
    diff_text = await landed_diff(repo_path, base_commit, head_commit)

    # Parse file paths from the diff
    files = []
    if diff_text:
        for line in diff_text.splitlines():
            if line.startswith("diff --git a/"):
                # Extract the file path after "a/"
                start_pos = line.find("a/") + 2
                end_pos = line.find(" b/", start_pos)
                if end_pos != -1:
                    files.append(line[start_pos:end_pos])

    # Cap the diff text
    truncated = False
    if len(diff_text) > TASK_DIFF_MAX_CHARS:
        diff_text = diff_text[:TASK_DIFF_MAX_CHARS]
        truncated = True

    return {
        "task_id": task_id,
        "branch": branch,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "files": files,
        "diff": diff_text,
        "truncated": truncated,
    }


async def run_queue(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Run queued dev tasks one at a time, forever (API process lifespan task).

    One at a time on purpose: queued work is unattended (nightly suggestions),
    usually on the local model, and several concurrent runs would contend for
    one GPU and trip the per-project WIP limit.
    """
    while True:
        try:
            task = await claim_next_queued(session_factory)
            if task is None:
                await asyncio.sleep(QUEUE_POLL_SECONDS)
                continue
            logger.info("Running queued dev task %s (%s)", task.id, task.title)
            await run_claimed(session_factory, task)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Dev task queue runner iteration failed", exc_info=True)
            await asyncio.sleep(QUEUE_POLL_SECONDS)
