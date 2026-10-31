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

The 2026-10 upgrade (docs/research/study-helper-spec-2026-10.html, migration
056) keeps SM-2 and adds: a review log (``StudyReview``) behind streaks and
accuracy per deck, a lapse count with a leech flag, and draft cards — written
by the local model from one saved memory, document, topic or pasted notes,
then edited, accepted or dropped by the owner before they are scheduled.
Only ``active`` cards are ever due or counted.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from life_graph.config import settings
from life_graph.models.assistant import ReviewCard, StudyReview

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

GRADES = {"again": 1, "hard": 3, "good": 4, "easy": 5}
MAX_CARDS_PER_GENERATION = 15
MAX_SOURCE_CHARS = 8000
REVIEW_KEY = "telegram:review:{chat_id}"
DRAFTS_KEY = "telegram:drafts:{chat_id}"

DRAFT, ACTIVE, SUSPENDED = "draft", "active", "suspended"
SOURCE_KINDS = ("text", "topic", "memory", "document")
#: Anki's default: a card forgotten this often is a leech (flagged, not suspended).
LEECH_LAPSES = 8
#: An interval this long makes a card "mature" (Anki's convention).
MATURE_DAYS = 21
ACCURACY_DAYS = 30
STREAK_LOOKBACK_DAYS = 400


class DuplicateCardError(ValueError):
    """Another card of this tenant already has that front."""


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
    source_kind: str | None = None,
    source_id: uuid.UUID | None = None,
) -> int:
    """Insert cards, active and due today; duplicates (same front) are skipped."""
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
                status=ACTIVE,
                lapses=0,
                source_kind=source_kind,
                source_id=source_id,
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "dedup_key"])
        )
        added += result.rowcount or 0
    return added


async def stage_drafts(
    session: AsyncSession,
    tenant_id: str,
    cards: list[dict[str, str]],
    *,
    deck: str,
    today: date,
    source_kind: str,
    source_id: uuid.UUID | None = None,
) -> list[uuid.UUID]:
    """Insert cards as drafts (not due until accepted); ids of those inserted.

    A front that already exists (draft or not) is skipped, as for add_cards."""
    ids: list[uuid.UUID] = []
    for card in cards:
        result = await session.execute(
            insert(ReviewCard)
            .values(
                tenant_id=tenant_id,
                deck=(deck or "general")[:80],
                front=card["front"],
                back=card["back"],
                source_memory_id=source_id if source_kind == "memory" else None,
                due_on=today,
                dedup_key=dedup_key(card["front"]),
                status=DRAFT,
                lapses=0,
                source_kind=source_kind,
                source_id=source_id,
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "dedup_key"])
            .returning(ReviewCard.id)
        )
        new_id = result.scalar_one_or_none()
        if new_id is not None:
            ids.append(new_id)
    return ids


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
    added = await add_cards(
        session,
        tenant_id,
        cards,
        deck=deck or topic or "general",
        today=today,
        source_kind="text" if (text or "").strip() else "topic",
    )
    return {"written": len(cards), "added": added}


# ── Drafts: cards the owner checks before they are scheduled ────────────────


async def source_text(
    session: AsyncSession,
    tenant_id: str,
    source: str,
    *,
    source_id: uuid.UUID | None = None,
    topic: str | None = None,
    text: str | None = None,
) -> tuple[str, str]:
    """(study text, default deck) for one of SOURCE_KINDS; ("", …) when there is none.

    A memory must be the tenant's and active; a document gives its title,
    issuer, kind and notes — never its number."""
    if source == "text":
        return (text or "").strip(), "notes"
    if source == "topic":
        return (await memories_about(session, tenant_id, topic or "") if topic else ""), (
            topic or "general"
        )
    if source_id is None:
        return "", "general"
    if source == "memory":
        from life_graph.models.db import Memory

        content = (
            await session.execute(
                select(Memory.content).where(
                    Memory.tenant_id == tenant_id,
                    Memory.id == source_id,
                    Memory.status == "active",
                )
            )
        ).scalar_one_or_none()
        return (content or "").strip(), "notes"
    if source == "document":
        from life_graph.models.assistant import Document

        doc = (
            await session.execute(
                select(Document).where(Document.tenant_id == tenant_id, Document.id == source_id)
            )
        ).scalar_one_or_none()
        if doc is None:
            return "", "general"
        lines = [f"Title: {doc.title}", f"Kind: {doc.kind}"]
        if doc.issuer:
            lines.append(f"Issuer: {doc.issuer}")
        if doc.issued_on:
            lines.append(f"Issued: {doc.issued_on.isoformat()}")
        if doc.expires_on:
            lines.append(f"Expires: {doc.expires_on.isoformat()}")
        if doc.notes:
            lines.append(f"Notes:\n{doc.notes}")
        return "\n".join(lines), (doc.title or "documents")[:80]
    raise ValueError(f"source must be one of {', '.join(SOURCE_KINDS)}")


