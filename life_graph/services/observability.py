"""Read models for running the system: budget, health, agents, decision gaps.

Queries and probes only: nothing here writes, and nothing calls a model.
Pages: Spend & Budget, System Health, Agents Console and Decision Gaps
(docs/specs/agent-observability.md).
"""

from __future__ import annotations

import calendar
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import func, select, text

from life_graph.config import settings
from life_graph.models.db import AgentTask, Memory
from life_graph.services.dev_tasks import RUNNER_LOCK_KEY, _kind_filter

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── Budget ────────────────────────────────────────────────────


async def budget(session: AsyncSession, tenant_id: str, top: int = 10) -> dict[str, Any]:
    """Month-to-date spend against the cap, by category, top tasks, projection."""
    from life_graph.services.governor import governor

    status = await governor.status(tenant_id)
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    elapsed_days = max((now - month_start).total_seconds() / 86400, 1 / 24)
    projected = status.spent_usd / elapsed_days * days_in_month

    # Cost lives in each task's result JSON; a month is a few hundred rows,
    # so it is read in Python rather than cast in SQL.
    rows = (
        (
            await session.execute(
                select(AgentTask)
                .where(
                    AgentTask.tenant_id == tenant_id,
                    _kind_filter(),
                    AgentTask.created_at >= month_start,
                )
                .order_by(AgentTask.created_at.desc())
                .limit(2000)
            )
        )
        .scalars()
        .all()
    )
    spenders = sorted(
        (
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status,
                "persona": t.assigned_agent,
                "cost_usd": round(float((t.result or {}).get("cost_usd") or 0.0), 4),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in rows
            if float((t.result or {}).get("cost_usd") or 0.0) > 0
        ),
        key=lambda r: -r["cost_usd"],
    )
    return {
        "month": month_start.strftime("%Y-%m"),
        "spent_usd": round(status.spent_usd, 4),
        "cap_usd": status.cap_usd,
        "remaining_usd": round(status.remaining_usd, 4),
        "soft_threshold": settings.budget_soft_threshold,
        "used_fraction": round(status.spent_usd / status.cap_usd, 4) if status.cap_usd else None,
        "projected_month_usd": round(projected, 4),
        "by_category": {k: round(v, 4) for k, v in status.by_category.items()},
        "top_tasks": spenders[:top],
        "how_to_change_cap": "Set LIFE_GRAPH_MONTHLY_BUDGET_USD in .env and restart the API.",
    }


# ── System ────────────────────────────────────────────────────


def _ollama_base() -> str:
    return (os.environ.get("OLLAMA_API_BASE") or "http://localhost:11434").rstrip("/")


async def _ollama() -> dict[str, Any]:
    base = _ollama_base()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            loaded = (await client.get(f"{base}/api/ps")).json().get("models") or []
            installed = (await client.get(f"{base}/api/tags")).json().get("models") or []
    except Exception as exc:  # noqa: BLE001 - an absent Ollama is a state to show
        return {"base": base, "error": str(exc)[:200], "loaded": [], "installed": []}
    return {
        "base": base,
        "loaded": [
            {
                "name": m.get("name"),
                "size_bytes": m.get("size"),
                "vram_bytes": m.get("size_vram"),
                # Below 1.0, part of the model sits in system RAM: slower, and
                # the likely cause of "models are currently unavailable".
                "gpu_fraction": round(m["size_vram"] / m["size"], 3)
                if m.get("size") and m.get("size_vram") is not None
                else None,
                "expires_at": m.get("expires_at"),
            }
            for m in loaded
        ],
        "installed": [{"name": m.get("name"), "size_bytes": m.get("size")} for m in installed],
    }


async def system(session: AsyncSession, app_state: Any) -> dict[str, Any]:
    """Startup subsystems, the dev-task runner, the queue, drivers, Ollama."""
    from life_graph.drivers.registry import driver_registry

    report = getattr(app_state, "startup_report", None)
    subsystems = report.as_dict() if report is not None else {}

    holders = (
        await session.execute(
            text(
                "SELECT l.pid FROM pg_locks l WHERE l.locktype = 'advisory' AND l.granted "
                "AND ((l.classid::bigint << 32) | l.objid::bigint) = :k"
            ),
            {"k": RUNNER_LOCK_KEY},
        )
    ).all()
    counts = dict(
        (
            await session.execute(
                select(AgentTask.status, func.count())
                .where(_kind_filter(), AgentTask.status.in_(("queued", "running")))
                .group_by(AgentTask.status)
            )
        ).all()
    )
    drivers = []
    for d in driver_registry.list_all():
        try:
            available = bool(await d.available())
        except Exception:  # noqa: BLE001
            available = False
        drivers.append(
            {
                "name": d.name,
                "available": available,
                "timeout_seconds": getattr(d, "dispatch_timeout", 300),
            }
        )
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "process_pid": os.getpid(),
        "subsystems": subsystems,
        "runner": {
            "this_process": getattr(app_state, "dev_task_runner_lock", None) is not None,
            "holder_backend_pids": [h[0] for h in holders],
            "enabled": settings.dev_task_runner_enabled,
        },
        "queue": {"queued": counts.get("queued", 0), "running": counts.get("running", 0)},
        "drivers": drivers,
        "ollama": await _ollama(),
    }


