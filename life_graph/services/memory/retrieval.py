"""Memories that actually answer a question — or none.

Search always returns its top-k, related or not: on 2026-10-22 hybrid search
put the right memory first for 93.5% of answerable questions, and returned
something for 10 of 10 questions the memories could not answer
(evals/score-separability.md: no score threshold separates the two). So the
nearest candidates go to the local model, which keeps only the ones that help
answer the question, best first, and may keep none: that is what lets Jarvis
say it doesn't know instead of offering the nearest unrelated note.

Local model only: the question and the memories are the owner's.
"""

from __future__ import annotations

import contextlib
import inspect
import json
import logging
import math
import re
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

CANDIDATES = 10
#: Memories linked to an entity the question names, added to the judge's candidates.
ENTITY_CANDIDATES = 8
#: The best search hits whose linked memories are added (services/memory/associations.py) …
LINK_SEEDS = 5
#: … and at most this many of them.
LINKED_CANDIDATES = 6
#: A question asking what is known about one thing, rather than a specific question.
ABOUT = re.compile(
    r"\b(everything|all you know|what (do|did) (you|i) (know|remember|say|tell you)|"
    r"tell me|remind me)( \w+){0,3} about\b|^\s*(what|who) (is|are|was) \S+( \S+)?\s*\??\s*$",
    re.IGNORECASE,
)

PROMPT = """\
A person asked their assistant a question. Below are numbered notes from the
person's memory, found by search. Keep every note that is about the same
subject as the question or could help answer it, even partly; drop only notes
that are clearly about something else. Most useful first. If every note is
about something else, return an empty list. Do not answer the question.
Answer with JSON only: {"relevant": [n, ...]}"""

SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "relevant",
        "schema": {
            "type": "object",
            "properties": {"relevant": {"type": "array", "items": {"type": "integer"}}},
            "required": ["relevant"],
        },
    },
}


async def judge(question: str, contents: list[str]) -> list[int] | None:
    """Indexes (0-based) of the contents that help answer, best first; None if the model failed."""
    from life_graph.config import settings
    from life_graph.runtime import get_lm_client

    listing = "\n".join(f"{i + 1}. {' '.join(c.split())[:300]}" for i, c in enumerate(contents))
    reply = await get_lm_client().chat_local_only(
        [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"Question: {question}\n\nNotes:\n{listing}"},
        ],
        model=settings.memory_judge_model or settings.lm_extraction_model,
        temperature=0.0,
        max_tokens=200,
        response_format=SCHEMA,
    )
    try:
        picked = json.loads(reply)["relevant"]
    except (ValueError, KeyError, TypeError):
        return None
    out: list[int] = []
    for n in picked:
        if isinstance(n, int) and 1 <= n <= len(contents) and n - 1 not in out:
            out.append(n - 1)
    return out


def strength_order(hits: list[tuple[Any, float]]) -> list[tuple[Any, float]]:
    """Search hits reordered by match x strength: how important, how often used
    and how recently used or said a memory is. The match still leads: strength
    moves a memory by at most +/-15%, so it settles near-ties, never overrules
    a clearly better match."""
    now = datetime.now(UTC)

    def strength(m: Any) -> float:
        importance = float(getattr(m, "importance", 0.5) or 0.5)
        uses = min(1.0, math.log1p(getattr(m, "access_count", 0) or 0) / math.log1p(10))
        last = getattr(m, "last_accessed", None) or getattr(m, "created_at", None)
        days = max(0.0, (now - last).total_seconds() / 86400) if last else 365.0
        recency = 0.5 ** (days / 90)
        return 0.5 * importance + 0.3 * uses + 0.2 * recency

    return sorted(hits, key=lambda h: -h[1] * (0.85 + 0.3 * strength(h[0])))


async def _with_neighbours(tenant_id: str, candidates: list[Any]) -> list[Any]:
    """*candidates* plus the active memories most strongly linked to the best of
    them (services/memory/associations.py): said or used together with a match."""
    from life_graph.services.memory import associations

    try:
        linked = await associations.neighbours(
            tenant_id, [m.id for m in candidates[:LINK_SEEDS]], limit=LINKED_CANDIDATES
        )
    except Exception:  # noqa: BLE001 — links are a bonus; search alone still answers
        logger.warning("Linked candidates failed; using search only", exc_info=True)
        return candidates
    known = {m.id for m in candidates}
    return candidates + [m for m in linked if m.id not in known]


