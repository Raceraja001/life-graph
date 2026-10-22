"""What Jarvis remembers, put in front of it before it answers.

Until 2026-10-22 Jarvis saw a memory only if it chose to call the
``memory_search`` tool, and cloud runs do not have that tool at all: the
memory layer, Life Graph's core, reached almost no answer. Now a personal
request (which runs on this machine's model, services/lead.py) starts with
the owner's memories that match it. Never on a cloud run: these are personal.

There is no relevance score that separates a real match from the nearest
unrelated memory yet (evals/score-separability.md), so the block says so and
tells the model to use only what applies.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_MEMORIES = 6
MAX_CHARS = 300
#: A follow-up this short ("what about last year?") is searched together
#: with the owner's previous message.
FOLLOW_UP_WORDS = 8

HEADER = (
    "## What you remember about the owner\n"
    "Notes kept from earlier conversations, found by searching for this message. "
    "Some may not be relevant: use only those that are, and don't mention the rest. "
    "If they don't answer the question, say you don't know rather than guess."
)


def search_text(message: str, history: list[dict[str, Any]] | None) -> str:
    """The text to search memories for: the message, plus the previous one for a short follow-up."""
    message = (message or "").strip()
    if len(message.split()) >= FOLLOW_UP_WORDS:
        return message
    previous = next(
        (m.get("content", "") for m in reversed(history or []) if m.get("role") == "user"),
        "",
    )
    return f"{previous.strip()}\n{message}".strip()


def render(rows: list[tuple[str, Any]]) -> str:
    """rows: (content, created_at). Empty string when there is nothing to show."""
    if not rows:
        return ""
    lines = [HEADER]
    for content, created_at in rows[:MAX_MEMORIES]:
        text = " ".join((content or "").split())
        if len(text) > MAX_CHARS:
            text = text[: MAX_CHARS - 1] + "…"
        when = f"({created_at:%Y-%m-%d}) " if created_at else ""
        lines.append(f"- {when}{text}")
    return "\n".join(lines)


async def memory_block(tenant_id: str, message: str, history: list[dict] | None = None) -> str:
    """The block for the system prompt, or "" (no match, no embedding, any error)."""
    from life_graph.api.dependencies import get_memory_manager, get_store
    from life_graph.core.tenant import tenant_scope

    query = search_text(message, history)
    if not query:
        return ""
    try:
        with tenant_scope(tenant_id):
            embedding = await get_memory_manager().generate_embedding(query)
            if not embedding:
                return ""
            store = get_store()
            hits = await store.hybrid_search(
                embedding=embedding,
                query_text=query,
                limit=MAX_MEMORIES,
                statuses=("active",),
            )
            if hits:
                # Being put in front of the model is being read: it counts for
                # ranking and decay, like any other recall.
                await store.touch_many([m.id for m, _ in hits])
    except Exception as exc:  # noqa: BLE001 — memory is a bonus, never a failed answer
        # Never the message text in the log: it is personal.
        logger.warning("Memory context failed (%d chars): %s", len(query), exc)
        return ""
    return render([(m.content, m.created_at) for m, _ in hits])