# ── Agents ────────────────────────────────────────────────────


async def agents(tenant_id: str) -> list[dict[str, Any]]:
    """Every persona with its model, and which of its tools are not registered."""
    from life_graph.api.dependencies import get_persona_service
    from life_graph.tools.registry import registry

    registered = set(registry.tool_names)
    personas, _total = await get_persona_service().list_all(tenant_id)
    out = []
    for p in personas:
        allowed = p.get("allowed_tools")
        model = p.get("model") or settings.agent_llm_model
        out.append(
            {
                "name": p.get("name"),
                "display_name": p.get("display_name"),
                "icon": p.get("icon"),
                "description": p.get("description"),
                "model": model,
                "driver": (p.get("properties") or {}).get("driver") or p.get("driver"),
                "tools": [{"name": t, "registered": t in registered} for t in (allowed or [])],
                "missing_tools": [t for t in (allowed or []) if t not in registered],
                "unscoped": allowed is None,
                "notes": (
                    ["Runs on claude-cli, which gets no tools: its tool list is unused."]
                    if model == "claude-cli" and allowed
                    else []
                ),
            }
        )
    return out


# ── Decision gaps ─────────────────────────────────────────────

# Extraction sometimes tags pronouns and filler as entities; they are never a
# topic anyone decides about.
_NOT_TOPICS = (
    "what",
    "this",
    "that",
    "they",
    "them",
    "these",
    "those",
    "user",
    "the user",
    "you",
    "your",
    "we",
    "our",
    "it",
    "its",
    "something",
    "everything",
    "anything",
)


async def decision_gaps(
    session: AsyncSession, tenant_id: str, *, days: int = 90, min_mentions: int = 4, limit: int = 20
) -> list[dict[str, Any]]:
    """Entities discussed often in active memories with no decision among them."""
    since = datetime.now(UTC) - timedelta(days=days)
    # "life-graph", "Life Graph" and "life_graph" are one topic.
    entity = func.regexp_replace(
        func.lower(func.jsonb_array_elements_text(Memory.properties["entities"])),
        "[-_\\s]+",
        " ",
        "g",
    )
    mentions = (
        select(
            entity.label("entity"),
            Memory.id.label("memory_id"),
            Memory.properties["fact_type"].astext.label("fact_type"),
        )
        .where(
            Memory.tenant_id == tenant_id,
            Memory.status == "active",
            Memory.created_at >= since,
            func.jsonb_typeof(Memory.properties["entities"]) == "array",
        )
        .subquery()
    )
    rows = (
        await session.execute(
            select(
                mentions.c.entity,
                func.count(func.distinct(mentions.c.memory_id)).label("mentions"),
            )
            .where(
                func.length(mentions.c.entity) >= 3,
                mentions.c.entity.notin_(_NOT_TOPICS),
                mentions.c.entity.op("!~")("^[0-9 .#]+$"),
                # Branches, paths and PR numbers are references, not topics.
                mentions.c.entity.op("!~")("/|^(pr|pull request|issue) ?#?[0-9]+$"),
            )
            .group_by(mentions.c.entity)
            .having(
                func.count(func.distinct(mentions.c.memory_id)) >= min_mentions,
                func.count().filter(mentions.c.fact_type == "decision") == 0,
            )
            .order_by(func.count(func.distinct(mentions.c.memory_id)).desc())
            .limit(limit)
        )
    ).all()

    out = []
    for name, count in rows:
        recent = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.tenant_id == tenant_id,
                        Memory.status == "active",
                        func.regexp_replace(
                            func.lower(Memory.properties["entities"].astext),
                            "[-_\\s]+",
                            " ",
                            "g",
                        ).contains(f'"{name}"'),
                    )
                    .order_by(Memory.created_at.desc())
                    .limit(3)
                )
            )
            .scalars()
            .all()
        )
        out.append(
            {
                "entity": name,
                "mentions": count,
                "recent": [
                    {
                        "id": str(m.id),
                        "content": m.content[:240],
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in recent
                ],
            }
        )
    return out
