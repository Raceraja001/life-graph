"""Intention service — CRUD and trigger evaluation for prospective memories.

Handles creation, listing, triggering, completion, dismissal, and
expiration of intentions. All operations are async and use SQLAlchemy
select/update statements directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.models.db import Intention


def _utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)


class IntentionService:
    """Service layer for managing prospective memories (intentions).

    Supports three trigger types:
    - **time**: fires when trigger_time <= now
    - **event**: fires when trigger_condition matches current context
    - **context**: fires when context_match keys overlap with session context
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(
        self,
        content: str,
        trigger_type: str = "event",
        trigger_condition: str | None = None,
        trigger_time: datetime | None = None,
        context_match: dict[str, Any] | None = None,
        priority: str = "normal",
        source_session_id: str | None = None,
        source_memory_id: str | None = None,
        embedding: list[float] | None = None,
    ) -> Intention:
        """Create a new pending intention.

        Args:
            content: What the system should remember to do.
            trigger_type: One of 'time', 'event', or 'context'.
            trigger_condition: Free-text condition for event triggers.
            trigger_time: When to fire (for time triggers).
            context_match: JSONB keys to match against session context.
            priority: 'low', 'normal', or 'high'.
            source_session_id: Session that spawned this intention.
            source_memory_id: Memory that spawned this intention.
            embedding: Optional 768-dim vector for semantic matching.

        Returns:
            The newly created Intention ORM instance.
        """
        intention = Intention(
            content=content,
            trigger_type=trigger_type,
            trigger_condition=trigger_condition,
            trigger_time=trigger_time,
            context_match=context_match,
            priority=priority,
            status="pending",
            source_session=uuid.UUID(source_session_id) if source_session_id else None,
            source_memory=uuid.UUID(source_memory_id) if source_memory_id else None,
            embedding=embedding,
        )

        async with self._session_factory() as session:
            session.add(intention)
            await session.commit()
            await session.refresh(intention)

        return intention

    async def list_pending(self, limit: int = 50) -> list[Intention]:
        """Return up to *limit* pending intentions, newest first.

        Args:
            limit: Maximum number of results.

        Returns:
            List of pending Intention records.
        """
        stmt = (
            select(Intention)
            .where(Intention.status == "pending")
            .order_by(Intention.created_at.desc())
            .limit(limit)
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_triggered(self, context: dict[str, Any]) -> list[Intention]:
        """Find pending intentions whose triggers are satisfied.

        Checks two trigger types:
        1. **time** — trigger_time is at or before now.
        2. **context/event** — context_match keys overlap with *context*.

        Args:
            context: Current session context dict (project, topics, files, etc.).

        Returns:
            List of triggered Intention records (status still 'pending').
        """
        now = _utcnow()
        triggered: list[Intention] = []

        async with self._session_factory() as session:
            # ── Time-based triggers ───────────────────────────────
            time_stmt = (
                select(Intention)
                .where(
                    Intention.status == "pending",
                    Intention.trigger_type == "time",
                    Intention.trigger_time <= now,
                )
            )
            time_result = await session.execute(time_stmt)
            triggered.extend(time_result.scalars().all())

            # ── Context/event triggers ────────────────────────────
            ctx_stmt = (
                select(Intention)
                .where(
                    Intention.status == "pending",
                    Intention.trigger_type.in_(["event", "context"]),
                    Intention.context_match.isnot(None),
                )
            )
            ctx_result = await session.execute(ctx_stmt)
            for intention in ctx_result.scalars().all():
                if self._context_matches(intention.context_match, context):
                    triggered.append(intention)

        return triggered

    async def complete(self, intention_id: str) -> Intention:
        """Mark an intention as completed.

        Args:
            intention_id: UUID string of the intention.

        Returns:
            The updated Intention record.

        Raises:
            ValueError: If the intention does not exist.
        """
        uid = uuid.UUID(intention_id)
        now = _utcnow()

        async with self._session_factory() as session:
            stmt = (
                update(Intention)
                .where(Intention.id == uid)
                .values(status="completed", completed_at=now)
                .returning(Intention)
            )
            result = await session.execute(stmt)
            intention = result.scalar_one_or_none()
            if intention is None:
                raise ValueError(f"Intention {intention_id} not found")
            await session.commit()
            return intention

    async def dismiss(self, intention_id: str) -> Intention:
        """Dismiss an intention without completing it.

        Args:
            intention_id: UUID string of the intention.

        Returns:
            The updated Intention record.

        Raises:
            ValueError: If the intention does not exist.
        """
        uid = uuid.UUID(intention_id)

        async with self._session_factory() as session:
            stmt = (
                update(Intention)
                .where(Intention.id == uid)
                .values(status="dismissed")
                .returning(Intention)
            )
            result = await session.execute(stmt)
            intention = result.scalar_one_or_none()
            if intention is None:
                raise ValueError(f"Intention {intention_id} not found")
            await session.commit()
            return intention

    async def expire_overdue(self) -> int:
        """Expire all pending intentions past their expires_at deadline.

        Returns:
            Number of intentions that were expired.
        """
        now = _utcnow()

        async with self._session_factory() as session:
            stmt = (
                update(Intention)
                .where(
                    Intention.status == "pending",
                    Intention.expires_at.isnot(None),
                    Intention.expires_at <= now,
                )
                .values(status="expired")
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount  # type: ignore[return-value]

    @staticmethod
    def _context_matches(
        required: dict[str, Any],
        provided: dict[str, Any],
    ) -> bool:
        """Check if *provided* context satisfies the *required* context_match.

        Matching rules:
        - **project**: exact string match.
        - **topics**: any overlap between required and provided topic lists.
        - **files_pattern**: any provided file path contains the pattern substring.
        - All other keys: exact equality check.

        Args:
            required: The context_match dict stored on the intention.
            provided: The current session context dict.

        Returns:
            True if all keys in *required* are satisfied by *provided*.
        """
        for key, req_value in required.items():
            prov_value = provided.get(key)
            if prov_value is None:
                return False

            if key == "project":
                if str(req_value).lower() != str(prov_value).lower():
                    return False

            elif key == "topics":
                req_set = set(req_value) if isinstance(req_value, list) else {req_value}
                prov_set = set(prov_value) if isinstance(prov_value, list) else {prov_value}
                if not req_set & prov_set:
                    return False

            elif key == "files_pattern":
                pattern = str(req_value).lower()
                if isinstance(prov_value, list):
                    if not any(pattern in str(f).lower() for f in prov_value):
                        return False
                elif pattern not in str(prov_value).lower():
                    return False

            else:
                if req_value != prov_value:
                    return False

        return True
