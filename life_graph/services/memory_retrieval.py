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
from typing import Any

logger = logging.getLogger(__name__)

CANDIDATES = 10

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
    now = datetime.now(UTC)
    seen = {m.id for m in dated}
    # A fact with an end date that has passed is no longer true ("in Chennai
    # until Friday"); it stays stored, but it does not answer questions.
    memories = [
        m
        for m, _ in hits
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
