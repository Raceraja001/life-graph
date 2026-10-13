"""Read models for studying the dev agent: plans, scorecards, failures.

Everything here is a query over rows that already exist (agent_tasks,
approvals, verification_runs, agent_run_steps). Nothing is stored and
nothing calls a model. Pages: Plan Board, Agent Scorecards and Failure
Explorer (docs/specs/agent-observability.md).
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from life_graph.models.db import AgentRunStep, AgentTask, VerificationRun
from life_graph.services import acceptance
from life_graph.services.dev_tasks import (
    _approvals_by_task,
    _kind_filter,
    _plan_gate,
    _stage,
    _verification_summary,
    auto_merge_status,
    driver_of,
    serialize,
)
from life_graph.services.failure_causes import CAUSES, classify
from life_graph.services.trajectories import list_steps

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

FAILED = ("failed", "cancelled", "timeout")


def _pinned_driver(persona: str | None) -> str | None:
    """The driver a built-in persona pins (code-fixer -> claude_code, ...)."""
    from life_graph.kernel.personas import _BUILTIN_PERSONAS

    for p in _BUILTIN_PERSONAS:
        if p["name"] == persona and p.get("driver") not in (None, "auto"):
            return p["driver"]
    return None


def _driver(task: AgentTask) -> str:
    """Recorded or inferred driver, else the persona's pinned one, else the persona."""
    return (
        driver_of(task) or _pinned_driver(task.assigned_agent) or task.assigned_agent or "unknown"
    )


