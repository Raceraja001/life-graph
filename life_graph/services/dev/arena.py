"""Arena: race one instruction on several drivers or accounts; the owner picks.

docs/specs/agent-drivers.md, "Phase 4b". Off by default
(``driver_arena_enabled``). ``create_arena`` queues N ordinary dev tasks with
the same instruction for the same project, each **pinned** to one driver (and
optionally one agent account): no fallback to another driver, and their
results never auto-open or auto-merge (``hold_auto``), so every racer ends as a
pending ``driver_pr`` approval at most. ``get_arena`` shows them side by side
-- status and stage, diff size, verification attempts and outcome, cost,
rounds, time -- with each driver's scorecard. ``pick_winner`` is the owner's:
the other racers still running are cancelled and their pending approvals
rejected (``resolved_by = "system: arena"``); the winner's approval is left
exactly as it is, to be approved like any other. Nothing is approved here.

The race is a ``dev_task_groups`` row (kind ``arena``); the racers carry
``properties.arena_id``. Rebuilt from race-app's ``arena/arena-manager.ts``
(the owner's code).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.config import settings
from life_graph.drivers.registry import driver_registry
from life_graph.models.db import AgentTask, Approval, DevTaskGroup
from life_graph.services.agent_accounts.service import AccountNotFoundError, get_account
from life_graph.services.agent_insights import _attempts, scorecards
from life_graph.services.dev import tasks as dev_tasks

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

KIND = "arena"
MIN_RACERS = 2
MAX_RACERS = 5
_OPEN = frozenset({"queued", "running", "parked"})
_LANDED_STAGES = frozenset({"awaiting_pr", "pr_open", "awaiting_merge", "merged"})


class ArenaError(Exception):
    """An arena request refused; ``code`` and ``http_status`` for the API."""

    def __init__(self, code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def normalize_entries(entries: list[Any]) -> list[dict[str, str | None]]:
    """``["codex", {"driver": "claude_code", "account_id": "…"}]`` -> checked dicts."""
    out: list[dict[str, str | None]] = []
    for raw in entries or []:
        if isinstance(raw, str):
            entry = {"driver": raw.strip(), "account_id": None}
        elif isinstance(raw, dict):
            account = raw.get("account_id")
            entry = {
                "driver": str(raw.get("driver") or "").strip(),
                "account_id": str(account) if account else None,
            }
        else:
            raise ArenaError("invalid", "Each racer is a driver name or {driver, account_id}", 422)
        if not entry["driver"]:
            raise ArenaError("invalid", "A racer has no driver", 422)
        if entry in out:
            raise ArenaError("invalid", f"Racer {entry['driver']} is listed twice", 422)
        out.append(entry)
    if not MIN_RACERS <= len(out) <= MAX_RACERS:
        raise ArenaError("invalid", f"An arena races {MIN_RACERS} to {MAX_RACERS} racers", 422)
    return out


async def _check_racers(
    session: AsyncSession, tenant_id: str, entries: list[dict[str, str | None]]
) -> None:

    for entry in entries:
        if driver_registry.get(str(entry["driver"])) is None:
            raise ArenaError("unknown_driver", f"Unknown driver {entry['driver']!r}", 422)
        if entry["account_id"]:
            try:
                account = await get_account(session, tenant_id, entry["account_id"])
            except AccountNotFoundError:
                raise ArenaError(
                    "unknown_account", f"Unknown agent account {entry['account_id']}", 422
                ) from None
            if account.driver != entry["driver"]:
                raise ArenaError(
                    "unknown_account",
                    f"Account {entry['account_id']} is a {account.driver} account",
                    422,
                )


async def create_arena(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    *,
    project: dict[str, Any],
    instruction: str,
    entries: list[Any],
    persona_name: str,
    requested_by: str | None = None,
) -> dict[str, Any]:
    """Queue the race; returns it as :func:`get_arena` shows it."""

    if not settings.driver_arena_enabled:
        raise ArenaError("arena_disabled", "The arena is off (driver_arena_enabled=false)")
    racers = normalize_entries(entries)
    group_id = uuid.uuid4()
    async with session_factory() as session:
        await _check_racers(session, tenant_id, racers)
        session.add(
            DevTaskGroup(
                id=group_id,
                tenant_id=tenant_id,
                kind=KIND,
                project_id=uuid.UUID(project["id"]),
                status="racing",
                title=(instruction.strip().splitlines() or ["Arena"])[0][:200],
                properties={"instruction": instruction[:8000], "racers": []},
            )
        )
        await session.commit()
    created: list[dict[str, Any]] = []
    for i, entry in enumerate(racers, start=1):
        task = await dev_tasks.create_dev_task(
            session_factory,
            tenant_id,
            instruction=instruction,
            project=project,
            persona_name=persona_name,
            task_type="code_change",
            start=True,  # the owner asked for this race now
            dedupe_scope=f"arena:{group_id}:{i}",
            properties={
                "origin": "arena",
                "arena_id": str(group_id),
                "arena_index": i,
                "driver_pin": entry["driver"],
                **({"account_pin": entry["account_id"]} if entry["account_id"] else {}),
                **({"requested_by": requested_by} if requested_by else {}),
            },
        )
        created.append({"task_id": str(task["id"]), **entry})
    async with session_factory() as session:
        group = await session.get(DevTaskGroup, group_id)
        group.properties = {**(group.properties or {}), "racers": created}
        await session.commit()

    await dev_tasks._emit_bus(
        "ARENA_CREATED",
        {"tenant_id": tenant_id, "arena_id": str(group_id), "racers": len(created),
         "drivers": [c["driver"] for c in created]},
    )  # fmt: skip
    async with session_factory() as session:
        return await get_arena(session, tenant_id, str(group_id))


async def _group(session: AsyncSession, tenant_id: str, arena_id: str, *, lock: bool = False):
    try:
        pk = uuid.UUID(str(arena_id))
    except ValueError:
        return None
    stmt = select(DevTaskGroup).where(
        DevTaskGroup.id == pk, DevTaskGroup.tenant_id == tenant_id, DevTaskGroup.kind == KIND
    )
    if lock:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


def _diff_stats(pr: Approval | None) -> dict[str, Any] | None:
    change = ((pr.payload or {}).get("change") or {}) if pr is not None else {}
    if not change:
        return None
    return {
        "files": len(change.get("files") or []),
        "lines": change.get("lines"),
        "kind": change.get("kind"),
    }


def racer_row(
    task: AgentTask | None, entry: dict, approvals: list[Approval], attempts: int, stage: str | None
) -> dict[str, Any]:
    """One racer, side by side with the others."""

    if task is None:
        return {**entry, "status": "gone", "stage": None}
    result = task.result or {}
    metadata = result.get("metadata") or {}
    prs = sorted((a for a in approvals if a.kind == "driver_pr"), key=dev_tasks._created_key)
    pr = prs[-1] if prs else None
    return {
        "task_id": str(task.id),
        "driver": entry.get("driver"),
        "account_id": entry.get("account_id"),
        "ran_on": metadata.get("driver"),
        "model": metadata.get("model"),
        "status": task.status,
        "stage": stage,
        "error": task.error,
        "cost_usd": result.get("cost_usd"),
        "duration_ms": result.get("duration_ms"),
        "rounds": attempts,
        "verified": (pr.payload or {}).get("verified") if pr is not None else None,
        "checks": list((pr.payload or {}).get("checks") or []) if pr is not None else [],
        "diff": _diff_stats(pr),
        "branch": metadata.get("landed_branch"),
        "approval": (
            {"id": str(pr.id), "status": pr.status, "title": pr.title} if pr is not None else None
        ),
    }


def race_status(group_status: str, rows: list[dict[str, Any]]) -> str:
    """``racing`` while a racer is still open, then ``ready_to_pick`` (or the decision)."""
    if group_status in ("decided", "cancelled"):
        return group_status
    return "racing" if any(r.get("status") in _OPEN for r in rows) else "ready_to_pick"


async def get_arena(session: AsyncSession, tenant_id: str, arena_id: str) -> dict[str, Any] | None:
    """The race and its racers side by side; None for no such race of this tenant."""

    group = await _group(session, tenant_id, arena_id)
    if group is None:
        return None
    props = group.properties or {}
    entries = list(props.get("racers") or [])
    ids = [uuid.UUID(e["task_id"]) for e in entries if e.get("task_id")]
    rows = (
        (
            await session.execute(
                select(AgentTask).where(
                    AgentTask.tenant_id == tenant_id,
                    dev_tasks._kind_filter(),
                    AgentTask.id.in_(ids),
                )
            )
        )
        .scalars()
        .all()
        if ids
        else []
    )
    by_id = {str(r.id): r for r in rows}
    approvals = await dev_tasks._approvals_by_task(session, tenant_id, list(by_id))
    attempts = await _attempts(session, tenant_id, [r.id for r in rows])
    racers = []
    for entry in entries:
        task = by_id.get(str(entry.get("task_id")))
        mine = approvals.get(str(entry.get("task_id")), [])
        stage = dev_tasks._stage(task, mine) if task is not None else None
        racers.append(racer_row(task, entry, mine, attempts.get(task.id, 1) if task else 0, stage))
    cards = {}
    try:
        board = await scorecards(session, tenant_id)
        cards = {c.get("driver"): c for c in (board.get("cards") or [])}
    except Exception:  # best-effort: the race is shown without scorecards
        logger.debug("Arena: scorecards unavailable", exc_info=True)
    for r in racers:
        card = cards.get(r.get("driver"))
        r["scorecard"] = (
            {
                k: card.get(k)
                for k in ("runs", "success_rate", "bounce_rate", "merged", "cost_per_merged")
            }  # fmt: skip
            if card
            else None
        )
    return {
        "id": str(group.id),
        "project_id": str(group.project_id) if group.project_id else None,
        "instruction": props.get("instruction"),
        "status": race_status(group.status, racers),
        "winner_task_id": props.get("winner_task_id"),
        "decided_at": props.get("decided_at"),
        "racers": racers,
        "created_at": group.created_at.isoformat() if group.created_at else None,
    }


async def pick_winner(
    session_factory: async_sessionmaker[AsyncSession], tenant_id: str, arena_id: str, task_id: str
) -> dict[str, Any]:
    """The owner's pick: cancel/reject the others; the winner's approval proceeds as is."""

    now = datetime.now(UTC)
    to_cancel: list[str] = []
    rejected: list[str] = []
    async with session_factory() as session:
        group = await _group(session, tenant_id, arena_id, lock=True)
        if group is None:
            raise ArenaError("not_found", "Arena race not found", 404)
        if group.status in ("decided", "cancelled"):
            raise ArenaError("decided", f"The race is already {group.status}")
        props = dict(group.properties or {})
        entries = list(props.get("racers") or [])
        racer_ids = [str(e.get("task_id")) for e in entries]
        if str(task_id) not in racer_ids:
            raise ArenaError("not_a_racer", f"Task {task_id} is not a racer of this race", 422)
        rows = (
            (
                await session.execute(
                    select(AgentTask).where(
                        AgentTask.tenant_id == tenant_id,
                        dev_tasks._kind_filter(),
                        AgentTask.id.in_([uuid.UUID(i) for i in racer_ids]),
                    )
                )
            )
            .scalars()
            .all()
        )
        by_id = {str(r.id): r for r in rows}
        approvals = await dev_tasks._approvals_by_task(session, tenant_id, racer_ids)
        winner = by_id.get(str(task_id))
        if (
            winner is None
            or dev_tasks._stage(winner, approvals.get(str(task_id), [])) not in _LANDED_STAGES
        ):
            raise ArenaError(
                "not_ready", "The winner has no change to approve yet; pick a racer that landed"
            )
        for rid in racer_ids:
            if rid == str(task_id):
                continue
            row = by_id.get(rid)
            if row is not None and row.status in _OPEN:
                to_cancel.append(rid)
            for appr in approvals.get(rid, []):
                if appr.kind in ("driver_pr", "driver_merge") and appr.status == "pending":
                    appr.status = "rejected"
                    appr.resolved_at = now
                    appr.resolved_by = "system: arena"
                    appr.resolution_note = f"Another racer won arena race {str(group.id)[:8]} (task {str(task_id)[:8]})."
                    rejected.append(str(appr.id))
        props.update(
            {"winner_task_id": str(task_id), "decided_at": now.isoformat(),
             "cancelled_task_ids": to_cancel, "rejected_approval_ids": rejected}
        )  # fmt: skip
        group.properties = props
        group.status = "decided"
        await session.commit()
    for rid in to_cancel:
        try:
            await dev_tasks.request_cancel(session_factory, tenant_id, rid)
        except Exception:
            logger.warning("Arena: could not cancel racer %s", rid, exc_info=True)
    winner_driver = next(
        (e.get("driver") for e in entries if e.get("task_id") == str(task_id)), None
    )
    await dev_tasks._emit_bus(
        "ARENA_DECIDED",
        {"tenant_id": tenant_id, "arena_id": str(arena_id), "winner_task_id": str(task_id),
         "winner_driver": winner_driver, "cancelled": len(to_cancel), "rejected": len(rejected)},
    )  # fmt: skip
    async with session_factory() as session:
        data = await get_arena(session, tenant_id, str(arena_id))
    return {**(data or {}), "cancelled_task_ids": to_cancel, "rejected_approval_ids": rejected}
