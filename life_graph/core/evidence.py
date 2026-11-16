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

The owner boundary (2026-11-14). The stamp is server-side provenance, but
``PATCH /memories/{id}`` takes a whole ``properties`` object from the caller,
so an MCP client or a watcher could send ``{"evidence": "said"}`` and have its
own page text read back as the owner's word on the always-loaded profile card
(services/profile_card.py). So a stamp is now only honoured when it is no
stronger than what the row's own ``source_type`` and ``trust_tier`` derive
(:func:`derive_evidence`): a stamp may be more careful than the provenance,
never more confident. :func:`may_state_as_owner_truth` is the one gate every
"is this the owner's own fact?" caller asks, and OUTSIDE content passes it
only after the owner said so themselves (:func:`confirm_from_owner`).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

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


#: How much a kind lets Jarvis claim, highest first. Used to refuse a stamp
#: that claims more than the row's own provenance earns (see the module note).
AUTHORITY = {SAID: 4, DOCUMENT: 4, OBSERVED: 3, SUMMARY: 2, INFERRED: 1, OUTSIDE: 0}

#: The kinds that are the owner's own account of their life. The profile card
#: and the owner's form are built from these and nothing else.
OWNER_KINDS = frozenset({SAID, DOCUMENT})

#: ``properties`` keys that are server-side provenance: a caller that could
#: write them could promote its own text to the owner's word. Kept out of
#: every client-supplied patch (:func:`merge_client_properties`).
SERVER_ONLY_PROPS = ("evidence", "owner_confirmed", "lineage")

#: Where in ``properties`` an explicit owner confirmation is recorded.
OWNER_CONFIRMED = "owner_confirmed"


def derive_evidence(
    source_type: str | None,
    trust_tier: str | None,
    properties: Mapping[str, Any] | None = None,
) -> str:
    """The evidence kind the row's own provenance earns, ignoring any stamp."""
    props = properties or {}
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


def evidence_of(
    source_type: str | None,
    trust_tier: str | None,
    properties: Mapping[str, Any] | None = None,
) -> str:
    """The evidence kind of a memory, from what its row already records.

    A stamped ``properties["evidence"]`` is honoured only while it claims no
    more than :func:`derive_evidence` does from the row's own provenance: the
    stamp is written server-side at store time, but ``properties`` as a whole
    is patchable by whoever can call the API, and "said" is the one label that
    puts a memory in front of every answer.
    """
    props = properties or {}
    derived = derive_evidence(source_type, trust_tier, props)
    stamped = props.get("evidence")
    if stamped in KINDS and AUTHORITY[stamped] <= AUTHORITY[derived]:
        return stamped
    return derived


def owner_confirmed(properties: Mapping[str, Any] | None = None) -> bool:
    """True when the owner themselves kept this memory (:func:`confirm_from_owner`).

    Only the server's own record counts — a mapping naming who confirmed. A
    bare ``True`` is not a confirmation: it is the shape a client would guess
    at, and the mark exists to say *who* decided. ``by`` is read as well as
    ``actor`` because rows stamped before the record grew its audit fields
    carry only the old name.
    """
    mark = (properties or {}).get(OWNER_CONFIRMED)
    if not isinstance(mark, Mapping):
        return False
    return bool(mark.get("actor") or mark.get("by"))


