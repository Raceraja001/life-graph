"""What Jarvis remembers, put in front of it before it answers.

Until 2026-10-22 Jarvis saw a memory only if it chose to call the
``memory_search`` tool, and cloud runs do not have that tool at all: the
memory layer, Life Graph's core, reached almost no answer. Now a personal
request (which runs on this machine's model, services/lead.py) starts with
the owner's memories that match it. Never on a cloud run: these are personal.

Search alone always returns its nearest memories, related or not, so the
candidates pass through the local relevance judge first
(services/memory_retrieval.py); when none help, the block says so.
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
    "Notes kept from earlier conversations that match this message. Use what "
    "answers it; if they don't fully answer it, say what you don't know rather "
    "than guess."
)
NOTHING_FOUND = (
    "## What you remember about the owner\n"
    "Nothing you remember matches this message. If it asks about the owner's own"
    " life and your tools can't find it either, say you don't know."
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
    """The block for the system prompt: the matching memories, a "nothing matches"
    note, or "" when memory could not be searched at all (no embedding, any error)."""
    from life_graph.api.dependencies import get_store
    from life_graph.core.tenant import tenant_scope

    query = search_text(message, history)
    if not query:
        return ""
    from life_graph.services.memory_retrieval import retrieve

    try:
        with tenant_scope(tenant_id):
            found = await retrieve(query, limit=MAX_MEMORIES)
            if found:
                # Being put in front of the model is being read: it counts for
                # ranking and decay, like any other recall.
                await get_store().touch_many([m.id for m in found])
    except Exception as exc:  # noqa: BLE001 — memory is a bonus, never a failed answer
        # Never the message text in the log: it is personal.
        logger.warning("Memory context failed (%d chars): %s", len(query), exc)
        return ""
    if found is None:
        return ""  # memory could not be searched: say nothing rather than "nothing found"
    if not found:
        # Said, not left out: without it the model fills the gap with a guess.
        return NOTHING_FOUND
    return render([(m.content, m.created_at) for m in found])
