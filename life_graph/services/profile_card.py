"""The owner's lasting facts, in front of every local Jarvis answer.

Search decides what Jarvis sees (services/memory_context.py), so a fact it
misses is a fact Jarvis "forgets": asked "which phone should I buy a case
for?", the search for that wording need not find "my phone is a Realme X2
Pro". Supermemory's static profile, Letta's memory blocks and Claude's memory
entries all keep a short always-loaded profile for this reason (memory
research, 2026-10-29). This is ours: no model call, one query.

Only what the owner said or what their documents say (core/evidence.py), and
only lasting kinds: a guess, a day summary or a passing event is never stated
as who the owner is.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from life_graph.core import evidence as ev

logger = logging.getLogger(__name__)

MAX_CHARS = 1800
ITEM_CHARS = 200
#: Rows read before filtering: the card is a short list, the scan stays small.
SCAN = 120
#: Per-tenant cache: a card changes only when a memory is kept or dropped.
TTL_S = 60.0

#: Fact types that describe the owner rather than something that happened.
LASTING_TYPES = frozenset(
    {"identity", "fact", "preference", "anti_preference", "decision", "constraint", "explicit_save"}
)

HEADER = (
    "## Who the owner is\n"
    "Lasting facts the owner told you or that their documents state. Treat them as "
    'true unless the owner says otherwise now; a fact marked "as of" a date may '
    "have changed."
)

_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def clear_cache() -> None:
    _cache.clear()


def belongs(m: Any, now: datetime) -> bool:
    """True when *m* is a lasting fact the owner said or a document states."""
    props = getattr(m, "properties", None) or {}
    if props.get("kind") == "episode":
        return False
    kind = ev.evidence_of(getattr(m, "source_type", None), getattr(m, "trust_tier", None), props)
    if kind not in (ev.SAID, ev.DOCUMENT):
        return False
    until = getattr(m, "valid_until", None)
    if until is not None and until <= now:
        return False
    # Stored as written (no fact type) is kept: an explicit "remember that …".
    fact_type = props.get("fact_type")
    return fact_type is None or fact_type in LASTING_TYPES


def pick(rows: list[Any], max_items: int, now: datetime | None = None) -> list[Any]:
    """The card's memories, in the order given (best first), within the size budget."""
    now = now or datetime.now(UTC)
    out: list[Any] = []
    seen: set[str] = set()
    used = len(HEADER)
    for m in rows:
        if len(out) >= max_items:
            break
        if not belongs(m, now):
            continue
        text = " ".join((m.content or "").split())
        key = text.lower()
        if not text or key in seen:
            continue
        line = len(text[:ITEM_CHARS]) + 16
        if used + line > MAX_CHARS:
            break
        seen.add(key)
        used += line
        out.append(m)
    return out


def render(items: list[dict[str, Any]]) -> str:
    """items: {"content", "created_at", "changes_over_time"}. Empty string for none."""
    if not items:
        return ""
    lines = [HEADER]
    for it in items:
        text = " ".join((it["content"] or "").split())
        if len(text) > ITEM_CHARS:
            text = text[: ITEM_CHARS - 1] + "…"
        when = it.get("created_at")
        prefix = f"(as of {when:%Y-%m-%d}) " if it.get("changes_over_time") and when else ""
        lines.append(f"- {prefix}{text}")
    return "\n".join(lines)


async def card_items(tenant_id: str) -> list[dict[str, Any]]:
    """The card's memories for *tenant_id*: {"id", "content", "created_at", "changes_over_time"}."""
    from life_graph.config import settings

    max_items = settings.profile_card_max_items
    if max_items <= 0:
        return []
    hit = _cache.get(tenant_id)
    if hit and time.monotonic() - hit[0] < TTL_S:
        return hit[1]

    from sqlalchemy import or_, select

    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    now = datetime.now(UTC)
    query = (
        select(Memory)
        .where(
            Memory.tenant_id == tenant_id,
            Memory.status == "active",
            or_(Memory.valid_until.is_(None), Memory.valid_until > now),
        )
        .order_by(Memory.importance.desc(), Memory.access_count.desc(), Memory.created_at.desc())
        .limit(SCAN)
    )
    async with async_session() as session:
        rows = list((await session.execute(query)).scalars().all())
    items = [
        {
            "id": str(m.id),
            "content": m.content,
            "created_at": m.created_at,
            "changes_over_time": bool((m.properties or {}).get("changes_over_time")),
        }
        for m in pick(rows, max_items, now)
    ]
    _cache[tenant_id] = (time.monotonic(), items)
    return items