def confirm_from_owner(
    properties: Mapping[str, Any] | None = None,
    *,
    by: str,
    at: datetime | None = None,
    target_id: str | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """*properties* with the owner's explicit confirmation recorded.

    Only the server calls this, and only from the path where a person acted —
    an owner-authenticated approve of a pending memory
    (api/memories.py ``approve_memory``, which refuses the request outright
    when the ingress is not the owner's). It is what lets outside-origin
    content be stated as the owner's own fact, so the record it writes is an
    audit record and not a flag:

    * ``actor`` — how the server recognised the caller (``device:<id>``,
      ``owner:api_key``), so a wrong card entry can be traced back to a
      credential rather than to the word "owner".
    * ``confirmed_at`` — when, in UTC.
    * ``target_id`` — what was confirmed, so the record stands alone if it is
      ever copied out of the row.
    * ``evidence`` — what the owner was actually looking at: the row's
      provenance and a hash of the exact text. A later edit to the content no
      longer matches the hash, which is the difference between "the owner
      confirmed something" and "the owner confirmed *this*".
    """
    if not by or not str(by).strip():
        raise ValueError("owner confirmation needs who confirmed it")
    when = at or datetime.now(UTC)
    record: dict[str, Any] = {
        "actor": str(by).strip()[:120],
        "confirmed_at": when.isoformat(),
    }
    if target_id is not None:
        record["target_id"] = str(target_id)[:120]
    if evidence is not None:
        record["evidence"] = dict(evidence)
    return {**dict(properties or {}), OWNER_CONFIRMED: record}


def confirmation_evidence(
    content: str | None,
    source_type: str | None,
    trust_tier: str | None,
    properties: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """What a memory's own row says, for :func:`confirm_from_owner`'s record.

    The content is hashed, not copied: the record has to be able to say
    *which* text the owner read without becoming a second copy of it.
    """
    text = content or ""
    return {
        "source_type": source_type,
        "trust_tier": trust_tier,
        "evidence_kind": evidence_of(source_type, trust_tier, properties),
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "content_chars": len(text),
    }


def may_state_as_owner_truth(
    source_type: str | None,
    trust_tier: str | None,
    properties: Mapping[str, Any] | None = None,
) -> bool:
    """True when a memory may be stated as the owner's own, lasting fact.

    The learn-only-from-owner boundary. A web page, an email or an external
    MCP write is content Jarvis *read*, not something the owner told it, so it
    never becomes who the owner is on its own — however the text labels
    itself. The owner can still keep such a memory by hand
    (:func:`confirm_from_owner`); that decision is theirs, not the page's.
    """
    props = properties or {}
    from life_graph.core.trust import is_excluded_from_agents, is_untrusted

    if is_excluded_from_agents(trust_tier):
        # Written by someone else outright (a forwarded message): trust.py
        # keeps it out of every acting agent's packet, so it certainly does
        # not become who the owner is. Not even the owner's own confirmation
        # moves this one — they can retype the fact instead.
        return False
    if owner_confirmed(props):
        return True
    if is_untrusted(trust_tier):
        # Second gate, independent of the stamp: an untrusted-origin row is
        # not the owner's word even if its derived kind somehow says so.
        return False
    return evidence_of(source_type, trust_tier, props) in OWNER_KINDS


def merge_client_properties(
    existing: Mapping[str, Any] | None,
    incoming: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """*incoming* properties with server-side provenance kept from *existing*.

    A client patching ``properties`` replaces the whole object, which would
    drop — or forge — the provenance the server stamped at store time. The
    caller's own keys are taken as given; :data:`SERVER_ONLY_PROPS` are not.
    """
    out = dict(incoming or {})
    for key in SERVER_ONLY_PROPS:
        out.pop(key, None)
        if existing and key in existing:
            out[key] = existing[key]
    return out


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


def _clean_str(value: Any, *, max_len: int = 240) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:max_len] if text else None


def normalize_lineage(
    properties: Mapping[str, Any] | None = None,
    *,
    capture_event_id: Any = None,
    source_type: str | None = None,
    supersedes: Any = None,
) -> dict[str, Any]:
    """Normalize source, extraction, span, and derivation lineage into a bounded dict."""
    props = dict(properties or {})
    raw_lineage = props.get("lineage")
    base = dict(raw_lineage) if isinstance(raw_lineage, dict) else {}

    cap_id = capture_event_id or base.get("capture_event_id") or props.get("capture_event_id")
    trace_id = base.get("extraction_trace_id") or props.get("extraction_trace_id")
    fact_idx = base.get("extraction_fact_index", props.get("extraction_fact_index"))
    if not isinstance(fact_idx, int) or isinstance(fact_idx, bool) or fact_idx < 0:
        fact_idx = None

    excerpt = _clean_str(base.get("excerpt") or props.get("source_excerpt") or props.get("excerpt"))
    location = base.get("location") or props.get("source_location") or props.get("source_span")
    if not isinstance(location, dict):
        location = {"ref": _clean_str(location)} if _clean_str(location) else None

    raw_derived = (
        base.get("derived_from") or props.get("derived_from") or props.get("inferred_from")
    )
    derived_from: list[str] = []
    if isinstance(raw_derived, (list, tuple)):
        derived_from = [str(x) for x in raw_derived if x is not None and str(x).strip()]
    elif raw_derived is not None and str(raw_derived).strip():
        derived_from = [str(raw_derived).strip()]

    lineage: dict[str, Any] = {
        "source_type": _clean_str(base.get("source_type") or source_type, max_len=64),
        "capture_event_id": str(cap_id) if cap_id is not None and str(cap_id).strip() else None,
        "extraction_trace_id": str(trace_id)
        if trace_id is not None and str(trace_id).strip()
        else None,
        "extraction_fact_index": fact_idx,
        "excerpt": excerpt,
        "location": location,
        "derived_from": derived_from,
        "supersedes": str(supersedes or base.get("supersedes"))
        if (supersedes or base.get("supersedes"))
        else None,
    }
    return {k: v for k, v in lineage.items() if v not in (None, [], {})}


def resolve_memory_lineage(
    memory: Any,
    *,
    source_available: bool = True,
    ancestors: list[Any] | None = None,
) -> dict[str, Any]:
    """Resolve a memory's origin, extraction trace, span, and derivation ancestry without fabricating."""
    if isinstance(memory, dict):
        mid = memory.get("id")
        props = memory.get("properties") or {}
        source_type = memory.get("source_type")
        trust_tier = memory.get("trust_tier")
        cap_id = memory.get("capture_event_id")
        supersedes = memory.get("supersedes")
    else:
        mid = getattr(memory, "id", None)
        props = getattr(memory, "properties", None) or {}
        source_type = getattr(memory, "source_type", None)
        trust_tier = getattr(memory, "trust_tier", None)
        cap_id = getattr(memory, "capture_event_id", None)
        supersedes = getattr(memory, "supersedes", None)

    ev_kind = evidence_of(source_type, trust_tier, props if isinstance(props, dict) else {})
    lineage = normalize_lineage(
        props if isinstance(props, dict) else {},
        capture_event_id=cap_id,
        source_type=source_type,
        supersedes=supersedes,
    )
    ancestry = [
        str(a.get("id") if isinstance(a, dict) else getattr(a, "id", a))
        for a in (ancestors or [])
        if a is not None
    ]
    has_source = bool(
        lineage.get("capture_event_id")
        or lineage.get("extraction_trace_id")
        or lineage.get("excerpt")
        or lineage.get("location")
        or lineage.get("derived_from")
    )
    return {
        "memory_id": str(mid) if mid is not None else None,
        "evidence_kind": ev_kind,
        "source_available": bool(source_available) if has_source else False,
        "lineage": lineage,
        "ancestry": ancestry,
    }


# ── Claim support (5.2) ───────────────────────────────────────────────────
#
# A ``[Memory 3]`` marker is a pointer, not a proof. The local model writes
# those markers while synthesizing an answer, and it mis-attributes: it will
# cite the memory it was *looking at* rather than the one that carries the
# fact, so "You live in London [Memory 1]" can arrive with Memory 1 reading
# "likes painting". Treating the marker as support is what lets an answer
# claim a citation it does not have. Every citation is therefore checked
# against the cited text before it counts.

#: The citation entails the claim: the cited text actually says it.
SUPPORTED = "supported"
#: The cited text asserts something incompatible with the claim.
CONTRADICTED = "contradicted"
#: The cited text is about something else; the marker proves nothing.
UNSUPPORTED = "unsupported"
#: The citation points at nothing we can read — out of range, or a tombstone.
UNRESOLVED_SOURCE = "unresolved_source"
#: The citation resolves, but carries no text to compare, so entailment was
#: never assessed. Related, not proof — reported honestly rather than as support.
CONTEXT = "context"

#: Worst-first. A claim takes the most severe status among its citations: one
#: good citation must not launder a contradicted or unresolvable co-citation.
_STATUS_SEVERITY = (CONTRADICTED, UNRESOLVED_SOURCE, UNSUPPORTED, CONTEXT, SUPPORTED)

#: Statuses that let a claim stand. ``CONTEXT`` is included because an
#: unreadable-but-present source is a gap in *our* records, not a false claim;
#: the confidence breakdown still reports it.
_STANDS = frozenset({SUPPORTED, CONTEXT})

#: Overlap at or above this counts as the cited text saying the claim.
ENTAILMENT_THRESHOLD = 0.45
#: Below this the two texts share nothing, so a value conflict between them is
#: coincidence rather than contradiction (a claim about an idea and a memory
#: about a job both match the "is a …" frame without disagreeing).
_CONTRADICTION_FLOOR = 0.25

#: Function words, plus the auxiliaries that make negation work ("does not"),
#: so overlap is measured on the words that carry the claim.
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "this",
        "that",
        "these",
        "those",
        "there",
        "here",
        "and",
        "or",
        "but",
        "if",
        "then",
        "else",
        "so",
        "as",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "from",
        "by",
        "with",
        "about",
        "into",
        "over",
        "under",
        "between",
        "during",
        "within",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "do",
        "does",
        "did",
        "done",
        "has",
        "have",
        "had",
        "having",
        "will",
        "would",
        "shall",
        "should",
        "can",
        "could",
        "may",
        "might",
        "must",
        "i",
        "me",
        "my",
        "mine",
        "you",
        "your",
        "yours",
        "he",
        "him",
        "his",
        "she",
        "her",
        "hers",
        "it",
        "its",
        "we",
        "us",
        "our",
        "ours",
        "they",
        "them",
        "their",
        "theirs",
        "who",
        "whom",
        "whose",
        "which",
        "what",
        "when",
        "where",
        "why",
        "how",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "only",
        "own",
        "same",
        "than",
        "too",
        "very",
        "just",
        "now",
        "also",
        "still",
        "really",
        "quite",
        "s",
        "t",
    ]
)

