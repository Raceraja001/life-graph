"""Multi-signal retrieval ranking for memory recall.

Combines semantic similarity, contextual relevance, importance,
recency, frequency, and trust into a single ranking score.
Includes diversity-aware reranking to avoid topic clustering.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from life_graph.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weight configuration
# ---------------------------------------------------------------------------

_WEIGHT_SEMANTIC: float = 0.20
_WEIGHT_CONTEXT: float = 0.20
_WEIGHT_IMPORTANCE: float = 0.15
_WEIGHT_IMPACT: float = 0.15
_WEIGHT_RECENCY: float = 0.15
_WEIGHT_FREQUENCY: float = 0.10
_WEIGHT_TRUST: float = 0.05

# Soft ceiling per type bucket in rerank(): beyond this a candidate is
# deferred to the top-up pass, not dropped.
_MAX_PER_TYPE: int = 3

_SIGNAL_WEIGHTS: dict[str, float] = {
    "semantic": _WEIGHT_SEMANTIC,
    "context": _WEIGHT_CONTEXT,
    "importance": _WEIGHT_IMPORTANCE,
    "impact": _WEIGHT_IMPACT,
    "recency": _WEIGHT_RECENCY,
    "frequency": _WEIGHT_FREQUENCY,
    "trust": _WEIGHT_TRUST,
}

# Inert-signal reporting is memoised per process so a per-session recall does
# not repeat the same line forever.
_reported_inert: set[frozenset[str]] = set()

# How much of a memory's text a compact index line carries. Long enough to
# recognise a memory, short enough that the line stays ~12 tokens instead of
# the ~150 a full MemoryResponse costs. Tune with
# LIFE_GRAPH_RECALL_INDEX_CONTENT_CHARS. Read once at import, so it is a
# deployment setting rather than a per-request one; to_index() still takes an
# explicit content_chars for callers that need to override it.
INDEX_CONTENT_CHARS: int = settings.recall_index_content_chars


def to_index(
    candidates: list[dict[str, Any]],
    *,
    content_chars: int = INDEX_CONTENT_CHARS,
) -> list[dict[str, Any]]:
    """Project ranked candidates onto a compact progressive-disclosure index.

    Built here, from the plain dicts :meth:`RecallRanker.rank` already
    produces, rather than downstream from ``MemoryResponse``. A
    ``MemoryResponse`` costs a ``math.exp`` and a ``datetime.now()`` per item
    in ``model_post_init`` and serialises twenty fields — three UUIDs, three
    timestamps, five floats and an unbounded JSONB blob — of which only the
    content is read by a model. Projecting before that construction is both
    the cheaper payload and the cheaper computation.

    Only keys retrieval actually populates are read (``id``, ``content``,
    ``tags``, ``status``) plus ``final_score``, which ``rank()`` writes onto
    its own output.

    Args:
        candidates: Scored candidate dicts, already in the desired order.
        content_chars: Maximum characters of content per line.

    Returns:
        List of ``{id, content, tags, score, status}`` dicts, order preserved.
    """
    index: list[dict[str, Any]] = []
    for cand in candidates:
        content = str(cand.get("content", "") or "")
        if len(content) > content_chars:
            content = content[:content_chars].rstrip() + "…"
        tags = cand.get("tags") or []
        index.append(
            {
                "id": str(cand.get("id", "")),
                "content": content,
                "tags": list(tags) if isinstance(tags, list) else [],
                "score": round(float(cand.get("final_score", 0.0) or 0.0), 4),
                "status": str(cand.get("status", "active") or "active"),
            }
        )
    return index


def inert_signals(scored: list[dict[str, Any]]) -> dict[str, float]:
    """Signals identical across every candidate, and the weight they waste.

    A weighted signal with the same value on every candidate adds a constant
    to each final score. It does not misorder anything — it simply takes no
    part in the ordering, and the weight it was given is spent on nothing.

    That is exactly how two defects stayed invisible here. ``context`` scored
    0.0 for every candidate because the four keys it reads were never written
    into Memory.properties, and ``semantic`` is still a hardcoded 0.5 while
    retrieval is non-vector. Between them, 40% of the weight was inert while
    every score looked plausible.
    """
    if len(scored) < 2:
        return {}

    inert: dict[str, float] = {}
    for signal, weight in _SIGNAL_WEIGHTS.items():
        values = {c.get("_sub_scores", {}).get(signal) for c in scored}
        if len(values) == 1:
            inert[signal] = weight
    return inert


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
        now = datetime.now(UTC)
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        return max((now - last).total_seconds() / 86400.0, 0.0)
    return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class RecallRanker:
    """Multi-signal ranker for memory retrieval results.

    Blends seven signals into a final score and applies diversity-aware
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
            - ``impact_score`` (float): Learned usefulness from outcomes.
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
            impact = float(cand.get("impact_score", 0.5))
            rec = _recency_score(_resolve_days_since_access(cand))
            freq = _frequency_score(int(cand.get("access_count", 1)))
            trust = float(cand.get("trust_score", 0.5))

            final = (
                _WEIGHT_SEMANTIC * sem
                + _WEIGHT_CONTEXT * ctx_score
                + _WEIGHT_IMPORTANCE * imp
                + _WEIGHT_IMPACT * impact
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
                "impact": round(impact, 4),
                "recency": round(rec, 4),
                "frequency": round(freq, 4),
                "trust": round(trust, 4),
            }
            scored.append(enriched)

        scored.sort(key=lambda c: c["final_score"], reverse=True)
        self._report_inert(scored)
        return scored

    @staticmethod
    def _report_inert(scored: list[dict[str, Any]]) -> None:
        """Surface weights that took no part in this ordering.

        Logged rather than raised: a constant signal is legitimate in small
        or homogeneous result sets, and recall must never fail because of it.
        Reported once per distinct signal set per process.
        """
        inert = inert_signals(scored)
        if not inert:
            return

        key = frozenset(inert)
        wasted = sum(inert.values())
        message = (
            "Ranking signals identical across all %d candidates, so %.0f%% of "
            "the weight took no part in the ordering: %s"
        )
        args = (len(scored), wasted * 100, ", ".join(sorted(inert)))
        if key in _reported_inert:
            logger.debug(message, *args)
        else:
            _reported_inert.add(key)
            logger.info(message, *args)

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
        now = datetime.now(UTC)
        results: list[dict[str, Any]] = []
        # Passed over by the type rule only. Type diversity is a preference,
        # so these are eligible again if the first pass comes up short.
        deferred: list[dict[str, Any]] = []

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
            mem_type = self._candidate_type(cand)
            if type_counts[mem_type] >= _MAX_PER_TYPE and len(ranked) > max_results:
                deferred.append(cand)
                continue

            results.append(cand)
            topic_counts[topic] += 1
            type_counts[mem_type] += 1

        # Top up from the type-deferred candidates, still in score order.
        #
        # This pass is what makes the type rule a preference rather than a
        # cap. Without it the single pass dropped those candidates for good:
        # no candidate carried a "type" key at all, so every one collapsed to
        # "unknown" and the rule truncated proactive recall to
        # _MAX_PER_TYPE results — asking for 5 returned 3. Topic caps and
        # cooldown are real limits and are not revisited here.
        for cand in deferred:
            if len(results) >= max_results:
                break
            topic = self._extract_topic(cand)
            if topic_counts[topic] >= max_per_topic:
                continue
            results.append(cand)
            topic_counts[topic] += 1
            type_counts[self._candidate_type(cand)] += 1

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _candidate_type(candidate: dict[str, Any]) -> str:
        """Type bucket for the diversity preference.

        Falls back to ``source_type``, which retrieval actually populates.
        The core is schema-less and has no memory-type column, so reading
        only ``type`` bucketed every candidate as "unknown".
        """
        return str(candidate.get("type") or candidate.get("source_type") or "unknown")

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
                last_surfaced = last_surfaced.replace(tzinfo=UTC)
            days_ago = (now - last_surfaced).total_seconds() / 86400.0
            return days_ago < cooldown_days
        return False