async def _tasks(session: AsyncSession, tenant_id: str, *filters: Any, limit: int = 500):
    return (
        (
            await session.execute(
                select(AgentTask)
                .where(AgentTask.tenant_id == tenant_id, _kind_filter(), *filters)
                .order_by(AgentTask.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def _attempts(session: AsyncSession, tenant_id: str, ids: list[uuid.UUID]) -> dict:
    """Highest verification attempt per task (2 means it was bounced)."""
    if not ids:
        return {}
    rows = await session.execute(
        select(VerificationRun.task_id, func.max(VerificationRun.attempt))
        .where(VerificationRun.tenant_id == tenant_id, VerificationRun.task_id.in_(ids))
        .group_by(VerificationRun.task_id)
    )
    return {tid: n for tid, n in rows.all()}


async def _has_steps(session: AsyncSession, tenant_id: str, ids: list[uuid.UUID]) -> set:
    if not ids:
        return set()
    rows = await session.execute(
        select(AgentRunStep.task_id)
        .where(AgentRunStep.tenant_id == tenant_id, AgentRunStep.task_id.in_(ids))
        .distinct()
    )
    return {r[0] for r in rows.all()}


async def cause_of(session: AsyncSession, tenant_id: str, task: AgentTask) -> dict[str, Any]:
    """The primary failure cause of one finished-but-failed task."""
    return classify(
        status=task.status,
        error=task.error,
        verification=await _verification_summary(session, tenant_id, task.id),
        steps=await list_steps(session, tenant_id, task.id),
    )


# ── Plans ─────────────────────────────────────────────────────


async def list_plans(session: AsyncSession, tenant_id: str, limit: int = 30) -> list[dict]:
    """Plan tasks, newest first, each with its child tasks counted by stage."""
    plans = await _tasks(session, tenant_id, AgentTask.task_type == "plan", limit=limit)
    if not plans:
        return []
    ids = [str(p.id) for p in plans]
    children = await _tasks(
        session, tenant_id, AgentTask.properties["plan_task_id"].astext.in_(ids), limit=2000
    )
    approvals = await _approvals_by_task(session, tenant_id, ids + [str(c.id) for c in children])
    by_plan: dict[str, Counter] = {}
    for c in children:
        stage = _stage(c, approvals.get(str(c.id), []))
        by_plan.setdefault(str((c.properties or {}).get("plan_task_id")), Counter())[stage] += 1
    out = []
    for p in plans:
        row = serialize(p, approvals.get(str(p.id), []))
        counts = by_plan.get(str(p.id), Counter())
        row["children"] = {"total": sum(counts.values()), "by_stage": dict(counts)}
        row["criteria_count"] = len(acceptance.parse_criteria(row.get("spec")))
        out.append(row)
    return out


async def get_plan(session: AsyncSession, tenant_id: str, plan_id: str) -> dict | None:
    """One plan: spec, criteria with conformance, and its tasks in order."""
    try:
        pk = uuid.UUID(plan_id)
    except ValueError:
        return None
    plan = await session.get(AgentTask, pk)
    if (
        plan is None
        or plan.tenant_id != tenant_id
        or (plan.properties or {}).get("kind") != "dev_task"
        or plan.task_type != "plan"
    ):
        return None
    children = await _tasks(
        session, tenant_id, AgentTask.properties["plan_task_id"].astext == plan_id, limit=200
    )
    children = sorted(
        children, key=lambda c: ((c.properties or {}).get("plan_task_index") or 0, c.created_at)
    )
    approvals = await _approvals_by_task(
        session, tenant_id, [plan_id] + [str(c.id) for c in children]
    )
    data = serialize(plan, approvals.get(plan_id, []))

    report = {c.get("id"): c for c in ((data.get("conformance") or {}).get("criteria") or [])}
    data["criteria"] = [
        {
            "id": c.id,
            "text": c.text,
            "test": c.test,
            "status": (report.get(c.id) or {}).get("status", "unchecked"),
        }
        for c in acceptance.parse_criteria(data.get("spec"))
    ]

    tasks = []
    for c in children:
        row = serialize(c, approvals.get(str(c.id), []))
        if c.status == "queued":
            gate, _prev, prev_stage = await _plan_gate(session, c)
            row["gate"] = {"state": gate, "waiting_on_stage": prev_stage or None}
        if c.status in FAILED:
            row["failure"] = await cause_of(session, tenant_id, c)
        row["acceptance_tests"] = (c.properties or {}).get("acceptance_tests") or []
        tasks.append(row)
    data["tasks"] = tasks
    return data


# ── Scorecards and failures ───────────────────────────────────


def _since(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=max(1, days))


async def scorecards(session: AsyncSession, tenant_id: str, days: int = 30) -> dict[str, Any]:
    """Per driver: how often its runs succeed, bounce, merge, and what they cost."""
    tasks = await _tasks(session, tenant_id, AgentTask.created_at >= _since(days), limit=2000)
    approvals = await _approvals_by_task(session, tenant_id, [str(t.id) for t in tasks])
    attempts = await _attempts(session, tenant_id, [t.id for t in tasks])

    cards: dict[str, dict[str, Any]] = {}
    for t in tasks:
        if t.status in ("queued", "running"):
            continue
        metadata = (t.result or {}).get("metadata") or {}
        driver = _driver(t)
        card = cards.setdefault(
            driver,
            {
                "driver": driver,
                "models": [],
                "personas": [],
                "runs": 0,
                "succeeded": 0,
                "failed": 0,
                "bounced": 0,
                "merged": 0,
                "cost_usd": 0.0,
                "plan_runs": 0,
                "_failed": [],
            },
        )
        if metadata.get("model") and metadata["model"] not in card["models"]:
            card["models"].append(metadata["model"])
        if t.assigned_agent and t.assigned_agent not in card["personas"]:
            card["personas"].append(t.assigned_agent)
        card["runs"] += 1
        card["cost_usd"] += float((t.result or {}).get("cost_usd") or 0.0)
        if t.task_type == "plan":
            card["plan_runs"] += 1
        if attempts.get(t.id, 1) >= 2:
            card["bounced"] += 1
        if _stage(t, approvals.get(str(t.id), [])) == "merged":
            card["merged"] += 1
        if t.status == "completed":
            card["succeeded"] += 1
        elif t.status in FAILED:
            card["failed"] += 1
            card["_failed"].append(t)

    out = []
    for card in cards.values():
        causes: Counter = Counter()
        for t in card.pop("_failed"):
            causes[(await cause_of(session, tenant_id, t))["cause"]] += 1
        runs = card["runs"]
        card["cost_usd"] = round(card["cost_usd"], 4)
        card["success_rate"] = round(card["succeeded"] / runs, 3) if runs else 0.0
        card["bounce_rate"] = round(card["bounced"] / runs, 3) if runs else 0.0
        card["cost_per_merged"] = (
            round(card["cost_usd"] / card["merged"], 4) if card["merged"] else None
        )
        card["top_causes"] = [
            {"cause": c, "label": CAUSES[c], "count": n} for c, n in causes.most_common(3)
        ]
        out.append(card)
    out.sort(key=lambda c: (-c["runs"], c["driver"]))
    return {"days": days, "cards": out, "auto_merge": await auto_merge_status(session, tenant_id)}


async def failures(
    session: AsyncSession, tenant_id: str, days: int = 30, limit: int = 200
) -> dict[str, Any]:
    """Failed runs, each with its primary cause, plus counts per cause."""
    tasks = await _tasks(
        session,
        tenant_id,
        AgentTask.created_at >= _since(days),
        AgentTask.status.in_(FAILED),
        limit=limit,
    )
    recorded = await _has_steps(session, tenant_id, [t.id for t in tasks])
    rows, counts = [], Counter()
    for t in tasks:
        cause = await cause_of(session, tenant_id, t)
        counts[cause["cause"]] += 1
        rows.append(
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status,
                "error": t.error,
                "persona": t.assigned_agent,
                "driver": _driver(t),
                "task_type": t.task_type,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "has_steps": t.id in recorded,
                **cause,
            }
        )
    groups = [{"cause": c, "label": CAUSES[c], "count": n} for c, n in counts.most_common()]
    return {"days": days, "total": len(rows), "groups": groups, "failures": rows}
