"""Exponential decay scoring for memory retention.

Implements a forgetting-curve model where memories decay over time
but are boosted by access frequency. Critical memories are exempt
from archival.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


class DecayCalculator:
    """Calculate decay scores for memories based on the forgetting curve.

    Formula::

        score = importance × (access_count ^ 0.3) × e^(-decay_rate × days_since_access)

    Usage::

        calc = DecayCalculator()
        score = calc.calculate(importance=0.8, access_count=5, days_since_access=30.0)
    """

    def calculate(
        self,
        importance: float,
        access_count: int,
        days_since_access: float,
        decay_rate: float = 0.1,
    ) -> float:
        """Compute the current decay score for a single memory.

        Args:
            importance: Base importance score ∈ [0.0, 1.0].
            access_count: Number of times the memory was accessed.
                Treated as minimum 1 to avoid zeroing out.
            days_since_access: Days elapsed since the last access.
            decay_rate: Exponential decay lambda (default 0.1).

        Returns:
            Decay-adjusted score (non-negative float).
        """
        safe_access = max(access_count, 1)
        frequency_boost = math.pow(safe_access, 0.3)
        time_decay = math.exp(-decay_rate * days_since_access)
        return importance * frequency_boost * time_decay

    def should_archive(
        self,
        score: float,
        importance_tier: str,
        threshold: float = 0.01,
    ) -> bool:
        """Determine whether a memory should be archived.

        Critical memories are never archived regardless of score.

        Args:
            score: Current decay score.
            importance_tier: The importance tier label.
            threshold: Score below which archival is considered.

        Returns:
            ``True`` if the memory should be archived.
        """
        if importance_tier == "critical":
            return False
        return score < threshold

    def batch_calculate(
        self,
        memories: list[dict[str, Any]],
    ) -> list[tuple[str, float, bool]]:
        """Calculate decay scores for a batch of memories.

        Each dict in *memories* must have the keys:
        ``id``, ``importance``, ``access_count``, ``last_accessed``,
        ``decay_rate``, ``importance_tier``.

        ``last_accessed`` may be a :class:`datetime` object or a float
        representing days-since-access directly.

        Args:
            memories: List of memory dicts.

        Returns:
            List of ``(id, decay_score, should_archive)`` tuples, in the
            same order as the input.
        """
        now = datetime.now(timezone.utc)
        results: list[tuple[str, float, bool]] = []

        for mem in memories:
            days = self._resolve_days_since(mem["last_accessed"], now)
            score = self.calculate(
                importance=mem["importance"],
                access_count=mem["access_count"],
                days_since_access=days,
                decay_rate=mem.get("decay_rate", 0.1),
            )
            archive = self.should_archive(
                score=score,
                importance_tier=mem["importance_tier"],
            )
            results.append((mem["id"], score, archive))

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_days_since(
        last_accessed: datetime | float,
        now: datetime,
    ) -> float:
        """Convert *last_accessed* to days-since-access.

        Accepts either a ``datetime`` (UTC-aware or naive-treated-as-UTC)
        or a pre-computed float of days.
        """
        if isinstance(last_accessed, (int, float)):
            return float(last_accessed)
        if isinstance(last_accessed, datetime):
            if last_accessed.tzinfo is None:
                last_accessed = last_accessed.replace(tzinfo=timezone.utc)
            delta = now - last_accessed
            return max(delta.total_seconds() / 86400.0, 0.0)
        raise TypeError(
            f"last_accessed must be datetime or float, got {type(last_accessed).__name__}"
        )
