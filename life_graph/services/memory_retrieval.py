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

import json
import logging
import math
import re
from typing import Any

logger = logging.getLogger(__name__)

CANDIDATES = 10
#: Memories linked to an entity the question names, added to the judge's candidates.
ENTITY_CANDIDATES = 8
#: The best search hits whose linked memories are added (services/associations.py) …
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
    from life_graph.api.dependencies import get_lm_client
    from life_graph.config import settings

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
    from datetime import UTC, datetime

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
    them (services/associations.py): said or used together with a match."""
    from life_graph.services import associations

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
    if ev_kind == SAID or tier in ("self", "verified", "owner", "canonical") or src_type in ("user_explicit", "manual"):
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
        ev = evidence_of(getattr(m, "source_type", None), getattr(m, "trust_tier", None), props if isinstance(props, dict) else {})
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
    from datetime import UTC
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def is_valid_at(memory: Any, ref_time: datetime) -> bool:
    """Valid-time check: valid_from <= ref_time < valid_until."""
    ref = _ensure_utc(ref_time)
    v_from = getattr(memory, "valid_from", None)
    if v_from is not None and _ensure_utc(v_from) > ref:
        return False
    v_until = getattr(memory, "valid_until", None)
    if v_until is not None and _ensure_utc(v_until) <= ref:
        return False
    return True


def is_bitemporally_valid(
    memory: Any,
    *,
    valid_at: datetime | None = None,
    recorded_at: datetime | None = None,
) -> bool:
    """Full bitemporal check: valid time AND transaction time (created_at <= recorded_at)."""
    if valid_at is not None and not is_valid_at(memory, valid_at):
        return False
    if recorded_at is not None:
        rec = _ensure_utc(recorded_at)
        created = getattr(memory, "created_at", None)
        if created is not None and _ensure_utc(created) > rec:
            return False
    return True


async def retrieve(
    question: str,
    limit: int = 6,
    *,
    cold: bool = False,
    as_of: datetime | None = None,
    recorded_as_of: datetime | None = None,
) -> list[Any] | None:
    """Memories of the current tenant that help answer *question*, best first.

    Active memories first; archived and replaced ones (services/memory_tiers.py)
    when none of those helps, or alongside them when the question is about the
    past — only for a caller that labels them (*cold*, services/memory_context.py
    render); /ask and the dashboard chat would pass an old value on as current.
    ``[]`` means memory was searched and nothing helps; ``None`` means it
    could not be searched (no embedding), which a caller must not present as
    "nothing remembered". Falls back to the plain search order when the judge
    cannot answer, so a model outage costs precision, never the memories
    themselves.
    """
    from datetime import UTC, datetime

    from life_graph.api.dependencies import get_memory_manager, get_store
    from life_graph.config import settings
    from life_graph.core.tenant import get_current_tenant_id
    from life_graph.services import episodes, memory_tiers

    embedding = await get_memory_manager().generate_embedding(question)
    if not embedding:
        return None
    tenant_id = get_current_tenant_id()

    # "What did we talk about yesterday?": that period's day summaries,
    # fetched by date, first (services/episodes.py). Search cannot tell which
    # days "last week" means.
    dated: list[Any] = []
    window = episodes.time_window(question, datetime.now(episodes._tz()).date())
    if window is not None:
        dated = [m for m in await episodes.episodes_between(tenant_id, *window, limit=limit) if is_bitemporally_valid(m, valid_at=as_of, recorded_at=recorded_as_of)]

    by_strength = settings.memory_strength_rank
    search_statuses = ("active", "superseded", "archived") if (as_of is not None or recorded_as_of is not None) else ("active",)
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
    # A question that names a known person, project or thing also gets the
    # memories linked to it (services/entities.py): search finds what is worded
    # like the question, the link finds what is about the same thing. The
    # judge below still decides which of them answer it.
    from life_graph.services import entities

    linked: list[Any] = []
    asked = question
    try:
        named = await entities.known_in_text(tenant_id, question)
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
        ref_ = _ensure_utc(as_of) if as_of is not None else datetime.now(UTC)
        current = [m for m in linked if is_bitemporally_valid(m, valid_at=ref_, recorded_at=recorded_as_of)]
        return (dated + current)[:limit]
    if settings.memory_links and candidates:
        candidates = await _with_neighbours(tenant_id, candidates)

    ref_time = _ensure_utc(as_of) if as_of is not None else datetime.now(UTC)
    seen = {m.id for m in dated}
    # A fact with an end date that has passed is no longer true ("in Chennai
    # until Friday"); when as_of is given, reconstruct validity at that point in time.
    memories = [
        m
        for m in candidates
        if m.id not in seen
        and is_bitemporally_valid(m, valid_at=ref_time, recorded_at=recorded_as_of)
        # Asked about a time: other days' summaries only blur the answer.
        and not (window is not None and (m.properties or {}).get("kind") == episodes.KIND)
    ]
    cold_too = cold and settings.memory_cold_tier
    past = cold_too and memory_tiers.asks_about_past(question)
    if past:
        # "Where did I work before?": how things were is in the cold tier.
        known = {m.id for m in memories} | seen
        memories += [m for m in await _cold(embedding, question) if m.id not in known and is_bitemporally_valid(m, valid_at=ref_time, recorded_at=recorded_as_of)]
    picked = await _judged(asked, memories) if memories else []
    if picked is None:
        logger.warning("Memory relevance judge gave no answer; using the search order")
        # Unjudged, so active ones only: an unjudged cold hit is a guess, and
        # being returned would reawaken it (services/memory_tiers.py).
        warm = memories if (as_of is not None or recorded_as_of is not None) else [m for m in memories if getattr(m, "status", "active") == "active"]
        return (dated + warm)[:limit]
    if not picked and not dated and cold_too and not past:
        # Nothing warm answers: older memories might (nothing is forgotten).
        cold_rows = [m for m in await _cold(embedding, question) if is_bitemporally_valid(m, valid_at=ref_time, recorded_at=recorded_as_of)]
        picked = (await _judged(asked, cold_rows) or []) if cold_rows else []
    return (dated + picked)[:limit]


async def _cold(embedding: list[float], question: str) -> list[Any]:
    from life_graph.services import memory_tiers

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
