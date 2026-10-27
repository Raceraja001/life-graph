"""Temporary chats are purged a day after their last message (web-chat-wave1 F5).

A temporary chat is an ``AgentSession`` with ``context.temporary``: its turns
ran on the local model with nothing captured or saved (services/lead.py,
api/jarvis.py). What is left is the conversation itself — the session row and
its ``agent_tasks`` turns (and any child tasks under them) — and this removes
it once nothing has been said in it for ``PURGE_AFTER``. Rows that point at a
turn are ``SET NULL`` or ``CASCADE`` (models/agents.py), so nothing dangles.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, or_, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

PURGE_AFTER = timedelta(hours=24)


async def purge(
    session_factory: async_sessionmaker[AsyncSession], *, now: datetime | None = None
) -> dict[str, int]:
    """Delete every temporary chat quiet for ``PURGE_AFTER``; all tenants."""
    from life_graph.models.db import AgentSession, AgentTask

    cutoff = (now or datetime.now(UTC)) - PURGE_AFTER
    last = (
        select(AgentTask.session_id, func.max(AgentTask.created_at).label("at"))
        .group_by(AgentTask.session_id)
        .subquery()
    )
    async with session_factory() as session:
        ids = list(
            (
                await session.execute(
                    select(AgentSession.id)
                    .outerjoin(last, last.c.session_id == AgentSession.id)
                    .where(
                        AgentSession.context["temporary"].as_boolean().is_(True),
                        func.coalesce(last.c.at, AgentSession.created_at) < cutoff,
                    )
                )
            ).scalars()
        )
        if not ids:
            return {"chats": 0, "turns": 0}
        turns = list(
            (
                await session.execute(select(AgentTask.id).where(AgentTask.session_id.in_(ids)))
            ).scalars()
        )
        removed = 0
        if turns:
            removed = (
                await session.execute(
                    delete(AgentTask).where(
                        or_(
                            AgentTask.id.in_(turns),
                            AgentTask.root_task_id.in_(turns),
                            AgentTask.parent_task_id.in_(turns),
                        )
                    )
                )
            ).rowcount or 0
        await session.execute(delete(AgentSession).where(AgentSession.id.in_(ids)))
        await session.commit()
    logger.info("Purged %d temporary chats (%d turns)", len(ids), removed)
    return {"chats": len(ids), "turns": removed}
