"""Contradiction detector for memory consistency (T-026).

Detects contradictions between new content and existing memories using:
  1. Semantic similarity via pgvector (``settings.contradiction_similarity_threshold``)
  2. Negation flip detection via regex
  3. Entity swap detection — an exclusive verb ("prefer", "switched to",
     "favourite … is") with a different object
  4. Value change detection — the same statement with one value replaced
     ("Priya lives in Chennai" → "Priya lives in Bangalore"), 2026-11-25
  5. Scope difference detection (either memory scoped to a different
     project/module = both valid)
  6. With ``settings.ingest_supersession_tiers`` on, more changes
     (2026-11-28): a "not" ("no longer eats meat"), a new amount ("₹10,000"
     → "₹15,000"), a new person in a one-holder role ("Divya is my manager
     now"), a new object said as a change ("uses Linear now"), and the
     Tamil/Tanglish forms. See "More changes" below.

A detection is only a suspicion: MemoryManager records it and the supersede
waits for the owner (see MemoryManager._process_fact).

Review 2026-10-22: plain "use/like" with different objects used to count as
a swap, so "I use Python for scripts" superseded "I use VS Code"; the scope
check looked only at the old memory; and a candidate with no embedding was
assumed similar (0.8). All three are fixed below.
"""

from __future__ import annotations

import difflib
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from life_graph.config import settings

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
    conflict_type: str  # 'negation', 'preference_change', 'value_change', 'scope'
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
        4. Run value change detection (same statement, one value replaced)
        5. Check scope differences (different context = both valid)

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
            # A clash with any active memory, whoever wrote it: this checks
            # new content, it does not build a packet for an agent.
            include_hostile=True,
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

        threshold = settings.contradiction_similarity_threshold

        # Stage 2: Run contradiction checks on each candidate
        contradictions: list[Contradiction] = []
        for memory in similar_memories:
            similarity = _compute_similarity_from_memory(memory, new_embedding)

            # Skip if unknown (no embedding to compare) or below threshold
            if similarity is None or similarity < threshold:
                continue

            # Check for negation flips, then entity swaps (exclusive verb,
            # different object), then a plain change of value
            found = _check_negation_flip(new_content, memory.content)
            if not found:
                swap = _check_entity_swap(new_content, memory.content)
                found = ("preference_change", swap) if swap else None
            if not found:
                change = _check_value_change(new_content, memory.content)
                found = ("value_change", change) if change else None
            if not found and settings.ingest_supersession_tiers:
                # Prod runs with the flag off: these rules wait for it.
                found = _check_more_changes(new_content, memory.content)
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


# A word that turns a statement into its opposite: "not", "no", "never",
# "no longer", "without", or a contraction ending in n't ("isn't", "can't").
# The apostrophe-less spellings ("dont", "cant") are listed too.
_NEGATOR_RE = re.compile(
    r"\b(?:not|no|never|none|nobody|nothing|nowhere|neither|nor|without|cannot"
    r"|dont|doesnt|didnt|isnt|arent|wasnt|werent|cant|couldnt|wont|wouldnt"
    r"|shouldnt|havent|hasnt|hadnt|aint)\b|\w(?:n't|n\u2019t)\b",
    re.IGNORECASE,
)


def _has_negator(text: str) -> bool:
    """Whether the text contains a negating word (see ``_NEGATOR_RE``)."""
    return _NEGATOR_RE.search(text) is not None


def differs_by_negation(text_a: str, text_b: str) -> bool:
    """Whether one text negates the other ("I use X" vs "I don't use X").

    MemoryManager asks this before its near-duplicate merge: a negation
    barely moves an embedding, so the two can score above dedup_threshold
    and used to be merged as one memory, losing the "not" (2026-10-22).

    Two checks. First the contradiction rules (``_check_negation_flip``).
    Then, since those only know a few verbs (use, like, prefer, always),
    a plain asymmetry: one text has a negating word and the other has none
    ("Priya eats meat" / "Priya does not eat meat", "I am allergic" / "I am
    not allergic", "has never drunk", "no longer", "isn't", "can't"),
    2026-11-25. The asymmetry is only a merge guard: it does not flag a
    contradiction. It does not look at which verb the "not" belongs to, so
    "I live in Chennai, not Pune" and "I live in Chennai" are also kept
    apart; that costs a duplicate memory, never a lost "not".

    With ``settings.ingest_supersession_tiers`` on, a Tamil or Tanglish "not"
    counts too ("குடிப்பதில்லை", "maatten", "illa"; ``_strip_negation``),
    2026-11-28: the English word list does not see it.
    """
    if _check_negation_flip(text_a, text_b) is not None:
        return True
    if _has_negator(text_a) != _has_negator(text_b):
        return True
    return bool(settings.ingest_supersession_tiers) and (
        _strip_negation(text_a)[2] != _strip_negation(text_b)[2]
    )


