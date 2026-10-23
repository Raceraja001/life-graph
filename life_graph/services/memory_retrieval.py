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
import re
from typing import Any

logger = logging.getLogger(__name__)

CANDIDATES = 10
#: Memories linked to an entity the question names, added to the judge's candidates.
ENTITY_CANDIDATES = 8
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


async def retrieve(question: str, limit: int = 6) -> list[Any] | None:
    """Active memories of the current tenant that help answer *question*, best first.

    ``[]`` means memory was searched and nothing helps; ``None`` means it could
    not be searched (no embedding), which a caller must not present as "nothing
    remembered". Falls back to the plain search order when the judge cannot
    answer, so a model outage costs precision, never the memories themselves.
    """
    from datetime import UTC, datetime

    from life_graph.api.dependencies import get_memory_manager, get_store
    from life_graph.core.tenant import get_current_tenant_id
    from life_graph.services import episodes

    embedding = await get_memory_manager().generate_embedding(question)
    if not embedding:
        return None

    # "What did we talk about yesterday?": that period's day summaries,
    # fetched by date, first (services/episodes.py). Search cannot tell which
    # days "last week" means.
    dated: list[Any] = []
    window = episodes.time_window(question, datetime.now(episodes._tz()).date())
    if window is not None:
        dated = await episodes.episodes_between(get_current_tenant_id(), *window, limit=limit)

    hits = await get_store().hybrid_search(
        embedding=embedding, query_text=question, limit=CANDIDATES, statuses=("active",)
    )
    candidates = [m for m, _ in hits]
    # A question that names a known person, project or thing also gets the
    # memories linked to it (services/entities.py): search finds what is worded
    # like the question, the link finds what is about the same thing. The
    # judge below still decides which of them answer it.
    from life_graph.services import entities

    linked: list[Any] = []
    try:
        named = await entities.known_in_text(get_current_tenant_id(), question)
        if named:
            linked = await entities.memories_for(
                get_current_tenant_id(), [eid for eid, _ in named], limit=ENTITY_CANDIDATES
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
    if not memories:
        return dated[:limit]
    keep = await judge(question, [m.content or "" for m in memories])
    if keep is None:
        logger.warning("Memory relevance judge gave no answer; using the search order")
        return (dated + memories)[:limit]
    return (dated + [memories[i] for i in keep])[:limit]
