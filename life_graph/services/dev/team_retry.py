"""Retrying a failed team worker, and the owner's retry that reopens a team.

docs/specs/agent-drivers.md, "Team upgrades (2026-11-28)". A retry is a
**fresh** worker task (``team_replaces`` = the attempt it replaces,
``team_attempt`` + 1) on the rung :class:`team_rungs.RungPicker` chooses; the
team's other rows are re-pointed at it (``depends_on``, ``seed_from``,
``dependency_wait``, the group's ``worker_ids``), so dependents keep waiting
instead of being cancelled. Which attempt is current is read from the rows
(a row some other row replaces is superseded), so a restart resumes exactly.

``teams.reconcile`` queues the automatic retries; :func:`owner_retry` is
``POST /kernel/drivers/plans/{plan_id}/workers/{task_id}/retry``.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.core.redaction import redact_secrets
from life_graph.drivers.plan_spec import TIERS
from life_graph.models.db import AgentTask, DevTaskGroup
from life_graph.services.dev import task_events, team_notes, team_rungs
from life_graph.services.dev import tasks as dev_tasks

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

KIND = "team"
#: Worker endings that are retried (a cancel -- the owner's, the kill switch's
#: or the team's own -- never is).
RETRYABLE = frozenset({"failed", "timeout"})
#: What the owner may retry.
OWNER_RETRYABLE = frozenset({"failed", "timeout", "cancelled"})
_OPEN = frozenset({"queued", "running", "parked"})

FAILURE_START = "--- WHY THE PREVIOUS ATTEMPT FAILED ---"
FAILURE_END = "--- END OF PREVIOUS ATTEMPT ---"
_FAILURE_RE = re.compile(
    r"\n*" + re.escape(FAILURE_START) + r".*?" + re.escape(FAILURE_END) + r"\n*", re.DOTALL
)

#: The properties a new attempt carries over from the one it replaces.
_CARRY = (
    "plan_task_id",
    "plan_group_id",
    "plan_task_count",
    "origin",
    "team_role",
    "plan_task_index",
    "team_files",
    "team_max_parallel",
    "acceptance_criteria",
    "acceptance_tests",
    "requested_by",
    "team_agent",
    "team_tier",
)


class TeamError(Exception):
    """A refused owner retry: ``code`` and the HTTP status it maps to."""

    def __init__(self, code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _event(tenant_id: str, task_id: str, content: str, data: dict[str, Any]) -> None:
    task_events.emit(tenant_id, task_id, "team", content, data=data, source="runner")


# ── Which attempt is current ──────────────────────────────────


def replacements(rows: list[AgentTask]) -> dict[str, str]:
    """``{replaced task id: the newest attempt that replaces it}`` for one team."""
    direct = {
        str((r.properties or {}).get("team_replaces")): str(r.id)
        for r in rows
        if (r.properties or {}).get("team_replaces")
    }
    out: dict[str, str] = {}
    for old in direct:
        cur, hops = old, 0
        while cur in direct and hops <= len(direct):
            cur, hops = direct[cur], hops + 1
        out[old] = cur
    return out


def live(rows: list[AgentTask], mapping: dict[str, str]) -> list[AgentTask]:
    """The rows no other row replaces (the current attempt of each task)."""
    return [r for r in rows if str(r.id) not in mapping]


def _mapped(ids: Any, mapping: dict[str, str]) -> list[str]:
    return [mapping.get(str(i), str(i)) for i in ids or []]


def rewire(rows: list[AgentTask], mapping: dict[str, str]) -> int:
    """Point every queued row's ``depends_on`` / ``seed_from`` / wait at the
    newest attempts; how many rows changed (they are modified in place)."""
    if not mapping:
        return 0
    changed = 0
    for row in rows:
        if row.status != "queued":
            continue
        props = dict(row.properties or {})
        before = (props.get("depends_on"), props.get("seed_from"), props.get("dependency_wait"))
        if props.get("depends_on"):
            props["depends_on"] = _mapped(props["depends_on"], mapping)
        if props.get("seed_from"):
            props["seed_from"] = _mapped(props["seed_from"], mapping)
        wait = props.get("dependency_wait")
        if isinstance(wait, dict) and wait.get("waiting_on"):
            props["dependency_wait"] = {
                **wait,
                "waiting_on": _mapped(wait["waiting_on"], mapping),
            }
        if before != (
            props.get("depends_on"),
            props.get("seed_from"),
            props.get("dependency_wait"),
        ):
            row.properties = props
            changed += 1
    return changed


def remap_group(props: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """The group's ``worker_ids`` / ``integration_task_id`` at their newest attempts."""
    out = dict(props)
    if mapping:
        out["worker_ids"] = _mapped(props.get("worker_ids"), mapping)
        if props.get("integration_task_id"):
            out["integration_task_id"] = mapping.get(
                str(props["integration_task_id"]), str(props["integration_task_id"])
            )
        pending = dict(props.get("retry_pending") or {})
        for old in list(pending):
            if old in mapping:
                pending.pop(old)
        out["retry_pending"] = pending
    return out