# Capitalised words that are grammar, not a detail ("My", "The", "I").
_NOT_DETAILS = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "i i'm i've i'd i'll my me we our us you your he his him she her it its they "
        "their them this that these those the a an and or but so if when then"
    ).split()
)
_CALENDAR = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "january february march april may june july august september october november "
        "december jan feb mar apr jun jul aug sep sept oct nov dec monday tuesday "
        "wednesday thursday friday saturday sunday"
    ).split()
)
# Number words. "one", "first" and "second" are left out: they are mostly
# pronouns or time ("the one I like", "first time", "a second"), and a change
# to or from them is still caught by the other word ("class one" / "class two").
_NUMBER_WORDS = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "zero two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty "
        "fifty sixty seventy eighty ninety hundred thousand lakh lakhs crore crores "
        "million billion dozen third fourth fifth sixth seventh eighth ninth tenth"
    ).split()
)
# Colour words, plus "light"/"dark" (a light vs dark theme or shade).
_COLOUR_WORDS = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "white black grey gray red blue green yellow orange purple pink brown silver "
        "golden gold maroon navy beige violet cream light dark"
    ).split()
)
# Lowercase words that are values on their own: a changed month, weekday,
# number word or colour is a different fact, not a paraphrase.
_VALUE_WORDS = _CALENDAR | _NUMBER_WORDS | _COLOUR_WORDS
# Spellings of the same value, so "grey" and "gray" do not count as different.
_SAME_VALUE = {"gray": "grey"}
_NUMBER_RE = re.compile(r"\d+(?:[.,:/]\d+)*")
_CAPITALISED_RE = re.compile(r"\b([A-Z][\w-]*)")
_WORD_RE = re.compile(r"[a-z0-9]+(?:[.,:/][0-9]+)*")


def _words(text: str) -> set[str]:
    """Lowercased words, with spellings of the same value made one."""
    return {_SAME_VALUE.get(w, w) for w in _WORD_RE.findall(text.lower())}


def _details(text: str) -> set[str]:
    """The specific values a statement carries: numbers, dates, names, and
    number and colour words ("four", "grey")."""
    found = set(_NUMBER_RE.findall(text))
    found |= {
        _SAME_VALUE.get(w.lower(), w.lower())
        for w in _CAPITALISED_RE.findall(text)
        if w.lower() not in _NOT_DETAILS
    }
    found |= {w for w in _words(text) if w in _VALUE_WORDS}
    return found


def differs_in_detail(text_a: str, text_b: str) -> bool:
    """Whether one text names a value the other does not mention at all.

    A number, a month or weekday, a number word ("four"), a colour ("grey",
    "dark"), or a capitalised name in one text that does not appear (in any
    case) anywhere in the other. "Priya's birthday is 3 May"
    and "Priya's birthday is 4 May" embed almost the same, and so do "Priya's
    birthday…" and "Maha's birthday…"; merging either pair keeps one value and
    drops the other. MemoryManager asks this before its near-duplicate merge
    (Stage 0 finding 5, 2026-11-25); a pair that differs is stored as its own
    memory and goes to the contradiction check. Erring towards "differs" only
    costs a duplicate, never a lost fact. Number and colour words were added
    on 2026-11-25: "class four" / "class five" and "a white car" / "a grey
    car" used to merge.

    Two texts that each prefer a different thing ("I prefer pytest" / "I
    prefer unittest", the detector's entity swap) also differ: lowercase
    names carry no capital, and the merge used to fold the swap into one
    memory before the contradiction check could see it (2026-11-25).

    With ``settings.ingest_supersession_tiers`` on, a pair the "More
    changes" rules flag differs too ("Tea dhaan pidikkum" / "Coffee dhaan
    pidikkum" has no capital to tell them apart), 2026-11-28.
    """
    words_a = _words(text_a)
    words_b = _words(text_b)
    if any(d not in words_b for d in _details(text_a)) or any(
        d not in words_a for d in _details(text_b)
    ):
        return True
    if _check_entity_swap(text_a, text_b) is not None:
        return True
    return (
        bool(settings.ingest_supersession_tiers) and _check_more_changes(text_a, text_b) is not None
    )


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


# ── Value change ──────────────────────────────────────────────
#
# "Priya lives in Chennai" → "Priya lives in Bangalore", "birthday is 3 May"
# → "4 May", "rent is 18,000" → "21,000": the same sentence with one value
# swapped. Every flag becomes an owner approval, so the rule is narrow on
# purpose (added 2026-11-25). Two facts that can both be true ("I speak
# Tamil" / "I speak English", "Priya lives in Chennai" / "Arun lives in
# Bangalore") must not be flagged; a missed change only costs a duplicate.

