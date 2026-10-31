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


async def retrieve(question: str, limit: int = 6) -> list[Any] | None:
    """Memories of the current tenant that help answer *question*, best first.

    Active memories first; archived and replaced ones (services/memory_tiers.py)
    when none of those helps, or alongside them when the question is about the
    past. ``[]`` means memory was searched and nothing helps; ``None`` means it
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
        dated = await episodes.episodes_between(tenant_id, *window, limit=limit)

    by_strength = settings.memory_strength_rank
    hits = await get_store().hybrid_search(
        embedding=embedding,
        query_text=question,
        limit=CANDIDATES * 2 if by_strength else CANDIDATES,
        statuses=("active",),
    )
    if by_strength:
        hits = strength_order(hits)[:CANDIDATES]
    candidates = [m for m, _ in hits]
    # A question that names a known person, project or thing also gets the
    # memories linked to it (services/entities.py): search finds what is worded
    # like the question, the link finds what is about the same thing. The
    # judge below still decides which of them answer it.
    from life_graph.services import entities

    linked: list[Any] = []
    try:
        named = await entities.known_in_text(tenant_id, question)
        if named:
            linked = await entities.memories_for(
                tenant_id, [eid for eid, _ in named], limit=ENTITY_CANDIDATES
            )
            known_ids = {m.id for m in candidates}
            candidates += [m for m in linked if m.id not in known_ids]
    except Exception:  # noqa: BLE001 — the index is a bonus; search alone still answers
        logger.warning("Entity candidates failed; using search only", exc_info=True)
    if linked and ABOUT.search(question):
        # "Tell me everything about Dify": the memories linked to Dify are about
        # Dify by construction, and the judge dropped the one that mattered
        # ("Life Graph does NOT use … Dify", 2026-10-23). They go first, unjudged.
        now_ = datetime.now(UTC)
        current = [
            m for m in linked if getattr(m, "valid_until", None) is None or m.valid_until > now_
        ]
        return (dated + current)[:limit]
    if settings.memory_links and candidates:
        candidates = await _with_neighbours(tenant_id, candidates)

    now = datetime.now(UTC)
    seen = {m.id for m in dated}
    # A fact with an end date that has passed is no longer true ("in Chennai
    # until Friday"); it stays stored, but it does not answer questions.
    memories = [
        m
        for m in candidates
        if m.id not in seen
        and (getattr(m, "valid_until", None) is None or m.valid_until > now)
        # Asked about a time: other days' summaries only blur the answer.
        and not (window is not None and (m.properties or {}).get("kind") == episodes.KIND)
    ]
    cold_too = settings.memory_cold_tier
    past = cold_too and memory_tiers.asks_about_past(question)
    if past:
        # "Where did I work before?": how things were is in the cold tier.
        known = {m.id for m in memories} | seen
        memories += [m for m in await _cold(embedding, question) if m.id not in known]
    picked = await _judged(question, memories) if memories else []
    if picked is None:
        logger.warning("Memory relevance judge gave no answer; using the search order")
        return (dated + memories)[:limit]
    if not picked and not dated and cold_too and not past:
        # Nothing warm answers: older memories might (nothing is forgotten).
        cold = await _cold(embedding, question)
        picked = (await _judged(question, cold) or []) if cold else []
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
