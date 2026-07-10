"""Trust score calculator — Bayesian trust with decay and streak bonuses.

Calculates trust updates based on success/failure history using
a Bayesian prior, streak bonuses, recency bonuses, and time-based decay.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.autonomy.models import TrustScore

logger = logging.getLogger(__name__)


@dataclass
class TrustUpdate:
    """Calculated trust score update values."""

    new_score: float
    total_successes: int
    total_failures: int
    consecutive_successes: int
    consecutive_failures: int
    peak_score: float


class TrustCalculator:
    """Bayesian trust calculator with streak bonuses and decay.

    Trust formula on success:
        base = S / (S + F + PRIOR_WEIGHT)
        streak_bonus = min(0.1, consecutive * 0.005)
        recency_bonus = 0.02 if last_action < 7 days
        score = min(MAX_SCORE, base + streak_bonus + recency_bonus)

    Trust formula on failure:
        score *= (1 - failure_penalty)
        additional = 0.1 * (consecutive_failures - 1) if > 1
        score = max(0.0, score - additional)

    Decay:
        score *= (1 - decay_rate) ^ weeks_since_last_action
    """

    PRIOR_WEIGHT: float = 5.0
    MAX_SCORE: float = 0.99

    def calculate_success(self, current: TrustScore) -> TrustUpdate:
        """Calculate new trust values after a successful action."""
        s = current.total_successes + 1
        f = current.total_failures
        base = s / (s + f + self.PRIOR_WEIGHT)

        consecutive = current.consecutive_successes + 1
        streak_bonus = min(0.1, consecutive * 0.005)

        recency_bonus = 0.0
        if current.last_action_at is not None:
            days_since = (
                datetime.now(timezone.utc) - current.last_action_at
            ).total_seconds() / 86400
            if days_since < 7:
                recency_bonus = 0.02

        new_score = min(self.MAX_SCORE, base + streak_bonus + recency_bonus)
        new_peak = max(float(current.peak_score), new_score)

        return TrustUpdate(
            new_score=new_score,
            total_successes=s,
            total_failures=f,
            consecutive_successes=consecutive,
            consecutive_failures=0,
            peak_score=new_peak,
        )

    def calculate_failure(self, current: TrustScore) -> TrustUpdate:
        """Calculate new trust values after a failed action."""
        s = current.total_successes
        f = current.total_failures + 1

        penalty = float(current.failure_penalty)
        current_score = float(current.score)
        new_score = current_score * (1 - penalty)

        consecutive = current.consecutive_failures + 1
        if consecutive > 1:
            additional_penalty = 0.1 * (consecutive - 1)
            new_score = max(0.0, new_score - additional_penalty)

        new_score = max(0.0, new_score)

        return TrustUpdate(
            new_score=new_score,
            total_successes=s,
            total_failures=f,
            consecutive_successes=0,
            consecutive_failures=consecutive,
            peak_score=float(current.peak_score),
        )

    @staticmethod
    def apply_decay(
        score: float,
        last_action_at: datetime | None,
        decay_rate: float,
    ) -> float:
        """Apply time-based decay to a trust score.

        No decay within the first week of inactivity.
        After that, score *= (1 - decay_rate) ^ weeks.
        """
        if last_action_at is None:
            return score

        weeks = (
            datetime.now(timezone.utc) - last_action_at
        ).total_seconds() / (7 * 86400)

        if weeks < 1:
            return score

        decayed = score * ((1 - decay_rate) ** weeks)
        return max(0.0, decayed)

    async def get_effective_trust(
        self,
        session: AsyncSession,
        tenant_id: str,
        agent_id: str,
        action_type: str,
        project_id: str | None = None,
    ) -> float:
        """Get the minimum trust score across all applicable scopes.

        Considers exact action_type match, wildcard '*', and
        project-specific scores. Applies decay and manual overrides.
        """
        stmt = select(TrustScore).where(
            TrustScore.tenant_id == tenant_id,
            TrustScore.agent_id == agent_id,
        )
        result = await session.execute(stmt)
        scores = result.scalars().all()

        if not scores:
            return 0.0

        effective_scores: list[float] = []

        for ts in scores:
            is_relevant = (
                ts.action_type == action_type
                or ts.action_type == "*"
                or (project_id is not None and ts.project_id == project_id)
            )
            if not is_relevant:
                continue

            if ts.manual_override is not None:
                effective_scores.append(float(ts.manual_override))
            else:
                decayed = self.apply_decay(
                    float(ts.score),
                    ts.last_action_at,
                    float(ts.decay_rate),
                )
                effective_scores.append(decayed)

        return min(effective_scores) if effective_scores else 0.0