def provenance_score(m: Any) -> float:
    """Bounded provenance score in [0.0, 1.0] using evidence kind, trust, confidence, and corroboration."""
    from life_graph.core.evidence import DOCUMENT, INFERRED, OBSERVED, OUTSIDE, SAID, evidence_of

    props = getattr(m, "properties", None) or {}
    if not isinstance(props, dict):
        props = {}
    trust = float(getattr(m, "trust_score", 0.5) or 0.5)
    conf = float(getattr(m, "confidence", 0.5) or 0.5)
    tier = str(getattr(m, "trust_tier", "") or "").lower()
    src_type = str(getattr(m, "source_type", "") or "").lower()
    ev_kind = evidence_of(src_type, tier, props)

    bonus = 0.0
    if (
        ev_kind == SAID
        or tier in ("self", "verified", "owner", "canonical")
        or src_type in ("user_explicit", "manual")
    ):
        bonus = 0.18
    elif ev_kind == DOCUMENT:
        bonus = 0.12
    elif ev_kind == OBSERVED:
        bonus = 0.10
    elif ev_kind == INFERRED or tier in ("inferred", "unverified"):
        bonus = -0.08
    elif ev_kind == OUTSIDE:
        bonus = -0.05

    corrob = props.get("corroboration_count", 0)
    try:
        corrob_n = max(0, int(corrob))
    except (TypeError, ValueError):
        corrob_n = 0
    bonus += min(0.08, 0.02 * corrob_n)

    raw = 0.45 * trust + 0.45 * conf + bonus
    return max(0.0, min(1.0, raw))


def provenance_order(hits: list[tuple[Any, float]]) -> list[tuple[Any, float]]:
    """Apply a bounded +/-10% provenance tie-breaker to hybrid search hits."""
    return sorted(hits, key=lambda h: -h[1] * (0.90 + 0.20 * provenance_score(h[0])))


def provenance_tiebreak_order(
    hits: list[tuple[Any, float]],
    *,
    score_tolerance: float = 0.02,
) -> list[tuple[Any, float]]:
    """Break near-ties in relevance score using provenance without overriding clear relevance winners."""
    if len(hits) <= 1:
        return list(hits)
    ordered = sorted(hits, key=lambda h: -float(h[1]))
    result: list[tuple[Any, float]] = []
    cluster: list[tuple[Any, float]] = [ordered[0]]
    cluster_top = float(ordered[0][1])

    for item in ordered[1:]:
        score = float(item[1])
        if (cluster_top - score) <= max(1e-9, abs(cluster_top) * score_tolerance):
            cluster.append(item)
        else:
            cluster.sort(key=lambda h: (-provenance_score(h[0]), -float(h[1])))
            result.extend(cluster)
            cluster = [item]
            cluster_top = score

    cluster.sort(key=lambda h: (-provenance_score(h[0]), -float(h[1])))
    result.extend(cluster)
    return result


# ── Adaptive retrieval (§3.C — retrieval that knows when to stop) ─────────
#
# Two decisions, both taken from the candidates' *own* evidence and never
# from their retrieval score (a similarity number is not a calibrated
# confidence — see core/evidence.py):
#
# * Stop early. When the best hit is fresh, high-trust, and accounts for the
#   question's content words, entity and link expansion can only add
#   distractors and latency: there is nothing left to find.
# * Say the evidence will not do. Memories that contradict the question, or
#   a candidate whose source no longer resolves, are not fixed by retrieving
#   more.
#
# The second is *reported*, not acted on here: `retrieve` still returns what
# it found, with the assessment attached (:class:`RetrievalResult`), so each
# surface decides what an abstention indicator means for it. /ask turns it
# into an epistemic status (api/search.py) rather than a refusal, because a
# memory that contradicts the question often answers it ("you no longer live
# in London") — what must not happen is presenting it as plain agreement.

#: Calibrated confidence at which the top hit alone is strong enough to answer.
EARLY_EXIT_CONFIDENCE = 0.92
#: … and how much of the question's content words that hit must account for.
EARLY_EXIT_ENTAILMENT = 0.85
#: Calibrated confidence below which a candidate carries no usable evidence.
THIN_EVIDENCE_CONFIDENCE = 0.40


