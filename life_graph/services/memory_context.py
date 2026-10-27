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
    'than guess. A note marked "as of" a date may have changed since: say so '
    "when it matters."
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


#: A day's conversation summary (services/episodes.py) is a paragraph, not a note.
MAX_EPISODE_CHARS = 900


def render(rows: list[tuple]) -> str:
    """rows: (content, created_at[, properties]). Empty string when there is nothing to show.

    A fact that changes over time (where the owner lives, their job, the
    current plan) is shown "as of" the day it was noted, so it is not read as
    true today; a day summary carries its own date.
    """
    if not rows:
        return ""
    lines = [HEADER]
    for row in rows[:MAX_MEMORIES]:
        content, created_at = row[0], row[1]
        props = (row[2] if len(row) > 2 else None) or {}
        episode = props.get("kind") == "episode"
        limit = MAX_EPISODE_CHARS if episode else MAX_CHARS
        text = " ".join((content or "").split())
        if len(text) > limit:
            text = text[: limit - 1] + "…"
        if episode or not created_at:
            when = ""
        elif props.get("changes_over_time"):
            when = f"(as of {created_at:%Y-%m-%d}) "
        else:
            when = f"({created_at:%Y-%m-%d}) "
        lines.append(f"- {when}{text}")
    return "\n".join(lines)


async def memory_block(
    tenant_id: str,
    message: str,
    history: list[dict] | None = None,
    *,
    used: list[dict] | None = None,
) -> str:
    """The block for the system prompt: the matching memories, a "nothing matches"
    note, or "" when memory could not be searched at all (no embedding, any error).

    *used*, when given, receives ``{"id", "content"}`` for each memory put in the
    block — what the turn's trace shows as "what shaped this answer"."""
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
    if used is not None:
        used.extend({"id": str(m.id), "content": m.content} for m in found[:MAX_MEMORIES])
    return render([(m.content, m.created_at, getattr(m, "properties", None)) for m in found])