#: Polarity markers. Dropped from the content tokens (so "drinks coffee" and
#: "does not drink coffee" overlap fully) and compared separately.
_NEGATIONS = frozenset(
    [
        "not",
        "no",
        "never",
        "none",
        "cannot",
        "cant",
        "dont",
        "doesnt",
        "didnt",
        "isnt",
        "arent",
        "wasnt",
        "werent",
        "wont",
        "havent",
        "hasnt",
        "hadnt",
        "nor",
        "neither",
        "nothing",
        "nowhere",
        "without",
        "nope",
    ]
)

#: Whatever follows a frame's verb, up to the end of the clause.
_FRAME_TAIL = r"([a-z0-9 ,'&./-]+)"

#: Single-valued predicate frames. When the claim and the cited text both fill
#: the same frame with values that share nothing, they are not merely failing
#: to overlap — they disagree, and the claim is contradicted.
_FRAMES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "location",
        re.compile(
            r"\b(?:lives?|living|lived|resides?|residing|based|located|stays?|staying)\s+(?:in|at)\s+"
            + _FRAME_TAIL
        ),
    ),
    ("employer", re.compile(r"\b(?:works?|working|worked|employed)\s+(?:at|for)\s+" + _FRAME_TAIL)),
    ("preference", re.compile(r"\b(?:prefers?|preferred|favours?|favors?)\s+" + _FRAME_TAIL)),
    (
        "tool",
        re.compile(
            r"\b(?:uses?|using|used|owns?|owned|drives?|runs?)\s+(?:a|an|the)?\s*" + _FRAME_TAIL
        ),
    ),
    ("role", re.compile(r"\b(?:is|was|am|are)\s+(?:a|an|the)\s+" + _FRAME_TAIL)),
    ("branch", re.compile(r"\b(?:on\s+branch|branch)\s+" + _FRAME_TAIL)),
)

