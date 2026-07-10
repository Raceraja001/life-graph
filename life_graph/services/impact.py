"""Impact scoring — RL-lite feedback loop for memory recall.

Tracks whether recalled memories led to successful outcomes
and adjusts impact_score accordingly. Memories that consistently
appear in successful sessions get boosted; those in failed sessions
get penalized (asymmetrically — boost > penalty).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from life_graph.config import settings
from life_graph.models.db import Memory, MemorySession
from life_graph.storage.database import async_session
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


class ImpactScorer:
    """Updates memory impact scores based on session outcomes.

    The scoring is asymmetric: a successful outcome boosts
    impact_score by ``settings.impact_boost_on_success`` (default 0.1),
    while a failure penalizes by ``settings.impact_penalty_on_failure``
    (default 0.05). This prevents a single bad session from
    destroying a memory's reputation.
    """

    async def record_outcome(
        self,
        session_id: UUID,
        outcome: str,
    ) -> dict[str, Any]:
        """Record a session outcome and update impact scores for recalled memories.

        Args:
            session_id: The session that just ended.
            outcome: One of 'success', 'failure', or 'neutral'.

        Returns:
            A dict with 'memories_updated' count and 'outcome' applied.
        """
        if outcome not in ("success", "failure", "neutral"):
            logger.warning("Invalid outcome '%s' — treating as neutral", outcome)
            outcome = "neutral"

        async with async_session() as db:
            # Find all memories recalled (not created) in this session
            stmt = (
                select(MemorySession.memory_id)
                .where(
                    MemorySession.session_id == session_id,
                    MemorySession.role == "recalled",
                )
            )
            result = await db.execute(stmt)
            recalled_ids = [row[0] for row in result.all()]

            if not recalled_ids:
                logger.info(
                    "Session %s: no recalled memories to score (outcome=%s)",
                    session_id, outcome,
                )
                return {"memories_updated": 0, "outcome": outcome}

            # Compute deltas based on outcome
            boost = settings.impact_boost_on_success
            penalty = settings.impact_penalty_on_failure

            if outcome == "success":
                score_delta = boost
                confidence_delta = 0.05
            elif outcome == "failure":
                score_delta = -penalty
                confidence_delta = 0.02
            else:  # neutral
                score_delta = 0.0
                confidence_delta = 0.01

            # Batch update impact scores
            if score_delta != 0.0 or confidence_delta != 0.0:
                # Use raw SQL for efficient batch update with clamping
                from sqlalchemy import case, literal
                from sqlalchemy.sql.expression import func as sql_func

                # Clamp impact_score between 0.0 and 1.0
                new_score = case(
                    (Memory.impact_score + score_delta > 1.0, literal(1.0)),
                    (Memory.impact_score + score_delta < 0.0, literal(0.0)),
                    else_=Memory.impact_score + score_delta,
                )
                new_confidence = case(
                    (Memory.impact_confidence + confidence_delta > 1.0, literal(1.0)),
                    else_=Memory.impact_confidence + confidence_delta,
                )

                update_stmt = (
                    update(Memory)
                    .where(Memory.id.in_(recalled_ids))
                    .values(
                        impact_score=new_score,
                        impact_confidence=new_confidence,
                    )
                )
                await db.execute(update_stmt)
                await db.commit()

            logger.info(
                "Session %s: updated %d recalled memories "
                "(outcome=%s, score_delta=%+.2f)",
                session_id, len(recalled_ids), outcome, score_delta,
            )
            return {
                "memories_updated": len(recalled_ids),
                "outcome": outcome,
            }
