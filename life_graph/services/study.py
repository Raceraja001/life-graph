"""Study cards with spaced repetition (SM-2).

Phase G of docs/specs/assistant-capabilities.md. The user learns from what
they already captured: cards are written by the local model from pasted
notes or from memories matching a topic, kept free of duplicates, and
scheduled with SM-2. A card answered well comes back after 1, then 6 days,
then ever longer gaps; one forgotten starts over.

Reviewing works from the dashboard API or from Telegram:
``/review`` shows the next due card, ``/review show`` reveals the answer, and
``/review again|hard|good|easy`` grades it and moves on. The card being
reviewed in a chat is remembered in Redis.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from life_graph.config import settings
from life_graph.models.assistant import ReviewCard

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

GRADES = {"again": 1, "hard": 3, "good": 4, "easy": 5}
MAX_CARDS_PER_GENERATION = 15
MAX_SOURCE_CHARS = 8000
REVIEW_KEY = "telegram:review:{chat_id}"

_SYSTEM = (
    "You write flashcards for spaced-repetition study from the user's notes."
    " Each card tests ONE fact, idea or definition from the notes; never add"
    " facts that are not in the notes. The front is a short question; the back"
    " is a short answer (one or two sentences). Skip trivia, greetings and"
    f" anything personal or secret (passwords, numbers). At most {MAX_CARDS_PER_GENERATION} cards."
)
_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "flashcards",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "cards": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"front": {"type": "string"}, "back": {"type": "string"}},
                        "required": ["front", "back"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["cards"],
            "additionalProperties": False,
        },
    },
}


def dedup_key(front: str) -> str:
    norm = re.sub(r"[^a-z0-9]+", " ", front.lower()).strip()
    return hashlib.sha256(norm.encode()).hexdigest()


def schedule(
    ease: float, interval: int, reps: int, grade: str, today: date
) -> tuple[float, int, int, date]:
    """SM-2: (ease, interval days, repetitions, due date) after one review."""
    q = GRADES[grade]
    if q < 3:
        reps, interval = 0, 1
    else:
        reps += 1
        interval = 1 if reps == 1 else 6 if reps == 2 else max(1, round(interval * ease))
    ease = max(1.3, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    return round(ease, 3), interval, reps, today + timedelta(days=interval)


async def write_cards(text: str, *, client=None) -> list[dict[str, str]]:
    """Cards for ``text`` from the local model; [] on failure."""
    if not text.strip():
        return []
    if client is None:
        from life_graph.api.dependencies import get_lm_client

        client = get_lm_client()
    try:
        raw = await client.chat_local_only(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": text[:MAX_SOURCE_CHARS]},
            ],
            model=settings.lm_extraction_model or None,
            temperature=0.2,
            max_tokens=2000,
            response_format=_SCHEMA,
        )
        cards = json.loads(raw).get("cards") if raw else None
    except Exception:
        logger.warning("Local flashcard generation failed", exc_info=True)
        return []
    out = []
    for c in cards or []:
        if not isinstance(c, dict):
            continue
        front, back = str(c.get("front") or "").strip(), str(c.get("back") or "").strip()
        if front and back and len(front) <= 500 and len(back) <= 1500:
            out.append({"front": front, "back": back})
    return out[:MAX_CARDS_PER_GENERATION]


async def add_cards(
    session: AsyncSession,
    tenant_id: str,
    cards: list[dict[str, str]],
    *,
    deck: str,
    today: date,
    source_memory_id: uuid.UUID | None = None,
) -> int:
    """Insert cards, due today; duplicates (same front) are skipped."""
    added = 0
    for card in cards:
        result = await session.execute(
            insert(ReviewCard)
            .values(
                tenant_id=tenant_id,
                deck=(deck or "general")[:80],
                front=card["front"],
                back=card["back"],
                source_memory_id=source_memory_id,
                due_on=today,
                dedup_key=dedup_key(card["front"]),
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "dedup_key"])
        )
        added += result.rowcount or 0
    return added


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def memories_about(session: AsyncSession, tenant_id: str, topic: str, limit: int = 25) -> str:
    """Approved memories mentioning ``topic``, as study source text."""
    from life_graph.models.db import Memory

    rows = (
        (
            await session.execute(
                select(Memory.content)
                .where(
                    Memory.tenant_id == tenant_id,
                    Memory.status == "active",
                    Memory.content.ilike(f"%{_like_escape(topic.strip())}%", escape="\\"),
                )
                .order_by(Memory.importance.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return "\n".join(f"- {r}" for r in rows)


async def generate(
    session: AsyncSession,
    tenant_id: str,
    *,
    today: date,
    text: str | None = None,
    topic: str | None = None,
    deck: str | None = None,
    client=None,
) -> dict[str, Any]:
    """Write and store cards from pasted notes or from memories on a topic."""
    source = (text or "").strip()
    if not source and topic:
        source = await memories_about(session, tenant_id, topic)
        if not source:
            return {"written": 0, "added": 0, "note": f"No approved memories mention {topic!r}."}
    cards = await write_cards(source, client=client)
    added = await add_cards(session, tenant_id, cards, deck=deck or topic or "general", today=today)
    return {"written": len(cards), "added": added}


async def due_cards(
    session: AsyncSession, tenant_id: str, today: date, limit: int = 20, deck: str | None = None
) -> list[ReviewCard]:
    stmt = select(ReviewCard).where(ReviewCard.tenant_id == tenant_id, ReviewCard.due_on <= today)
    if deck:
        stmt = stmt.where(ReviewCard.deck == deck)
    return list(
        (
            await session.execute(
                stmt.order_by(ReviewCard.due_on, ReviewCard.created_at).limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def count_due(session: AsyncSession, tenant_id: str, today: date) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(ReviewCard)
            .where(ReviewCard.tenant_id == tenant_id, ReviewCard.due_on <= today)
        )
    ).scalar_one()


def deck_row(deck: str, cards: int, due: int, reviewed: int, remembered: int) -> dict[str, Any]:
    """One deck's counts; retention is the share of reviewed cards whose last
    answer was not "again" (None until a card has been reviewed)."""
    return {
        "deck": deck,
        "cards": cards,
        "due": due,
        "reviewed": reviewed,
        "retention": round(remembered / reviewed, 3) if reviewed else None,
    }


async def deck_stats(session: AsyncSession, tenant_id: str, today: date) -> list[dict[str, Any]]:
    """Every deck with its card, due and reviewed counts, most cards first."""
    reviewed = ReviewCard.reviews > 0
    stmt = (
        select(
            ReviewCard.deck,
            func.count(),
            func.count().filter(ReviewCard.due_on <= today),
            func.count().filter(reviewed),
            func.count().filter(reviewed, func.coalesce(ReviewCard.last_grade, "") != "again"),
        )
        .where(ReviewCard.tenant_id == tenant_id)
        .group_by(ReviewCard.deck)
        .order_by(func.count().desc(), ReviewCard.deck)
    )
    return [deck_row(*row) for row in (await session.execute(stmt)).all()]


async def get_card(session: AsyncSession, tenant_id: str, card_id: uuid.UUID) -> ReviewCard | None:
    return (
        await session.execute(
            select(ReviewCard).where(ReviewCard.tenant_id == tenant_id, ReviewCard.id == card_id)
        )
    ).scalar_one_or_none()


def grade_card(card: ReviewCard, grade: str, today: date) -> ReviewCard:
    if grade not in GRADES:
        raise ValueError(f"grade must be one of {', '.join(GRADES)}")
    card.ease, card.interval_days, card.repetitions, card.due_on = schedule(
        card.ease, card.interval_days, card.repetitions, grade, today
    )
    card.last_grade = grade
    card.reviews = (card.reviews or 0) + 1
    return card


def card_dict(c: ReviewCard) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "deck": c.deck,
        "front": c.front,
        "back": c.back,
        "due_on": c.due_on.isoformat(),
        "interval_days": c.interval_days,
        "repetitions": c.repetitions,
        "ease": c.ease,
        "reviews": c.reviews,
        "last_grade": c.last_grade,
    }


def brief_line(due: int) -> str | None:
    return f"Study: {due} card{'s' if due != 1 else ''} due — /review on Telegram" if due else None


# ── Telegram /review ────────────────────────────────────────────────────────


async def _remember(chat_id: int, card_id: str | None) -> None:
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return
    key = REVIEW_KEY.format(chat_id=chat_id)
    try:
        if card_id:
            await redis.set(key, card_id, ex=6 * 3600)
        else:
            await redis.delete(key)
    except Exception:  # noqa: BLE001
        logger.warning("telegram review state not saved", exc_info=True)


async def _current(chat_id: int) -> str | None:
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(REVIEW_KEY.format(chat_id=chat_id))
    except Exception:  # noqa: BLE001
        return None
    return raw.decode() if isinstance(raw, bytes) else raw


async def telegram_review(chat_id: int, tenant_id: str, arg: str, today: date | None = None) -> str:
    """One step of a review session in a chat; returns the reply text."""
    from life_graph.services.assistant_daily import user_today
    from life_graph.storage.database import async_session

    today = today or user_today()
    word = (arg or "").strip().lower()
    async with async_session() as session:
        if word in ("show", "answer"):
            current = await _current(chat_id)
            card = await get_card(session, tenant_id, uuid.UUID(current)) if current else None
            if card is None:
                return "No card in progress. /review to start."
            return f"A: {card.back}\n\nHow did you do? /review again · hard · good · easy"
        prefix = ""
        if word in GRADES:
            current = await _current(chat_id)
            card = await get_card(session, tenant_id, uuid.UUID(current)) if current else None
            if card is None:
                return "No card in progress. /review to start."
            grade_card(card, word, today)
            await session.commit()
            prefix = f"Next time: in {card.interval_days} day{'s' if card.interval_days != 1 else ''}.\n\n"
        elif word:
            return "Use /review, /review show, or /review again|hard|good|easy."
        nxt = await due_cards(session, tenant_id, today, limit=1)
        left = await count_due(session, tenant_id, today)
    if not nxt:
        await _remember(chat_id, None)
        return prefix + "Nothing due. Well done."
    card = nxt[0]
    await _remember(chat_id, str(card.id))
    return f"{prefix}[{card.deck}] {left} due\n\nQ: {card.front}\n\n/review show for the answer"