#: Antonym pairs whose presence across claim and source indicates direct state contradiction.
_ANTONYM_PAIRS: tuple[tuple[str, str], ...] = (
    ("activ", "inactiv"),
    ("runn", "stopp"),
    ("enabl", "disabl"),
    ("fre", "paid"),
    ("onlin", "offlin"),
    ("open", "clos"),
    ("succes", "failur"),
)


def _has_antonym_conflict(claim_tokens: set[str], source_tokens: set[str]) -> str | None:
    for a, b in _ANTONYM_PAIRS:
        if (a in claim_tokens and b in source_tokens) or (b in claim_tokens and a in source_tokens):
            return f"{a}_vs_{b}"
    return None


def _stem(word: str) -> str:
    """Crude suffix strip so "lives"/"living"/"lived" meet at "liv"-ish forms.

    Deliberately not a real stemmer: it only has to make plural and simple
    verb inflections of the *same* word match, and must never merge two
    different words (hence the length floors).
    """
    for suffix, floor in (("ing", 6), ("ies", 5), ("ed", 5), ("s", 4)):
        if len(word) >= floor and word.endswith(suffix):
            word = word[: -len(suffix)] + ("y" if suffix == "ies" else "")
            break
    # One more pass so the whole family lands on one form: "live", "lives"
    # ("liv" + "e" after the "s" came off) and "living" all become "liv".
    return word[:-1] if len(word) >= 4 and word.endswith("e") else word


def _normalize_text(text: str) -> str:
    return (text or "").replace("'", "").replace("’", "").lower()


def _content_tokens(text: str) -> set[str]:
    """The claim-bearing words of *text*, stemmed; function and polarity words out."""
    words = re.findall(r"[a-z0-9]+", _normalize_text(text))
    return {
        _stem(w)
        for w in words
        if w not in _STOPWORDS and w not in _NEGATIONS and (len(w) > 1 or w.isdigit())
    }


def _is_negated(text: str) -> bool:
    norm = _normalize_text(text)
    if "no longer" in norm or "used to" in norm:
        return True
    return bool(_NEGATIONS & set(re.findall(r"[a-z]+", norm)))


def _frame_conflict(claim: str, source: str) -> str | None:
    """The name of a predicate frame both texts fill with disjoint values, if any."""
    for name, pattern in _FRAMES:
        claim_match = pattern.search(_normalize_text(claim))
        source_match = pattern.search(_normalize_text(source))
        if not (claim_match and source_match):
            continue
        claim_val = _content_tokens(claim_match.group(1))
        source_val = _content_tokens(source_match.group(1))
        if claim_val and source_val and not (claim_val & source_val):
            return name
    return None


def lexical_entailment_score(claim: str, source: str) -> float:
    """How much of *claim*'s content the *source* text actually accounts for, 0–1.

    The default entailment signal: a share of the claim's content words found
    in the cited text. It is a proxy, not a judgement about meaning — pass a
    ``scorer`` to :func:`verify_claim_support` to put a real entailment model
    (or an embedding similarity) in front of it.
    """
    claim_tokens = _content_tokens(claim)
    source_tokens = _content_tokens(source)
    if not claim_tokens or not source_tokens:
        return 0.0
    return round(len(claim_tokens & source_tokens) / len(claim_tokens), 4)


def citation_text(memory: Any) -> str:
    """Everything of a cited memory we are allowed to check a claim against.

    The memory's own content first, then the preserved source span: a memory
    distilled down to a short statement keeps the words it came from in
    ``properties["source_excerpt"]`` (:func:`normalize_lineage`), and that span
    is often the only text that carries the fact.
    """
    if memory is None:
        return ""
    get = (
        (lambda k: memory.get(k))
        if isinstance(memory, dict)
        else (lambda k: getattr(memory, k, None))
    )
    props = get("properties") or {}
    if not isinstance(props, dict):
        props = {}
    lineage = props.get("lineage") if isinstance(props.get("lineage"), dict) else {}
    parts = [
        get("content"),
        get("summary"),
        props.get("source_excerpt"),
        props.get("excerpt"),
        props.get("text"),
        lineage.get("excerpt"),
    ]
    seen: list[str] = []
    for part in parts:
        if isinstance(part, str) and part.strip() and part.strip() not in seen:
            seen.append(part.strip())
    return " ".join(seen)


