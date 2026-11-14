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

    Only the server's own record counts — a mapping naming who confirmed and
    when. A bare ``True`` is not a confirmation: it is the shape a client
    would guess at, and the mark exists to say *who* decided.
    """
    mark = (properties or {}).get(OWNER_CONFIRMED)
    return isinstance(mark, Mapping) and bool(mark.get("by"))


def confirm_from_owner(
    properties: Mapping[str, Any] | None = None,
    *,
    by: str,
    at: datetime | None = None,
) -> dict[str, Any]:
    """*properties* with the owner's explicit confirmation recorded.

    Only the server calls this, from the path where a person acted (approving
    a pending memory): it is what lets outside-origin content be stated as
    true. ``by`` is who confirmed, so a wrong card entry can be traced back.
    """
    if not by or not str(by).strip():
        raise ValueError("owner confirmation needs who confirmed it")
    when = at or datetime.now(UTC)
    return {
        **dict(properties or {}),
        OWNER_CONFIRMED: {"by": str(by).strip()[:120], "at": when.isoformat()},
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

    raw_derived = base.get("derived_from") or props.get("derived_from") or props.get("inferred_from")
    derived_from: list[str] = []
    if isinstance(raw_derived, (list, tuple)):
        derived_from = [str(x) for x in raw_derived if x is not None and str(x).strip()]
    elif raw_derived is not None and str(raw_derived).strip():
        derived_from = [str(raw_derived).strip()]

    lineage: dict[str, Any] = {
        "source_type": _clean_str(base.get("source_type") or source_type, max_len=64),
        "capture_event_id": str(cap_id) if cap_id is not None and str(cap_id).strip() else None,
        "extraction_trace_id": str(trace_id) if trace_id is not None and str(trace_id).strip() else None,
        "extraction_fact_index": fact_idx,
        "excerpt": excerpt,
        "location": location,
        "derived_from": derived_from,
        "supersedes": str(supersedes or base.get("supersedes")) if (supersedes or base.get("supersedes")) else None,
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


def extract_claim_evidence(answer: str, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map synthesized answer sentences to their cited memory lineage; uncited claims are marked unsupported."""
    import re

    if not answer or not answer.strip():
        return []
    tag_re = re.compile(r"\[Memory\s+(\d+)\]")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer.strip()) if s.strip()]
    claims: list[dict[str, Any]] = []
    for sent in sentences:
        cited_indices = [int(m.group(1)) - 1 for m in tag_re.finditer(sent)]
        supporting: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for idx in cited_indices:
            if 0 <= idx < len(memories):
                mem = memories[idx]
                mid = str(mem.get("id") or "")
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    supporting.append(resolve_memory_lineage(mem))
        breakdowns = [
            decompose_memory_confidence(memories[idx])
            for idx in cited_indices
            if 0 <= idx < len(memories)
        ]
        # Weakest-link claim confidence: one strong citation cannot validate a weak co-cited claim.
        claim_conf = round(min((b["calibrated_confidence"] for b in breakdowns), default=0.0), 4)
        claims.append(
            {
                "claim": sent,
                "supported": bool(supporting),
                "memory_ids": [s["memory_id"] for s in supporting if s.get("memory_id")],
                "evidence": supporting,
                "confidence_breakdown": breakdowns,
                "claim_confidence": claim_conf,
                "claim_uncertainty": round(1.0 - claim_conf, 4),
            }
        )
    return claims


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
) -> dict[str, Any]:
    """Decompose confidence into extraction, trust, freshness, and evidence components.

    Vector similarity is intentionally excluded so retrieval rank never masquerades as truth.
    """
    get = (lambda k, d=None: memory.get(k, d)) if isinstance(memory, dict) else (lambda k, d=None: getattr(memory, k, d))
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
        ts = _parse_dt(get("updated_at")) or _parse_dt(get("recorded_at")) or _parse_dt(get("created_at"))
        if ts is None:
            freshness = 0.75
        else:
            age_days = max(0.0, (ref_now - ts).total_seconds() / 86400.0)
            freshness = round(1.0 / (1.0 + age_days / 180.0), 4)

    calibrated = round(
        max(0.0, min(1.0, 0.35 * extraction_conf + 0.25 * trust_score + 0.25 * prior + 0.15 * freshness)),
        4,
    )
    return {
        "extraction_confidence": round(extraction_conf, 4),
        "trust_score": round(trust_score, 4),
        "freshness_score": round(freshness, 4),
        "evidence_kind": ev_kind,
        "explicit_vs_inferred": explicit_vs_inferred,
        "calibrated_confidence": calibrated,
        "uncertainty": round(1.0 - calibrated, 4),
    }


def evaluate_confidence_calibration(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute Brier score and calibration summary overall and by evidence_kind."""
    if not samples:
        return {
            "count": 0,
            "brier_score": 0.0,
            "mean_confidence": 0.0,
            "accuracy": 0.0,
            "calibration_gap": 0.0,
            "by_evidence_kind": {},
        }

    buckets: dict[str, list[tuple[float, float]]] = {}
    all_pairs: list[tuple[float, float]] = []
    for item in samples:
        conf = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
        y = 1.0 if item.get("correct") else 0.0
        kind = str(item.get("evidence_kind") or "unknown")
        all_pairs.append((conf, y))
        buckets.setdefault(kind, []).append((conf, y))

    def _stats(pairs: list[tuple[float, float]]) -> dict[str, Any]:
        n = len(pairs)
        brier = sum((c - y) ** 2 for c, y in pairs) / n
        mean_c = sum(c for c, _ in pairs) / n
        acc = sum(y for _, y in pairs) / n
        return {
            "count": n,
            "brier_score": round(brier, 4),
            "mean_confidence": round(mean_c, 4),
            "accuracy": round(acc, 4),
            "calibration_gap": round(mean_c - acc, 4),
        }

    summary = _stats(all_pairs)
    summary["by_evidence_kind"] = {k: _stats(v) for k, v in sorted(buckets.items())}
    return summary
