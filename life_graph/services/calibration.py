"""Calibration Service — turns resolved predictions into calibration snapshots.

The math lives in ``scoring/calibration.py`` (pure functions). This service
loads predictions, runs the math, and persists ``calibration_snapshots``:

- one ``overall`` snapshot plus one per domain tag, each only once it has
  MIN_RESOLVED_FOR_CALIBRATION resolved predictions (spec: never show fake
  curves);
- at most one row per (tenant, domain, window) per UTC day: a recompute on
  the same day replaces that day's row, so the table is a clean daily history
  that trend comparisons can read.

It runs nightly (``workers.tasks.run_nightly_calibration``) and right after a
manual resolution, so the curve appears the moment the 20th prediction
resolves instead of the next morning.

Follows the JudgmentService pattern: operates on a caller-provided
``AsyncSession`` and emits events via ``EventBus``; the caller commits.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, select

from life_graph.core.events import EventBus, EventType
from life_graph.models.db import CalibrationSnapshot, Prediction
from life_graph.scoring.calibration import (
    MIN_RESOLVED_FOR_CALIBRATION,
    CalibrationResult,
    full_calibration,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

OVERALL = "overall"
DEFAULT_WINDOW_DAYS = 90
RESOLVED_OUTCOMES = ("correct", "incorrect", "ambiguous")


async def latest_snapshot(
    session: AsyncSession,
    tenant_id: str,
    domain: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> CalibrationSnapshot | None:
    """Latest snapshot for ``domain``, falling back to the overall one.

    Readers used to take the newest snapshot of *any* domain when none was
    asked for, so a bias model computed from three infra predictions could be
    presented as the user's overall calibration. ``None`` now means overall.
    """
    for scope in dict.fromkeys([domain or OVERALL, OVERALL]):
        result = await session.execute(
            select(CalibrationSnapshot)
            .where(
                CalibrationSnapshot.tenant_id == tenant_id,
                CalibrationSnapshot.domain == scope,
                CalibrationSnapshot.window_days == window_days,
            )
            .order_by(CalibrationSnapshot.computed_at.desc())
            .limit(1)
        )
        snap = result.scalars().first()
        if snap is not None:
            return snap
    return None


def describe_finding(finding: dict[str, Any]) -> str:
    """One bias finding as a sentence, for reports that people or agents read."""
    direction = finding.get("direction", "miscalibrated")
    if finding.get("kind") == "bucket":
        return (
            f"When you say about {finding['claimed']:.0%}, you are right "
            f"{finding['actual']:.0%} of the time ({finding['n']} predictions): {direction}."
        )
    return (
        f"Overall {direction}: average confidence {finding.get('avg_confidence', 0):.0%}, "
        f"right {finding.get('hit_rate', 0):.0%} of the time ({finding.get('count', 0)} predictions)."
    )


class CalibrationService:
    """Computes calibration from resolved predictions."""

    def __init__(self, session: AsyncSession, event_bus: EventBus | None = None) -> None:
        self.session = session
        self.event_bus = event_bus

    # ── Reads ─────────────────────────────────────────────────

    async def resolved_predictions(
        self,
        tenant_id: str,
        window_days: int = DEFAULT_WINDOW_DAYS,
        *,
        end: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Predictions resolved in the ``window_days`` before ``end`` (default now)."""
        end = end or datetime.now(UTC)
        start = end - timedelta(days=window_days)
        result = await self.session.execute(
            select(Prediction.confidence, Prediction.outcome, Prediction.domain_tags).where(
                Prediction.tenant_id == tenant_id,
                Prediction.outcome.in_(RESOLVED_OUTCOMES),
                Prediction.resolved_at > start,
                Prediction.resolved_at <= end,
            )
        )
        return [
            {"confidence": c, "outcome": o, "domain_tags": list(tags or [])}
            for c, o, tags in result.all()
        ]

    async def pending_count(self, tenant_id: str) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Prediction)
            .where(Prediction.tenant_id == tenant_id, Prediction.outcome == "pending")
        )
        return int(result.scalar() or 0)

    async def compute(
        self,
        tenant_id: str,
        domain: str | None = None,
        window_days: int = DEFAULT_WINDOW_DAYS,
        *,
        end: datetime | None = None,
    ) -> CalibrationResult:
        """Live calibration for one scope — nothing is written."""
        rows = await self.resolved_predictions(tenant_id, window_days, end=end)
        scope = domain or OVERALL
        if scope != OVERALL:
            rows = [r for r in rows if scope in r["domain_tags"]]
        return full_calibration(rows, domain=scope)

    # ── Writes ────────────────────────────────────────────────

    async def recompute(
        self, tenant_id: str, window_days: int = DEFAULT_WINDOW_DAYS
    ) -> dict[str, Any]:
        """Write today's snapshots (overall + each domain with enough data).

        Returns a summary: {resolved, written: [domains], findings}.
        """
        rows = await self.resolved_predictions(tenant_id, window_days)
        scopes: dict[str, list[dict[str, Any]]] = {OVERALL: rows}
        for row in rows:
            for tag in row["domain_tags"]:
                if tag and tag != OVERALL:
                    scopes.setdefault(tag, []).append(row)

        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        written: list[str] = []
        findings = 0
        for scope, scope_rows in scopes.items():
            result = full_calibration(scope_rows, domain=scope)
            if not result.sufficient_data:
                continue
            await self.session.execute(
                delete(CalibrationSnapshot).where(
                    CalibrationSnapshot.tenant_id == tenant_id,
                    CalibrationSnapshot.domain == scope,
                    CalibrationSnapshot.window_days == window_days,
                    CalibrationSnapshot.computed_at >= day_start,
                )
            )
            self.session.add(
                CalibrationSnapshot(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    domain=scope,
                    window_days=window_days,
                    resolved_count=result.resolved_count,
                    ambiguous_count=result.ambiguous_count,
                    brier_score=result.brier_score,
                    buckets=[asdict(b) for b in result.buckets],
                    estimate_multiplier=result.estimate_multiplier,
                    bias_findings=result.bias_findings,
                    computed_at=now,
                )
            )
            written.append(scope)
            findings += len(result.bias_findings)
        await self.session.flush()

        if written and self.event_bus:
            await self.event_bus.emit(
                EventType.CALIBRATION_UPDATED,
                {"tenant_id": tenant_id, "domains": written, "window_days": window_days},
            )
        logger.info(
            "Calibration for %s: %d resolved in %dd, snapshots=%s",
            tenant_id,
            len(rows),
            window_days,
            written or "none (insufficient data)",
        )
        return {"resolved": len(rows), "written": written, "findings": findings}

    # ── API view ──────────────────────────────────────────────

    async def report(
        self,
        tenant_id: str,
        domain: str | None = None,
        window_days: int = DEFAULT_WINDOW_DAYS,
    ) -> dict[str, Any]:
        """Current calibration for the dashboard/API, computed live.

        Below MIN_RESOLVED_FOR_CALIBRATION it reports progress instead of a
        curve. ``trend`` compares against the preceding window of the same
        length, and appears only when that window also had enough data.
        """
        scope = domain or OVERALL
        now = datetime.now(UTC)
        current = await self.compute(tenant_id, scope, window_days, end=now)
        previous = await self.compute(
            tenant_id, scope, window_days, end=now - timedelta(days=window_days)
        )
        decided = current.resolved_count + current.ambiguous_count
        report: dict[str, Any] = {
            "status": "ok" if current.sufficient_data else "insufficient_data",
            "domain": scope,
            "window_days": window_days,
            "resolved_count": current.resolved_count,
            "ambiguous_count": current.ambiguous_count,
            "pending_count": await self.pending_count(tenant_id),
            "required": MIN_RESOLVED_FOR_CALIBRATION,
            "unresolved_rate": (round(current.ambiguous_count / decided, 3) if decided else None),
            "brier_score": current.brier_score,
            "buckets": [asdict(b) for b in current.buckets],
            "estimate_multiplier": current.estimate_multiplier,
            "bias_findings": current.bias_findings,
            "trend": None,
        }
        if current.brier_score is not None and previous.brier_score is not None:
            prev = previous.brier_score
            report["trend"] = {
                "previous_brier": prev,
                # Lower Brier is better, so a negative delta is an improvement.
                "delta_pct": (
                    round((current.brier_score - prev) / prev * 100, 1) if prev else None
                ),
            }
        return report