# Words as compared: letters and digits, keeping "18,000", "7:30" and "3.5" whole.
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[.,:/][0-9]+)*")
# Words that may be added or dropped without changing the statement
# ("I live in Chennai now", "is on 3 May").
_FILLER = frozenset(
    ("now", "currently", "actually", "really", "still", "today", "these", "days", "on", "at", "the")
)
# A second value alongside the first, not instead of it.
_ADDITIVE = frozenset(("also", "too", "another", "both", "either", "besides"))
# The value is one item of a list ("friends with Anand", "Tamil and English").
_LIST_JOINERS = frozenset(("with", "and", "or", "nor"))
# Relations that hold many values at once ("is friends with", "is interested
# in", "is a fan of").
_MULTI_VALUE = frozenset(("friend", "friends", "interested", "fan", "member", "part", "allergic"))
# A copula whose subject has one value at a time ("my manager is", "the
# dentist appointment is on"). Not "was": two past values can both be true.
_COPULAS = frozenset(("is", "are"))
# Present-tense verbs that hold one value at a time, with the words that must
# follow them (None: any). Past forms are left out: "I lived in Pune" and "I
# lived in Delhi" can both be true.
_SINGLE_VALUE_VERBS: dict[str, frozenset[str] | None] = {
    **dict.fromkeys(
        ("live", "lives", "living", "stay", "stays", "staying", "based"), frozenset(("in", "at"))
    ),
    **dict.fromkeys(("work", "works", "working"), frozenset(("at", "for"))),
    **dict.fromkeys(
        (
            "leave",
            "leaves",
            "depart",
            "departs",
            "arrive",
            "arrives",
            "start",
            "starts",
            "begin",
            "begins",
            "end",
            "ends",
            "due",
        ),
        frozenset(("at", "on", "in")),
    ),
    **dict.fromkeys(("weigh", "weighs", "cost", "costs", "earn", "earns"), None),
}
# At most this many words on each side of the swapped value ("VS Code").
_MAX_VALUE_TOKENS = 3


def _tokens(text: str) -> tuple[list[str], list[str]]:
    """The text's words as written, and lowercased with one spelling per value."""
    raw = _TOKEN_RE.findall(text)
    return raw, [_SAME_VALUE.get(w.lower(), w.lower()) for w in raw]


def _has_single_value_cue(prefix: list[str]) -> bool:
    """Whether the words before the value say it has one value at a time.

    A copula ("is", "are") not followed by an -ing verb ("Raja is working on
    X" is an activity, and people do several), or a verb from
    ``_SINGLE_VALUE_VERBS`` with its preposition ("lives in", "works at").
    """
    for i, word in enumerate(prefix):
        nxt = prefix[i + 1] if i + 1 < len(prefix) else ""
        if word in _COPULAS and not nxt.endswith("ing"):
            return True
        if word in _SINGLE_VALUE_VERBS:
            follow = _SINGLE_VALUE_VERBS[word]
            if follow is None or nxt in follow:
                return True
    return False


def _value_words(block: list[str], text: str, other_words: set[str]) -> list[str]:
    """Words of *block* that are values (``_details``, or carry a digit, like
    "5th") and that the other text does not mention at all."""
    details = {_SAME_VALUE.get(d.lower(), d.lower()) for d in _details(text)}
    return [
        w for w in block if (w in details or any(c.isdigit() for c in w)) and w not in other_words
    ]


def _changed_block(old: list[str], new: list[str]) -> tuple[int, int, int, int] | None:
    """The one place where *old* and *new* differ, as (i1, i2, j1, j2).

    None unless, after ignoring added or dropped filler words, exactly one
    run of words was replaced by another, each at most ``_MAX_VALUE_TOKENS``
    long. Two changed places ("Priya lives in Chennai" / "Arun lives in
    Bangalore") mean a different subject or a different statement.
    """
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    changed = [
        op
        for op in matcher.get_opcodes()
        if op[0] != "equal"
        and not (op[0] == "delete" and set(old[op[1] : op[2]]) <= _FILLER)
        and not (op[0] == "insert" and set(new[op[3] : op[4]]) <= _FILLER)
    ]
    if len(changed) != 1 or changed[0][0] != "replace":
        return None
    _, i1, i2, j1, j2 = changed[0]
    if i2 - i1 > _MAX_VALUE_TOKENS or j2 - j1 > _MAX_VALUE_TOKENS:
        return None
    return i1, i2, j1, j2


