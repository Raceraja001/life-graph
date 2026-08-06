"""Compose the enriched prompt an ambient advisory persona runs on.

Watch-list topics are primary; recent memory tags are a secondary nudge; the
persona's own recent finding titles are injected so it does not repeat itself.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from life_graph.models.db import Notification
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


async def _recent_finding_titles(agent_name: str, tenant_id: str, days: int) -> list[str]:
    """Titles of this persona's own notifications from the last `days` days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Notification.title).where(
                    Notification.tenant_id == tenant_id,
                    Notification.source_type == agent_name,
                    Notification.created_at >= since,
                )
            )
        ).all()
    return [r[0] for r in rows][:30]


async def _memory_signal_tags(tenant_id: str, limit: int = 5) -> list[str]:
    """Best-effort: a few salient recent memory tags to nudge research. Degrades to []."""
    try:
        from life_graph.models.db import Memory  # tenant_id, created_at, tags: ARRAY(String)

        async with async_session() as session:
            rows = (
                await session.execute(
                    select(Memory)
                    .where(Memory.tenant_id == tenant_id)
                    .order_by(Memory.created_at.desc())
                    .limit(40)
                )
            ).scalars().all()
        counts: dict[str, int] = {}
        for m in rows:
            for tag in (getattr(m, "tags", None) or []):
                counts[tag] = counts.get(tag, 0) + 1
        return [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:limit]
    except Exception:
        logger.debug("Memory signal unavailable; continuing with watch-list only", exc_info=True)
        return []


_CONTRACT = (
    "End your reply with ONLY a JSON array of findings, each "
    '{"title": str, "detail": str, "urgency": "now" | "brief"}. Use "now" only '
    "for genuinely time-sensitive items. Return [] if you have nothing new."
)


async def build_ambient_input(
    agent_name: str, job_input: dict, tenant_id: str, *, novelty_days: int = 7
) -> dict:
    """Build the {"message": ...} input for an ambient advisory run."""
    parts: list[str] = []
    if agent_name == "scout":
        topics = job_input.get("topics") or []
        if topics:
            parts.append("Your watch-list topics: " + ", ".join(str(t) for t in topics) + ".")
        else:
            parts.append("You have no watch-list topics yet; use recent memory signals below.")
    already = await _recent_finding_titles(agent_name, tenant_id, novelty_days)
    if already:
        parts.append(
            "You have ALREADY reported these recently — do not repeat them: "
            + "; ".join(already)
            + "."
        )
    tags = await _memory_signal_tags(tenant_id)
    if tags:
        parts.append("Recent interest signals from the user's memory: " + ", ".join(tags) + ".")
    parts.append(_CONTRACT)
    return {"message": "\n\n".join(parts)}