async def draft(
    session: AsyncSession,
    tenant_id: str,
    *,
    today: date,
    source: str,
    source_id: uuid.UUID | None = None,
    topic: str | None = None,
    text: str | None = None,
    deck: str | None = None,
    client=None,
) -> dict[str, Any]:
    """Draft cards from one source with the LOCAL model; the owner accepts them later."""
    if source not in SOURCE_KINDS:
        raise ValueError(f"source must be one of {', '.join(SOURCE_KINDS)}")
    body, default_deck = await source_text(
        session, tenant_id, source, source_id=source_id, topic=topic, text=text
    )
    if not body:
        return {
            "written": 0,
            "drafted": 0,
            "drafts": [],
            "note": f"Nothing to study in that {source}.",
        }
    cards = await write_cards(body, client=client)
    ids = await stage_drafts(
        session,
        tenant_id,
        cards,
        deck=deck or default_deck,
        today=today,
        source_kind=source,
        source_id=source_id,
    )
    rows = await cards_by_ids(session, tenant_id, ids) if ids else []
    return {"written": len(cards), "drafted": len(ids), "drafts": [card_dict(c) for c in rows]}


async def cards_by_ids(
    session: AsyncSession, tenant_id: str, ids: list[uuid.UUID]
) -> list[ReviewCard]:
    return list(
        (
            await session.execute(
                select(ReviewCard)
                .where(ReviewCard.tenant_id == tenant_id, ReviewCard.id.in_(ids))
                .order_by(ReviewCard.created_at, ReviewCard.id)
            )
        )
        .scalars()
        .all()
    )


