"""Metamemory tracker — the system's knowledge of its own knowledge gaps.

Records topics the system has been asked about but couldn't answer,
tracks repeat queries, suggests proactive learning when gaps persist,
and assesses confidence in query results.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.models.db import KnowledgeGap


def _utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)


# ── Confidence thresholds ─────────────────────────────────────────────────
_HIGH_THRESHOLD = 0.7
_PARTIAL_THRESHOLD = 0.3
_GAP_TEACH_THRESHOLD = 3


class MetamemoryTracker:
    """Tracks knowledge gaps and assesses retrieval confidence.

    When the system fails a query (zero results or low confidence),
    the gap is recorded. Repeated failures for the same topic trigger
    a 'teach me' prompt, nudging the user to provide the information.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def track_query(
        self,
        query: str,
        results_count: int,
        max_confidence: float,
        embedding: list[float] | None = None,
    ) -> None:
        """Record a query outcome, creating or updating a knowledge gap if needed.

        A gap is recorded when results_count == 0 **or** max_confidence < 0.3.

        Args:
            query: The original query text.
            results_count: Number of memory results returned.
            max_confidence: Highest similarity/confidence score among results.
            embedding: Optional query embedding for future semantic gap matching.
        """
        if results_count > 0 and max_confidence >= _PARTIAL_THRESHOLD:
            return  # query was answered — no gap

        topic = self._normalise_topic(query)
        now = _utcnow()

        async with self._session_factory() as session:
            # Check for existing unresolved gap on the same topic
            existing = await self._find_existing_gap(session, topic)

            if existing is not None:
                stmt = (
                    update(KnowledgeGap)
                    .where(KnowledgeGap.id == existing.id)
                    .values(
                        query_count=KnowledgeGap.query_count + 1,
                        last_asked=now,
                    )
                )
                await session.execute(stmt)
            else:
                gap = KnowledgeGap(
                    topic=topic,
                    query_count=1,
                    first_asked=now,
                    last_asked=now,
                    resolved=False,
                    embedding=embedding,
                )
                session.add(gap)

            await session.commit()

    async def get_gaps(
        self,
        min_query_count: int = 1,
        limit: int = 20,
    ) -> list[KnowledgeGap]:
        """List unresolved knowledge gaps ordered by query_count descending.

        Args:
            min_query_count: Only return gaps asked at least this many times.
            limit: Maximum number of gaps to return.

        Returns:
            List of KnowledgeGap records.
        """
        stmt = (
            select(KnowledgeGap)
            .where(
                KnowledgeGap.resolved == False,  # noqa: E712
                KnowledgeGap.query_count >= min_query_count,
            )
            .order_by(KnowledgeGap.query_count.desc())
            .limit(limit)
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def resolve_gap(self, gap_id: str, memory_id: str) -> None:
        """Mark a knowledge gap as resolved by a specific memory.

        Args:
            gap_id: UUID string of the gap to resolve.
            memory_id: UUID string of the memory that fills the gap.

        Raises:
            ValueError: If the gap does not exist.
        """
        async with self._session_factory() as session:
            stmt = (
                update(KnowledgeGap)
                .where(KnowledgeGap.id == uuid.UUID(gap_id))
                .values(
                    resolved=True,
                    resolved_by=uuid.UUID(memory_id),
                )
            )
            result = await session.execute(stmt)
            if result.rowcount == 0:
                raise ValueError(f"KnowledgeGap {gap_id} not found")
            await session.commit()

    async def check_teach_me(self, query: str) -> str | None:
        """Check if the user should be prompted to teach the system.

        If a gap with query_count >= 3 exists for this topic, returns
        a suggestion message. Otherwise returns None.

        Args:
            query: The query text to check.

        Returns:
            A suggestion string, or None.
        """
        topic = self._normalise_topic(query)

        async with self._session_factory() as session:
            existing = await self._find_existing_gap(session, topic)

        if existing is not None and existing.query_count >= _GAP_TEACH_THRESHOLD:
            return (
                f"You've asked about '{topic}' {existing.query_count} times. "
                f"Want to teach me?"
            )

        return None

    def assess_confidence(
        self,
        results: list[Any],
        query: str,
    ) -> tuple[str, str]:
        """Assess retrieval confidence and return a tier with optional caveat.

        Confidence is based on the maximum similarity score among results.
        Results are expected to have a ``confidence`` or ``score`` attribute,
        or be dicts with a 'confidence' or 'score' key.

        Args:
            results: List of retrieval results (objects or dicts).
            query: The original query (unused currently, reserved for future).

        Returns:
            Tuple of (confidence_tier, caveat_message).
            Tiers: 'high', 'partial', 'unknown'.
        """
        if not results:
            return ("unknown", "I don't have reliable information on this.")

        max_score = self._extract_max_score(results)

        if max_score >= _HIGH_THRESHOLD:
            return ("high", "")

        if max_score >= _PARTIAL_THRESHOLD:
            return ("partial", "Note: I have limited information on this topic.")

        return ("unknown", "I don't have reliable information on this.")

    # ── Private helpers ───────────────────────────────────────────────────

    async def _find_existing_gap(
        self,
        session: AsyncSession,
        topic: str,
    ) -> KnowledgeGap | None:
        """Find an existing unresolved gap matching the normalised topic.

        Uses case-insensitive exact match on the normalised topic string.
        """
        stmt = (
            select(KnowledgeGap)
            .where(
                KnowledgeGap.resolved == False,  # noqa: E712
                func.lower(KnowledgeGap.topic) == topic.lower(),
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _normalise_topic(query: str) -> str:
        """Normalise a query into a canonical topic string.

        Strips leading/trailing whitespace and common question words.
        """
        topic = query.strip()
        # Remove leading question words for cleaner topic matching
        for prefix in ("what is ", "what are ", "how to ", "how do i ", "where is "):
            if topic.lower().startswith(prefix):
                topic = topic[len(prefix):]
                break
        return topic.strip()

    @staticmethod
    def _extract_max_score(results: list[Any]) -> float:
        """Extract the highest confidence/score value from a results list."""
        scores: list[float] = []
        for r in results:
            if isinstance(r, dict):
                score = r.get("confidence") or r.get("score") or 0.0
            else:
                score = getattr(r, "confidence", None) or getattr(r, "score", 0.0)
            scores.append(float(score))
        return max(scores) if scores else 0.0