def _is_tombstone(memory: Any) -> bool:
    """True when the cited row exists only as a marker that its source is gone."""
    if memory is None:
        return True
    get = (
        (lambda k: memory.get(k))
        if isinstance(memory, dict)
        else (lambda k: getattr(memory, k, None))
    )
    if get("deleted") or get("missing"):
        return True
    return str(get("status") or "").lower() in ("deleted", "purged", "missing", "unavailable")


def verify_claim_support(
    claim: str,
    memory: Any,
    *,
    scorer: Any = None,
) -> dict[str, Any]:
    """Check one citation against one claim; never take the marker's word for it.

    *scorer*, when given, is called as ``scorer(claim, source_text)`` and must
    return a 0–1 entailment score; it replaces the lexical proxy. Returns the
    per-citation support detail that goes into the claim's breakdown.
    """
    mem_id = None
    if memory is not None:
        mem_id = memory.get("id") if isinstance(memory, dict) else getattr(memory, "id", None)
    detail: dict[str, Any] = {
        "memory_id": str(mem_id) if mem_id is not None else None,
        "support_status": UNRESOLVED_SOURCE,
        "entailment_score": None,
        "detail": "Cited source could not be resolved",
    }
    if _is_tombstone(memory):
        return detail

    source_text = citation_text(memory)
    if not source_text:
        detail.update(
            support_status=CONTEXT,
            detail="Cited memory carries no readable text; entailment not verified",
        )
        return detail

    if scorer is not None:
        try:
            score = round(max(0.0, min(1.0, float(scorer(claim, source_text)))), 4)
        except Exception:  # noqa: BLE001 — a failing scorer must not fabricate support
            score = lexical_entailment_score(claim, source_text)
    else:
        score = lexical_entailment_score(claim, source_text)
    detail["entailment_score"] = score

    conflict = _frame_conflict(claim, source_text)
    antonym_clash = _has_antonym_conflict(_content_tokens(claim), _content_tokens(source_text))
    polarity_clash = _is_negated(claim) != _is_negated(source_text)
    if score >= _CONTRADICTION_FLOOR and (
        conflict or antonym_clash or (polarity_clash and score >= 0.5)
    ):
        clash_reason = conflict or antonym_clash or "opposite polarity"
        detail.update(
            support_status=CONTRADICTED,
            detail=f"Citation contradicts claim ({clash_reason})",
        )
    elif score >= ENTAILMENT_THRESHOLD:
        detail.update(support_status=SUPPORTED, detail=f"Citation entails claim (score {score})")
    else:
        detail.update(support_status=UNSUPPORTED, detail="Citation does not entail claim")
    return detail


def _worst_status(statuses: list[str]) -> str:
    for status in _STATUS_SEVERITY:
        if status in statuses:
            return status
    return UNSUPPORTED