class RetrievalResult(list):
    """The retrieved memories, plus what retrieval learned about their evidence.

    A ``list`` subclass so every existing caller keeps working unchanged
    (``len``, iteration, indexing, truthiness); the attributes are for callers
    that need to know *why* — that the evidence was contradictory or too thin
    (``abstain`` / ``abstention_reason``), or that one hit was good enough to
    stop expanding (``early_exit``). Each returned memory also carries its own
    ``retrieval_evidence`` dict.
    """

    __slots__ = ("abstain", "abstention_reason", "early_exit", "evidence")

    def __init__(
        self,
        items: Any = (),
        *,
        abstain: bool = False,
        abstention_reason: str | None = None,
        evidence: dict[str, Any] | None = None,
        early_exit: bool = False,
    ) -> None:
        super().__init__(items)
        self.abstain = abstain
        self.abstention_reason = abstention_reason
        self.evidence = evidence or {}
        self.early_exit = early_exit


def assess_hit_evidence(
    question: str,
    memory: Any,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """What one candidate's own evidence says about *question*.

    Entailment (does the memory's text actually account for what was asked?)
    and calibrated confidence (how much is this kind of evidence, from this
    path, at this age, worth?) are kept apart in the result: a memory can be
    highly trusted and still be about something else, and collapsing the two
    is how a confident-looking answer gets built out of a near-miss.
    """
    from life_graph.core.evidence import (
        CONTRADICTED,
        SUPPORTED,
        UNRESOLVED_SOURCE,
        decompose_memory_confidence,
        verify_claim_support,
    )

    support = verify_claim_support(question, memory)
    status = str(support.get("support_status") or UNRESOLVED_SOURCE)
    breakdown = decompose_memory_confidence(memory, now=now, support_status=status)
    score = float(support.get("entailment_score") or 0.0)
    conf = float(breakdown["calibrated_confidence"])
    # Every content word of the question is in the memory's text or its
    # preserved source span: the strongest entailment signal we have locally.
    covered = score >= 1.0
    entailed = status == SUPPORTED and (covered or score >= EARLY_EXIT_ENTAILMENT)
    return {
        "memory_id": support.get("memory_id"),
        "support_status": status,
        "support_detail": support.get("detail"),
        "entailment_score": score,
        "keywords_covered": covered,
        "calibrated_confidence": conf,
        "base_confidence": breakdown["base_confidence"],
        "evidence_kind": breakdown["evidence_kind"],
        "explicit_vs_inferred": breakdown["explicit_vs_inferred"],
        "recommended_action": breakdown["recommended_action"],
        "sufficient": bool(conf >= EARLY_EXIT_CONFIDENCE and entailed),
        "contradicted": status == CONTRADICTED,
        # A contradicted memory is not "unresolvable": it resolved, and it
        # disagrees — a different problem, reported separately.
        "unresolvable": status == UNRESOLVED_SOURCE
        or (status not in (SUPPORTED, CONTRADICTED) and conf < THIN_EVIDENCE_CONFIDENCE),
    }


def _neutral_assessment(memory: Any) -> dict[str, Any]:
    """A no-claim assessment, used when assessing one candidate itself failed."""
    mid = memory.get("id") if isinstance(memory, dict) else getattr(memory, "id", None)
    return {
        "memory_id": str(mid) if mid is not None else None,
        "support_status": "context",
        "support_detail": "Evidence assessment failed; nothing claimed either way",
        "entailment_score": 0.0,
        "keywords_covered": False,
        "calibrated_confidence": 0.0,
        "base_confidence": 0.0,
        "evidence_kind": None,
        "explicit_vs_inferred": None,
        "recommended_action": "abstain",
        "sufficient": False,
        "contradicted": False,
        "unresolvable": False,
    }


def assess_candidate_evidence(
    question: str,
    candidates: list[Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Whether the candidate set is contradictory or too thin to answer *question*.

    ``abstain`` is an indicator for the caller, not a decision taken here:
    more retrieval cannot reconcile two memories that disagree, nor conjure a
    source for a claim whose lineage is gone, so the honest thing is to say
    which it is. One entry per candidate comes back in ``per_memory``, in the
    candidates' own order.
    """
    from life_graph.core.evidence import SUPPORTED

    per: list[dict[str, Any]] = []
    for m in candidates:
        try:
            per.append(assess_hit_evidence(question, m, now=now))
        except Exception:  # noqa: BLE001 — a failed assessment must not claim support
            logger.warning("Evidence assessment failed for a candidate", exc_info=True)
            per.append(_neutral_assessment(m))

    contradicted = [a["memory_id"] for a in per if a["contradicted"]]
    unresolvable = [a["memory_id"] for a in per if a["unresolvable"]]
    supported = [a for a in per if a["support_status"] == SUPPORTED]

    if contradicted:
        abstain, reason = True, "contradictory_evidence"
        detail = (
            f"{len(contradicted)} of {len(per)} candidate memories assert something "
            "incompatible with the question"
        )
    elif per and len(unresolvable) == len(per):
        abstain, reason = True, "unresolvable_missing_evidence"
        detail = (
            "No candidate memory resolves to readable evidence above the "
            f"{THIN_EVIDENCE_CONFIDENCE} confidence floor"
        )
    else:
        abstain, reason, detail = False, None, None

    return {
        "abstain": abstain,
        "abstention_reason": reason,
        "detail": detail,
        "contradicted": contradicted,
        "unresolvable": unresolvable,
        "assessed": len(per),
        "supported": len(supported),
        "per_memory": per,
    }


def _result(
    question: str,
    items: list[Any],
    *,
    early: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> RetrievalResult:
    """*items* as a :class:`RetrievalResult`, with their evidence assessed.

    The assessment reads the memories that are actually being returned, so a
    caller's abstention indicator is about the evidence it was handed.
    """
    assessment = assess_candidate_evidence(question, items, now=now)
    for memory, per in zip(items, assessment["per_memory"], strict=False):
        # A read-only or mapping row simply does not carry it; the collection's
        # own assessment is the one every caller can rely on.
        with contextlib.suppress(AttributeError, TypeError):
            memory.retrieval_evidence = per
    return RetrievalResult(
        items,
        abstain=assessment["abstain"],
        abstention_reason=assessment["abstention_reason"],
        evidence=assessment,
        early_exit=bool(early and early.get("sufficient")),
    )


def explain_retrieval_selection(
    candidates: list[Any],
    picked: list[Any],
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Explain why retrieval candidates were selected or dropped."""
    from life_graph.core.evidence import evidence_of

    picked_ids = {getattr(m, "id", None) for m in picked}
    final_ids = {getattr(m, "id", None) for m in (picked[:limit] if limit is not None else picked)}
    trace: list[dict[str, Any]] = []
    for m in candidates:
        mid = getattr(m, "id", None)
        props = getattr(m, "properties", None) or {}
        ev = evidence_of(
            getattr(m, "source_type", None),
            getattr(m, "trust_tier", None),
            props if isinstance(props, dict) else {},
        )
        if mid in final_ids:
            decision, reason = "selected", "relevant_and_valid"
        elif mid in picked_ids:
            decision, reason = "truncated", "exceeded_limit"
        else:
            decision, reason = "rejected", "filtered_or_not_selected_by_judge"
        trace.append(
            {
                "memory_id": str(mid) if mid is not None else None,
                "decision": decision,
                "reason": reason,
                "evidence_kind": ev,
                "provenance_score": round(provenance_score(m), 4),
            }
        )
    return trace


def _ensure_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _as_utc(value: Any) -> datetime | None:
    """*value* as an aware UTC datetime, or None when it is not a usable timestamp.

    Timestamps reach us three ways: as a column (already a ``datetime``, aware
    or — for a naive SQLite/SimpleNamespace row — not), as an ISO string out of
    the JSONB ``properties`` column, or as an epoch number. A naive datetime is
    read as UTC: every writer in the system stores UTC.
    """
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), UTC)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _temporal(memory: Any, *names: str) -> datetime | None:
    """The first of *names* carried by *memory* as an attribute or in ``properties``.

    ``recorded_at`` and ``superseded_at`` have no columns of their own
    (models/memory.py): consolidation and correction write them into the JSONB
    ``properties``. Reading both places keeps one predicate for either shape.
    """
    props = getattr(memory, "properties", None)
    if not isinstance(props, dict):
        props = memory.get("properties") if isinstance(memory, dict) else None
        if not isinstance(props, dict):
            props = {}
    for name in names:
        raw = props.get(name)
        if raw is None:
            raw = getattr(memory, name, None)
        if raw is None and isinstance(memory, dict):
            raw = memory.get(name)
        found = _as_utc(raw)
        if found is not None:
            return found
    return None


def is_valid_at(memory: Any, ref_time: datetime) -> bool:
    """Valid-time check: was the fact true in the world at *ref_time*?

    The window is half-open — ``valid_from <= ref_time < valid_until`` — so a
    fact and its replacement never both answer for the instant they meet.
    ``valid_to`` is accepted as an alias for ``valid_until``
    (core/evidence.py's confidence decomposition uses that name).
    For an episode summary (``properties.kind == 'episode'``), real-world valid
    time starts on the episode's calendar ``date`` rather than the DB row's
    auto-populated ``valid_from`` insertion timestamp.
    """
    ref = _ensure_utc(ref_time)
    props = getattr(memory, "properties", None)
    if not isinstance(props, dict):
        props = memory.get("properties") if isinstance(memory, dict) else {}
    if (
        isinstance(props, dict)
        and props.get("kind") == "episode"
        and "valid_from" not in props
        and props.get("date")
    ):
        v_from = _as_utc(props.get("date"))
    else:
        v_from = _temporal(memory, "valid_from")
    v_until = _temporal(memory, "valid_until", "valid_to")
    started = v_from is None or v_from <= ref
    not_ended = v_until is None or ref < v_until
    return started and not_ended


def recorded_time_of(memory: Any) -> datetime | None:
    """When the system *learned* the fact (transaction time), or None if unknown.

    ``created_at`` is only the last fallback: a row that was corrected in place
    keeps its original ``created_at``, so an explicit ``recorded_at`` (written
    by whichever path recorded or re-recorded the fact) is the one that tells
    the truth about when we knew.
    """
    return _temporal(memory, "recorded_at", "created_at")


def is_known_at(memory: Any, recorded_at: datetime) -> bool:
    """Transaction-time check: did the system hold this as a *current* belief then?

    Two edges, and they are different questions:

    * Had we recorded it yet? ``recorded_at`` before the memory's own recorded
      time means we did not know it (a late-arriving or backdated capture is
      invisible to a query about an earlier state of knowledge).
    * Had we replaced it yet? Before ``superseded_at`` the memory *was* the
      active belief and must be reconstructed as such; at or after it, the
      correction had landed and this row is history, not current belief.
    """
    rec = _ensure_utc(recorded_at)
    known_from = recorded_time_of(memory)
    superseded_at = _temporal(memory, "superseded_at", "replaced_at")
    recorded_yet = known_from is None or known_from <= rec
    still_believed = superseded_at is None or rec < superseded_at
    return recorded_yet and still_believed


def is_bitemporally_valid(
    memory: Any,
    *,
    valid_at: datetime | None = None,
    recorded_at: datetime | None = None,
) -> bool:
    """Both timelines: true in the world at *valid_at*, and believed at *recorded_at*.

    The two axes are independent, which is what makes the three historical
    questions expressible:

    * ``recorded_at=X`` — what did we believe on X (about any time)?
    * ``valid_at=Y, recorded_at=now`` — what do we *now* believe was true on Y?
    * ``valid_at=Y, recorded_at=X`` — what did we believe on X was true on Y?

    A ``None`` axis is no constraint on that axis, so the plain
    ``is_bitemporally_valid(m, valid_at=now)`` of ordinary retrieval keeps
    asking only about real-world validity.
    """
    if valid_at is not None and not is_valid_at(memory, valid_at):
        return False
    return recorded_at is None or is_known_at(memory, recorded_at)


async def retrieve(
    question: str,
    limit: int = 6,
    *,
    cold: bool = False,
    as_of: datetime | None = None,
    recorded_as_of: datetime | None = None,
) -> RetrievalResult | None:
    """Memories of the current tenant that help answer *question*, best first.

    Active memories first; archived and replaced ones (services/memory/tiers.py)
    when none of those helps, or alongside them when the question is about the
    past — only for a caller that labels them (*cold*, services/memory/context.py
    render); /ask and the dashboard chat would pass an old value on as current.
    ``[]`` means memory was searched and nothing helps; ``None`` means it
    could not be searched (no embedding), which a caller must not present as
    "nothing remembered". Falls back to the plain search order when the judge
    cannot answer, so a model outage costs precision, never the memories
    themselves.

    The return is a :class:`RetrievalResult` — a list, so every caller keeps
    working — carrying what retrieval learned about the evidence it found:
    whether it stopped early on a sufficient top hit, and whether the evidence
    is contradictory or too thin to answer from (§3.C).
    """
    from life_graph.config import settings
    from life_graph.core.tenant import get_current_tenant_id
    from life_graph.runtime import get_memory_manager, get_store
    from life_graph.services import episodes
    from life_graph.services.memory import tiers as memory_tiers

    embedding = await get_memory_manager().generate_embedding(question)
    if not embedding:
        return None
    tenant_id = get_current_tenant_id()

    # A valid-time question with no transaction time given is the common
    # "what do we *now* believe was true on date Y?": anchor transaction time
    # to now, so the superseded rows that as_of lets into search_statuses
    # below are read as the history they are, not as current belief. Asking
    # for both (recorded_as_of) is the other question — what we believed then.
    if recorded_as_of is not None:
        recorded_ref: datetime | None = _ensure_utc(recorded_as_of)
    elif as_of is not None:
        recorded_ref = datetime.now(UTC)
    else:
        recorded_ref = None

    # "What did we talk about yesterday?": that period's day summaries,
    # fetched by date, first (services/episodes.py). Search cannot tell which
    # days "last week" means.
    #
    # "Yesterday" is relative to *when the question is being asked about*, not
    # to when it is being asked. An as_of query is a question about an earlier
    # present — "on 15 June, what had we talked about yesterday?" — so the
    # anchor is as_of's own calendar day and the window is 14 June. Anchoring
    # to the wall clock instead silently answered a different question, and
    # answered it with real memories, which is the worst kind of wrong: the
    # reply looked sourced.
    #
    # The tenant's timezone both ways (episodes._tz), because a calendar day
    # is a local thing: 15 June 00:30 UTC is still 14 June in New York, and
    # the day summaries are written per local day.
    dated: list[Any] = []
    reference_date = (
        _ensure_utc(as_of).astimezone(episodes._tz()).date()
        if as_of is not None
        else datetime.now(episodes._tz()).date()
    )
    by_strength = settings.memory_strength_rank
    search_statuses = (
        ("active", "superseded", "archived")
        if (as_of is not None or recorded_as_of is not None)
        else ("active",)
    )
    window = episodes.time_window(question, reference_date)
    if window is not None:
        ep_kwargs: dict[str, Any] = {"limit": limit}
        if "statuses" in inspect.signature(episodes.episodes_between).parameters:
            ep_kwargs["statuses"] = search_statuses
        dated = [
            m
            for m in await episodes.episodes_between(tenant_id, *window, **ep_kwargs)
            if is_bitemporally_valid(m, valid_at=as_of, recorded_at=recorded_ref)
        ][:limit]
    hits = await get_store().hybrid_search(
        embedding=embedding,
        query_text=question,
        limit=CANDIDATES * 2 if by_strength else CANDIDATES,
        statuses=search_statuses,
    )
    if by_strength:
        hits = strength_order(hits)[:CANDIDATES]
    hits = provenance_tiebreak_order(hits)
    candidates = [m for m, _ in hits]
    ref_time = _ensure_utc(as_of) if as_of is not None else datetime.now(UTC)
    # §3.C — stop when the evidence is already sufficient. The best hit's own
    # calibrated confidence and entailment, not its search score, decide: when
    # fresh high-trust words already account for the question, every further
    # expansion below can only add distractors and latency.
    early = assess_hit_evidence(question, candidates[0], now=ref_time) if candidates else None
    early_exit = bool(early and early["sufficient"])
    if early_exit:
        logger.debug(
            "Retrieval early exit: top hit %s conf=%.3f entailment=%.3f",
            early["memory_id"],
            early["calibrated_confidence"],
            early["entailment_score"],
        )

    # A question that names a known person, project or thing also gets the
    # memories linked to it (services/entities.py): search finds what is worded
    # like the question, the link finds what is about the same thing. The
    # judge below still decides which of them answer it.
    from life_graph.services import entities

    linked: list[Any] = []
    asked = question
    try:
        named = [] if early_exit else await entities.known_in_text(tenant_id, question)
        if named:
            linked = await entities.memories_for(
                tenant_id, [eid for eid, _ in named], limit=max(ENTITY_CANDIDATES, limit)
            )
            known_ids = {m.id for m in candidates}
            candidates += [m for m in linked if m.id not in known_ids]
            # "When is Maha's birthday?" against "Mahalakshmi's birthday is …":
            # the judge is told they are one person (migration 057), else it
            # may drop the note as about someone else.
            hint = entities.alias_hint(tenant_id, named)
            if hint:
                asked = f"{question}\n({hint})"
    except Exception:  # noqa: BLE001 — the index is a bonus; search alone still answers
        logger.warning("Entity candidates failed; using search only", exc_info=True)
    if linked and ABOUT.search(question):
        # "Tell me everything about Dify": the memories linked to Dify are about
        # Dify by construction, and the judge dropped the one that mattered
        # ("Life Graph does NOT use … Dify", 2026-10-23). They go first, unjudged.
        current = [
            m
            for m in linked
            if is_bitemporally_valid(m, valid_at=ref_time, recorded_at=recorded_ref)
        ]
        return _result(question, (dated + current)[:limit], early=early, now=ref_time)
    if settings.memory_links and candidates and not early_exit:
        candidates = await _with_neighbours(tenant_id, candidates)

    seen = {m.id for m in dated}
    # A fact with an end date that has passed is no longer true ("in Chennai
    # until Friday"); when as_of is given, reconstruct validity at that point in time.
    memories = [
        m
        for m in candidates
        if m.id not in seen
        and is_bitemporally_valid(m, valid_at=ref_time, recorded_at=recorded_ref)
        # Asked about a time: other days' summaries only blur the answer.
        and not (window is not None and (m.properties or {}).get("kind") == episodes.KIND)
    ]
    cold_too = cold and settings.memory_cold_tier
    past = cold_too and memory_tiers.asks_about_past(question)
    if past:
        # "Where did I work before?": how things were is in the cold tier.
        known = {m.id for m in memories} | seen
        memories += [
            m
            for m in await _cold(embedding, question)
            if m.id not in known
            and is_bitemporally_valid(m, valid_at=ref_time, recorded_at=recorded_ref)
        ]
    picked = await _judged(asked, memories) if memories else []
    if picked is None:
        logger.warning("Memory relevance judge gave no answer; using the search order")
        # Unjudged, so active ones only: an unjudged cold hit is a guess, and
        # being returned would reawaken it (services/memory/tiers.py).
        warm = (
            memories
            if (as_of is not None or recorded_as_of is not None)
            else [m for m in memories if getattr(m, "status", "active") == "active"]
        )
        return _result(question, (dated + warm)[:limit], early=early, now=ref_time)
    if not picked and not dated and cold_too and not past:
        # Nothing warm answers: older memories might (nothing is forgotten).
        cold_rows = [
            m
            for m in await _cold(embedding, question)
            if is_bitemporally_valid(m, valid_at=ref_time, recorded_at=recorded_ref)
        ]
        picked = (await _judged(asked, cold_rows) or []) if cold_rows else []
    return _result(question, (dated + picked)[:limit], early=early, now=ref_time)


async def _cold(embedding: list[float], question: str) -> list[Any]:
    from life_graph.services.memory import tiers as memory_tiers

    try:
        return await memory_tiers.search(embedding, question)
    except Exception:  # noqa: BLE001 — the cold tier is a bonus
        logger.warning("Cold memory search failed", exc_info=True)
        return []


async def _judged(question: str, memories: list[Any]) -> list[Any] | None:
    """The *memories* the judge keeps, best first; None if it gave no answer."""
    keep = await judge(question, [m.content or "" for m in memories])
    if keep is None:
        return None
    return [memories[i] for i in keep]
