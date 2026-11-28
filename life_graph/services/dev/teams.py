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
3. **Failure** -- a worker that ends ``failed`` / ``timeout`` is first retried
   (``driver_team_worker_retries``, default 1) as a fresh worker on the next
   escalation rung while the rest keep going (services/dev/team_retry.py);
   a worker cancelled, or one out of retries, cancels the rest and the
   integration task, and the team is ``failed`` (the owner is told once). The
   owner may retry that worker (``POST .../workers/{id}/retry``), which reopens
   the team; re-approving the plan starts a new team.
4. **Who works** -- a plan line's ``Agent:`` / ``Tier:`` (or the plan task's
   ``team_worker_persona`` / ``team_worker_tier``) choose a worker's persona
   and rung (services/dev/team_rungs.py); a bad value is a warning on the team.
5. **Notes** -- a finished worker's ``## Notes for the team`` bullets go on the
   team's board and into the instructions of later-wave workers and the
   integration task (services/dev/team_notes.py).

docs/specs/agent-drivers.md, "Team upgrades (2026-11-28)" for 3-5.

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
from life_graph.drivers.plan_spec import (
    TIERS,
    parse_task_agent,
    parse_task_files,
    parse_task_tier,
)
from life_graph.models.db import AgentTask, DevTaskGroup
from life_graph.models.dev_outcomes import DevOutcomeLog
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev import team_notes, team_retry, team_rungs
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
        "afterwards.\n\n"
        "If you learned something the other workers or the integrator need (an interface "
        "you chose, a name, a gotcha), end your final summary with a section headed "
        f"exactly `{team_notes.NOTES_HEADING}` holding short bullets (at most "
        f"{team_notes.MAX_NOTES_PER_WORKER}, one line each). Later workers of this plan "
        "and the integration task will see them. Never put secrets there."
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
    defaults = await _plan_defaults(session_factory, tenant_id, plan_task_id)
    warnings: list[str] = []
    chooser = _WorkerChooser(session_factory, tenant_id, persona_name, defaults, warnings)
    choices = [await chooser.choose(i + 1, item) for i, item in enumerate(items)]
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
                    "warnings": warnings[:_MAX_WARNINGS],
                    "notes": [],
                    **({"defaults": defaults} if defaults else {}),
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
        worker_persona, extra = choices[i]
        task = await dev_tasks.create_dev_task(
            session_factory,
            tenant_id,
            instruction=worker_instruction(instruction, spec, item, i + 1, count, scopes[i])
            + criteria_block(cited[i]),
            project=project,
            persona_name=worker_persona,
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
                "team_attempt": 1,
                **extra,
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
            "team_attempt": 1,
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
        "warnings": warnings[:_MAX_WARNINGS],
    }


_MAX_WARNINGS = 50


async def _plan_defaults(
    session_factory: async_sessionmaker[AsyncSession], tenant_id: str, plan_task_id: str | None
) -> dict[str, str]:
    """The plan task's ``team_worker_persona`` / ``team_worker_tier`` (set when it
    was created), as ``{persona?, tier?}``."""
    try:
        pk = uuid.UUID(str(plan_task_id))
    except ValueError:
        return {}
    try:
        async with session_factory() as session:
            plan = (
                await session.execute(
                    select(AgentTask).where(
                        AgentTask.tenant_id == tenant_id,
                        dev_tasks._kind_filter(),
                        AgentTask.id == pk,
                    )
                )
            ).scalar_one_or_none()
    except Exception:
        logger.warning("Could not read the plan task %s", plan_task_id, exc_info=True)
        return {}
    props = (plan.properties or {}) if isinstance(plan, AgentTask) else {}
    out: dict[str, str] = {}
    if props.get("team_worker_persona"):
        out["persona"] = str(props["team_worker_persona"])[:100]
    if props.get("team_worker_tier"):
        out["tier"] = str(props["team_worker_tier"]).lower()[:40]
    return out


