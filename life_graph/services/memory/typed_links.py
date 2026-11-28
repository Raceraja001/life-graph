"""Typed links between the facts of one message, made at extraction (M8 ADR §5.3).

When the owner says "I moved to Supabase because Firebase got too expensive, so I
rewrote the sync service", the extractor returns three facts and already knows
how two pairs relate. This module turns that into ``memory_links`` rows the
context snapshot reads as ``relations`` (services/memory/snapshot.py):

- **BECAUSE**: fact A has a ``reason`` (the extractor's existing field) and
  another fact B of the same message says that reason. A match is at least
  :data:`BECAUSE_MIN_OVERLAP` of the reason's content words found in B
  (Tamil-safe tokens). The link is A -> B.
- **LEADS_TO**: the model proposed it (the optional ``leads_to`` field, resolved
  to the target fact in extraction/llm.py) **and** the owner's words hold an
  explicit sequence or result cue ("so", "therefore", "then", ``அதனால்``,
  "adhanala", "apram"). A proposal without a cue, or a cue without a
  proposal, makes nothing. The link is A -> B.

Rules, all deterministic:
- Only facts of **one message** are linked: a proposal that names a fact not in
  the message is refused. Only memories **stored new** by this message take
  part: a fact that matched an existing memory (an exact or near duplicate,
  maybe the owner's own from earlier) is never linked, so outside text cannot
  attach a link to the owner's facts. Both ends must also carry the same trust
  tier.
- No similarity links: ``RELATED_TO`` is not written, and
  ``links.auto_link_memories`` stays unwired.
- Each link has ``properties.why`` starting with :data:`WHY_PREFIX`, so a
  rollback can delete exactly these rows (``properties->>'why' LIKE
  'extraction:%'``), and ``strength`` = the lower confidence of the two facts.
- Written through ``links.create_link``, which checks both ends are the
  tenant's. A link says how two records relate, never that either is true: it
  changes no status.
- No model call here. Behind ``settings.ingest_typed_links`` (default off), read
  by the caller (core/memory_manager.py).
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from life_graph.core.errors import ConflictError
from life_graph.core.evidence import _NEGATIONS, _STOPWORDS
from life_graph.services.memory import links

if TYPE_CHECKING:
    from collections.abc import Iterable

    from life_graph.extraction.rules import ExtractedFact

logger = logging.getLogger(__name__)

#: Every link written here has ``properties.why`` starting with this (rollback key).
WHY_PREFIX = "extraction:"
BECAUSE = "BECAUSE"
LEADS_TO = "LEADS_TO"
#: Share of the reason's content words another fact must contain to be the reason.
BECAUSE_MIN_OVERLAP = 0.6
#: Most LEADS_TO targets read from one fact's proposal.
MAX_LEADS_TO = 3

#: Words every extracted sentence shares ("The owner ..."): never evidence of a match.
_FRAME = frozenset({"owner", "owners", "user", "users"})

#: Sequence or result cues, as token runs (lower-case, apostrophes dropped:
#: "that's why" is ("thats", "why")). English and Tanglish.
_CUE_RUNS: tuple[tuple[str, ...], ...] = (
    ("so",),
    ("therefore",),
    ("thus",),
    ("hence",),
    ("then",),
    ("after", "that"),
    ("afterwards",),
    ("as", "a", "result"),
    ("which", "is", "why"),
    ("thats", "why"),
    ("that", "is", "why"),
    ("because", "of", "that"),
    ("because", "of", "this"),
    # Tanglish ("adhanala" = so/therefore, "apram" = then/after that).
    ("adhanala",),
    ("adhanaala",),
    ("athanala",),
    ("athanaala",),
    ("adhunala",),
    ("athunala",),
    ("adhanal",),
    ("athanal",),
    ("apram",),
    ("appram",),
    ("aprom",),
    ("apparam",),
    ("appuram",),
    ("apuram",),
    ("piragu",),
    ("pirahu",),
)
#: Tamil cues, matched as the start of a token so case endings still match
#: (அதனால், அதனாலே; அப்புறம், அப்புறமா). The owner reviews this list.
_TAMIL_CUE_STEMS: tuple[str, ...] = (
    "அதனால",  # so, therefore
    "ஆதலால",  # therefore
    "ஆகையால",  # therefore
    "எனவே",  # so
    "ஆகவே",  # so
    "அப்புறம",  # then, after that
    "அப்பறம",  # then (spoken)
    "பிறகு",  # after that
    "அதன்பிறகு",  # after that
)


def _is_word_char(ch: str) -> bool:
    """A letter, a mark or a digit of any script: Tamil vowel signs are marks."""
    return unicodedata.category(ch)[0] in "LMN"


def tokens(text: str) -> list[str]:
    """Lower-case word tokens of any script, split on whitespace and punctuation.

    A ``\\w`` split broke Tamil words at their vowel signs (audit D10); this
    keeps letters and marks together.
    """
    folded = unicodedata.normalize("NFKC", text or "").lower()
    folded = folded.replace("'", "").replace("’", "")
    out: list[str] = []
    word: list[str] = []
    for ch in folded + " ":
        if _is_word_char(ch):
            word.append(ch)
        elif word:
            out.append("".join(word))
            word = []
    return out


def _stem(word: str) -> str:
    """A plain English plural or third-person "s" dropped ("costs" -> "cost")."""
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss") and word.isascii():
        return word[:-1]
    return word


def content_words(text: str) -> frozenset[str]:
    """The words that carry the claim: no function words, no "not", no "owner"."""
    return frozenset(
        _stem(w)
        for w in tokens(text)
        if w not in _STOPWORDS and w not in _NEGATIONS and w not in _FRAME
        if len(w) > 1 or w.isdigit()
    )


def reason_overlap(reason: str, content: str) -> float:
    """Share of *reason*'s content words found in *content* (0.0 when it has none)."""
    wanted = content_words(reason)
    if not wanted:
        return 0.0
    return len(wanted & content_words(content)) / len(wanted)