def _check_value_change(new_text: str, existing_text: str) -> str | None:
    """Whether the new text is the existing statement with one value replaced.

    All of these must hold:

    * neither text has a negating word (those are the negation rules' job)
      and neither says "also", "too", "another" (a second value, not a new one);
    * the two are the same words except one replaced run (``_changed_block``),
      so the subject and the predicate are the same. "Priya's birthday" vs
      "Maha's birthday" changes the subject, which comes before the verb, and
      is not flagged;
    * the words before that run say the slot holds one value at a time
      (``_has_single_value_cue``: "is", "lives in", "works at", "leaves at"),
      do not end in a list word ("friends with"), and name no many-valued
      relation (``_MULTI_VALUE``). "I speak Tamil" / "I speak English" and
      "I visited Delhi in March" / "in June" have no such word;
    * both sides of the run carry a value (``_details``: a number, date, name,
      number word or colour) that the other text does not mention, so "My
      manager is Anand" / "My manager is a nice guy" is not flagged.

    Returns:
        Explanation string if a value change is detected, else None.
    """
    if _has_negator(new_text) or _has_negator(existing_text):
        return None
    old_raw, old = _tokens(existing_text)
    new_raw, new = _tokens(new_text)
    if _ADDITIVE & (set(old) | set(new)):
        return None
    block = _changed_block(old, new)
    if block is None:
        return None
    i1, i2, j1, j2 = block
    prefix = old[:i1]
    if _LIST_JOINERS & set(prefix[-1:]) or _MULTI_VALUE & set(prefix):
        return None
    if not _has_single_value_cue(prefix):
        return None
    if not _value_words(old[i1:i2], existing_text, set(new)) or not _value_words(
        new[j1:j2], new_text, set(old)
    ):
        return None
    was = _trim_filler(old_raw[i1:i2], old[i1:i2])
    now = _trim_filler(new_raw[j1:j2], new[j1:j2])
    return f"Value change: '{was}' → '{now}'"


def _trim_filler(raw: list[str], words: list[str]) -> str:
    """The words as written, without filler at either end ("Coimbatore now")."""
    start, end = 0, len(words)
    while start < end and words[start] in _FILLER:
        start += 1
    while end > start and words[end - 1] in _FILLER:
        end -= 1
    return " ".join(raw[start:end])


# ── More changes (flag ``ingest_supersession_tiers``) ─────────
#
# Added 2026-11-28. The rules above miss most changes that are not "X is A"
# → "X is B": "no longer eats meat", "does not use Jira" against "uses
# Jira", "invests ₹10,000" → "₹15,000", "Divya is my manager now" against
# "Suresh is my manager", and the same in Tamil and Tanglish. The rules
# below catch those, and only with ``settings.ingest_supersession_tiers`` on,
# so the save path in prod (flag off) is unchanged until the flag is turned
# on. With the flag on every detector hit is the medium tier: an approval
# that waits for the owner, never an applied supersede.
#
# Precision comes first: a false hit is an approval in the owner's queue.
# Every rule wants the two texts to be the same words apart from the one
# change it looks for. "I don't eat meat on Tuesdays" against "I eat meat"
# has an extra "on Tuesdays", so it is not a hit; nor is a different subject.
#
# Words are matched as tokens of any script (letters, marks and digits: the
# D10 rule of extraction/world_time.py and snapshot._words), never with
# ``\w``, so Tamil vowel signs stay inside their word.

