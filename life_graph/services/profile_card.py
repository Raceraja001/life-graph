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
import re
import time
from datetime import UTC, datetime
from typing import Any

from life_graph.core import evidence as ev

logger = logging.getLogger(__name__)

MAX_CHARS = 2600
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
    "have changed. A fact in [brackets] is the owner's current value for that field "
    "(an older value was replaced)."
)
HISTORY_HEADER = (
    "## Earlier values (replaced)\n"
    "What used to be true, newest first. Use these only for questions about the past."
)
#: A question about the past: earlier values of the form are shown with it.
PAST = re.compile(
    r"\b(?:before|used to|previous(?:ly)?|earlier|former(?:ly)?|first|old|originally|"
    r"in the past|back then|last (?:job|home|phone|year)|until|changed)\b|முன்பு|முன்னாடி|பழைய",
    re.IGNORECASE,
)

_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def clear_cache() -> None:
    _cache.clear()


def invalidate(tenant_id: str) -> None:
    """A memory was saved, kept, dropped or replaced: rebuild the card on next use,
    so a correction is not contradicted by the cached card for a minute."""
    _cache.pop(tenant_id, None)


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


def _raw_slot(m: Any) -> str | None:
    """*m*'s slot read through today's rules: an older spelling of the same field
    (hobbies.cricket_day, family.anushka.anu.age) is the same slot."""
    from life_graph.core import slots

    props = getattr(m, "properties", None) or {}
    slot = props.get("slot")
    if not slot:
        return None
    text = " ".join((getattr(m, "content", None) or "").split())
    return slots.normalise(slot, subject=props.get("subject") or "owner", content=text) or slot


def card_slot(m: Any, filed: dict[str, str] | None = None) -> str | None:
    """The slot *m* is shown under: normalised, then filed under the name its
    person is known by (*filed*, from :func:`filed_slots`)."""
    slot = _raw_slot(m)
    return (filed or {}).get(slot, slot) if slot else None


async def filed_slots(tenant_id: str, rows: list[Any]) -> dict[str, str]:
    """Normalised family slot → the slot under the person's known name
    (entities.canonical_slot), so ``family.priya.birthday`` saved before Priya was
    linked to Priyadharshini shows with ``family.priyadharshini.*``: one person."""
    from life_graph.services import entities

    out: dict[str, str] = {}
    for m in rows:
        slot = _raw_slot(m)
        if not slot or not slot.startswith("family.") or slot in out:
            continue
        try:
            out[slot] = await entities.canonical_slot(tenant_id, slot)
        except Exception:  # noqa: BLE001 — the filing is a bonus on the card
            logger.warning("Filing a card slot under the known name failed", exc_info=True)
            return out
    return out


def _form_order(m: Any, filed: dict[str, str] | None = None) -> tuple:
    """The form first (slotted facts, by topic), then the other lasting facts."""
    from life_graph.core import slots

    slot = card_slot(m, filed)
    if not slot:
        return (1, 0, "", 0.0)
    topic = slots.topic_of(slot)
    rank = slots.TOPICS.index(topic) if topic in slots.TOPICS else len(slots.TOPICS)
    # Two active memories can share a slot while a replacement waits for the
    # owner (services/form_fill.py): the newest is the current value.
    created = getattr(m, "created_at", None)
    return (0, rank, slot, -created.timestamp() if created else 0.0)


#: Room kept on a family field for the other names the person goes by
#: (" (Maha, Ma)"), added after picking (:func:`_add_other_names`).
AKA_RESERVE = 24


def pick(
    rows: list[Any],
    max_items: int,
    now: datetime | None = None,
    *,
    filed: dict[str, str] | None = None,
) -> list[Any]:
    """The card's memories within the size budget: the owner's form (one memory
    per slot) first, then the other lasting facts in the order given (best first).
    The budget counts each line as rendered (label, date and all), so the card
    stays within MAX_CHARS (bake-off 2026-10-31: 3,714 chars were rendered)."""
    now = now or datetime.now(UTC)
    # stable: best-first order kept within each group
    rows = sorted(rows, key=lambda m: _form_order(m, filed))
    out: list[Any] = []
    slots_seen: set[str] = set()
    seen: set[str] = set()
    used = len(HEADER)
    for m in rows:
        if len(out) >= max_items:
            break
        if not belongs(m, now):
            continue
        text = " ".join((m.content or "").split())
        key = text.lower()
        slot = card_slot(m, filed)
        if not text or key in seen or (slot and slot in slots_seen):
            continue
        if slot:
            slots_seen.add(slot)
        props = getattr(m, "properties", None) or {}
        item = {
            "content": text,
            "created_at": getattr(m, "created_at", None),
            "changes_over_time": bool(props.get("changes_over_time")),
            "slot": slot,
        }
        size = 1 + len(_line(item))
        if slot and slot.startswith("family.") and slot.count(".") >= 2:
            size += AKA_RESERVE
        if used + size > MAX_CHARS:
            break
        seen.add(key)
        used += size
        out.append(m)
    return out


