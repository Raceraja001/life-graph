"""Contradiction detector for memory consistency (T-026).

Detects contradictions between new content and existing memories using:
  1. Semantic similarity via pgvector (cosine > 0.75 threshold)
  2. Negation flip detection via regex
  3. Entity swap detection (same structure, different object)
  4. Scope difference detection (different project/module = both valid)

85% rule-based — only truly ambiguous cases get flagged for user review.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from life_graph.models.db import Memory
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)

# Similarity threshold for contradiction candidates
_SIMILARITY_THRESHOLD: float = 0.75

# Maximum candidates to check for contradictions
_MAX_CANDIDATES: int = 10


@dataclass
class Contradiction:
    """A detected contradiction between new content and an existing memory."""

    existing_memory_id: str
    existing_content: str
    new_content: str
    conflict_type: str  # 'negation', 'preference_change', 'scope', 'ambiguous'
    similarity: float
    resolution: str  # 'supersede', 'scope', 'ask_user'
    reason: str


# ── Negation Patterns ─────────────────────────────────────────

_NEGATION_PAIRS: list[tuple[re.Pattern[str], re.Pattern[str], str]] = [
    # "not X" vs "X" / "X" vs "not X"
    (
        re.compile(r"\b(?:do\s+not|don'?t|never|avoid)\s+(?:use\s+)?(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        re.compile(r"\b(?:always|prefer|use|like)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        "negation",
    ),
    # "avoid X" vs "use X"
    (
        re.compile(r"\bavoid\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        re.compile(r"\buse\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        "negation",
    ),
    # "never X" vs "always X"
    (
        re.compile(r"\bnever\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        re.compile(r"\balways\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        "negation",
    ),
    # "stopped using X" vs "use X"
    (
        re.compile(r"\bstopped?\s+using\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        re.compile(r"\b(?:use|prefer|like)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        "preference_change",
    ),
    # "switched from X" vs "use X"
    (
        re.compile(r"\bswitched?\s+(?:from|away\s+from)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        re.compile(r"\b(?:use|prefer)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        "preference_change",
    ),
]

# Preference verbs for entity swap detection
_PREFERENCE_RE = re.compile(
    r"\b(?:prefer|use|like|choose|pick|go\s+with|switched?\s+to)\s+(.+?)(?:\s+(?:over|instead|for|because)\b|[.,;!?\n]|$)",
    re.IGNORECASE,
)


class ContradictionDetector:
    """Detects contradictions between new content and existing memories.

    Uses a multi-step rule-based approach:
        1. Find semantically similar active memories (cosine > 0.75)
        2. Run negation flip detection (regex patterns)
        3. Run entity swap detection (same structure, different object)
        4. Check scope differences (different context = both valid)

    Usage::

        detector = ContradictionDetector(store)
        contradictions = await detector.check(
            "I prefer PostgreSQL",
            embedding=[0.1, 0.2, ...],
        )
    """

    def __init__(self, store: PostgresMemoryStore) -> None:
        self._store = store

    async def check(
        self,
        new_content: str,
        new_embedding: list[float],
    ) -> list[Contradiction]:
        """Check new content against existing memories for contradictions.

        Args:
            new_content: The new text to check.
            new_embedding: Pre-computed embedding vector for the new content.

        Returns:
            List of detected Contradiction objects, sorted by severity.
        """
        if not new_content.strip():
            return []

        # Stage 1: Find semantically similar active memories
        similar_memories = await self._store.search_similar(
            embedding=new_embedding,
            limit=_MAX_CANDIDATES,
            filters={"status": "active"},
        )

        if not similar_memories:
            return []

        # Stage 2: Run contradiction checks on each candidate
        contradictions: list[Contradiction] = []
        for memory in similar_memories:
            similarity = _compute_similarity_from_memory(memory, new_embedding)

            # Skip if below threshold
            if similarity < _SIMILARITY_THRESHOLD:
                continue

            # Check for negation flips
            negation = _check_negation_flip(new_content, memory.content)
            if negation:
                conflict_type, reason = negation
                resolution = _determine_resolution(conflict_type, memory)
                contradictions.append(Contradiction(
                    existing_memory_id=str(memory.id),
                    existing_content=memory.content,
                    new_content=new_content,
                    conflict_type=conflict_type,
                    similarity=similarity,
                    resolution=resolution,
                    reason=reason,
                ))
                continue

            # Check for entity swaps (same verb pattern, different object)
            entity_swap = _check_entity_swap(new_content, memory.content)
            if entity_swap:
                reason = entity_swap
                # Check if scope difference makes both valid
                scope_diff = _check_scope_difference(memory)
                if scope_diff:
                    contradictions.append(Contradiction(
                        existing_memory_id=str(memory.id),
                        existing_content=memory.content,
                        new_content=new_content,
                        conflict_type="scope",
                        similarity=similarity,
                        resolution="scope",
                        reason=f"Both valid in different contexts: {scope_diff}",
                    ))
                else:
                    contradictions.append(Contradiction(
                        existing_memory_id=str(memory.id),
                        existing_content=memory.content,
                        new_content=new_content,
                        conflict_type="preference_change",
                        similarity=similarity,
                        resolution="supersede",
                        reason=reason,
                    ))

        # Sort: auto-resolvable first, then by similarity
        contradictions.sort(
            key=lambda c: (
                0 if c.resolution == "supersede" else 1 if c.resolution == "scope" else 2,
                -c.similarity,
            ),
        )

        logger.info(
            "Contradiction check: %d candidates, %d contradictions found",
            len(similar_memories), len(contradictions),
        )
        return contradictions


# ── Detection Helpers ─────────────────────────────────────────


def _check_negation_flip(
    new_text: str, existing_text: str,
) -> tuple[str, str] | None:
    """Check if two texts express opposing sentiments via negation patterns.

    Tests both directions: new negates existing, and existing negates new.

    Returns:
        Tuple of (conflict_type, reason) if negation found, else None.
    """
    for neg_pattern, pos_pattern, conflict_type in _NEGATION_PAIRS:
        # Direction 1: new text has negative, existing has positive
        neg_match_new = neg_pattern.search(new_text)
        pos_match_existing = pos_pattern.search(existing_text)
        if neg_match_new and pos_match_existing:
            neg_entity = neg_match_new.group(1).strip().lower()
            pos_entity = pos_match_existing.group(1).strip().lower()
            if _entities_overlap(neg_entity, pos_entity):
                return (
                    conflict_type,
                    f"New '{new_text.strip()[:60]}' contradicts "
                    f"existing '{existing_text.strip()[:60]}'",
                )

        # Direction 2: existing has negative, new has positive
        neg_match_existing = neg_pattern.search(existing_text)
        pos_match_new = pos_pattern.search(new_text)
        if neg_match_existing and pos_match_new:
            neg_entity = neg_match_existing.group(1).strip().lower()
            pos_entity = pos_match_new.group(1).strip().lower()
            if _entities_overlap(neg_entity, pos_entity):
                return (
                    conflict_type,
                    f"New '{new_text.strip()[:60]}' contradicts "
                    f"existing '{existing_text.strip()[:60]}'",
                )

    return None


def _check_entity_swap(new_text: str, existing_text: str) -> str | None:
    """Check if two texts use the same preference verb but different objects.

    E.g. "I prefer PostgreSQL" vs "I prefer MongoDB" — same structure,
    different entity = preference change.

    Returns:
        Explanation string if entity swap detected, else None.
    """
    new_matches = _PREFERENCE_RE.findall(new_text)
    existing_matches = _PREFERENCE_RE.findall(existing_text)

    if not new_matches or not existing_matches:
        return None

    for new_entity in new_matches:
        new_entity_clean = new_entity.strip().lower()
        for existing_entity in existing_matches:
            existing_entity_clean = existing_entity.strip().lower()
            # Same verb pattern but different entity
            if (
                new_entity_clean
                and existing_entity_clean
                and new_entity_clean != existing_entity_clean
                and not _entities_overlap(new_entity_clean, existing_entity_clean)
            ):
                return (
                    f"Entity swap: '{existing_entity.strip()}' → "
                    f"'{new_entity.strip()}'"
                )

    return None


def _check_scope_difference(memory: Memory) -> str | None:
    """Check if a memory has project/module scope that limits its validity.

    If the memory is scoped to a specific project or module, a
    contradiction might actually be valid in a different scope.

    Returns:
        Scope description string if scoped, else None.
    """
    props = memory.properties or {}
    scopes: list[str] = []

    project = props.get("project")
    if project:
        scopes.append(f"project={project}")

    module = props.get("module")
    if module:
        scopes.append(f"module={module}")

    return ", ".join(scopes) if scopes else None


def _entities_overlap(entity_a: str, entity_b: str) -> bool:
    """Check if two entity strings refer to the same thing.

    Uses substring containment for simple cases. Could be extended
    with spaCy entity linking for higher accuracy.
    """
    if entity_a == entity_b:
        return True
    if entity_a in entity_b or entity_b in entity_a:
        return True

    # Tokenize and check word overlap
    words_a = set(entity_a.split())
    words_b = set(entity_b.split())
    if words_a and words_b:
        overlap = len(words_a & words_b)
        max_len = max(len(words_a), len(words_b))
        if max_len > 0 and overlap / max_len >= 0.5:
            return True

    return False


def _determine_resolution(conflict_type: str, memory: Memory) -> str:
    """Determine the best resolution strategy for a contradiction.

    Rules:
        - negation / preference_change: supersede (newer wins)
        - scope: keep both (different contexts)
        - ambiguous: ask user

    Args:
        conflict_type: Type of conflict detected.
        memory: The existing memory being contradicted.

    Returns:
        Resolution strategy string.
    """
    if conflict_type in ("negation", "preference_change"):
        return "supersede"
    if conflict_type == "scope":
        return "scope"
    return "ask_user"


def _compute_similarity_from_memory(
    memory: Memory, new_embedding: list[float],
) -> float:
    """Compute cosine similarity between a memory's embedding and a new vector.

    Falls back to 0.8 if the memory has no embedding (was retrieved
    by pgvector so it's above threshold by definition).
    """
    if memory.embedding is None:
        # If retrieved by pgvector, it's similar enough
        return 0.8

    # Compute cosine similarity
    dot_product = sum(a * b for a, b in zip(memory.embedding, new_embedding))
    norm_a = sum(a * a for a in memory.embedding) ** 0.5
    norm_b = sum(b * b for b in new_embedding) ** 0.5

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)