#: Words that may be added or dropped on either side ("now", "anymore").
_CHANGE_FILLER = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "now currently nowadays anymore again still actually really today "
        "ippo ippa ipo ini inimel inime இப்போ இப்போது இப்ப இனி இனிமேல் இனிமே"
    ).split()
)
#: Words that say the new statement replaces an earlier one ("now", "ippo").
_CHANGE_MARKERS = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "now currently nowadays ippo ippa ipo inimel inime இப்போ இப்போது இப்ப இனிமேல் இனிமே"
    ).split()
)
#: English auxiliaries a "not" folds into ("does not eat" is "eats").
_NOT_AUX = frozenset(("do", "does", "did"))
#: Stopping verbs before an -ing verb: "stopped eating meat" is "not eat meat".
_STOP_VERBS = frozenset(("stop", "stops", "stopped", "quit", "quits", "quitted"))
#: Tamil and Tanglish words that negate the verb before them ("சாப்பிட
#: மாட்டேன்", "kudikka maatten", "illa").
_TA_NEG_WORDS = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "இல்லை இல்ல மாட்டேன் மாட்டான் மாட்டாள் மாட்டார் மாட்டோம் மாட்டாங்க "
        "illa illai ille maaten maatten maattaen maatan maattan maatal maattaal "
        "maatar maattar maatom maattom maataanga maattaanga"
    ).split()
)
#: Tamil and Tanglish "stopped" / "gave up" after a verbal noun ("குடிப்பதை
#: நிறுத்திவிட்டேன்", "kudikradha niruthiten").
_TA_STOP_WORDS = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "நிறுத்திவிட்டேன் நிறுத்திட்டேன் நிறுத்தினேன் விட்டுவிட்டேன் விட்டுட்டேன் "
        "niruthiten niruthitten niruthinen nirutthiten vittuten vittutten vitten"
    ).split()
)
#: A habitual "does not" glued to the verb: "குடிப்பதில்லை", "kudikkradhilla".
_TA_NEG_SUFFIXES = ("தில்லை", "dhilla", "thilla", "dhillai", "thillai")
#: Past endings of the affirmed verb: "I drank coffee" is no clash with "I
#: don't drink coffee".
_TA_PAST_ENDINGS = ("த்தேன்", "ந்தேன்", "ட்டேன்", "ன்னேன்", "tten", "then", "nden", "chen")
#: Words that mark a past or one-off statement: an amount then and an amount
#: now can both be true.
_PAST_WORDS = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "was were had did got went ran paid spent bought sold won lost made took gave "
        "came left grew fell rose drank ate ago yesterday last"
    ).split()
)
_MONTHS = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "january february march april may june july august september october november "
        "december jan feb mar apr jun jul aug sep sept oct nov dec"
    ).split()
)
#: Present-tense endings of Tamil and Tanglish verbs ("செய்கிறேன்", "odaren").
_TA_PRESENT_ENDINGS = (
    "கிறேன்",
    "கிறாள்",
    "கிறான்",
    "கிறார்",
    "கிறது",
    "கின்றேன்",
    "ren",
    "raen",
    "ran",
    "raan",
    "raanga",
    "ruven",
    "duven",
)
#: Roles one person holds at a time, for "Divya is my manager now".
_ONE_HOLDER_ROLES = frozenset(
    ("manager", "boss", "supervisor", "landlord", "landlady", "principal", "lead")
)
#: "my", "our", "the owner's" (apostrophes dropped), Tanglish "en", "enga".
_POSSESSIVES = frozenset(("my", "our", "owners", "en", "enga", "ennoda", "engaloda"))
#: Emphasis after the one chosen thing: "Coffee dhaan pidikkum".
_EMPHASIS = frozenset(("dhaan", "thaan", "than", "dhan", "தான்"))
#: Tamil and Tanglish "like" / "prefer" verbs.
_TA_LIKE = frozenset(
    ("pidikkum", "pudikkum", "pidikum", "pudikum", "பிடிக்கும்", "prefer", "prefers")
)
#: Verbs that hold many objects at once: "I speak English now" adds a
#: language, it does not replace one.
_MULTI_OBJECT_VERBS = frozenset(
    (  # noqa: SIM905 - a word list reads better as one string
        "speaks knows likes loves enjoys visits reads watches learns plays meets follows "
        "calls has owns eats drinks wants needs supports helps teaches sees writes takes "
        "buys gets makes does is was"
    ).split()
)
_NUMBER_TOKEN_RE = re.compile(r"\d+(?:[.,:/]\d+)*")
#: Words that join a purpose or a second thing to an object ("for scripts").
_JOINING_WORDS = frozenset(("for", "in", "at", "on", "with", "and", "or", "to", "from", "of"))


def _is_word_char(ch: str) -> bool:
    """A letter, a mark or a digit of any script (the D10 rule)."""
    return unicodedata.category(ch)[0] in "LMN"


