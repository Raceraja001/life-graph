"""Warm and cold memory: nothing is forgotten, old memories are only further away.

Search reads active memories (warm). Archived ones (approved by the owner from
a decay proposal) and replaced ones (superseded by a newer value or a
correction) are cold: kept, never deleted, and until 2026-10-31 never read
again either, so "archived" meant forgotten in practice. Now cold memories are
searched when no warm one answers, or when the question is about the past
("where did I work before?"), and they are shown as what they are: an older
note, or a value later replaced or corrected.

An archived memory that answers a question has earned its place: it goes back
to active, as recall does in the brain. A replaced one stays replaced; it is
history, and the newer value is the current one.

Never cold: what the owner took back (memory_forget's "forgotten", the undo of
a Jarvis save), what a bulk clean-up moved out on purpose (BULK_ARCHIVES), and
anything older than the owner's fresh start (settings.memory_start_at).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

COLD_STATUSES = ("archived", "superseded")
#: properties.archived_by of bulk clean-ups: moved out on purpose, never read again.
BULK_ARCHIVES = ("fresh_start_2026-10-23", "edition_split_2026-10-29", "live_test")
#: Most cold memories added to the judge's candidates.
COLD_CANDIDATES = 8


def asks_about_past(question: str) -> bool:
    """A question about how things were ("where did I work before?"): the form's
    own test (services/profile_card.py)."""
    from life_graph.services import profile_card

    return bool(profile_card.PAST.search(question or ""))


def filters() -> dict[str, Any]:
    """hybrid_search filters for the cold tier."""
    from life_graph.config import settings

    out: dict[str, Any] = {
        "statuses": COLD_STATUSES,
        "cold_tier": True,
        "bulk_archives": BULK_ARCHIVES,
    }
    start = settings.memory_start()
    if start is not None:
        out["created_after"] = start
    return out


async def search(embedding: list[float], question: str, limit: int = COLD_CANDIDATES) -> list[Any]:
    """Cold memories of the current tenant nearest to *question*, best first."""
    from life_graph.api.dependencies import get_store

    hits = await get_store().hybrid_search(
        embedding=embedding, query_text=question, limit=limit, filters=filters()
    )
    found = [m for m, _ in hits]
    await _mark_replacements(found)
    return found


async def _mark_replacements(memories: list[Any]) -> None:
    """Note on each replaced memory when and how it was replaced (render labels it).

    A transient attribute, never saved: ``replaced`` = (date, corrected?).
    """
    ids = [m.superseded_by for m in memories if getattr(m, "superseded_by", None)]
    if not ids:
        return
    from sqlalchemy import select

    from life_graph.core.tenant import get_current_tenant_id
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = (
            await session.execute(
                select(Memory.id, Memory.created_at, Memory.properties).where(
                    Memory.id.in_(ids), Memory.tenant_id == get_current_tenant_id()
                )
            )
        ).all()
    by_id = {
        r[0]: (r[1], bool((r[2] or {}).get("correction") or (r[2] or {}).get("replaces_id")))
        for r in rows
    }
    for m in memories:
        if getattr(m, "superseded_by", None) in by_id:
            m.replaced = by_id[m.superseded_by]


def label(m: Any) -> str:
    """How a cold memory is shown: "" for a warm one."""
    status = getattr(m, "status", "active")
    if status == "superseded":
        when, corrected = getattr(m, "replaced", (None, False))
        verb = "corrected" if corrected else "replaced"
        return f"later {verb} on {when:%Y-%m-%d}" if when else f"later {verb}"
    if status == "archived":
        return "older note"
    return ""


async def reawaken(memories: list[Any]) -> int:
    """Archived memories that were just used go back to active. Returns how many."""
    ids = [m.id for m in memories if getattr(m, "status", None) == "archived"]
    if not ids:
        return 0
    import json

    from sqlalchemy import text

    from life_graph.core.tenant import get_current_tenant_id
    from life_graph.storage.database import async_session

    note = json.dumps(
        {"reawakened": {"at": datetime.now(UTC).isoformat(), "previous_status": "archived"}}
    )
    async with async_session() as session:
        result = await session.execute(
            text(
                "UPDATE memories SET status = 'active', updated_at = NOW(),"
                " properties = COALESCE(properties, '{}'::jsonb) || CAST(:note AS jsonb)"
                " WHERE id = ANY(:ids) AND tenant_id = :t AND status = 'archived'"
                " AND NOT (COALESCE(properties, '{}'::jsonb) ?| ARRAY['forgotten', 'undone'])"
                # Archived by the owner (memory page) or a clean-up: their call, not recall's.
                " AND NOT (COALESCE(properties, '{}'::jsonb) ? 'archived_by')"
            ),
            {"ids": ids, "t": get_current_tenant_id(), "note": note},
        )
        await session.commit()
    n = result.rowcount or 0
    if n:
        logger.info("Reawakened %d archived memories that answered a question", n)
    return n