async def list_drafts(session: AsyncSession, tenant_id: str, limit: int = 50) -> list[ReviewCard]:
    return list(
        (
            await session.execute(
                select(ReviewCard)
                .where(ReviewCard.tenant_id == tenant_id, ReviewCard.status == DRAFT)
                .order_by(ReviewCard.created_at, ReviewCard.id)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def accept_drafts(
    session: AsyncSession, tenant_id: str, today: date, ids: list[uuid.UUID] | None = None
) -> int:
    """Drafts become active and due today; ``ids=None`` accepts every draft."""
    stmt = update(ReviewCard).where(ReviewCard.tenant_id == tenant_id, ReviewCard.status == DRAFT)
    if ids is not None:
        if not ids:
            return 0
        stmt = stmt.where(ReviewCard.id.in_(ids))
    result = await session.execute(
        stmt.values(status=ACTIVE, due_on=today).execution_options(synchronize_session=False)
    )
    return result.rowcount or 0


async def reject_drafts(
    session: AsyncSession, tenant_id: str, ids: list[uuid.UUID] | None = None
) -> int:
    """Delete drafts (never a scheduled card); ``ids=None`` drops every draft."""
    stmt = delete(ReviewCard).where(ReviewCard.tenant_id == tenant_id, ReviewCard.status == DRAFT)
    if ids is not None:
        if not ids:
            return 0
        stmt = stmt.where(ReviewCard.id.in_(ids))
    result = await session.execute(stmt.execution_options(synchronize_session=False))
    return result.rowcount or 0


async def edit_card(
    session: AsyncSession,
    tenant_id: str,
    card: ReviewCard,
    *,
    front: str | None = None,
    back: str | None = None,
    deck: str | None = None,
    status: str | None = None,
) -> ReviewCard:
    """Change a card's text, deck, or suspend/unsuspend it.

    A draft is made active by accepting it, not here. A new front that another
    card already has raises DuplicateCardError."""
    if card.tenant_id != tenant_id:
        raise ValueError("not this tenant's card")
    if status is not None:
        if status not in (ACTIVE, SUSPENDED):
            raise ValueError("status must be active or suspended")
        if card.status == DRAFT:
            raise ValueError("accept the draft first")
    if front is not None:
        front = front.strip()
        if not front:
            raise ValueError("front must not be empty")
        key = dedup_key(front)
        if key != card.dedup_key:
            clash = (
                await session.execute(
                    select(ReviewCard.id).where(
                        ReviewCard.tenant_id == tenant_id,
                        ReviewCard.dedup_key == key,
                        ReviewCard.id != card.id,
                    )
                )
            ).scalar_one_or_none()
            if clash is not None:
                raise DuplicateCardError("another card already asks that")
            card.dedup_key = key
        card.front = front
    if back is not None:
        if not back.strip():
            raise ValueError("back must not be empty")
        card.back = back.strip()
    if deck is not None:
        card.deck = (deck.strip() or "general")[:80]
    if status is not None:
        card.status = status
    return card


async def due_cards(
    session: AsyncSession, tenant_id: str, today: date, limit: int = 20, deck: str | None = None
) -> list[ReviewCard]:
    stmt = select(ReviewCard).where(
        ReviewCard.tenant_id == tenant_id,
        ReviewCard.status == ACTIVE,
        ReviewCard.due_on <= today,
    )
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
            .where(
                ReviewCard.tenant_id == tenant_id,
                ReviewCard.status == ACTIVE,
                ReviewCard.due_on <= today,
            )
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
        .where(ReviewCard.tenant_id == tenant_id, ReviewCard.status == ACTIVE)
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
    # A lapse: forgetting a card that had been remembered.
    lapsed = GRADES[grade] < 3 and (card.repetitions or 0) > 0
    card.ease, card.interval_days, card.repetitions, card.due_on = schedule(
        card.ease, card.interval_days, card.repetitions, grade, today
    )
    card.last_grade = grade
    card.reviews = (card.reviews or 0) + 1
    card.lapses = (card.lapses or 0) + (1 if lapsed else 0)
    card.last_reviewed_on = today
    return card


async def review(
    session: AsyncSession,
    tenant_id: str,
    card: ReviewCard,
    grade: str,
    today: date,
    now: datetime | None = None,
) -> ReviewCard:
    """Grade an active card and log the answer (StudyReview) for streaks and accuracy."""
    if card.tenant_id != tenant_id:
        raise ValueError("not this tenant's card")
    if card.status not in (None, ACTIVE):
        raise ValueError(f"a {card.status} card is not reviewed; accept or unsuspend it first")
    before = card.interval_days or 0
    grade_card(card, grade, today)
    session.add(
        StudyReview(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            card_id=card.id,
            deck=card.deck,
            grade=grade,
            reviewed_on=today,
            reviewed_at=now or datetime.now(UTC),
            interval_before=before,
            interval_after=card.interval_days,
            ease_after=card.ease,
        )
    )
    return card


def maturity(c: ReviewCard) -> str:
    """new (never reviewed), learning (just forgotten), young, or mature (≥ 21 days)."""
    if not c.reviews:
        return "new"
    if not c.repetitions:
        return "learning"
    return "mature" if (c.interval_days or 0) >= MATURE_DAYS else "young"


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
        "status": c.status or ACTIVE,
        "lapses": c.lapses or 0,
        "leech": (c.lapses or 0) >= LEECH_LAPSES,
        "maturity": maturity(c),
        "last_reviewed_on": c.last_reviewed_on.isoformat() if c.last_reviewed_on else None,
        "source_kind": c.source_kind,
        "source_id": str(c.source_id) if c.source_id else None,
    }


# ── Progress ────────────────────────────────────────────────────────────────


def streak_days(days: set[date], today: date) -> int:
    """Consecutive days with a review, ending today — or yesterday, when today
    has no review yet (the streak is still alive until the day ends)."""
    day = today if today in days else today - timedelta(days=1)
    n = 0
    while day in days:
        n += 1
        day -= timedelta(days=1)
    return n


def share(ok: int, total: int) -> float | None:
    return round(ok / total, 3) if total else None


async def progress(session: AsyncSession, tenant_id: str, today: date) -> dict[str, Any]:
    """Due, new/learning/young/mature, drafts, streak and accuracy per deck."""
    active = ReviewCard.status == ACTIVE
    counts = (
        await session.execute(
            select(
                func.count().filter(active, ReviewCard.due_on <= today),
                func.count().filter(active, ReviewCard.reviews == 0),
                func.count().filter(active, ReviewCard.reviews > 0, ReviewCard.repetitions == 0),
                func.count().filter(
                    active, ReviewCard.repetitions > 0, ReviewCard.interval_days < MATURE_DAYS
                ),
                func.count().filter(
                    active, ReviewCard.repetitions > 0, ReviewCard.interval_days >= MATURE_DAYS
                ),
                func.count().filter(ReviewCard.status == DRAFT),
                func.count().filter(ReviewCard.status == SUSPENDED),
                func.count().filter(active, ReviewCard.lapses >= LEECH_LAPSES),
            ).where(ReviewCard.tenant_id == tenant_id)
        )
    ).first() or (0,) * 8
    due, new, learning, young, mature, drafts, suspended, leeches = (int(x or 0) for x in counts)
    days = set(
        (
            await session.execute(
                select(StudyReview.reviewed_on)
                .where(
                    StudyReview.tenant_id == tenant_id,
                    StudyReview.reviewed_on > today - timedelta(days=STREAK_LOOKBACK_DAYS),
                    StudyReview.reviewed_on <= today,
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    reviewed_today = int(
        (
            await session.execute(
                select(func.count())
                .select_from(StudyReview)
                .where(StudyReview.tenant_id == tenant_id, StudyReview.reviewed_on == today)
            )
        ).scalar()
        or 0
    )
    deck_rows = (
        await session.execute(
            select(
                StudyReview.deck,
                func.count(),
                func.count().filter(StudyReview.grade != "again"),
            )
            .where(
                StudyReview.tenant_id == tenant_id,
                StudyReview.reviewed_on > today - timedelta(days=ACCURACY_DAYS),
            )
            .group_by(StudyReview.deck)
            .order_by(func.count().desc(), StudyReview.deck)
        )
    ).all()
    decks = [
        {"deck": d, "reviews": int(n), "accuracy": share(int(ok), int(n))} for d, n, ok in deck_rows
    ]
    total = sum(d["reviews"] for d in decks)
    ok_total = sum(int(ok) for _d, _n, ok in deck_rows)
    return {
        "due": due,
        "new": new,
        "learning": learning,
        "young": young,
        "mature": mature,
        "learned": young + mature,
        "drafts": drafts,
        "suspended": suspended,
        "leeches": leeches,
        "reviewed_today": reviewed_today,
        "streak": streak_days(days, today),
        "accuracy": share(ok_total, total),
        "accuracy_days": ACCURACY_DAYS,
        "decks": decks,
    }


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{round(x * 100)}%"


def progress_text(p: dict[str, Any], *, with_decks: bool = True) -> str:
    """Progress as a few lines for Telegram or a tool answer."""
    days = "day" if p["streak"] == 1 else "days"
    lines = [
        f"Streak: {p['streak']} {days} · {p['due']} due · {p['reviewed_today']} reviewed today",
        f"Learned {p['learned']} (mature {p['mature']}) · new {p['new']} · learning {p['learning']}",
    ]
    extra = []
    if p["drafts"]:
        extra.append(f"{p['drafts']} draft{'s' if p['drafts'] != 1 else ''} to check — /drafts")
    if p["suspended"]:
        extra.append(f"{p['suspended']} suspended")
    if p["leeches"]:
        extra.append(
            f"{p['leeches']} leech{'es' if p['leeches'] != 1 else ''} (forgotten 8+ times)"
        )
    if extra:
        lines.append(" · ".join(extra))
    acc = f"Accuracy ({p['accuracy_days']} days): {_pct(p['accuracy'])}"
    if with_decks and p["decks"]:
        acc += " — " + ", ".join(f"{d['deck']} {_pct(d['accuracy'])}" for d in p["decks"][:5])
    lines.append(acc)
    return "\n".join(lines)


def brief_line(due: int) -> str | None:
    return f"Study: {due} card{'s' if due != 1 else ''} due — /review on Telegram" if due else None


# ── Telegram /review ────────────────────────────────────────────────────────


async def _remember(chat_id: int, card_id: str | None, key_format: str = REVIEW_KEY) -> None:
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return
    key = key_format.format(chat_id=chat_id)
    try:
        if card_id:
            await redis.set(key, card_id, ex=6 * 3600)
        else:
            await redis.delete(key)
    except Exception:  # noqa: BLE001
        logger.warning("telegram review state not saved", exc_info=True)


async def _current(chat_id: int, key_format: str = REVIEW_KEY) -> str | None:
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(key_format.format(chat_id=chat_id))
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
            try:
                await review(session, tenant_id, card, word, today)
            except ValueError as exc:
                await _remember(chat_id, None)
                return f"{exc}. /review for the next card."
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


# ── Telegram /study and /drafts ─────────────────────────────────────────────

DRAFTS_SHOWN = 10
DRAFTS_USAGE = "Use /drafts, /drafts accept [numbers], or /drafts drop [numbers]."


async def telegram_progress(tenant_id: str, today: date | None = None) -> str:
    """/study: streak, counts and accuracy."""
    from life_graph.services.assistant_daily import user_today
    from life_graph.storage.database import async_session

    today = today or user_today()
    async with async_session() as session:
        p = await progress(session, tenant_id, today)
    return progress_text(p) + "\n\n/review to study"


def parse_numbers(words: list[str]) -> list[int] | None:
    """[1, 3] from ["1", "3"] or ["1,3"]; None when anything is not a number ≥ 1."""
    out: list[int] = []
    for w in words:
        for part in w.split(","):
            if not part:
                continue
            if not part.isdigit() or int(part) < 1:
                return None
            out.append(int(part))
    return out


def drafts_text(cards: list[ReviewCard], total: int) -> str:
    if not cards:
        return "No drafts waiting. Ask me to make cards from a note or document."
    lines = [f"Drafts ({total}) — check them before they are scheduled:"]
    for n, c in enumerate(cards, 1):
        lines.append(f"{n}. [{c.deck}] Q: {c.front}\n   A: {c.back}")
    if total > len(cards):
        lines.append(f"…and {total - len(cards)} more (accept or drop these first).")
    lines.append("/drafts accept · /drafts accept 1 3 · /drafts drop 2 · edit in the app")
    return "\n".join(lines)


async def telegram_drafts(chat_id: int, tenant_id: str, arg: str, today: date | None = None) -> str:
    """/drafts lists numbered drafts; accept/drop act on all, or on numbers
    from the list last shown in this chat (kept in Redis)."""
    from life_graph.services.assistant_daily import user_today
    from life_graph.storage.database import async_session

    today = today or user_today()
    words = (arg or "").strip().lower().split()
    verb = words[0] if words else ""
    async with async_session() as session:
        if not verb or verb in ("list", "show"):
            cards = await list_drafts(session, tenant_id, limit=200)
            shown = cards[:DRAFTS_SHOWN]
            await _remember(
                chat_id, ",".join(str(c.id) for c in shown) or None, key_format=DRAFTS_KEY
            )
            return drafts_text(shown, len(cards))
        if verb not in ("accept", "drop", "reject"):
            return DRAFTS_USAGE
        numbers = parse_numbers(words[1:])
        if numbers is None:
            return DRAFTS_USAGE
        ids: list[uuid.UUID] | None = None
        if numbers:
            listed = [i for i in (await _current(chat_id, DRAFTS_KEY) or "").split(",") if i]
            if not listed:
                return "Show them first with /drafts, then pick numbers."
            if any(n > len(listed) for n in numbers):
                return f"Pick numbers from 1 to {len(listed)}."
            ids = [uuid.UUID(listed[n - 1]) for n in numbers]
        if verb == "accept":
            done = await accept_drafts(session, tenant_id, today, ids)
            word = "accepted — due today, /review to start"
        else:
            done = await reject_drafts(session, tenant_id, ids)
            word = "dropped"
        await session.commit()
    await _remember(chat_id, None, key_format=DRAFTS_KEY)
    return f"{done} card{'s' if done != 1 else ''} {word}. /drafts for the rest."