class _WorkerChooser:
    """Each worker's persona and rung from its ``Agent:`` / ``Tier:`` (or the
    plan's defaults); every value that cannot be used is a warning."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_id: str,
        plan_persona: str,
        defaults: dict[str, str],
        warnings: list[str],
    ) -> None:
        self.sf, self.tenant_id = session_factory, tenant_id
        self.plan_persona, self.defaults, self.warnings = plan_persona, defaults, warnings
        self._personas: dict[str, dict[str, Any] | None] = {}
        self._picker: team_rungs.RungPicker | None = None

    async def _persona(self, name: str) -> dict[str, Any] | None:
        if name not in self._personas:
            self._personas[name] = await team_rungs.get_persona(self.sf, self.tenant_id, name)
        return self._personas[name]

    async def choose(self, index: int, item: str) -> tuple[str, dict[str, Any]]:
        """``(persona name, extra worker properties)`` for plan task *index*."""
        agent_req = parse_task_agent(item) or self.defaults.get("persona")
        tier_req = parse_task_tier(item) or self.defaults.get("tier")
        persona = self.plan_persona
        if agent_req:
            if await self._persona(agent_req) is not None:
                persona = agent_req
            else:
                self.warnings.append(
                    f"task {index}: unknown agent {agent_req!r} (no active persona with a "
                    f"driver); using {self.plan_persona}"
                )
        extra: dict[str, Any] = {
            "team_agent": {"requested": agent_req, "resolved": persona},
            "team_tier": {"requested": tier_req, "resolved": None},
        }
        if not tier_req:
            return persona, extra
        if tier_req not in TIERS:
            self.warnings.append(
                f"task {index}: unknown tier {tier_req!r} (use {', '.join(TIERS)}); ignored"
            )
            return persona, extra
        pinned = team_rungs.persona_pins(await self._persona(persona))
        if pinned:
            self.warnings.append(
                f"task {index}: tier {tier_req} ignored: persona {persona} pins driver {pinned}"
            )
            return persona, extra
        if self._picker is None:
            self._picker = team_rungs.RungPicker(self.sf, self.tenant_id)
        choice = await self._picker.for_tier(tier_req)
        if choice.rung is None:
            refused = f" ({'; '.join(choice.refused)})" if choice.refused else ""
            self.warnings.append(f"task {index}: {choice.why}{refused}; using selection")
            return persona, extra
        if choice.refused:
            self.warnings.append(
                f"task {index}: tier {tier_req} -> {choice.rung.label} "
                f"({'; '.join(choice.refused)[:300]})"
            )
        extra["team_tier"]["resolved"] = choice.tier
        extra.update(choice.pin())
        return persona, extra


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
    tenant. Per team, in order: re-point rows at the newest attempts, collect
    finished workers' notes (and refresh queued instructions), queue retries
    of failed workers that have some left, then the status (a failing worker
    with no retry left cancels the rest of its team).
    """

    changes: list[dict[str, Any]] = []
    to_cancel: list[tuple[str, str]] = []
    to_retry: list[tuple[str, str, str]] = []  # (tenant, group id, failed task id)
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
            change = await _step(session, group, to_cancel, to_retry)
            if change is not None:
                changes.append(change)
        await session.commit()

    for tenant_id, group_id, task_id in to_retry:
        try:
            await _auto_retry(session_factory, tenant_id, group_id, task_id)
        except Exception:
            # The pending mark stays: the next pass fails the team instead of
            # retrying forever.
            logger.warning("Could not queue the retry of team task %s", task_id, exc_info=True)
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


async def _step(
    session: AsyncSession,
    group: DevTaskGroup,
    to_cancel: list[tuple[str, str]],
    to_retry: list[tuple[str, str, str]],
) -> dict[str, Any] | None:
    """One team's pass of :func:`reconcile` (in its locked session); the change, if any."""
    rows = await team_retry.group_rows(session, group)
    mapping = team_retry.replacements(rows)
    team_retry.rewire(rows, mapping)
    props = team_retry.remap_group(dict(group.properties or {}), mapping)
    current = team_retry.live(rows, mapping)
    _collect_notes(props, current)
    workers = [r for r in current if (r.properties or {}).get("team_role") == "worker"]
    integ = next(
        (r for r in current if (r.properties or {}).get("team_role") == "integration"), None
    )
    istate = None
    if integ is not None:
        approvals = await dev_tasks._approvals_by_task(session, group.tenant_id, [str(integ.id)])
        istate = (integ.status, dev_tasks._stage(integ, approvals.get(str(integ.id), [])))
    statuses, retrying = _worker_states(group.status, props, workers)
    new, why = decide(group.status, statuses, istate)
    now = datetime.now(UTC).isoformat()
    if new != "failed" and retrying:
        pending = dict(props.get("retry_pending") or {})
        for w in retrying:
            pending[str(w.id)] = now
            to_retry.append((group.tenant_id, str(group.id), str(w.id)))
        props["retry_pending"] = pending
    if new != group.status:
        props["history"] = [
            *(props.get("history") or []),
            {"status": new, "at": now, **({"why": why} if why else {})},
        ]
        if why:
            props["reason"] = why
    if new == "failed":
        broken = next((wid for wid, st in statuses if st in _BROKEN), None)
        props["failed_task_id"] = broken or (str(integ.id) if integ is not None else None)
        cancel = [str(r.id) for r in current if r.status in _OPEN]
        props["team_cancelled"] = cancel
        to_cancel.extend((group.tenant_id, tid) for tid in cancel)
    if props != (group.properties or {}):
        group.properties = props
    if new == group.status:
        return None
    group.status = new
    return {
        "tenant_id": group.tenant_id,
        "group_id": str(group.id),
        "plan_task_id": group.source_ref,
        "status": new,
        "reason": why,
        "integration_task_id": str(integ.id) if integ is not None else None,
    }


