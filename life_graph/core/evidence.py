"""Where a memory's content came from: the owner's words, a document, or a guess.

Trust tier (core/trust.py) answers "may an agent act on this?"; evidence
answers "should Jarvis state this as fact?". The two differ: a day summary is
trusted (our own pipeline) but is not something the owner said, and a
distilled "the owner seems to prefer short answers" is trusted yet is still
only a guess.

Until 2026-10-29 the two were blurred by a default: a memory stored without a
source got ``source_type="inferred"``, so 13 of 15 production memories labelled
"inferred" were in fact the owner's own notes and test strings sent over the
API, and the real guesses (failure_mining) carried the same label.

Pure policy: no DB, no I/O. ``evidence_of`` is computed at write time
(PostgresMemoryStore.store puts it in ``properties["evidence"]``) and on read
for rows written before that.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

SAID = "said"  # the owner's own words, through a first-party surface
DOCUMENT = "document"  # read from one of the owner's documents
OBSERVED = "observed"  # recorded by Life Graph's own systems (scans, agent results)
INFERRED = "inferred"  # Jarvis's conclusion, not something anyone said
SUMMARY = "summary"  # a summary of a day's conversations (services/episodes.py)
OUTSIDE = "outside"  # arrived over MCP, the API or the web: origin not vouched for

KINDS = (SAID, DOCUMENT, OBSERVED, INFERRED, SUMMARY, OUTSIDE)

#: Sources whose memories are conclusions drawn by Life Graph itself.
INFERRED_SOURCES = frozenset(
    {
        "distillation",
        "failure_mining",
        "self_improving",
        "belief_challenge",
        "consolidation",
        "metamemory",
        "derived",
    }
)

#: What a memory stored without a source is labelled (was "inferred").
UNKNOWN_SOURCE = "unknown"


def evidence_of(
    source_type: str | None,
    trust_tier: str | None,
    properties: Mapping[str, Any] | None = None,
) -> str:
    """The evidence kind of a memory, from what its row already records."""
    props = properties or {}
    stamped = props.get("evidence")
    if stamped in KINDS:
        return stamped
    source = (source_type or "").lower()
    if props.get("kind") == "episode" or source == "episode":
        return SUMMARY
    if source in INFERRED_SOURCES or props.get("inferred_from"):
        return INFERRED
    if source == "inferred":
        # The old default for "no source given": a guess only when our own
        # pipeline wrote it (failure_mining sets it on purpose, tier verified);
        # over the API it meant nothing more than "unlabelled".
        return INFERRED if trust_tier in ("self", "verified") else OUTSIDE
    if source == "document":
        # The source is declared by the caller: over the API or MCP anyone can
        # say "document". Only our own pipeline's word counts; otherwise a
        # pasted web page would be filed as the owner's paperwork and reach
        # the always-loaded profile card (services/profile_card.py).
        return DOCUMENT if trust_tier in ("self", "verified") else OUTSIDE
    if trust_tier == "self":
        return SAID
    if trust_tier == "verified":
        return OBSERVED
    return OUTSIDE


def is_guess(evidence: str) -> bool:
    """True when Jarvis must present the memory as a guess, not a fact."""
    return evidence in (INFERRED, OUTSIDE)


#: How a memory is introduced to the model in the "what you remember" block.
PROMPT_LABEL = {
    SAID: "owner said",
    DOCUMENT: "from a document",
    OBSERVED: "observed",
    INFERRED: "your guess",
    SUMMARY: "day summary",
    OUTSIDE: "unverified",
}
