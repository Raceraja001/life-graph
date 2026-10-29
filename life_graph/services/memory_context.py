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

from life_graph.core import evidence as ev

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
    'when it matters. A note marked "your guess" or "unverified" is not something '
    'the owner told you: present it as a guess ("I think …"), never as a fact.'
)
NOTHING_FOUND = (
    "## What you remember about the owner\n"
    "Nothing you remember matches this message. If it asks about the owner's own"
    " life and your tools can't find it either, say you don't know."
)
#: With the profile card shown, "nothing matches" would contradict it.
NOTHING_ELSE = (
    "## What you remember about the owner\n"
    "No other notes match this message. If the facts above don't answer it and "
    "your tools can't find it either, say you don't know."
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
    true today; a day summary carries its own date. A note that is not the
    owner's own word is labelled with where it came from (core/evidence.py):
    the caller sets properties["evidence"] for rows written before it was
    stamped.
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
        kind = props.get("evidence")
        label = "" if episode or kind in (None, ev.SAID) else ev.PROMPT_LABEL.get(kind, "")
        tail = f" · {label}" if label else ""
        if episode or not created_at:
            when = f"({label}) " if label else ""
        elif props.get("changes_over_time"):
            when = f"(as of {created_at:%Y-%m-%d}{tail}) "
        else:
            when = f"({created_at:%Y-%m-%d}{tail}) "
        lines.append(f"- {when}{text}")
    return "\n".join(lines)


def _row(m) -> tuple:
    props = dict(getattr(m, "properties", None) or {})
    props["evidence"] = ev.evidence_of(
        getattr(m, "source_type", None), getattr(m, "trust_tier", None), props
    )
    return (m.content, m.created_at, props)


async def _card(tenant_id: str) -> list[dict]:
    from life_graph.services import profile_card

    try:
        return await profile_card.card_items(tenant_id)
    except Exception as exc:  # noqa: BLE001 — the card is a bonus, like the rest of memory
        logger.warning("Profile card failed: %s", exc)
        return []


async def memory_block(
    tenant_id: str,
    message: str,
    history: list[dict] | None = None,
    *,
    used: list[dict] | None = None,
) -> str:
    """The block for the system prompt: the owner's profile card (services/profile_card.py),
    then the matching memories or a "nothing (else) matches" note. "" when there is
    no card and memory could not be searched at all (no embedding, any error).

    *used*, when given, receives ``{"id", "content"}`` for each memory put in the
    block (with ``"via": "profile"`` for the card's) — what the turn's trace
    shows as "what shaped this answer"."""
    from life_graph.api.dependencies import get_store
    from life_graph.core.tenant import tenant_scope
    from life_graph.services import profile_card

    query = search_text(message, history)
    if not query:
        return ""
    from life_graph.services.memory_retrieval import retrieve

    card = await _card(tenant_id)
    card_text = profile_card.render(card)
    on_card = {c["id"] for c in card}
    if used is not None:
        used.extend({"id": c["id"], "content": c["content"], "via": "profile"} for c in card)

    found = None
    try:
        with tenant_scope(tenant_id):
            found = await retrieve(query, limit=MAX_MEMORIES)
            if found:
                # Already on the card: shown once, there.
                found = [m for m in found if str(m.id) not in on_card]
                if found:
                    # Being put in front of the model is being read: it counts
                    # for ranking and decay, like any other recall. The card's
                    # are not touched: always shown is not read, and counting
                    # it would freeze the card's own ranking.
                    await get_store().touch_many([m.id for m in found])
    except Exception as exc:  # noqa: BLE001 — memory is a bonus, never a failed answer
        # Never the message text in the log: it is personal.
        logger.warning("Memory context failed (%d chars): %s", len(query), exc)
        found = None
    if found is None:
        # Memory could not be searched: the card alone, never "nothing found".
        return card_text
    if not found:
        # Said, not left out: without it the model fills the gap with a guess.
        return f"{card_text}\n\n{NOTHING_ELSE}" if card_text else NOTHING_FOUND
    if used is not None:
        used.extend({"id": str(m.id), "content": m.content} for m in found[:MAX_MEMORIES])
    block = render([_row(m) for m in found])
    return f"{card_text}\n\n{block}" if card_text else block