def _worker_states(
    team_status: str, props: dict[str, Any], workers: list[AgentTask]
) -> tuple[list[tuple[str, str]], list[AgentTask]]:
    """``(statuses for decide, workers to retry now)``.

    A failed / timed-out worker with a retry left counts as still waiting (the
    team runs on) and is retried; one whose retry was already asked for but
    never appeared (it could not be queued) is broken.
    """
    limit = max(0, int(settings.driver_team_worker_retries))
    pending = props.get("retry_pending") or {}
    statuses: list[tuple[str, str]] = []
    retrying: list[AgentTask] = []
    for w in workers:
        wid, status = str(w.id), w.status
        if (
            status in team_retry.RETRYABLE
            and team_status == "running"
            and wid not in pending
            and int((w.properties or {}).get("team_attempt") or 1) <= limit
        ):
            retrying.append(w)
            status = "queued"
        statuses.append((wid, status))
    return statuses, retrying


def _collect_notes(props: dict[str, Any], current: list[AgentTask]) -> None:
    """Add finished workers' notes to the board (once each) and refresh the
    notes block of every queued team task that may see them."""
    read = set(props.get("notes_read") or [])
    notes = list(props.get("notes") or [])
    added = False
    for row in sorted(current, key=lambda r: (r.properties or {}).get("plan_task_index") or 0):
        rprops = row.properties or {}
        if rprops.get("team_role") != "worker" or row.status != "completed" or str(row.id) in read:
            continue
        read.add(str(row.id))
        added = True
        index = rprops.get("plan_task_index")
        for text in team_notes.parse_notes((row.result or {}).get("output")):
            if len(notes) >= team_notes.MAX_TEAM_NOTES:
                break
            notes.append(
                {
                    "task_id": str(row.id),
                    "author_index": index,
                    "author_title": (row.title or "")[:120],
                    "author_wave": team_notes.wave_of(props.get("waves"), index),
                    "text": text,
                    "at": datetime.now(UTC).isoformat(),
                }
            )
    if not added:
        return
    props["notes_read"] = sorted(read)
    props["notes"] = notes
    for row in current:
        if row.status != "queued" or not (row.properties or {}).get("team_role"):
            continue
        visible = team_retry.visible_notes(props, row)
        if not visible and team_notes.BLOCK_START not in (row.instructions or ""):
            continue
        text = team_notes.with_notes(row.instructions, visible)
        if text != (row.instructions or ""):
            row.instructions = text