async def group_rows(session: AsyncSession, group: DevTaskGroup) -> list[AgentTask]:
    """Every task row of *group* (its tenant only)."""
    return list(
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


# ── A new attempt ─────────────────────────────────────────────


def failure_block(reason: str | None) -> str:
    """The delimited "why the previous attempt failed" block for a retry."""
    text = redact_secrets(" ".join(str(reason or "it failed").split()))[:800]
    return (
        f"{FAILURE_START}\nThis task was tried before and failed: {text}\n"
        f"Avoid that failure this time.\n{FAILURE_END}"
    )


def attempt_instruction(
    old_instruction: str | None, notes: list[dict[str, Any]], reason: str | None
) -> str:
    """A new attempt's instruction: the original task, why the last attempt
    failed (a retry), and the teammates' notes it may see."""
    base = _FAILURE_RE.sub("\n\n", team_notes.strip_block(old_instruction)).rstrip()
    if reason is not None:
        base = f"{base}\n\n{failure_block(reason)}"
    return team_notes.with_notes(base, notes)


def _wave(group_props: dict[str, Any], row: AgentTask) -> int | None:
    return team_notes.wave_of(
        group_props.get("waves"), (row.properties or {}).get("plan_task_index")
    )


def visible_notes(group_props: dict[str, Any], row: AgentTask) -> list[dict[str, Any]]:
    """The board entries *row* gets in its instruction."""
    notes = list(group_props.get("notes") or [])
    if (row.properties or {}).get("team_role") == "integration":
        return team_notes.notes_for(notes, None, integration=True)
    return team_notes.notes_for(notes, _wave(group_props, row))


async def create_attempt(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    group_props: dict[str, Any],
    old: AgentTask,
    mapping: dict[str, str],
    *,
    retry: bool,
    reason: str | None = None,
    by: str = "team",
    tier: str | None = None,
    persona: str | None = None,
    picker: team_rungs.RungPicker | None = None,
    ran_on: Any = None,
) -> dict[str, Any]:
    """Queue a new attempt of team task *old*; the new task's summary.

    ``retry`` = a retry of a failed worker (attempt + 1, a rung chosen,
    the failure in its instruction); otherwise a re-queue of a task the team
    cancelled (same attempt, same pins). *mapping* holds the newest attempts
    so far and gets the new one added.
    """
    props = dict(old.properties or {})
    attempt = int(props.get("team_attempt") or 1) + (1 if retry else 0)
    new_props: dict[str, Any] = {k: props[k] for k in _CARRY if k in props}
    new_props.update(
        {
            "team_attempt": attempt,
            "team_replaces": str(old.id),
            "seed_from": _mapped(props.get("seed_from"), mapping),
        }
    )
    persona_name = persona or props.get("routed_from") or old.assigned_agent or "code-fixer"
    choice: team_rungs.RungChoice | None = None
    if retry:
        picker = picker or team_rungs.RungPicker(session_factory, tenant_id)
        persona_row = await team_rungs.get_persona(session_factory, tenant_id, persona_name)
        pinned = team_rungs.persona_pins(persona_row)
        if tier:
            choice = (
                team_rungs.RungChoice(why=f"tier {tier} ignored: persona pins {pinned}")
                if pinned
                else await picker.for_tier(tier)
            )
        elif pinned:
            choice = team_rungs.RungChoice(why=f"retry with the persona's own driver ({pinned})")
        else:
            choice = await picker.for_retry(ran_on)
        new_props.update(choice.pin())
        new_props["team_retry_reason"] = redact_secrets(str(reason or "failed"))[:500]
        new_props["team_retry_by"] = by
        new_props["team_retry_why"] = choice.why[:300]
        if persona:
            new_props["team_agent"] = {
                **(props.get("team_agent") or {}),
                "requested": persona,
                "resolved": persona,
            }
        new_props["team_tier"] = {
            "requested": tier or (props.get("team_tier") or {}).get("requested"),
            "resolved": choice.tier,
        }
    else:
        for key in ("driver_pin", "team_rung"):
            if key in props:
                new_props[key] = props[key]
    instruction = attempt_instruction(
        old.instructions, visible_notes(group_props, old), reason if retry else None
    )
    depends_on = _mapped(props.get("depends_on"), mapping)
    task = await dev_tasks.create_dev_task(
        session_factory,
        tenant_id,
        instruction=instruction,
        project={"id": str(old.project_id), "name": props.get("project_name") or ""},
        persona_name=persona_name,
        task_type=old.task_type or "code_change",
        start=False,
        depends_on=depends_on or None,
        properties=new_props,
        dedupe_scope=f"team:{props.get('plan_group_id')}:{props.get('plan_task_index')}:"
        f"{attempt}:{old.id}",
    )
    if task.get("duplicate_of"):
        raise TeamError("duplicate", f"an open task already does this ({task['duplicate_of']})")
    new_id = str(task["id"])
    mapping[str(old.id)] = new_id
    for old_id, cur in list(mapping.items()):
        if cur == str(old.id):
            mapping[old_id] = new_id
    rung = (new_props.get("team_rung") or {}).get("label")
    what = "retry" if retry else "re-queued"
    _event(
        tenant_id, str(old.id), f"team: {what} as {new_id[:8]}" + (f" on {rung}" if rung else ""),
        {"kind": what, "task_id": new_id, "attempt": attempt, "rung": rung,
         "why": choice.why if choice else None, "by": by},
    )  # fmt: skip
    _event(
        tenant_id, new_id, f"team: attempt {attempt} of task {props.get('plan_task_index')}",
        {"kind": what, "replaces": str(old.id), "attempt": attempt, "rung": rung,
         "reason": new_props.get("team_retry_reason"), "by": by},
    )  # fmt: skip
    return {
        "task_id": new_id,
        "replaces": str(old.id),
        "index": props.get("plan_task_index"),
        "attempt": attempt,
        "rung": rung,
        "why": choice.why if choice else None,
        "refused": choice.refused if choice else [],
    }


def failed_worker_matches(group: DevTaskGroup, task_id: str) -> bool:
    """Whether *group* failed because of worker *task_id* (and nothing else)."""
    props = group.properties or {}
    failed = props.get("failed_task_id")
    if failed:
        return str(failed) == task_id
    # A team that failed before failed_task_id was recorded: read the reason.
    return str(props.get("reason") or "").startswith(f"worker {task_id[:8]} ")


# ── The owner's retry ─────────────────────────────────────────


async def owner_retry(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    plan_id: str,
    task_id: str,
    *,
    tier: str | None = None,
    persona: str | None = None,
    by: str = "owner",
) -> dict[str, Any]:
    """Re-run one failed worker of a plan's team; reopen the team when it had
    failed because of that worker (see docs/specs/agent-drivers.md)."""
    if tier is not None and tier not in TIERS:
        raise TeamError("invalid_tier", f"tier must be one of {', '.join(TIERS)}", 422)
    if (
        persona is not None
        and await team_rungs.get_persona(session_factory, tenant_id, persona) is None
    ):
        raise TeamError("unknown_persona", f"no active persona {persona!r} with a driver", 422)
    async with session_factory() as session:
        task = (
            await session.execute(
                select(AgentTask).where(
                    AgentTask.tenant_id == tenant_id,
                    dev_tasks._kind_filter(),
                    AgentTask.id == uuid.UUID(task_id),
                )
            )
        ).scalar_one_or_none()
        props = (task.properties or {}) if task is not None else {}
        if (
            task is None
            or props.get("team_role") != "worker"
            or str(props.get("plan_task_id")) != plan_id
        ):
            raise TeamError("not_found", "no such worker in this plan's team", 404)
        try:
            group_id = uuid.UUID(str(props.get("plan_group_id")))
        except ValueError:
            raise TeamError("not_found", "the worker has no team", 404) from None
        group = (
            await session.execute(
                select(DevTaskGroup)
                .where(
                    DevTaskGroup.id == group_id,
                    DevTaskGroup.tenant_id == tenant_id,
                    DevTaskGroup.kind == KIND,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if group is None:
            raise TeamError("not_found", "the worker's team is gone", 404)
        gprops = dict(group.properties or {})
        rows = await group_rows(session, group)
        mapping = replacements(rows)
        if task_id in mapping:
            raise TeamError("superseded", f"a newer attempt exists ({mapping[task_id]})")
        if task_id in (gprops.get("retry_pending") or {}):
            raise TeamError("retry_pending", "the team is already retrying this worker")
        if task.status not in OWNER_RETRYABLE:
            raise TeamError("not_failed", f"the worker is {task.status}, not failed")
        if group.status in ("integrating", "awaiting_approval"):
            raise TeamError("team_busy", f"the team is {group.status}")
        reopen = group.status == "failed"
        if reopen and not failed_worker_matches(group, task_id):
            raise TeamError(
                "failed_elsewhere",
                f"the team failed because of {gprops.get('failed_task_id') or gprops.get('reason')}"
                "; retry that worker",
            )
        reason = task.error or task.status
        ran = await team_rungs.ran_on(session, tenant_id, task)
        made = await create_attempt(
            session_factory, tenant_id, gprops, task, mapping, retry=True,
            reason=reason, by=by, tier=tier, persona=persona, ran_on=ran,
        )  # fmt: skip
        requeued: list[dict[str, Any]] = []
        if reopen:
            cancelled_by_team = {str(t) for t in gprops.get("team_cancelled") or []}
            again = [
                r
                for r in live(rows, mapping)
                if str(r.id) != task_id
                and r.status == "cancelled"
                and (
                    str(r.id) in cancelled_by_team or (r.properties or {}).get("dependency_failed")
                )
            ]
            again.sort(
                key=lambda r: (
                    (r.properties or {}).get("team_role") == "integration",
                    (r.properties or {}).get("plan_task_index") or 0,
                )
            )
            for row in again:
                requeued.append(
                    await create_attempt(
                        session_factory, tenant_id, gprops, row, mapping, retry=False, by=by
                    )
                )
        rewire(rows, mapping)
        gprops = remap_group(gprops, mapping)
        if reopen:
            group.status = "running"
            gprops["history"] = [
                *(gprops.get("history") or []),
                {
                    "status": "running",
                    "at": _now(),
                    "why": f"reopened: owner retried worker {props.get('plan_task_index')}",
                },
            ]
            for key in ("reason", "failed_task_id"):
                gprops.pop(key, None)
            gprops["team_cancelled"] = []
            gprops["reopened"] = int(gprops.get("reopened") or 0) + 1
        group.properties = gprops
        await session.commit()
    return {
        "group_id": str(group_id),
        "status": "running" if reopen else group.status,
        "reopened": reopen,
        "retry": made,
        "requeued": requeued,
    }