def extract_claim_evidence(
    answer: str,
    memories: list[dict[str, Any]],
    *,
    scorer: Any = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Map answer sentences to the lineage they cite, keeping only citations that hold up.

    Each claim reports the lineage behind it *and* whether the cited text
    actually says it: a sentence whose only citation is irrelevant comes back
    ``unsupported``, and one whose citation disagrees comes back
    ``contradicted``. Both leave ``supported`` false, which is what gives the
    caller something to abstain on (:func:`decide_claim_action`).
    """
    if not answer or not answer.strip():
        return []
    tag_re = re.compile(r"\[Memory\s+(\d+)\]")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer.strip()) if s.strip()]
    claims: list[dict[str, Any]] = []
    for sent in sentences:
        cited_indices: list[int] = []
        for match in tag_re.finditer(sent):
            idx = int(match.group(1)) - 1
            if idx not in cited_indices:
                cited_indices.append(idx)
        # The claim is what the sentence asserts; the markers are bookkeeping
        # and would otherwise count as content words shared with nothing.
        claim_text = tag_re.sub(" ", sent).strip()

        supporting: list[dict[str, Any]] = []
        support_details: list[dict[str, Any]] = []
        breakdowns: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for idx in cited_indices:
            mem = memories[idx] if 0 <= idx < len(memories) else None
            support = verify_claim_support(claim_text, mem, scorer=scorer)
            support["citation"] = idx + 1
            support_details.append(support)
            if mem is None:
                continue
            breakdowns.append(
                decompose_memory_confidence(mem, now=now, support_status=support["support_status"])
            )
            mid = (
                str(mem.get("id") or "")
                if isinstance(mem, dict)
                else str(getattr(mem, "id", "") or "")
            )
            if support["support_status"] in _STANDS and mid and mid not in seen_ids:
                seen_ids.add(mid)
                supporting.append(resolve_memory_lineage(mem))

        if support_details:
            status = _worst_status([s["support_status"] for s in support_details])
        else:
            status = UNSUPPORTED  # uncited: nothing was offered as evidence
        scores = [
            s["entailment_score"] for s in support_details if s["entailment_score"] is not None
        ]
        # Weakest-link, on both axes: one strong citation cannot validate a
        # claim that also rests on a weak or wrong one.
        claim_conf = round(min((b["calibrated_confidence"] for b in breakdowns), default=0.0), 4)
        claims.append(
            {
                "claim": sent,
                "supported": bool(supporting) and status in _STANDS,
                "support_status": status,
                "entailment_score": round(min(scores), 4) if scores else None,
                "citation_support": support_details,
                "memory_ids": [s["memory_id"] for s in supporting if s.get("memory_id")],
                "evidence": supporting,
                "confidence_breakdown": breakdowns,
                "claim_confidence": claim_conf,
                "claim_uncertainty": round(1.0 - claim_conf, 4),
                "recommended_action": decide_claim_action(claim_conf if status in _STANDS else 0.0),
            }
        )
    return claims


# ── Causal rationale (5.4) ───────────────────────────────────────────────

#: Decision sources that mean the reasoning came out of the owner's own mouth.
#: Anything else — a challenge, a distillation, a watcher — produced a
#: rationale *we* deduced, and a deduced "why" must never be replayed to the
#: owner as something they said.
STATED_RATIONALE_SOURCES = frozenset({"explicit", "conversation", "user", "owner"})

#: The owner stated the reasoning.
EXPLICIT = "explicit"
#: Life Graph deduced the reasoning.
RATIONALE_INFERRED = "inferred"


def rationale_type(
    source: str | None,
    properties: Mapping[str, Any] | None = None,
) -> str:
    """``"explicit"`` when the owner stated the rationale, ``"inferred"`` when we deduced it.

    Derived from the server-side decision ``source``, never from a stamp in
    ``properties`` — the one exception is a recorded owner confirmation, which
    :func:`owner_confirmed` only honours when an authenticated owner path
    wrote it.
    """
    if owner_confirmed(properties):
        return EXPLICIT
    return (
        EXPLICIT
        if (source or "").strip().lower() in STATED_RATIONALE_SOURCES
        else RATIONALE_INFERRED
    )


# ── Confidence calibration and action thresholds (5.3) ───────────────────

#: What to do with a claim at a given calibrated confidence, highest first.
#: Thresholds, not calibrated probabilities: they are where the *behaviour*
#: changes, and :func:`evaluate_confidence_calibration` is what says whether
#: the numbers feeding them deserve to be believed.
ANSWER = "answer"
QUALIFY = "qualify"
ASK = "ask"
ABSTAIN = "abstain"

ACTION_THRESHOLDS: tuple[tuple[float, str], ...] = ((0.85, ANSWER), (0.60, QUALIFY), (0.40, ASK))


def decide_claim_action(confidence: float) -> str:
    """Answer, qualify it, ask the owner, or say nothing — from one confidence.

    ``>= 0.85`` state it; ``0.60–0.85`` state it hedged; ``0.40–0.60`` ask the
    owner rather than guess; below ``0.40`` abstain. A confidence that is not a
    number at all abstains: an unreadable signal is not permission to answer.
    """
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        return ABSTAIN
    if conf != conf:  # NaN
        return ABSTAIN
    for floor, action in ACTION_THRESHOLDS:
        if conf >= floor:
            return action
    return ABSTAIN


#: What a citation that failed verification costs the memory behind it.
#: Support is a property of the *claim*, so it multiplies the memory's own four
#: components rather than hiding inside them — ``base_confidence`` stays
#: readable next to the penalised figure.
SUPPORT_PENALTY: dict[str, float] = {
    SUPPORTED: 1.0,
    CONTEXT: 1.0,  # entailment unassessed: no support to credit, none to punish
    UNSUPPORTED: 0.55,
    UNRESOLVED_SOURCE: 0.50,
    CONTRADICTED: 0.30,
}


_TRUST_SCORES = {
    "self": 0.98,
    "core": 0.95,
    "verified": 0.95,
    "standard": 0.78,
    "normal": 0.78,
    "unverified": 0.40,
    "quarantined": 0.15,
}

_EVIDENCE_PRIORS = {
    SAID: 0.95,
    DOCUMENT: 0.90,
    OBSERVED: 0.88,
    SUMMARY: 0.72,
    INFERRED: 0.55,
    OUTSIDE: 0.35,
}


def _parse_dt(val: Any) -> datetime | None:
    if isinstance(val, datetime):
        return val if val.tzinfo is not None else val.replace(tzinfo=UTC)
    if isinstance(val, str) and val.strip():
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def decompose_memory_confidence(
    memory: Any,
    *,
    now: datetime | None = None,
    support_status: str | None = None,
) -> dict[str, Any]:
    """Decompose confidence into extraction, trust, evidence-prior, and freshness components.

    The four components answer four different questions and are kept apart in
    the result, because collapsing them is how a confident-sounding number
    gets built out of nothing: *extraction* is how sure the parser was it read
    the fact correctly, *trust* is how much the ingress path earns, *evidence
    prior* is what the kind of evidence is worth at all (the owner's own words
    versus a distilled guess), and *freshness* is how long ago we last saw it
    confirmed.

    Vector similarity is excluded on purpose, so retrieval rank never
    masquerades as truth.

    *support_status*, when a caller has checked this memory against a specific
    claim (:func:`verify_claim_support`), applies the penalty for a
    contradicted, unsupported or unresolvable citation on top. It multiplies
    rather than folds in: ``base_confidence`` stays readable beside the
    penalised ``calibrated_confidence``.
    """
    get = (
        (lambda k, d=None: memory.get(k, d))
        if isinstance(memory, dict)
        else (lambda k, d=None: getattr(memory, k, d))
    )
    props = get("properties") or {}
    if not isinstance(props, dict):
        props = {}

    raw_ext = get("confidence")
    if raw_ext is None:
        raw_ext = props.get("extraction_confidence", 0.5)
    try:
        extraction_conf = max(0.0, min(1.0, float(raw_ext)))
    except (TypeError, ValueError):
        extraction_conf = 0.5

    trust_tier = str(get("trust_tier") or "standard").lower()
    trust_score = _TRUST_SCORES.get(trust_tier, 0.70)

    ev_kind = evidence_of(get("source_type"), trust_tier, props)
    explicit_vs_inferred = "inferred" if is_guess(ev_kind) else "explicit"
    prior = _EVIDENCE_PRIORS.get(ev_kind, 0.65)

    ref_now = now or datetime.now(UTC)
    if ref_now.tzinfo is None:
        ref_now = ref_now.replace(tzinfo=UTC)

    valid_to = _parse_dt(get("valid_to"))
    if valid_to is not None and valid_to < ref_now:
        freshness = 0.20
    else:
        ts = (
            _parse_dt(get("updated_at"))
            or _parse_dt(get("recorded_at"))
            or _parse_dt(get("created_at"))
        )
        if ts is None:
            freshness = 0.75
        else:
            age_days = max(0.0, (ref_now - ts).total_seconds() / 86400.0)
            freshness = round(1.0 / (1.0 + age_days / 180.0), 4)

    base = round(
        max(
            0.0,
            min(1.0, 0.35 * extraction_conf + 0.25 * trust_score + 0.25 * prior + 0.15 * freshness),
        ),
        4,
    )
    penalty = SUPPORT_PENALTY.get(support_status, 1.0) if support_status else 1.0
    calibrated = round(max(0.0, min(1.0, base * penalty)), 4)
    return {
        "extraction_confidence": round(extraction_conf, 4),
        "trust_score": round(trust_score, 4),
        "evidence_prior": round(prior, 4),
        "freshness_score": round(freshness, 4),
        "evidence_kind": ev_kind,
        "explicit_vs_inferred": explicit_vs_inferred,
        "support_status": support_status,
        "support_penalty": round(penalty, 4),
        "base_confidence": base,
        "calibrated_confidence": calibrated,
        "uncertainty": round(1.0 - calibrated, 4),
        "recommended_action": decide_claim_action(calibrated),
    }


def evaluate_confidence_calibration(
    samples: list[dict[str, Any]],
    *,
    num_bins: int = 10,
    decision_threshold: float = 0.5,
    abstain_threshold: float = 0.4,
) -> dict[str, Any]:
    """Compute Brier score, ECE, MCE, and calibration summary overall and by evidence_kind.

    Args:
        samples: List of sample dicts containing 'confidence' and 'correct' (bool/float).
            May optionally include 'evidence_kind', 'contradiction_predicted',
            and 'contradiction_ground_truth'.
        num_bins: Number of equal-width bins for ECE calculation (default 10).
        decision_threshold: Confidence threshold for predicting positive (default 0.5).
        abstain_threshold: Confidence threshold below which the system abstains (default 0.4).

    Returns:
        Dict with Brier score, ECE, MCE, precision, recall, F1, abstention quality,
        reliability bins, and breakdown by evidence_kind.
    """
    if not samples:
        return {
            "count": 0,
            "brier_score": 0.0,
            "ece": 0.0,
            "mce": 0.0,
            "mean_confidence": 0.0,
            "accuracy": 0.0,
            "calibration_gap": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "abstention_rate": 0.0,
            "abstention_precision": 0.0,
            "answering_accuracy": 0.0,
            "bins": [],
            "by_evidence_kind": {},
        }

    buckets: dict[str, list[dict[str, Any]]] = {}
    normalized_samples: list[dict[str, Any]] = []
    for item in samples:
        conf = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
        y = 1.0 if item.get("correct") else 0.0
        kind = str(item.get("evidence_kind") or "unknown")
        entry: dict[str, Any] = {
            "confidence": conf,
            "correct": y,
            "evidence_kind": kind,
        }
        if "contradiction_predicted" in item:
            entry["contradiction_predicted"] = bool(item["contradiction_predicted"])
        if "contradiction_ground_truth" in item:
            entry["contradiction_ground_truth"] = bool(item["contradiction_ground_truth"])
        normalized_samples.append(entry)
        buckets.setdefault(kind, []).append(entry)

    def _stats(items: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(items)
        if n == 0:
            return {
                "count": 0,
                "brier_score": 0.0,
                "ece": 0.0,
                "mce": 0.0,
                "mean_confidence": 0.0,
                "accuracy": 0.0,
                "calibration_gap": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "abstention_rate": 0.0,
                "abstention_precision": 0.0,
                "answering_accuracy": 0.0,
                "bins": [],
            }

        confs = [it["confidence"] for it in items]
        ys = [it["correct"] for it in items]

        brier = sum((c - y) ** 2 for c, y in zip(confs, ys, strict=True)) / n
        mean_c = sum(confs) / n
        acc = sum(ys) / n
        gap = mean_c - acc

        # Reliability bins and Expected Calibration Error (ECE / MCE)
        bin_records = []
        ece_acc = 0.0
        mce_val = 0.0
        for b_idx in range(num_bins):
            b_lower = b_idx / num_bins
            b_upper = (b_idx + 1) / num_bins
            if b_idx == num_bins - 1:
                in_bin = [it for it in items if b_lower <= it["confidence"] <= b_upper]
            else:
                in_bin = [it for it in items if b_lower <= it["confidence"] < b_upper]
            b_count = len(in_bin)
            if b_count > 0:
                b_conf = sum(it["confidence"] for it in in_bin) / b_count
                b_acc = sum(it["correct"] for it in in_bin) / b_count
                b_gap = abs(b_acc - b_conf)
                ece_acc += (b_count / n) * b_gap
                if b_gap > mce_val:
                    mce_val = b_gap
            else:
                b_conf = (b_lower + b_upper) / 2.0
                b_acc = 0.0
                b_gap = 0.0
            bin_records.append(
                {
                    "bin": b_idx,
                    "range": (round(b_lower, 2), round(b_upper, 2)),
                    "count": b_count,
                    "mean_confidence": round(b_conf, 4),
                    "accuracy": round(b_acc, 4),
                    "gap": round(b_gap, 4),
                }
            )

        # Classification metrics at decision_threshold
        tp = sum(1 for c, y in zip(confs, ys, strict=True) if c >= decision_threshold and y == 1.0)
        fp = sum(1 for c, y in zip(confs, ys, strict=True) if c >= decision_threshold and y == 0.0)
        fn = sum(1 for c, y in zip(confs, ys, strict=True) if c < decision_threshold and y == 1.0)

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        # Abstention quality at abstain_threshold
        abstained = [it for it in items if it["confidence"] < abstain_threshold]
        answered = [it for it in items if it["confidence"] >= abstain_threshold]
        abstention_rate = len(abstained) / n
        abstention_precision = (
            sum(1 for it in abstained if it["correct"] == 0.0) / len(abstained)
            if abstained
            else 0.0
        )
        answering_acc = sum(it["correct"] for it in answered) / len(answered) if answered else 0.0

        res: dict[str, Any] = {
            "count": n,
            "brier_score": round(brier, 4),
            "ece": round(ece_acc, 4),
            "mce": round(mce_val, 4),
            "mean_confidence": round(mean_c, 4),
            "accuracy": round(acc, 4),
            "calibration_gap": round(gap, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "abstention_rate": round(abstention_rate, 4),
            "abstention_precision": round(abstention_precision, 4),
            "answering_accuracy": round(answering_acc, 4),
            "bins": bin_records,
        }

        # Contradiction metrics when ground truth is supplied
        contr_items = [
            it
            for it in items
            if "contradiction_predicted" in it and "contradiction_ground_truth" in it
        ]
        if contr_items:
            c_tp = sum(
                1
                for it in contr_items
                if it["contradiction_predicted"] and it["contradiction_ground_truth"]
            )
            c_fp = sum(
                1
                for it in contr_items
                if it["contradiction_predicted"] and not it["contradiction_ground_truth"]
            )
            c_fn = sum(
                1
                for it in contr_items
                if not it["contradiction_predicted"] and it["contradiction_ground_truth"]
            )
            c_prec = (c_tp / (c_tp + c_fp)) if (c_tp + c_fp) > 0 else 0.0
            c_rec = (c_tp / (c_tp + c_fn)) if (c_tp + c_fn) > 0 else 0.0
            c_f1 = (2 * c_prec * c_rec / (c_prec + c_rec)) if (c_prec + c_rec) > 0 else 0.0
            res["contradiction_detection"] = {
                "count": len(contr_items),
                "precision": round(c_prec, 4),
                "recall": round(c_rec, 4),
                "f1": round(c_f1, 4),
            }

        return res

    summary = _stats(normalized_samples)
    summary["by_evidence_kind"] = {k: _stats(v) for k, v in sorted(buckets.items())}
    return summary