async def _auto_retry(
    session_factory: async_sessionmaker[AsyncSession], tenant_id: str, group_id: str, task_id: str
) -> dict[str, Any] | None:
    """Queue the retry of failed worker *task_id* and re-point its team at it."""
    async with session_factory() as session:
        group = (
            await session.execute(
                select(DevTaskGroup)
                .where(
                    DevTaskGroup.id == uuid.UUID(group_id),
                    DevTaskGroup.tenant_id == tenant_id,
                    DevTaskGroup.kind == KIND,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if group is None:
            return None
        rows = await team_retry.group_rows(session, group)
        mapping = team_retry.replacements(rows)
        old = next((r for r in rows if str(r.id) == task_id), None)
        if old is None or task_id in mapping:
            return None
        props = dict(group.properties or {})
        ran = await team_rungs.ran_on(session, tenant_id, old)
        made = await team_retry.create_attempt(
            session_factory, tenant_id, props, old, mapping, retry=True,
            reason=old.error or old.status, by="team", ran_on=ran,
        )  # fmt: skip
        team_retry.rewire(rows, mapping)
        props = team_retry.remap_group(props, mapping)
        props["history"] = [
            *(props.get("history") or []),
            {
                "status": group.status,
                "at": datetime.now(UTC).isoformat(),
                "why": f"worker {made['index']} retried (attempt {made['attempt']}"
                + (f" on {made['rung']}" if made.get("rung") else "")
                + ")",
            },
        ]
        group.properties = props
        await session.commit()
    return made


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
    """The team of a plan, for ``GET /kernel/drivers/plans/{id}``; None if it had none.

    One row per plan task: its current attempt, with every attempt's rung,
    the retry reasons, and the agent / tier asked for and used.
    """

    team_rows = [c for c in children if (c.properties or {}).get("team_role")]
    if not team_rows:
        return None
    group_id = (team_rows[-1].properties or {}).get("plan_group_id")
    group = None
    try:
        group = await session.get(DevTaskGroup, uuid.UUID(str(group_id)))
    except (ValueError, TypeError):
        group = None
    if group is not None and group.tenant_id != tenant_id:
        group = None
    team_rows = [c for c in team_rows if (c.properties or {}).get("plan_group_id") == group_id]
    mapping = team_retry.replacements(team_rows)
    ran = await _ran_on_all(session, tenant_id, team_rows)
    by_id = {str(t.id): t for t in team_rows}

    def chain(t: AgentTask) -> list[AgentTask]:
        out = [t]
        while (out[0].properties or {}).get("team_replaces") in by_id and len(out) <= len(by_id):
            out.insert(0, by_id[str((out[0].properties or {})["team_replaces"])])
        return out

    def row(t: AgentTask) -> dict[str, Any]:
        props = t.properties or {}
        meta = (t.result or {}).get("metadata") or {}
        attempts = chain(t)
        retried = [a for a in attempts if (a.properties or {}).get("team_retry_reason")]
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
            "attempts": int(props.get("team_attempt") or 1),
            "attempt_task_ids": [str(a.id) for a in attempts],
            "rungs": [ran.get(str(a.id)) or _planned_rung(a) for a in attempts],
            "agent": props.get("team_agent") or {"requested": None, "resolved": t.assigned_agent},
            "tier": props.get("team_tier") or {"requested": None, "resolved": None},
            "rung": (props.get("team_rung") or {}).get("label"),
            "retry_reasons": [
                {
                    "attempt": (a.properties or {}).get("team_attempt"),
                    "reason": (a.properties or {}).get("team_retry_reason"),
                    "by": (a.properties or {}).get("team_retry_by"),
                    "why": (a.properties or {}).get("team_retry_why"),
                }
                for a in retried
            ],
        }

    current = team_retry.live(team_rows, mapping)
    workers = sorted(
        (c for c in current if (c.properties or {}).get("team_role") == "worker"),
        key=lambda c: (c.properties or {}).get("plan_task_index") or 0,
    )
    integ = next(
        (c for c in current if (c.properties or {}).get("team_role") == "integration"), None
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
        "notes": [
            {k: n.get(k) for k in ("author_index", "author_title", "task_id", "text", "at")}
            for n in gprops.get("notes") or []
        ],
        "warnings": list(gprops.get("warnings") or []),
        "retries_per_worker": int(settings.driver_team_worker_retries),
        "reopened": int(gprops.get("reopened") or 0),
    }


def _planned_rung(task: AgentTask) -> str | None:
    rung = (task.properties or {}).get("team_rung") or {}
    return rung.get("label") if isinstance(rung, dict) else None


async def _ran_on_all(
    session: AsyncSession, tenant_id: str, rows: list[AgentTask]
) -> dict[str, str]:
    """``{task id: "driver[:model]"}`` each task's latest dispatch ended on."""
    ids = [str(r.id) for r in rows]
    if not ids:
        return {}
    try:
        result = await session.execute(
            select(DevOutcomeLog.task_id, DevOutcomeLog.final_driver, DevOutcomeLog.final_model)
            .where(DevOutcomeLog.tenant_id == tenant_id, DevOutcomeLog.task_id.in_(ids))
            .order_by(DevOutcomeLog.created_at)
        )
        found = list(result.all())
    except Exception:
        logger.debug("Could not read the team's outcome rows", exc_info=True)
        return {}
    out: dict[str, str] = {}
    for item in found:
        try:
            task_id, driver, model = item
        except (TypeError, ValueError):
            continue
        if driver:
            out[str(task_id)] = f"{driver}:{model}" if model else str(driver)
    return out
