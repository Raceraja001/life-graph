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
#: "Tell me about Nila" needs her school, class, age and dance class at once: with six
#: notes, newest first, two of four were cut (Kavitha's test life, 2026-11-01).
ABOUT_MEMORIES = 12
MAX_CHARS = 300
#: A follow-up this short ("what about last year?") is searched together
#: with the owner's previous message.
FOLLOW_UP_WORDS = 8

#: Jarvis's prompt speaks of "the user", the notes of "the owner": without this a
#: local model asked "what is my blood group?" read "The owner's blood group is
#: O negative." and said it didn't know (bake-off, 2026-11-01).
WHO = (
    'The owner in these notes is the person talking to you: their "I", "me" and '
    '"my" mean the owner, so "my blood group" is the owner\'s blood group.'
)

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


def render(rows: list[tuple], most: int = MAX_MEMORIES) -> str:
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
    for row in rows[:most]:
        content, created_at = row[0], row[1]
        props = (row[2] if len(row) > 2 else None) or {}
        episode = props.get("kind") == "episode"
        limit = MAX_EPISODE_CHARS if episode else MAX_CHARS
        text = " ".join((content or "").split())
        if len(text) > limit:
            text = text[: limit - 1] + "…"
        kind = props.get("evidence")
        label = "" if episode or kind in (None, ev.SAID) else ev.PROMPT_LABEL.get(kind, "")
        # An archived or replaced memory (services/memory_tiers.py) says so.
        label = " · ".join(x for x in (props.get("tier"), label) if x)
        tail = f" · {label}" if label else ""
        if episode or not created_at:
            when = f"({label}) " if label else ""
        elif props.get("changes_over_time") and not props.get("tier"):
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
    from life_graph.services import memory_tiers

    if tier := memory_tiers.label(m):
        props["tier"] = tier
    return (m.content, m.created_at, props)


async def _strengthen(tenant_id: str, found: list) -> None:
    """What one answer used is linked (services/associations.py), and an
    archived memory that answered goes back to active (services/memory_tiers.py)."""
    from life_graph.services import associations, memory_tiers

    await associations.used_together(tenant_id, [m.id for m in found])
    try:
        await memory_tiers.reawaken(found)
    except Exception:  # noqa: BLE001 — bookkeeping; the answer still has the memory
        logger.warning("Reawakening used memories failed", exc_info=True)


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
    """WHO, then the card and the matching memories (see _sections) with guessed
    relations corrected; "" when there is nothing."""
    out = await _sections(tenant_id, message, history, used=used)
    if not out:
        return ""
    return f"{WHO}\n\n{await _relabelled(tenant_id, out)}"


async def _sections(
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
    from life_graph.services.memory_retrieval import ABOUT, retrieve

    cap = ABOUT_MEMORIES if ABOUT.search(message or "") else MAX_MEMORIES

    card = await _card(tenant_id)
    card_text = profile_card.render(card)
    on_card = {c["id"] for c in card}
    if used is not None:
        used.extend({"id": c["id"], "content": c["content"], "via": "profile"} for c in card)
    if profile_card.PAST.search(message or ""):
        # "Where did I work before?": the replaced values of the form, dated.
        try:
            earlier = await profile_card.history(tenant_id)
        except Exception as exc:  # noqa: BLE001 — history is a bonus
            logger.warning("Form history failed: %s", exc)
            earlier = []
        if earlier:
            # Shown once, here, even when the cold tier finds them too.
            on_card |= {e["id"] for e in earlier}
            card_text = "\n\n".join(
                t for t in (card_text, profile_card.render_history(earlier)) if t
            )
            if used is not None:
                used.extend(
                    {"id": e["id"], "content": e["content"], "via": "history"} for e in earlier
                )

    found = None
    try:
        with tenant_scope(tenant_id):
            found = await retrieve(query, limit=cap, cold=True)
            if found:
                # Already on the card: shown once, there.
                found = [m for m in found if str(m.id) not in on_card]
                if found:
                    # Being put in front of the model is being read: it counts
                    # for ranking and decay, like any other recall. The card's
                    # are not touched: always shown is not read, and counting
                    # it would freeze the card's own ranking.
                    await get_store().touch_many([m.id for m in found])
                    await _strengthen(tenant_id, found[:cap])
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
        used.extend({"id": str(m.id), "content": m.content} for m in found[:cap])
    block = render([_row(m) for m in found], cap)
    return f"{card_text}\n\n{block}" if card_text else block


async def _relabelled(tenant_id: str, block: str) -> str:
    """*block* with guessed relations corrected from the people table
    (services/entities.py relabel): "Senthil (the owner's colleague)" was the
    owner's husband on Kavitha's test life, and every "my husband" question missed."""
    from life_graph.services import entities

    try:
        return await entities.relabel(tenant_id, block)
    except Exception:  # noqa: BLE001 — a label fix never costs the memories
        logger.warning("Relabelling the memory block failed", exc_info=True)
        return block
