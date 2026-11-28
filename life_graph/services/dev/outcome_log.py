"""The dev-task outcome log (``dev_outcome_log``): write, read, summarize.

docs/specs/agent-drivers.md, "Escalation ladder, starting floor, outcome log
(2026-11-28)". The dispatcher writes one row when a dispatch ends, on every
terminal path (landed, no changes, needs a person, failed, budget-denied,
parked, crashed); :func:`record_owner_decision` fills ``owner_decision`` when
``record_outcome`` (services/dev/outcomes.py, the trust recorder, unchanged)
settles the PR. Always on. Every write is best-effort: the log must never fail
a dispatch or an outcome.

Read side: :func:`recent_failure` (the starting floor's "failed before"),
:func:`top_tier_usage` (the ladder's top-rung cap) and :func:`list_outcomes`
(``GET /kernel/drivers/outcomes``, the cockpit).
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, literal, select, update
from sqlalchemy.dialects.postgresql import JSONB

from life_graph.models.dev_outcomes import DevOutcomeLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: Outcomes that count as "this failed" for the starting floor.
FAILED_OUTCOMES = ("failed", "needs_human", "error")
#: Owner decisions that count as a failure record too.
FAILED_DECISIONS = ("pr_rejected", "closed")

_WS = re.compile(r"\s+")


def instruction_fingerprint(instruction: str | None) -> str:
    """SHA-256 of the instruction, case- and whitespace-normalized."""
    text = _WS.sub(" ", (instruction or "").strip().lower())
    return hashlib.sha256(text.encode()).hexdigest()


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value is None or isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


async def write(session_factory: Any, row: dict[str, Any]) -> bool:
    """Insert one outcome row in its own session. True when written."""
    try:
        async with session_factory() as session:
            prior = (
                await session.execute(
                    select(func.count())
                    .select_from(DevOutcomeLog)
                    .where(
                        DevOutcomeLog.tenant_id == row["tenant_id"],
                        DevOutcomeLog.task_id == str(row["task_id"]),
                    )
                )
            ).scalar_one()
            session.add(
                DevOutcomeLog(
                    **{
                        **row,
                        "task_id": str(row["task_id"]),
                        "project_id": _uuid_or_none(row.get("project_id")),
                        "attempt": int(prior or 0) + 1,
                    }
                )
            )
            await session.commit()
        return True
    except Exception:
        logger.debug("Could not write the outcome log for %s", row.get("task_id"), exc_info=True)
        return False


async def recent_failure(
    session_factory: Any,
    tenant_id: str,
    project_id: Any,
    instruction_sha: str,
    *,
    days: int,
) -> bool:
    """Whether this project + instruction failed (or was rejected) in the last *days*.

    Read from the outcome log, so it only knows dispatches logged since it
    exists. An unreadable log reads as "no record" (the floor then simply
    doesn't trigger -- today's behaviour).
    """
    since = datetime.now(UTC) - timedelta(days=days)
    pid = _uuid_or_none(project_id)
    try:
        async with session_factory() as session:
            found = (
                await session.execute(
                    select(DevOutcomeLog.id)
                    .where(
                        DevOutcomeLog.tenant_id == tenant_id,
                        DevOutcomeLog.instruction_sha == instruction_sha,
                        DevOutcomeLog.project_id.is_(None)
                        if pid is None
                        else DevOutcomeLog.project_id == pid,
                        DevOutcomeLog.created_at >= since,
                        (DevOutcomeLog.outcome.in_(FAILED_OUTCOMES))
                        | (DevOutcomeLog.owner_decision.in_(FAILED_DECISIONS)),
                    )
                    .limit(1)
                )
            ).first()
        return found is not None
    except Exception:
        logger.debug("Could not read the outcome log for %s", tenant_id, exc_info=True)
        return False


async def top_tier_usage(session_factory: Any, tenant_id: str) -> tuple[int, int] | None:
    """``(sent to the top rung by the ladder/floor, all dispatches)`` today (UTC).

    None when the log can't be read: the caller then refuses the top rung
    (fail-closed on spend).
    """
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        async with session_factory() as session:
            row = (
                await session.execute(
                    select(
                        func.count(),
                        func.count().filter(DevOutcomeLog.reached_top.is_(True)),
                    ).where(
                        DevOutcomeLog.tenant_id == tenant_id,
                        DevOutcomeLog.created_at >= start,
                        # A dispatch refused before any driver was chosen
                        # (WIP limit) is not one the cap is a share of.
                        DevOutcomeLog.start_driver.is_not(None),
                    )
                )
            ).first()
        total, top = row if row is not None else (0, 0)
        return int(top or 0), int(total or 0)
    except Exception:
        logger.debug("Could not count top-rung use for %s", tenant_id, exc_info=True)
        return None


async def record_owner_decision(
    session: AsyncSession,
    tenant_id: str,
    task_id: Any,
    decision: str,
    *,
    panel: dict[str, Any] | None = None,
) -> None:
    """Set ``owner_decision`` on the task's latest logged dispatch (in *session*).

    *panel* (``review_panel.panel_for_outcome``: verdict, members, risky,
    gated) is stored as ``properties.review_panel`` -- what shadow mode is
    compared against the owner's decision with.

    Called beside ``record_outcome``, inside its transaction, in a savepoint:
    a failure here never undoes the trust record.
    """
    if not task_id:
        return
    try:
        async with session.begin_nested():
            latest = (
                select(DevOutcomeLog.id)
                .where(DevOutcomeLog.tenant_id == tenant_id, DevOutcomeLog.task_id == str(task_id))
                .order_by(DevOutcomeLog.created_at.desc())
                .limit(1)
                .scalar_subquery()
            )
            values: dict[str, Any] = {
                "owner_decision": decision,
                "owner_decided_at": datetime.now(UTC),
            }
            if panel is not None:
                values["properties"] = DevOutcomeLog.properties.op("||")(
                    literal({"review_panel": panel}, type_=JSONB)
                )
            await session.execute(
                update(DevOutcomeLog).where(DevOutcomeLog.id == latest).values(**values)
            )
    except Exception:
        logger.debug("Could not log the owner decision for %s", task_id, exc_info=True)


def _row_dict(r: DevOutcomeLog) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "task_id": r.task_id,
        "project_id": str(r.project_id) if r.project_id else None,
        "attempt": r.attempt,
        "task_type": r.task_type,
        "persona": r.persona,
        "start": {
            "driver": r.start_driver,
            "model": r.start_model,
            "tier": r.start_tier,
            "reason": r.start_reason,
        },
        "final": {"driver": r.final_driver, "model": r.final_model, "tier": r.final_tier},
        "escalations": list(r.escalations or []),
        "reached_top": bool(r.reached_top),
        "rounds_used": r.rounds_used,
        "verification": r.verification,
        "reviews": list(r.reviews or []),
        "review_verdict": r.review_verdict,
        "outcome": r.outcome,
        "owner_decision": r.owner_decision,
        "owner_decided_at": r.owner_decided_at.isoformat() if r.owner_decided_at else None,
        "review_panel": (r.properties or {}).get("review_panel"),
        "duration_ms": r.duration_ms,
        "cost_usd": r.cost_usd,
        "shadow": {"tier": r.shadow_tier, "reasons": list(r.shadow_reasons or [])},
        "error": r.error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts the cockpit shows over *rows*: outcomes, tiers, escalations, shadow agreement."""
    outcomes: dict[str, int] = {}
    final_tiers: dict[str, int] = {}
    for r in rows:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
        tier = r["final"]["tier"] or "off_ladder"
        final_tiers[tier] = final_tiers.get(tier, 0) + 1
    shadowed = [r for r in rows if r["shadow"]["tier"] and r["final"]["tier"]]
    return {
        "total": len(rows),
        "outcomes": outcomes,
        "final_tiers": final_tiers,
        "escalated": sum(1 for r in rows if any(e.get("to") for e in r["escalations"])),
        "reached_top": sum(1 for r in rows if r["reached_top"]),
        "not_reviewed": sum(1 for r in rows if r["review_verdict"] == "not_reviewed"),
        "review_skipped": sum(1 for r in rows if r["review_verdict"] == "skipped"),
        "shadow_agrees": sum(1 for r in shadowed if r["shadow"]["tier"] == r["final"]["tier"]),
        "shadow_compared": len(shadowed),
    }


async def list_outcomes(
    session: AsyncSession,
    tenant_id: str,
    *,
    days: int = 30,
    project_id: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """The tenant's logged dispatches of the last *days*, newest first, and a summary."""
    since = datetime.now(UTC) - timedelta(days=days)
    stmt = select(DevOutcomeLog).where(
        DevOutcomeLog.tenant_id == tenant_id, DevOutcomeLog.created_at >= since
    )
    if project_id is not None:
        stmt = stmt.where(DevOutcomeLog.project_id == uuid.UUID(str(project_id)))
    rows = (
        (await session.execute(stmt.order_by(DevOutcomeLog.created_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    items = [_row_dict(r) for r in rows]
    return {
        "days": days,
        "project_id": project_id,
        "summary": summarize(items),
        "outcomes": items,
    }