def _line(it: dict[str, Any]) -> str:
    """One card line, as rendered."""
    text = " ".join((it["content"] or "").split())
    if len(text) > ITEM_CHARS:
        text = text[: ITEM_CHARS - 1] + "…"
    when = it.get("created_at")
    prefix = f"(as of {when:%Y-%m-%d}) " if it.get("changes_over_time") and when else ""
    if it.get("slot"):
        from life_graph.core import slots

        parts = it["slot"].split(".")
        if it.get("aka") and len(parts) >= 3:
            # family · mahalakshmi (Maha, Ma) · birthday: the other names she goes by.
            parts[1] = f"{parts[1]} ({', '.join(it['aka'])})"
        label = " · ".join(parts) if it.get("aka") else slots.label(it["slot"])
        prefix = f"[{label}] " + (f"(since {when:%Y-%m-%d}) " if when else "")
    return f"- {prefix}{text}"


def render(items: list[dict[str, Any]]) -> str:
    """items: {"content", "created_at", "changes_over_time", "slot", "aka"}.
    Empty string for none. Never longer than MAX_CHARS: a line that would pass
    it is left off (pick already keeps within it; this is the guarantee)."""
    if not items:
        return ""
    lines = [HEADER]
    used = len(HEADER)
    for it in items:
        line = _line(it)
        if used + 1 + len(line) > MAX_CHARS:
            break
        used += 1 + len(line)
        lines.append(line)
    return "\n".join(lines)


def render_history(items: list[dict[str, Any]]) -> str:
    """items: {"content", "slot", "until"}. Empty string for none."""
    if not items:
        return ""
    from life_graph.core import slots

    lines = [HISTORY_HEADER]
    for it in items:
        text = " ".join((it["content"] or "").split())[:ITEM_CHARS]
        until = f"until {it['until']:%Y-%m-%d} · " if it.get("until") else ""
        lines.append(f"- ({until}{slots.label(it['slot'])}) {text}")
    return "\n".join(lines)


async def history(tenant_id: str, limit: int = 12) -> list[dict[str, Any]]:
    """Replaced values of the owner's form, newest first (superseded memories with a slot)."""
    from sqlalchemy import select

    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    query = (
        select(Memory)
        .where(
            Memory.tenant_id == tenant_id,
            Memory.status == "superseded",
            Memory.properties["slot"].astext.isnot(None),
        )
        .order_by(Memory.updated_at.desc())
        .limit(limit)
    )
    async with async_session() as session:
        rows = list((await session.execute(query)).scalars().all())
    return [
        {
            "id": str(m.id),
            "content": m.content,
            "slot": (m.properties or {}).get("slot"),
            # When it was replaced: the supersede is its last update.
            "until": m.updated_at,
        }
        for m in rows
    ]


async def _add_other_names(tenant_id: str, items: list[dict[str, Any]]) -> None:
    """``aka`` on each family field: the other names that person goes by
    (services/entities.py), so "Maha's birthday" matches the mahalakshmi field."""
    from life_graph.services import entities

    for it in items:
        parts = (it.get("slot") or "").split(".")
        if len(parts) < 3 or parts[0] != "family":
            continue
        try:
            aka = await entities.other_names(tenant_id, parts[1])
        except Exception:  # noqa: BLE001 — the names are a bonus on the card
            logger.warning("Other names for the card failed", exc_info=True)
            return
        if aka:
            it["aka"] = aka[:4]


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
    filed = await filed_slots(tenant_id, rows)
    items = [
        {
            "id": str(m.id),
            "content": m.content,
            "created_at": m.created_at,
            "changes_over_time": bool((m.properties or {}).get("changes_over_time")),
            "slot": card_slot(m, filed),
        }
        for m in pick(rows, max_items, now, filed=filed)
    ]
    await _add_other_names(tenant_id, items)
    _cache[tenant_id] = (time.monotonic(), items)
    return items