def sequence_cue(text: str) -> str | None:
    """The first sequence or result cue in *text* ("so", "அதனால்", "apram"), else None."""
    words = tokens(text)
    for i, word in enumerate(words):
        for stem in _TAMIL_CUE_STEMS:
            if word.startswith(stem):
                return word
        for run in _CUE_RUNS:
            if tuple(words[i : i + len(run)]) == run:
                return " ".join(run)
    return None


def _key(content: str) -> str:
    """The same key the pipeline dedups facts by (extraction/pipeline.py)."""
    return (content or "").strip().lower()


@dataclass(frozen=True)
class Proposed:
    """One link a rule found, by position in the message's fact list."""

    source: int
    target: int
    link_type: str
    strength: float
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class Outcome:
    """What one message's facts gave: the links found, and the model proposals refused."""

    proposed: list[Proposed] = field(default_factory=list)
    #: (source index, why): a leads_to naming no other fact of this message,
    #: or with no cue in the owner's words.
    refused: list[tuple[int, str]] = field(default_factory=list)


def _because(facts: list[ExtractedFact], i: int) -> Proposed | None:
    """A -> B for the one other fact B that best says A's reason, if it says enough."""
    reason = facts[i].reason
    if not reason:
        return None
    best: tuple[float, int] | None = None
    for j, other in enumerate(facts):
        if j == i or _key(other.content) == _key(facts[i].content):
            continue
        score = reason_overlap(reason, other.content)
        if score >= BECAUSE_MIN_OVERLAP and (best is None or score > best[0]):
            best = (score, j)
    if best is None:
        return None
    score, j = best
    return Proposed(
        source=i,
        target=j,
        link_type=BECAUSE,
        strength=min(facts[i].confidence, facts[j].confidence),
        properties={"why": f"{WHY_PREFIX}because", "overlap": round(score, 2)},
    )


def _leads_to(facts: list[ExtractedFact], i: int, outcome: Outcome) -> list[Proposed]:
    """A -> B for each B the model proposed, when the owner's words hold a cue."""
    targets = [t for t in (facts[i].leads_to or []) if t][:MAX_LEADS_TO]
    if not targets:
        return []
    cue = sequence_cue(facts[i].source_text)
    if cue is None:
        outcome.refused.append((i, "no sequence cue in the text"))
        return []
    by_key = {_key(f.content): j for j, f in enumerate(facts)}
    found: list[Proposed] = []
    for target in targets:
        j = by_key.get(_key(target))
        if j is None or j == i:
            # The model named a fact this message did not keep (or itself):
            # links stay inside one message.
            outcome.refused.append((i, "target is not another fact of this message"))
            continue
        found.append(
            Proposed(
                source=i,
                target=j,
                link_type=LEADS_TO,
                strength=min(facts[i].confidence, facts[j].confidence),
                properties={"why": f"{WHY_PREFIX}leads_to", "cue": cue},
            )
        )
    return found


def propose(facts: list[ExtractedFact]) -> Outcome:
    """The typed links between *facts*, all from one message. Pure: no I/O."""
    outcome = Outcome()
    seen: set[tuple[int, int, str]] = set()
    for i in range(len(facts)):
        found = [p for p in [_because(facts, i)] if p] + _leads_to(facts, i, outcome)
        for p in found:
            if (p.source, p.target, p.link_type) not in seen:
                seen.add((p.source, p.target, p.link_type))
                outcome.proposed.append(p)
    return outcome


async def link_message(
    tenant_id: str,
    stored: Iterable[tuple[ExtractedFact, Any]],
    new_ids: set[Any],
) -> int:
    """Write the typed links between the facts one message stored. Best-effort.

    *stored* pairs each fact with the memory it became; *new_ids* are the ids
    of the memories this message created. A fact that became an existing
    memory (a duplicate merged or reused) takes no part, nor does a memory of
    another trust tier than the rest. Returns how many links were written; a
    failure is logged and never costs the save.
    """
    kept = [
        (fact, memory)
        for fact, memory in stored
        if memory is not None and getattr(memory, "id", None) in new_ids
    ]
    tiers = {getattr(memory, "trust_tier", None) for _, memory in kept}
    if len(kept) < 2 or len(tiers) != 1:
        return 0
    outcome = propose([fact for fact, _ in kept])
    for index, why in outcome.refused:
        logger.info("Typed link refused for memory %s: %s", kept[index][1].id, why)
    written = 0
    for p in outcome.proposed:
        source, target = kept[p.source][1].id, kept[p.target][1].id
        if source == target:  # two facts merged into one memory
            continue
        try:
            await links.create_link(
                source,
                target,
                p.link_type,
                strength=p.strength,
                properties=p.properties,
                tenant_id=tenant_id,
            )
            written += 1
        except ConflictError:
            continue
        except Exception:  # noqa: BLE001 — a link is a bonus; the memories are saved
            logger.warning("Typed link %s failed", p.link_type, exc_info=True)
    return written
