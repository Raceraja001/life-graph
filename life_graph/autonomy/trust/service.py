"""Trust score service — recording, querying, overriding, and decaying trust scores."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.autonomy.models import TrustScore
from life_graph.autonomy.trust.calculator import TrustCalculator
from life_graph.models.db import _utcnow

logger = logging.getLogger(__name__)


class TrustScoreService:
    """Manages trust score lifecycle — record, query, override, decay."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._calculator = TrustCalculator()

    async def get_scores(
        self,
        tenant_id: str,
        agent_id: str | None = None,
        project_id: str | None = None,
        action_type: str | None = None,
    ) -> list[TrustScore]:
        """List trust scores with optional filters."""
        stmt = select(TrustScore).where(TrustScore.tenant_id == tenant_id)

        if agent_id:
            stmt = stmt.where(TrustScore.agent_id == agent_id)
        if project_id:
            stmt = stmt.where(TrustScore.project_id == project_id)
        if action_type:
            stmt = stmt.where(TrustScore.action_type == action_type)

        stmt = stmt.order_by(TrustScore.score.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create(
        self,
        tenant_id: str,
        agent_id: str,
        action_type: str,
        project_id: str | None = None,
    ) -> TrustScore:
        """Get an existing trust score or create one with defaults."""
        stmt = select(TrustScore).where(
            TrustScore.tenant_id == tenant_id,
            TrustScore.agent_id == agent_id,
            TrustScore.action_type == action_type,
        )
        if project_id is not None:
            stmt = stmt.where(TrustScore.project_id == project_id)
        else:
            stmt = stmt.where(TrustScore.project_id.is_(None))

        result = await self._session.execute(stmt)
        score = result.scalar_one_or_none()

        if score is not None:
            return score

        score = TrustScore(
            tenant_id=tenant_id,
            agent_id=agent_id,
            action_type=action_type,
            project_id=project_id,
        )
        self._session.add(score)
        await self._session.flush()
        logger.info(
            "Created trust score: agent=%s, action=%s, project=%s",
            agent_id, action_type, project_id,
        )
        return score

    async def record_success(
        self,
        tenant_id: str,
        agent_id: str,
        action_type: str,
        project_id: str | None = None,
    ) -> TrustScore:
        """Record a successful action and update trust score."""
        ts = await self.get_or_create(tenant_id, agent_id, action_type, project_id)
        update = self._calculator.calculate_success(ts)

        now = _utcnow()
        ts.score = Decimal(str(round(update.new_score, 3)))
        ts.total_successes = update.total_successes
        ts.consecutive_successes = update.consecutive_successes
        ts.consecutive_failures = 0
        ts.peak_score = Decimal(str(round(update.peak_score, 3)))
        ts.last_action_at = now
        ts.last_success_at = now
        ts.updated_at = now

        await self._session.flush()
        logger.info(
            "Recorded success: agent=%s, action=%s, new_score=%.3f",
            agent_id, action_type, update.new_score,
        )
        return ts

    async def record_failure(
        self,
        tenant_id: str,
        agent_id: str,
        action_type: str,
        project_id: str | None = None,
    ) -> TrustScore:
        """Record a failed action and update trust score."""
        ts = await self.get_or_create(tenant_id, agent_id, action_type, project_id)
        update = self._calculator.calculate_failure(ts)

        now = _utcnow()
        ts.score = Decimal(str(round(update.new_score, 3)))
        ts.total_failures = update.total_failures
        ts.consecutive_failures = update.consecutive_failures
        ts.consecutive_successes = 0
        ts.last_action_at = now
        ts.last_failure_at = now
        ts.updated_at = now

        await self._session.flush()
        logger.info(
            "Recorded failure: agent=%s, action=%s, new_score=%.3f",
            agent_id, action_type, update.new_score,
        )
        return ts

    async def override(
        self,
        tenant_id: str,
        agent_id: str,
        action_type: str,
        project_id: str | None = None,
        score: float | None = None,
        reason: str | None = None,
        by: str | None = None,
    ) -> TrustScore:
        """Manually override a trust score."""
        ts = await self.get_or_create(tenant_id, agent_id, action_type, project_id)

        now = _utcnow()
        ts.manual_override = Decimal(str(score)) if score is not None else None
        ts.override_reason = reason
        ts.override_by = by
        ts.override_at = now
        ts.updated_at = now

        await self._session.flush()
        logger.info(
            "Trust override: agent=%s, action=%s, override=%.3f, by=%s",
            agent_id, action_type, score or 0.0, by,
        )
        return ts

    async def decay_all(self, tenant_id: str) -> int:
        """Apply time-based decay to all stale trust scores for a tenant.

        Only decays scores that have a last_action_at and no manual override.
        Returns the number of scores that were actually decayed.
        """
        stmt = select(TrustScore).where(
            TrustScore.tenant_id == tenant_id,
            TrustScore.last_action_at.isnot(None),
            TrustScore.manual_override.is_(None),
        )
        result = await self._session.execute(stmt)
        scores = result.scalars().all()

        decayed_count = 0
        for ts in scores:
            current = float(ts.score)
            new_score = TrustCalculator.apply_decay(
                current,
                ts.last_action_at,
                float(ts.decay_rate),
            )
            if abs(new_score - current) > 0.001:
                ts.score = Decimal(str(round(new_score, 3)))
                ts.updated_at = _utcnow()
                decayed_count += 1

        if decayed_count:
            await self._session.flush()

        logger.info(
            "Decayed %d/%d trust scores for tenant=%s",
            decayed_count, len(scores), tenant_id,
        )
        return decayed_count
