"""Shadow Mode service — enrollment, would-have-done records, grading, graduation.

The pipeline consults :meth:`ShadowService.intercept` before an autonomous
execution; if the actor is shadowed it records a would-have-done via
:meth:`record_would_have_done` and skips execution. The user later grades runs;
grades feed the Era-8 trust calculator and drive graduation (``core/shadow``).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select

from life_graph.autonomy.models import ShadowEnrollment, ShadowRun, TrustScore
from life_graph.autonomy.trust.service import TrustScoreService
from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.core.shadow import ShadowGrade, should_graduate
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


@dataclass
class ShadowDecision:
    """Result of an intercept: whether to shadow, and the enrollment context."""

    shadow: bool
    enrollment_id: str
    status: str  # shadow | graduated


@dataclass
class GradeResult:
    graded: bool
    graduated: bool
    status: str
    graded_good: int
    graded_bad: int


class ShadowService:
    """Owns shadow enrollment, would-have-done records, grading and graduation."""

    async def intercept(self, tenant_id: str, agent_id: str) -> ShadowDecision:
        """Decide whether this actor's autonomous action should be shadowed.

        First sighting of an actor: grandfather it (``graduated``) if it already
        has a trust track record (a TrustScore with successes), else enroll it in
        ``shadow``. The decision is persisted so it is stable thereafter.
        """
        if not settings.shadow_mode_enabled:
            return ShadowDecision(shadow=False, enrollment_id="", status="disabled")

        async with async_session() as session:
            enrollment = await self._get_enrollment(session, tenant_id, agent_id)
            if enrollment is None:
                grandfather = await self._has_prior_success(session, tenant_id, agent_id)
                enrollment = ShadowEnrollment(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    status="graduated" if grandfather else "shadow",
                    graduated_at=datetime.now(UTC) if grandfather else None,
                )
                session.add(enrollment)
                await session.commit()
                await session.refresh(enrollment)

            return ShadowDecision(
                shadow=(enrollment.status == "shadow"),
                enrollment_id=enrollment.id,
                status=enrollment.status,
            )

    async def record_would_have_done(
        self,
        tenant_id: str,
        agent_id: str,
        enrollment_id: str,
        *,
        action_type: str,
        command: str,
        risk_level: str | None,
        project_id: str | None,
        would_have_routed: str,
        rationale: dict | None = None,
    ) -> str:
        """Persist a dry-run 'would-have-done' record. No execution happens."""
        run_id = str(uuid.uuid4())
        async with async_session() as session:
            session.add(ShadowRun(
                id=run_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                enrollment_id=enrollment_id,
                action_type=action_type,
                command=command,
                risk_level=risk_level,
                project_id=project_id,
                would_have_routed=would_have_routed,
                rationale=rationale or {},
            ))
            await session.commit()

        await event_bus.emit(
            EventType.SHADOW_RECORDED,
            {"run_id": run_id, "tenant_id": tenant_id, "agent_id": agent_id,
             "action_type": action_type},
            source="shadow",
        )
        return run_id

    async def grade(
        self, tenant_id: str, run_id: str, grade: ShadowGrade, graded_by: str = "user"
    ) -> GradeResult:
        """Grade a would-have-done run; update tallies, feed trust, check graduation.

        Trust is fed only on the FIRST grade of a run (re-grading adjusts the
        good/bad tallies but does not double-count trust).
        """
        async with async_session() as session:
            run = await session.get(ShadowRun, run_id)
            if run is None or run.tenant_id != tenant_id:
                raise ValueError(f"ShadowRun {run_id} not found")

            enrollment = await session.get(ShadowEnrollment, run.enrollment_id)
            if enrollment is None:
                raise ValueError("enrollment missing for shadow run")

            first_grade = run.grade is None
            # Adjust tallies for a re-grade.
            if run.grade == ShadowGrade.GOOD.value:
                enrollment.graded_good = max(0, enrollment.graded_good - 1)
            elif run.grade == ShadowGrade.BAD.value:
                enrollment.graded_bad = max(0, enrollment.graded_bad - 1)

            run.grade = grade.value
            run.graded_by = graded_by
            run.graded_at = datetime.now(UTC)
            if grade is ShadowGrade.GOOD:
                enrollment.graded_good += 1
            else:
                enrollment.graded_bad += 1

            # Feed the Era-8 trust calculator (only on first grade).
            if first_grade:
                trust = TrustScoreService(session)
                if grade is ShadowGrade.GOOD:
                    await trust.record_success(tenant_id, run.agent_id, run.action_type, run.project_id)
                else:
                    await trust.record_failure(tenant_id, run.agent_id, run.action_type, run.project_id)

            # Graduation check.
            graduated = False
            if enrollment.status == "shadow":
                days = (datetime.now(UTC) - enrollment.enrolled_at).total_seconds() / 86400
                if should_graduate(
                    days, enrollment.graded_good, enrollment.graded_bad,
                    min_days=settings.shadow_min_days,
                    min_samples=settings.shadow_min_samples,
                    good_rate_threshold=settings.shadow_good_rate,
                ):
                    enrollment.status = "graduated"
                    enrollment.graduated_at = datetime.now(UTC)
                    graduated = True

            await session.commit()
            result = GradeResult(
                graded=True, graduated=graduated, status=enrollment.status,
                graded_good=enrollment.graded_good, graded_bad=enrollment.graded_bad,
            )

        if graduated:
            await event_bus.emit(
                EventType.SHADOW_GRADUATED,
                {"tenant_id": tenant_id, "agent_id": run.agent_id,
                 "enrollment_id": run.enrollment_id},
                source="shadow",
            )
        return result

    async def list_runs(
        self, tenant_id: str, *, ungraded_only: bool = True, limit: int = 50
    ) -> list[ShadowRun]:
        async with async_session() as session:
            stmt = select(ShadowRun).where(ShadowRun.tenant_id == tenant_id)
            if ungraded_only:
                stmt = stmt.where(ShadowRun.grade.is_(None))
            stmt = stmt.order_by(ShadowRun.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_enrollments(self, tenant_id: str) -> list[ShadowEnrollment]:
        async with async_session() as session:
            result = await session.execute(
                select(ShadowEnrollment)
                .where(ShadowEnrollment.tenant_id == tenant_id)
                .order_by(ShadowEnrollment.enrolled_at.desc())
            )
            return list(result.scalars().all())

    # ── internals ─────────────────────────────────────────────

    @staticmethod
    async def _get_enrollment(session, tenant_id: str, agent_id: str) -> ShadowEnrollment | None:
        result = await session.execute(
            select(ShadowEnrollment).where(
                ShadowEnrollment.tenant_id == tenant_id,
                ShadowEnrollment.agent_id == agent_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _has_prior_success(session, tenant_id: str, agent_id: str) -> bool:
        """Proven actor = has a trust track record (any TrustScore with successes)."""
        result = await session.execute(
            select(func.coalesce(func.sum(TrustScore.total_successes), 0)).where(
                TrustScore.tenant_id == tenant_id,
                TrustScore.agent_id == agent_id,
            )
        )
        return (result.scalar_one() or 0) > 0


# ── Module-level singleton ─────────────────────────────────────────────
shadow_service = ShadowService()