def _expand_not(text: str) -> str:
    """English "n't" spelled out: "doesn't" → "does not", "won't" → "will not"."""
    text = re.sub(r"\bwon['’]?t\b", "will not", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcan['’]?t\b", "can not", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\w+)n['’]t\b", r"\1 not", text, flags=re.IGNORECASE)
    return re.sub(
        r"\b(do|does|did|is|are|was|were|has|have|had)nt\b", r"\1 not", text, flags=re.IGNORECASE
    )


def _d10_tokens(text: str) -> list[str]:
    """Lower-cased word tokens of any script, split on spaces and punctuation.

    The D10 rule (extraction/world_time.py ``tokens``): letters, marks and
    digits; digits and letters split ("Chennai-la" is "chennai", "la"; "10k"
    is "10", "k"). A number keeps its separators ("1,50,000", "7:30"), and
    an apostrophe is dropped ("owner's" is "owners").
    """
    folded = unicodedata.normalize("NFKC", text or "").lower()
    folded = folded.replace("'", "").replace("’", "")
    out: list[str] = []
    word: list[str] = []
    digit = False
    for i, ch in enumerate(folded):
        if _is_word_char(ch):
            is_digit = ch.isdigit()
            if word and is_digit != digit:
                out.append("".join(word))
                word = []
            word.append(ch)
            digit = is_digit
        elif ch in ".,:/" and word and digit and folded[i + 1 : i + 2].isdigit():
            word.append(ch)
        elif word:
            out.append("".join(word))
            word = []
    if word:
        out.append("".join(word))
    return out


def _content_tokens(text: str) -> list[str]:
    """``_d10_tokens`` without the words either side may add ("now")."""
    toks = _d10_tokens(text)
    out = [t for t in toks if t not in _CHANGE_FILLER]
    # "these days", "any more": two words, dropped together.
    for pair in (("these", "days"), ("any", "more")):
        out = _drop_pair(out, pair)
    return out


def _drop_pair(toks: list[str], pair: tuple[str, str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(toks):
        if tuple(toks[i : i + 2]) == pair:
            i += 2
            continue
        out.append(toks[i])
        i += 1
    return out


def _stem(word: str) -> str:
    """A rough English stem, so "eats", "eat" and "eating" compare equal.

    Only for words in Latin letters; other scripts are returned unchanged.
    Both sides get the same stem, so a stem that is not a real word is fine.
    """
    if not word.isascii() or not word.isalpha():
        return word
    if len(word) > 4 and word.endswith("ing"):
        word = word[:-3]
        if len(word) > 2 and word[-1] == word[-2]:
            word = word[:-1]  # running → run
    elif len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 3 and word.endswith("es") and word[:-2].endswith(("s", "sh", "ch", "x", "z")):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    if len(word) >= 3 and word.endswith("e"):
        word = word[:-1]
    return word


def _strip_negation(text: str) -> tuple[list[str], set[int], bool]:
    """The words of *text* with its negation taken out.

    Returns the words, the positions of verbs a Tamil or Tanglish negator
    was glued to or followed (compared by their start, see
    ``_same_statement``), and whether there was a negation at all. "The
    owner no longer eats meat" becomes "the owners eats meat"; "does not
    use", "use"; "stopped eating", "eating"; "காபி குடிப்பதில்லை", "காபி
    குடிப்ப" with that verb marked.
    """
    toks = _content_tokens(_expand_not(text))
    out: list[str] = []
    verbs: set[int] = set()
    negated = False
    i = 0
    while i < len(toks):
        tok, nxt = toks[i], toks[i + 1] if i + 1 < len(toks) else ""
        if tok == "not" or tok == "never":
            if tok == "not" and out and out[-1] in _NOT_AUX:
                out.pop()
            negated = True
        elif tok == "no" and nxt == "longer":
            negated = True
            i += 1
        elif tok in _STOP_VERBS and nxt.endswith("ing"):
            if out and out[-1] in ("has", "have", "had"):
                out.pop()
            negated = True
        elif tok in _TA_NEG_WORDS or tok in _TA_STOP_WORDS:
            if out:
                verbs.add(len(out) - 1)
            negated = True
        elif tok.endswith(_TA_NEG_SUFFIXES) and len(tok) > 6:
            suffix = next(s for s in _TA_NEG_SUFFIXES if tok.endswith(s))
            verbs.add(len(out))
            out.append(tok[: -len(suffix)])
            negated = True
        else:
            out.append(tok)
        i += 1
    return out, verbs, negated


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        n += 1
    return n


def _same_statement(neg: list[str], verbs: set[int], pos: list[str]) -> bool:
    """Whether the negated words *neg* say the same as the affirmed words *pos*.

    Every word must match, an English word by its stem. A Tamil or Tanglish
    verb the negation was glued to (*verbs*) may match by its first four
    letters instead ("குடிப்ப" / "குடிக்கிறேன்", "saapda" / "saapduven"),
    but at most one such word, never a past form ("குடித்தேன்", "I drank"),
    and at least one other word must match exactly.
    """
    if len(neg) < 2 or len(neg) != len(pos):
        return False
    loose = 0
    for i, (a, b) in enumerate(zip(neg, pos, strict=True)):
        if a == b or _stem(a) == _stem(b):
            continue
        if (
            i in verbs
            and not loose
            and _common_prefix(a, b) >= 4
            and not b.endswith(_TA_PAST_ENDINGS)
        ):
            loose += 1
            continue
        return False
    return True


def _check_cessation(new_text: str, existing_text: str) -> str | None:
    """One text is the other with a "not" in it: "no longer eats meat" /
    "eats meat", "does not use Jira" / "uses Jira", "stopped eating meat",
    "காபி குடிப்பதில்லை" / "காபி குடிக்கிறேன்", "meat saapda maatten" /
    "meat saapduven".

    Either side may be the negated one ("eats meat again" after "no longer
    eats meat"). Apart from the negation and filler ("now", "anymore") the
    words must be the same, so "I don't eat meat on Tuesdays" against "I
    eat meat" is not a hit: it is a narrower statement, not the opposite.
    """
    new_words, new_verbs, new_neg = _strip_negation(new_text)
    old_words, old_verbs, old_neg = _strip_negation(existing_text)
    if new_neg == old_neg:
        return None
    same = (
        _same_statement(new_words, new_verbs, old_words)
        if new_neg
        else _same_statement(old_words, old_verbs, new_words)
    )
    if not same:
        return None
    return f"Negation: '{existing_text.strip()[:60]}' → '{new_text.strip()[:60]}'"


def _one_change(old: list[str], new: list[str]) -> tuple[int, int, int, int] | None:
    """The one replaced run of words between *old* and *new*, at most three long."""
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    changed = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    if len(changed) != 1 or changed[0][0] != "replace":
        return None
    _, i1, i2, j1, j2 = changed[0]
    if i2 - i1 > _MAX_VALUE_TOKENS or j2 - j1 > _MAX_VALUE_TOKENS:
        return None
    return i1, i2, j1, j2


def _plain_pair(new_text: str, existing_text: str) -> tuple[list[str], list[str]] | None:
    """Both texts' content words, or None when either is negated or additive."""
    if any(_has_negator(t) or _strip_negation(t)[2] for t in (new_text, existing_text)):
        return None
    old, new = _content_tokens(existing_text), _content_tokens(new_text)
    if _ADDITIVE & (set(old) | set(new)) or _MULTI_VALUE & (set(old) | set(new)):
        return None
    return old, new


def _is_number(tok: str) -> bool:
    return _NUMBER_TOKEN_RE.fullmatch(tok) is not None


def _present_verb_cue(prefix: list[str], rest: list[str]) -> bool:
    """A present-tense verb: before the amount in English ("invests", "is",
    "has"), anywhere in Tamil or Tanglish, where the verb comes last
    ("செய்கிறேன்", "odaren")."""
    determiners = {"the", "a", "an", "my", "our", "his", "her", "their", "owners"}
    for i, tok in enumerate(prefix):
        if tok in ("is", "are", "am", "has", "have"):
            return True
        if (
            i > 0
            and tok.isascii()
            and len(tok) >= 4
            and tok.endswith("s")
            and not tok.endswith("ss")
            and prefix[i - 1] not in determiners
        ):
            return True
    return any(t.endswith(_TA_PRESENT_ENDINGS) and len(t) > 4 for t in rest)


def _check_amount_change(new_text: str, existing_text: str) -> str | None:
    """The same present-tense statement with one number replaced.

    "invests ₹10,000 a month in an index fund SIP" → "₹15,000", "runs 5 km
    on Mondays" → "8 km", "மாதம் ₹10,000 சேமிக்கிறேன்" → "₹15,000". Not a hit
    when the rest names another number or a month (a dated, one-off figure:
    "chapters 1 to 5"), when it is past ("scored 68%", "paid ₹500"), or when
    the number comes first, which is usually the subject ("Bus 21 goes").
    """
    pair = _plain_pair(new_text, existing_text)
    if pair is None:
        return None
    old, new = pair
    block = _one_change(old, new)
    if block is None:
        return None
    i1, i2, j1, j2 = block
    if i2 - i1 != 1 or j2 - j1 != 1 or not (_is_number(old[i1]) and _is_number(new[j1])):
        return None
    rest = old[:i1] + old[i2:]
    if len(rest) < 3 or i1 < 2 or any(_is_number(t) for t in rest):
        return None
    if any(t in _PAST_WORDS or t in _MONTHS for t in rest):
        return None
    if any(t.isascii() and len(t) > 4 and t.endswith("ed") for t in old[:i1]):
        return None
    if not _present_verb_cue(old[:i1], rest):
        return None
    return f"Value change: '{old[i1]}' → '{new[j1]}'"


def _names(text: str) -> set[str]:
    """Capitalised words of *text*, lower-cased: the names it carries."""
    return {w.lower() for w in _CAPITALISED_RE.findall(text) if w.lower() not in _NOT_DETAILS}


def _check_role_change(new_text: str, existing_text: str) -> str | None:
    """A different person in a one-holder role.

    "Suresh is my manager" → "Divya is my manager now", "Suresh is the
    owner's manager" → "Divya is the owner's manager", and the Tanglish "en
    manager Suresh" → "ippo en manager Divya dhaan". Only roles one person
    holds at a time (``_ONE_HOLDER_ROLES``), only names (capitalised words),
    and nothing else in the sentence: "Divya is my friend" or "Divya is my
    manager's wife" is not a hit. Tamil script has no capitals to tell a
    name, so it is not matched here. "My manager is Divya" is the copula
    value change above.
    """
    pair = _plain_pair(new_text, existing_text)
    if pair is None:
        return None
    old = [t for t in pair[0] if t not in _EMPHASIS]
    new = [t for t in pair[1] if t not in _EMPHASIS]
    block = _one_change(old, new)
    if block is None:
        return None
    i1, i2, j1, j2 = block
    rest = old[:i1] + old[i2:]
    was, now = old[i1:i2], new[j1:j2]
    if not set(was) <= _names(existing_text) or not set(now) <= _names(new_text):
        return None
    if set(was) & set(now):
        return None
    tail = [t for t in rest if t != "the"]
    subject_first = i1 == 0 and tail[:1] in (["is"], ["are"]) and tail[1:2] != []
    role_first = i2 == len(old) and j2 == len(new)
    shape = tail[1:] if subject_first else tail if role_first else []
    if len(shape) != 2 or shape[0] not in _POSSESSIVES or shape[1] not in _ONE_HOLDER_ROLES:
        return None
    return f"Value change: '{' '.join(was)}' → '{' '.join(now)}' as {shape[1]}"


def _check_object_change(new_text: str, existing_text: str) -> str | None:
    """The same verb with a different named object, said as a change.

    "The owner's team uses Jira for tickets" → "… uses Linear for tickets
    now". The new text must say it is a change ("now", "these days",
    "ippo", "இப்போது"), the verb must be present tense and hold one object
    at a time (not "speaks", "likes", "has": ``_MULTI_OBJECT_VERBS``), and
    both objects must be values (``_details``) the other text does not name.
    "I use Python for scripts" / "I use VS Code" has no change word and two
    changed places, so it is not a hit.
    """
    raw_new = _d10_tokens(new_text)
    if not set(raw_new) & _CHANGE_MARKERS and _drop_pair(raw_new, ("these", "days")) == raw_new:
        return None
    pair = _plain_pair(new_text, existing_text)
    if pair is None:
        return None
    old, new = pair
    block = _one_change(old, new)
    if block is None:
        return None
    i1, i2, j1, j2 = block
    if _JOINING_WORDS & set(old[i1:i2] + new[j1:j2]):
        return None  # "Python for scripts" → "VS Code": a purpose dropped, not swapped
    prefix = [t for t in old[:i1] if t not in ("a", "an", "the", "to", "in", "at", "on")]
    if len(prefix) < 2:
        return None
    verb = prefix[-1]
    if verb in _MULTI_OBJECT_VERBS or not (verb.isascii() and verb.endswith("s")):
        return None
    if verb.endswith("ss") or any(t in _PAST_WORDS for t in old):
        return None
    if _LIST_JOINERS & set(old[:i1][-1:]):
        return None
    if not _value_words(old[i1:i2], existing_text, set(new)) or not _value_words(
        new[j1:j2], new_text, set(old)
    ):
        return None
    return f"Value change: '{' '.join(old[i1:i2])}' → '{' '.join(new[j1:j2])}'"


def _check_ta_preference(new_text: str, existing_text: str) -> str | None:
    """Tamil and Tanglish "only X I like": "Tea dhaan pidikkum" → "Coffee dhaan
    pidikkum", "எனக்கு டீ தான் பிடிக்கும்" → "காபி தான் பிடிக்கும்".

    The emphasis word ("dhaan", "தான்") right after the thing makes it the
    one choice, like English "prefer". Plain "pidikkum" (I like it) is not
    exclusive, so it is not a hit.
    """
    pair = _plain_pair(new_text, existing_text)
    if pair is None:
        return None
    old, new = pair
    block = _one_change(old, new)
    if block is None:
        return None
    i1, i2, j1, j2 = block
    after = old[i2:]
    if not after or after[0] not in _EMPHASIS or not set(after[1:]) & _TA_LIKE:
        return None
    if set(old[i1:i2]) & set(new[j1:j2]):
        return None
    return f"Entity swap: '{' '.join(old[i1:i2])}' → '{' '.join(new[j1:j2])}'"


def _check_more_changes(new_text: str, existing_text: str) -> tuple[str, str] | None:
    """The 2026-11-28 rules, in order; (conflict_type, reason) or None.

    Called only with ``settings.ingest_supersession_tiers`` on.
    """
    if reason := _check_cessation(new_text, existing_text):
        return "negation", reason
    if reason := _check_ta_preference(new_text, existing_text):
        return "preference_change", reason
    for rule in (_check_amount_change, _check_role_change, _check_object_change):
        if reason := rule(new_text, existing_text):
            return "value_change", reason
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
    return _scope_difference(memory.properties or {}, new_properties or {})


def differs_in_scope(
    props_a: dict[str, Any] | None,
    props_b: dict[str, Any] | None,
) -> bool:
    """Whether two memories' properties name a different project or module.

    MemoryManager asks this before its near-duplicate merge (2026-11-25):
    "We prefer pytest" for project alpha and "We prefer unittest" for
    project beta are both true, and merging them kept one. Merging a scoped
    fact into an unscoped one would also copy the scope onto it. Same rule
    as the contradiction detector's scope check: a project or module on
    either side that the other does not share.
    """
    return _scope_difference(props_a or {}, props_b or {}) is not None


def _scope_difference(old_props: dict[str, Any], new_props: dict[str, Any]) -> str | None:
    """The project/module values that differ, as text, or None."""
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
        - negation / preference_change / value_change: supersede (newer
          wins — applied only once the owner approves, see
          MemoryManager._process_fact)
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
    if conflict_type in ("negation", "preference_change", "value_change"):
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
