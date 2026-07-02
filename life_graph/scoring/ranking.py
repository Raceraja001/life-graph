"""Multi-signal retrieval ranking for memory recall.

Combines semantic similarity, contextual relevance, importance,
recency, frequency, and trust into a single ranking score.
Includes diversity-aware reranking to avoid topic clustering.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Weight configuration
# ---------------------------------------------------------------------------

_WEIGHT_SEMANTIC: float = 0.25
_WEIGHT_CONTEXT: float = 0.25
_WEIGHT_IMPORTANCE: float = 0.20
_WEIGHT_RECENCY: float = 0.15
_WEIGHT_FREQUENCY: float = 0.10
_WEIGHT_TRUST: float = 0.05


# ---------------------------------------------------------------------------
# Context similarity helpers
# ---------------------------------------------------------------------------

def _set_overlap_ratio(a: set[str], b: set[str]) -> float:
    """Compute overlap ratio between two sets.

    Returns 0.0 when both sets are empty.
    """
    if not a and not b:
        return 0.0
    max_size = max(len(a), len(b))
    if max_size == 0:
        return 0.0
    return len(a & b) / max_size


def context_similarity(
    candidate: dict[str, Any],
    current_context: dict[str, Any],
) -> float:
    """Compute context-match score between a candidate memory and current session.

    Scoring breakdown:
        - Project match: +0.3
        - Module match:  +0.2
        - Tools overlap: +0.2 × (overlap / max_tools)
        - Files overlap: +0.3 × (overlap / max_files)

    Args:
        candidate: Memory dict with optional keys ``project``, ``module``,
            ``tools``, ``files``.
        current_context: Current session context with the same optional keys.

    Returns:
        Context score ∈ [0.0, 1.0].
    """
    score = 0.0

    # Project match
    cand_project = candidate.get("project", "")
    ctx_project = current_context.get("project", "")
    if cand_project and ctx_project and cand_project == ctx_project:
        score += 0.3

    # Module match
    cand_module = candidate.get("module", "")
    ctx_module = current_context.get("module", "")
    if cand_module and ctx_module and cand_module == ctx_module:
        score += 0.2

    # Tools overlap
    cand_tools = set(candidate.get("tools", []))
    ctx_tools = set(current_context.get("tools", []))
    if cand_tools or ctx_tools:
        score += 0.2 * _set_overlap_ratio(cand_tools, ctx_tools)

    # Files overlap
    cand_files = set(candidate.get("files", []))
    ctx_files = set(current_context.get("files", []))
    if cand_files or ctx_files:
        score += 0.3 * _set_overlap_ratio(cand_files, ctx_files)

    return score


# ---------------------------------------------------------------------------
# Sub-score computations
# ---------------------------------------------------------------------------

def _recency_score(days_since_access: float) -> float:
    """Exponential recency decay: e^(-0.02 × days)."""
    return math.exp(-0.02 * max(days_since_access, 0.0))


def _frequency_score(access_count: int) -> float:
    """Saturating frequency score: access_count^0.3 / 10."""
    return min(math.pow(max(access_count, 1), 0.3) / 10.0, 1.0)


def _resolve_days_since_access(candidate: dict[str, Any]) -> float:
    """Extract days-since-access from candidate dict.

    Supports ``days_since_access`` as a float or ``last_accessed``
    as a datetime.
    """
    if "days_since_access" in candidate:
        return float(candidate["days_since_access"])
    last = candidate.get("last_accessed")
    if isinstance(last, datetime):
        now = datetime.now(timezone.utc)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return max((now - last).total_seconds() / 86400.0, 0.0)
    return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class RecallRanker:
    """Multi-signal ranker for memory retrieval results.

    Blends six signals into a final score and applies diversity-aware
    reranking to avoid surfacing clusters of the same topic.

    Usage::

        ranker = RecallRanker()
        ranked = ranker.rank(candidates, current_context={"project": "life_graph"})
        final = ranker.rerank(ranked, max_results=5)
    """

    def rank(
        self,
        candidates: list[dict[str, Any]],
        current_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Score and sort candidates by multi-signal relevance.

        Each candidate dict should contain:
            - ``semantic_score`` (float): Pre-computed vector similarity.
            - ``importance`` (float): Importance score.
            - ``trust_score`` (float): Trust/reliability score.
            - ``access_count`` (int): Number of accesses.
            - ``days_since_access`` or ``last_accessed``: Recency info.
            - ``project``, ``module``, ``tools``, ``files``: Context keys (optional).

        Args:
            candidates: Raw retrieval results.
            current_context: Current session context for context scoring.

        Returns:
            Candidates sorted descending by ``final_score``, each dict
            augmented with ``final_score`` and ``_sub_scores``.
        """
        ctx = current_context or {}
        scored: list[dict[str, Any]] = []

        for cand in candidates:
            sem = float(cand.get("semantic_score", 0.0))
            ctx_score = context_similarity(cand, ctx) if ctx else 0.0
            imp = float(cand.get("importance", 0.5))
            rec = _recency_score(_resolve_days_since_access(cand))
            freq = _frequency_score(int(cand.get("access_count", 1)))
            trust = float(cand.get("trust_score", 0.5))

            final = (
                _WEIGHT_SEMANTIC * sem
                + _WEIGHT_CONTEXT * ctx_score
                + _WEIGHT_IMPORTANCE * imp
                + _WEIGHT_RECENCY * rec
                + _WEIGHT_FREQUENCY * freq
                + _WEIGHT_TRUST * trust
            )

            enriched = {**cand}
            enriched["final_score"] = round(final, 6)
            enriched["_sub_scores"] = {
                "semantic": round(sem, 4),
                "context": round(ctx_score, 4),
                "importance": round(imp, 4),
                "recency": round(rec, 4),
                "frequency": round(freq, 4),
                "trust": round(trust, 4),
            }
            scored.append(enriched)

        scored.sort(key=lambda c: c["final_score"], reverse=True)
        return scored

    def rerank(
        self,
        ranked: list[dict[str, Any]],
        max_results: int = 5,
        max_per_topic: int = 2,
        cooldown_days: float = 7.0,
    ) -> list[dict[str, Any]]:
        """Apply diversity-aware reranking to scored candidates.

        Rules:
            1. **Topic cap**: At most *max_per_topic* memories per topic
               cluster (grouped by first tag).
            2. **Type diversity**: Prefer a mix of memory types.
            3. **Cooldown filter**: Skip memories surfaced within
               *cooldown_days* (uses ``last_surfaced`` key).

        Args:
            ranked: Pre-sorted candidates (from :meth:`rank`).
            max_results: Maximum memories to return.
            max_per_topic: Maximum per topic cluster.
            cooldown_days: Minimum days since last surfacing.

        Returns:
            Filtered and diversified list of candidates.
        """
        topic_counts: dict[str, int] = defaultdict(int)
        type_counts: dict[str, int] = defaultdict(int)
        now = datetime.now(timezone.utc)
        results: list[dict[str, Any]] = []

        for cand in ranked:
            if len(results) >= max_results:
                break

            # --- cooldown filter ---
            if self._is_on_cooldown(cand, now, cooldown_days):
                continue

            # --- topic cap ---
            topic = self._extract_topic(cand)
            if topic_counts[topic] >= max_per_topic:
                continue

            # --- type diversity (soft: prefer under-represented) ---
            mem_type = cand.get("type", "unknown")
            # We still add it, but types with 3+ entries get deprioritised
            # by being skipped if there are remaining candidates
            if type_counts[mem_type] >= 3 and len(ranked) > max_results:
                continue

            results.append(cand)
            topic_counts[topic] += 1
            type_counts[mem_type] += 1

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_topic(candidate: dict[str, Any]) -> str:
        """Get topic cluster key from first tag, fallback to 'untagged'."""
        tags = candidate.get("tags", [])
        if tags and isinstance(tags, list) and len(tags) > 0:
            return str(tags[0])
        return "untagged"

    @staticmethod
    def _is_on_cooldown(
        candidate: dict[str, Any],
        now: datetime,
        cooldown_days: float,
    ) -> bool:
        """Check if a memory was surfaced too recently."""
        last_surfaced = candidate.get("last_surfaced")
        if last_surfaced is None:
            return False
        if isinstance(last_surfaced, datetime):
            if last_surfaced.tzinfo is None:
                last_surfaced = last_surfaced.replace(tzinfo=timezone.utc)
            days_ago = (now - last_surfaced).total_seconds() / 86400.0
            return days_ago < cooldown_days
        return False
