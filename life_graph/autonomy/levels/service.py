"""Autonomy level management service.

Manages per-project autonomy levels (L0–L3) with:
- Automatic promotion based on success thresholds
- Demotion on failures
- Manual override
- Counter tracking for promotion decisions

Levels:
    L0: Ask Everything — all actions require approval
    L1: Safe Auto — safe actions auto-execute, rest need approval
    L2: Notify Before — moderate actions notify then auto-approve
    L3: Full Auto — all actions auto-execute (except dangerous)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update

logger = logging.getLogger(__name__)


LEVEL_NAMES = {
    0: "Ask Everything",
    1: "Safe Auto",
    2: "Notify Before",
    3: "Full Auto",
}

# Promotion thresholds: safe_count needed to promote to next level
PROMOTION_THRESHOLDS = {
    0: {"safe_count": 10, "failure_max": 0},   # L0 → L1: 10 safe, 0 failures
    1: {"safe_count": 25, "failure_max": 2},   # L1 → L2: 25 safe, ≤2 failures
    2: {"safe_count": 50, "failure_max": 3},   # L2 → L3: 50 safe, ≤3 failures
}


@dataclass
class PromotionCheck:
    """Result of a promotion eligibility check."""

    eligible: bool
    current_level: int
    next_level: int | None
    reason: str
    safe_count: int
    failure_count: int


class AutonomyLevelService:
    """Manages per-project autonomy levels."""

    def __init__(self, session_factory, audit_service=None):
        self._session_factory = session_factory
        self._audit_service = audit_service

    async def get_level(self, tenant_id: str, project_id: str):
        """Get or create the autonomy level record for a project.

        Defaults to L0 (Ask Everything) for new projects.
        """
        from life_graph.autonomy.models import AutonomyLevel

        async with self._session_factory() as session:
            result = await session.execute(
                select(AutonomyLevel).where(
                    AutonomyLevel.tenant_id == tenant_id,
                    AutonomyLevel.project_id == project_id,
                )
            )
            level = result.scalar_one_or_none()

            if not level:
                # Real columns default level="L0" and all counters to 0.
                level = AutonomyLevel(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    project_id=project_id,
                )
                session.add(level)
                await session.commit()
                await session.refresh(level)

        return level

    async def check_promotion(
        self, tenant_id: str, project_id: str,
    ) -> PromotionCheck:
        """Check if a project is eligible for level promotion."""
        level = await self.get_level(tenant_id, project_id)

        if level.current_level >= 3:
            return PromotionCheck(
                eligible=False,
                current_level=level.current_level,
                next_level=None,
                reason="Already at maximum level (L3)",
                safe_count=level.safe_count,
                failure_count=level.failure_count,
            )

        thresholds = PROMOTION_THRESHOLDS[level.current_level]
        safe_ok = level.safe_count >= thresholds["safe_count"]
        failure_ok = level.failure_count <= thresholds["failure_max"]

        eligible = safe_ok and failure_ok
        next_level = level.current_level + 1 if eligible else None

        if eligible:
            reason = (
                f"Eligible: {level.safe_count}/{thresholds['safe_count']} safe actions, "
                f"{level.failure_count}/{thresholds['failure_max']} failures"
            )
        else:
            parts = []
            if not safe_ok:
                parts.append(
                    f"Need {thresholds['safe_count'] - level.safe_count} more safe actions"
                )
            if not failure_ok:
                parts.append(
                    f"Too many failures: {level.failure_count}/{thresholds['failure_max']}"
                )
            reason = "; ".join(parts)

        return PromotionCheck(
            eligible=eligible,
            current_level=level.current_level,
            next_level=next_level,
            reason=reason,
            safe_count=level.safe_count,
            failure_count=level.failure_count,
        )

    async def promote(self, tenant_id: str, project_id: str) -> int:
        """Promote the project one level (if eligible). Returns new level."""
        from life_graph.autonomy.models import AutonomyLevel

        check = await self.check_promotion(tenant_id, project_id)
        if not check.eligible:
            raise ValueError(f"Not eligible for promotion: {check.reason}")

        new_level = check.current_level + 1
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            await session.execute(
                update(AutonomyLevel)
                .where(
                    AutonomyLevel.tenant_id == tenant_id,
                    AutonomyLevel.project_id == project_id,
                )
                .values(
                    level=f"L{new_level}",
                    level_description=LEVEL_NAMES.get(new_level, ""),
                    safe_successes=0,  # Reset counters after promotion
                    total_failures=0,
                    last_promotion_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        if self._audit_service:
            await self._audit_service.log_autonomy_change(
                tenant_id=tenant_id,
                project_id=project_id,
                old_level=check.current_level,
                new_level=new_level,
                reason="Automatic promotion — thresholds met",
            )

        logger.info(
            "Promoted project %s from L%d to L%d",
            project_id, check.current_level, new_level,
        )

        return new_level

    async def demote(self, tenant_id: str, project_id: str, reason: str) -> int:
        """Demote the project one level. Returns new level."""
        from life_graph.autonomy.models import AutonomyLevel

        level = await self.get_level(tenant_id, project_id)
        if level.current_level <= 0:
            raise ValueError("Already at minimum level (L0)")

        new_level = level.current_level - 1
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            await session.execute(
                update(AutonomyLevel)
                .where(
                    AutonomyLevel.tenant_id == tenant_id,
                    AutonomyLevel.project_id == project_id,
                )
                .values(
                    level=f"L{new_level}",
                    level_description=LEVEL_NAMES.get(new_level, ""),
                    total_failures=0,
                    demotion_count=(level.demotion_count or 0) + 1,
                    last_demotion_at=now,
                    last_failure_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        if self._audit_service:
            await self._audit_service.log_autonomy_change(
                tenant_id=tenant_id,
                project_id=project_id,
                old_level=level.current_level,
                new_level=new_level,
                reason=reason,
            )

        logger.info(
            "Demoted project %s from L%d to L%d: %s",
            project_id, level.current_level, new_level, reason,
        )

        return new_level

    async def set_manual(
        self,
        tenant_id: str,
        project_id: str,
        level: int,
        reason: str,
        by: str,
    ) -> int:
        """Manually set the autonomy level. Returns the new level."""
        from life_graph.autonomy.models import AutonomyLevel

        if level < 0 or level > 3:
            raise ValueError(f"Invalid level: {level}. Must be 0-3.")

        current = await self.get_level(tenant_id, project_id)
        old_level = current.current_level
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            await session.execute(
                update(AutonomyLevel)
                .where(
                    AutonomyLevel.tenant_id == tenant_id,
                    AutonomyLevel.project_id == project_id,
                )
                .values(
                    level=f"L{level}",
                    level_description=LEVEL_NAMES.get(level, ""),
                    manual_level=f"L{level}",
                    manual_set_by=by,
                    manual_reason=reason,
                    manual_set_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        if self._audit_service:
            await self._audit_service.log_autonomy_change(
                tenant_id=tenant_id,
                project_id=project_id,
                old_level=old_level,
                new_level=level,
                reason=f"Manual override by {by}: {reason}",
                changed_by=by,
            )

        logger.info(
            "Manual level set for project %s: L%d → L%d by %s (%s)",
            project_id, old_level, level, by, reason,
        )

        return level

    async def record_action(
        self,
        tenant_id: str,
        project_id: str,
        risk_level: str,
        success: bool,
    ) -> None:
        """Record an action outcome for promotion tracking."""
        from life_graph.autonomy.models import AutonomyLevel

        level = await self.get_level(tenant_id, project_id)
        now = datetime.now(timezone.utc)

        updates = {"updated_at": now, "last_audit_at": now}

        if success:
            updates["total_successes"] = (level.total_successes or 0) + 1
            if risk_level == "safe":
                updates["safe_successes"] = level.safe_count + 1
            elif risk_level == "moderate":
                updates["moderate_successes"] = level.moderate_count + 1
        else:
            updates["total_failures"] = level.failure_count + 1
            updates["last_failure_at"] = now

        updates["total_auto_actions"] = (level.total_auto_actions or 0) + 1

        async with self._session_factory() as session:
            await session.execute(
                update(AutonomyLevel)
                .where(
                    AutonomyLevel.tenant_id == tenant_id,
                    AutonomyLevel.project_id == project_id,
                )
                .values(**updates)
            )
            await session.commit()

        # Auto-check promotion after recording
        if success:
            check = await self.check_promotion(tenant_id, project_id)
            if check.eligible:
                try:
                    await self.promote(tenant_id, project_id)
                except ValueError:
                    pass  # Race condition — already promoted
