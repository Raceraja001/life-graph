"""Using connector data: meeting prep and evidence hints for predictions.

- ``prepare_meetings`` — about 30 minutes before a timed event, a dashboard
  notification with what Life Graph already knows about the attendees and the
  topic: matching memories and recent mail from the attendees. No LLM call; the
  note stays on the dashboard (kernel notifications are not pushed off the
  machine), so it uses the LOCAL view.
- ``prediction_hints`` — mail and events that may bear on a prediction whose
  deadline passed, named in the "did it happen?" question. Rendered for CLOUD:
  interview questions can travel in the brief. Hints only — the judgment
  engine never resolves a prediction on its own.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from life_graph.connectors import store
from life_graph.connectors.base import KIND_EVENT
from life_graph.connectors.exposure import view_items
from life_graph.connectors.locality import CLOUD
from life_graph.connectors.models import ConnectorAccount, ConnectorItem
from life_graph.connectors.tools import user_tz
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

PREP_LEAD = (timedelta(minutes=20), timedelta(minutes=40))
MAX_MEMORIES = 3
MAX_MAILS = 3


async def _embed(text: str) -> list[float] | None:
    try:
        from life_graph.api.dependencies import get_embedding_service

        return (await get_embedding_service().embed_batch_async([text]))[0]
    except Exception:
        logger.debug("assist: embedding unavailable", exc_info=True)
        return None


async def _related_memories(tenant_id: str, text: str) -> list[str]:
    from life_graph.models.db import Memory

    vec = await _embed(text)
    if vec is None:
        return []
    async with async_session() as session:
        rows = await session.execute(
            select(Memory.content)
            .where(
                Memory.tenant_id == tenant_id,
                Memory.embedding.is_not(None),
                Memory.status == "active",
                Memory.embedding.cosine_distance(vec) < 0.45,
            )
            .order_by(Memory.embedding.cosine_distance(vec))
            .limit(MAX_MEMORIES)
        )
        return [c for (c,) in rows.all()]


def _names(attendees: list[str]) -> list[str]:
    return [a for a in attendees if a and len(a) > 1][:5]


async def prepare_meetings(now: datetime | None = None) -> int:
    """Create prep notes for timed events starting 20–40 minutes from now."""
    from life_graph.api.dependencies import get_notification_engine

    now = now or datetime.now(UTC)
    lo, hi = now + PREP_LEAD[0], now + PREP_LEAD[1]
    async with async_session() as session:
        rows = (
            await session.execute(
                select(ConnectorItem, ConnectorAccount)
                .join(ConnectorAccount, ConnectorAccount.id == ConnectorItem.account_id)
                .where(
                    ConnectorAccount.enabled.is_(True),
                    ConnectorItem.kind == KIND_EVENT,
                    ConnectorItem.starts_at >= lo,
                    ConnectorItem.starts_at < hi,
                )
            )
        ).all()
    made = 0
    for item, account in rows:
        flags = item.flags or {}
        if flags.get("all_day") or flags.get("prepped"):
            continue
        people = _names(item.attendees or [])
        lines: list[str] = []
        if item.location:
            lines.append(f"Where: {item.location}")
        if people:
            lines.append("With: " + ", ".join(people))
        memories = await _related_memories(item.tenant_id, " ".join([item.title or "", *people]))
        if memories:
            lines.append("What you know:")
            lines.extend(f"- {m[:200]}" for m in memories)
        mails: list[dict[str, Any]] = []
        async with async_session() as session:
            for person in people[:3]:
                first = re.split(r"[\s@]", person)[0]
                if len(first) < 3:
                    continue
                mails.extend(
                    await store.search_email(
                        session,
                        item.tenant_id,
                        "",
                        sender=first,
                        since=now - timedelta(days=30),
                        limit=MAX_MAILS,
                    )
                )
        if mails:
            lines.append("Recent mail:")
            for m in sorted(mails, key=lambda r: r["occurred_at"], reverse=True)[:MAX_MAILS]:
                gist = f" — {m['summary']}" if m.get("summary") else ""
                lines.append(
                    f"- {m.get('sender_name') or m.get('sender_addr')}: {m['title']}{gist}"
                )
        if len(lines) <= 1 and not memories and not mails:
            lines.append("Nothing on record about this meeting or its attendees.")
        start = item.starts_at.astimezone(user_tz()).strftime("%H:%M")
        try:
            await get_notification_engine().create(
                item.tenant_id,
                f"Prep: {item.title} at {start}",
                body="\n".join(lines),
                priority="info",
                channel="terminal",
                source_type="meeting_prep",
                metadata={"connector_item_id": str(item.id), "account": account.display_name},
            )
        except Exception:
            logger.warning("Meeting prep notification failed", exc_info=True)
            continue
        async with async_session() as session:
            await store.set_flag(session, item.tenant_id, str(item.id), prepped=True)
            await session.commit()
        made += 1
    return made


async def prediction_hints(
    tenant_id: str, statement: str, since: datetime, limit: int = 2
) -> list[str]:
    """Short, cloud-safe lines naming mail/events that may bear on a prediction."""
    async with async_session() as session:
        connected = await session.execute(
            select(ConnectorAccount.id)
            .where(ConnectorAccount.tenant_id == tenant_id, ConnectorAccount.enabled.is_(True))
            .limit(1)
        )
        if connected.first() is None:
            return []
    vec = await _embed(statement)
    words = " ".join(w for w in re.findall(r"[A-Za-z][\w-]{3,}", statement)[:6])
    async with async_session() as session:
        mails = await store.search_email(
            session, tenant_id, words, since=since, embedding=vec, limit=limit
        )
        events = []
        if words:
            now = datetime.now(UTC)
            events = [
                e
                for e in await store.events_between(session, tenant_id, since, now, limit=200)
                if any(w.lower() in (e["title"] or "").lower() for w in words.split())
            ][:limit]
    out: list[str] = []
    for m in view_items(mails, CLOUD)["items"]:
        when = m["date"][:10] if m.get("date") else ""
        out.append(
            f"email '{m['subject']}' from {m.get('sender_name') or m.get('sender_addr')} ({when})"
        )
    for e in view_items(events, CLOUD)["items"]:
        out.append(f"event '{e['title']}' ({(e.get('starts_at') or '')[:10]})")
    return out[: limit + 1]
