"""Contradiction detector for memory consistency (T-026).

Detects contradictions between new content and existing memories using:
  1. Semantic similarity via pgvector (``settings.contradiction_similarity_threshold``)
  2. Negation flip detection via regex
  3. Entity swap detection — an exclusive verb ("prefer", "switched to",
     "favourite … is") with a different object
  4. Scope difference detection (either memory scoped to a different
     project/module = both valid)

A detection is only a suspicion: MemoryManager records it and the supersede
waits for the owner (see MemoryManager._process_fact).

Review 2026-10-22: plain "use/like" with different objects used to count as
a swap, so "I use Python for scripts" superseded "I use VS Code"; the scope
check looked only at the old memory; and a candidate with no embedding was
assumed similar (0.8). All three are fixed below.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from life_graph.models.db import Memory
    from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)

# Maximum candidates to check for contradictions
_MAX_CANDIDATES: int = 10

# Filler words stripped before _entities_overlap's word-overlap check, so two
# unrelated entities that merely share an article/pronoun (e.g. "the API" vs
# "the UI") don't register as "the same entity".
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "i",
        "my",
        "me",
        "our",
        "we",
        "you",
        "your",
    }
)


@dataclass
class Contradiction:
    """A detected contradiction between new content and an existing memory."""

    existing_memory_id: str
    existing_content: str
    new_content: str
    conflict_type: str  # 'negation', 'preference_change', 'scope'
    similarity: float
    resolution: str  # 'supersede' (newer wins, once the owner agrees), 'scope' (keep both)
    reason: str


# ── Negation Patterns ─────────────────────────────────────────

_NEGATION_PAIRS: list[tuple[re.Pattern[str], re.Pattern[str], str]] = [
    # "not X" vs "X" / "X" vs "not X"
    (
        re.compile(
            r"\b(?:do\s+not|don'?t|never|avoid)\s+(?:use\s+)?(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE
        ),
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
    # "no longer use X" vs "use X" (added 2026-10-22: an explicit change of
    # mind, which the swap rule no longer infers from plain "use")
    (
        re.compile(
            r"\bno\s+longer\s+(?:use|using|like|prefer)?\s*(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE
        ),
        re.compile(r"\b(?:use|prefer|like)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        "preference_change",
    ),
    # "X instead of Y" vs "use Y" (added 2026-10-22)
    (
        re.compile(r"\binstead\s+of\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE),
        re.compile(r"\b(?:use|prefer|like)\s+(.+?)(?:\s+instead\b|[.,;!?\n]|$)", re.IGNORECASE),
        "preference_change",
    ),
]

_OBJECT_END = r"(?:\s+(?:over|instead|for|because|when|in)\b|[.,;!?\n]|$)"

# Any preference/usage verb. On its own this does not make a contradiction —
# people use and like many things at once — it only marks the other side of
# an exclusive statement below.
_PREFERENCE_RE = re.compile(
    r"\b(?:prefer(?:s|red)?|use[sd]?|using|like[sd]?|choose|chose|pick(?:ed)?|go\s+with"
    r"|switched?\s+to|moved\s+to|migrated\s+to)\s+(.+?)" + _OBJECT_END,
    re.IGNORECASE,
)

# Verbs that claim one thing *over* the others, so a different object is a
# change of mind rather than a second, compatible fact (2026-10-22).
_EXCLUSIVE_RE = re.compile(
    r"\b(?:prefer(?:s|red)?|switched?\s+to|moved\s+to|migrated\s+to)\s+(.+?)" + _OBJECT_END,
    re.IGNORECASE,
)

# "my favourite editor is X": exclusive within its slot ("editor"), so only
# another favourite for the same slot conflicts with it.
_FAVOURITE_RE = re.compile(
    r"\bfavou?rite\s+(\w+(?:\s+\w+)?)\s+(?:is|are)\s+(.+?)" + _OBJECT_END,
    re.IGNORECASE,
)

# "for scripts", "for analytics": the purpose a tool is used for. Two
# statements with different purposes can both be true.
_PURPOSE_RE = re.compile(r"\bfor\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE)


class ContradictionDetector:
    """Detects contradictions between new content and existing memories.

    Uses a multi-step rule-based approach:
        1. Find semantically similar active memories
           (cosine >= ``settings.contradiction_similarity_threshold``)
        2. Run negation flip detection (regex patterns)
        3. Run entity swap detection (exclusive verb, different object)
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
        new_properties: dict[str, Any] | None = None,
    ) -> list[Contradiction]:
        """Check new content against existing memories for contradictions.

        Args:
            new_content: The new text to check.
            new_embedding: Pre-computed embedding vector for the new content.
            new_properties: The new memory's properties (its ``project`` /
                ``module`` scope), for the scope check.

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

        return self._check_candidates(new_content, similar_memories, new_embedding, new_properties)

    async def check_candidates(
        self,
        new_content: str,
        candidates: list[Memory],
        new_embedding: list[float],
        new_properties: dict[str, Any] | None = None,
    ) -> list[Contradiction]:
        """Like check(), but skips the DB lookup — for callers that already
        fetched candidate memories (e.g. MemoryManager._process_fact(), which
        derives them from one shared similarity query it also uses for dedup,
        instead of paying for a second pgvector round-trip here).

        Args:
            new_content: The new text to check.
            candidates: Pre-fetched candidate memories (should be status
                "active" — this does no further status filtering).
            new_embedding: Pre-computed embedding vector for the new content.
            new_properties: The new memory's properties, for the scope check.

        Returns:
            List of detected Contradiction objects, sorted by severity.
        """
        if not new_content.strip():
            return []
        return self._check_candidates(new_content, candidates, new_embedding, new_properties)

    def _check_candidates(
        self,
        new_content: str,
        similar_memories: list[Memory],
        new_embedding: list[float],
        new_properties: dict[str, Any] | None = None,
    ) -> list[Contradiction]:
        if not similar_memories:
            return []

        from life_graph.config import settings

        threshold = settings.contradiction_similarity_threshold

        # Stage 2: Run contradiction checks on each candidate
        contradictions: list[Contradiction] = []
        for memory in similar_memories:
            similarity = _compute_similarity_from_memory(memory, new_embedding)

            # Skip if unknown (no embedding to compare) or below threshold
            if similarity is None or similarity < threshold:
                continue

            # Check for negation flips, then entity swaps (exclusive verb,
            # different object)
            found = _check_negation_flip(new_content, memory.content)
            if not found:
                swap = _check_entity_swap(new_content, memory.content)
                found = ("preference_change", swap) if swap else None
            if not found:
                continue
            conflict_type, reason = found

            # Either memory scoped to a different project/module: both valid
            scope_diff = _check_scope_difference(memory, new_properties)
            if scope_diff:
                conflict_type = "scope"
                reason = f"Both valid in different contexts: {scope_diff}"

            contradictions.append(
                Contradiction(
                    existing_memory_id=str(memory.id),
                    existing_content=memory.content,
                    new_content=new_content,
                    conflict_type=conflict_type,
                    similarity=similarity,
                    resolution=_determine_resolution(conflict_type, memory),
                    reason=reason,
                )
            )

        # Sort: supersede suggestions first, then by similarity
        contradictions.sort(
            key=lambda c: (0 if c.resolution == "supersede" else 1, -c.similarity),
        )

        logger.info(
            "Contradiction check: %d candidates, %d contradictions found",
            len(similar_memories),
            len(contradictions),
        )
        return contradictions


# ── Detection Helpers ─────────────────────────────────────────


def _check_negation_flip(
    new_text: str,
    existing_text: str,
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


def differs_by_negation(text_a: str, text_b: str) -> bool:
    """Whether one text negates the other ("I use X" vs "I don't use X").

    MemoryManager asks this before its near-duplicate merge: a negation
    barely moves an embedding, so the two can score above dedup_threshold
    and used to be merged as one memory, losing the "not" (2026-10-22).
    """
    return _check_negation_flip(text_a, text_b) is not None


def _check_entity_swap(new_text: str, existing_text: str) -> str | None:
    """Check if one text exclusively prefers a different object than the other.

    E.g. "I prefer PostgreSQL" vs "I prefer MongoDB", or "I switched to
    FastAPI" vs "I use Django". At least one side must use an exclusive verb
    (``_EXCLUSIVE_RE``) and the other any preference verb, or both must name a
    favourite for the same slot. Plain "use/like" on both sides is not a
    swap: "I use Python for scripts" and "I use VS Code" are both true, and
    until 2026-10-22 the first silently superseded the second. Different
    stated purposes ("for scripts" vs "for analytics") are not a swap either.

    Returns:
        Explanation string if entity swap detected, else None.
    """
    if _purposes_differ(new_text, existing_text):
        return None

    pairs: list[tuple[str, str]] = []
    new_excl = _EXCLUSIVE_RE.findall(new_text)
    existing_excl = _EXCLUSIVE_RE.findall(existing_text)
    if new_excl:
        pairs += [(e, n) for n in new_excl for e in _PREFERENCE_RE.findall(existing_text)]
    if existing_excl:
        pairs += [(e, n) for e in existing_excl for n in _PREFERENCE_RE.findall(new_text)]
    for new_slot, new_obj in _FAVOURITE_RE.findall(new_text):
        for old_slot, old_obj in _FAVOURITE_RE.findall(existing_text):
            if _entities_overlap(new_slot.lower(), old_slot.lower()):
                pairs.append((old_obj, new_obj))

    for existing_entity, new_entity in pairs:
        new_clean = new_entity.strip().lower()
        existing_clean = existing_entity.strip().lower()
        if (
            new_clean
            and existing_clean
            and new_clean != existing_clean
            and not _entities_overlap(new_clean, existing_clean)
        ):
            return f"Entity swap: '{existing_entity.strip()}' → '{new_entity.strip()}'"

    return None


def _purposes_differ(text_a: str, text_b: str) -> bool:
    """Both texts state a purpose ("for X") and the purposes differ."""
    a = _PURPOSE_RE.search(text_a)
    b = _PURPOSE_RE.search(text_b)
    if not a or not b:
        return False
    return not _entities_overlap(a.group(1).strip().lower(), b.group(1).strip().lower())


def _check_scope_difference(
    memory: Memory,
    new_properties: dict[str, Any] | None = None,
) -> str | None:
    """Check whether the two memories are scoped to different contexts.

    If either memory is scoped to a project or module the other does not
    share, both statements can be true at once. Symmetric since 2026-10-22:
    it used to look only at the old memory, so a new project-scoped
    statement superseded a general one.

    Returns:
        Scope description string if the scopes differ, else None.
    """
    old_props = memory.properties or {}
    new_props = new_properties or {}
    scopes: list[str] = []

    for key in ("project", "module"):
        old_val, new_val = old_props.get(key), new_props.get(key)
        if (old_val or new_val) and old_val != new_val:
            scopes.append(f"{key}={old_val or '-'} vs {new_val or '-'}")

    return ", ".join(scopes) if scopes else None


def _entities_overlap(entity_a: str, entity_b: str) -> bool:
    """Check if two entity strings refer to the same thing.

    Uses substring containment for simple cases. Could be extended
    with spaCy entity linking for higher accuracy.
    """
    entity_a = _strip_stopwords(entity_a)
    entity_b = _strip_stopwords(entity_b)
    if not entity_a or not entity_b:
        # An empty (or filler-word-only) capture can't be confirmed to
        # match anything. Without this, "" in "anything" is True in
        # Python, so a blank capture group used to register as
        # overlapping with every other entity.
        return False

    if entity_a == entity_b:
        return True
    if entity_a in entity_b or entity_b in entity_a:
        return True

    # Tokenize and check word overlap
    words_a = set(entity_a.split())
    words_b = set(entity_b.split())
    overlap = len(words_a & words_b)
    max_len = max(len(words_a), len(words_b))
    return overlap / max_len >= 0.5


def _strip_stopwords(entity: str) -> str:
    """Drop filler words (articles, pronouns) before entity comparison."""
    return " ".join(w for w in entity.split() if w not in _STOPWORDS)


def _determine_resolution(conflict_type: str, memory: Memory) -> str:
    """Determine the best resolution strategy for a contradiction.

    Rules:
        - negation / preference_change: supersede (newer wins — applied only
          once the owner approves, see MemoryManager._process_fact)
        - anything else: keep both

    There used to be a third answer, ``ask_user``, but nothing produced it
    and its handler only logged (review 2026-10-22). It was removed rather
    than built: every supersede now goes to the owner as a contradiction
    approval anyway, which is the asking.

    Args:
        conflict_type: Type of conflict detected.
        memory: The existing memory being contradicted.

    Returns:
        Resolution strategy string: ``supersede`` or ``scope``.
    """
    if conflict_type in ("negation", "preference_change"):
        return "supersede"
    return "scope"


def _compute_similarity_from_memory(
    memory: Memory,
    new_embedding: list[float] | None,
) -> float | None:
    """Compute cosine similarity between a memory's embedding and a new vector.

    Returns None when either vector is missing: an unknown similarity is not
    a high one. It used to default to 0.8, so any candidate without an
    embedding counted as similar enough to be superseded (2026-10-22).
    """
    if memory.embedding is None or new_embedding is None or len(new_embedding) == 0:
        return None

    # Compute cosine similarity
    dot_product = sum(a * b for a, b in zip(memory.embedding, new_embedding, strict=False))
    norm_a = sum(a * a for a in memory.embedding) ** 0.5
    norm_b = sum(b * b for b in new_embedding) ** 0.5

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)
