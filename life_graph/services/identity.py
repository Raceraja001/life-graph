"""Identity management service (T-061, T-062).

Tracks how the user's identity, preferences, and beliefs evolve over
time.  Supports:

- **Identity timeline**: grouped history of current and superseded beliefs
- **Belief states**: 'current', 'superseded', 'uncertain', 'exploring',
  'contextual', 'retired'
- **Stale belief challenging**: proactive prompts to review old beliefs
- **Challenge responses**: confirm, supersede, mark uncertain, or retire

All operations are rule-based with zero LLM dependency.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from itertools import groupby
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.models.db import Memory

logger = logging.getLogger(__name__)

# Tags that indicate identity-related memories
_IDENTITY_TAGS: list[str] = ["identity", "preference", "belief"]

# Valid belief states (flexible TEXT, not enum)
_VALID_BELIEF_STATES: set[str] = {
    "current",
    "superseded",
    "uncertain",
    "exploring",
    "contextual",
    "retired",
}


class IdentityService:
    """Manage identity, preferences, and beliefs over time.

    Provides a timeline view of how beliefs have changed, stale-belief
    challenging, and belief-state transitions.

    Usage::

        service = IdentityService(session_factory)
        current = await service.get_current_identity()
        timeline = await service.get_timeline()
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # ── Identity timeline ─────────────────────────────────────

    async def get_current_identity(self) -> list[Memory]:
        """Query active identity / preference / belief memories.

        Returns memories ordered by importance (highest first).
        """
        stmt = (
            select(Memory)
            .where(Memory.status == "active")
            .where(Memory.tags.overlap(_IDENTITY_TAGS))
            .order_by(Memory.importance.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_timeline(self) -> list[dict[str, Any]]:
        """Get the full identity timeline — active and superseded beliefs.

        Returns a list of chapter dicts grouped by time period::

            [
                {
                    "period": "2026-01",
                    "active": [Memory, ...],
                    "superseded": [Memory, ...],
                },
                ...
            ]
        """
        stmt = (
            select(Memory)
            .where(Memory.tags.overlap(_IDENTITY_TAGS))
            .order_by(Memory.valid_from.asc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            memories = list(result.scalars().all())

        return self._group_into_chapters(memories)

    @staticmethod
    def _group_into_chapters(memories: list[Memory]) -> list[dict[str, Any]]:
        """Group memories into monthly chapters."""
        chapters: list[dict[str, Any]] = []

        def _period_key(m: Memory) -> str:
            return m.valid_from.strftime("%Y-%m")

        for period, group in groupby(memories, key=_period_key):
            active: list[Memory] = []
            superseded: list[Memory] = []
            for mem in group:
                if mem.status == "active":
                    active.append(mem)
                else:
                    superseded.append(mem)
            chapters.append({
                "period": period,
                "active": active,
                "superseded": superseded,
            })

        return chapters

    # ── Belief states ─────────────────────────────────────────

    async def update_belief_state(
        self, memory_id: str, state: str
    ) -> Memory:
        """Update a memory's belief state.

        Args:
            memory_id: UUID string of the memory to update.
            state: New state — one of 'current', 'superseded',
                   'uncertain', 'exploring', 'contextual', 'retired'.

        Returns:
            The updated Memory instance.

        Raises:
            ValueError: If the state is invalid or the memory is not found.
        """
        if state not in _VALID_BELIEF_STATES:
            raise ValueError(
                f"Invalid belief state '{state}'. "
                f"Valid states: {', '.join(sorted(_VALID_BELIEF_STATES))}"
            )

        mid = uuid.UUID(memory_id)
        async with self._session_factory() as session:
            mem = await session.get(Memory, mid)
            if mem is None:
                raise ValueError(f"Memory {memory_id} not found")

            mem.status = state if state != "current" else "active"
            mem.updated_at = datetime.now(timezone.utc)

            if state in ("superseded", "retired"):
                mem.valid_until = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(mem)

        logger.info("Updated belief state for %s → %s", memory_id, state)
        return mem

    async def challenge_stale_beliefs(
        self, stale_months: int = 6
    ) -> list[dict[str, Any]]:
        """Find identity memories not accessed in *stale_months* months.

        Returns challenge prompts that can be shown to the user::

            [
                {
                    "memory": Memory,
                    "prompt": "You've held '...' for N months. Still current?",
                    "days_stale": 183,
                },
                ...
            ]
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_months * 30)
        stmt = (
            select(Memory)
            .where(Memory.status == "active")
            .where(Memory.tags.overlap(_IDENTITY_TAGS))
            .where(
                or_(
                    Memory.last_accessed < cutoff,
                    Memory.last_accessed.is_(None),
                )
            )
            .order_by(Memory.last_accessed.asc().nullsfirst())
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            stale = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        challenges: list[dict[str, Any]] = []
        for mem in stale:
            last = mem.last_accessed or mem.created_at
            days_stale = (now - last).days
            months = days_stale // 30
            content_preview = mem.content[:80]
            challenges.append({
                "memory": mem,
                "prompt": (
                    f"You've held '{content_preview}' for {months} months. "
                    "Still current?"
                ),
                "days_stale": days_stale,
            })

        logger.info("Found %d stale beliefs to challenge", len(challenges))
        return challenges

    async def respond_to_challenge(
        self, memory_id: str, response: str
    ) -> None:
        """Handle the user's response to a stale-belief challenge.

        Args:
            memory_id: UUID string of the challenged memory.
            response: One of 'confirm', 'supersede', 'uncertain', 'retire'.

        Raises:
            ValueError: If the response is invalid or memory not found.
        """
        valid_responses = {"confirm", "supersede", "uncertain", "retire"}
        if response not in valid_responses:
            raise ValueError(
                f"Invalid response '{response}'. "
                f"Valid: {', '.join(sorted(valid_responses))}"
            )

        mid = uuid.UUID(memory_id)
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            mem = await session.get(Memory, mid)
            if mem is None:
                raise ValueError(f"Memory {memory_id} not found")

            if response == "confirm":
                # Touch the memory — reset the stale timer
                mem.last_accessed = now
                mem.access_count += 1
                mem.updated_at = now
                logger.info("Belief confirmed: %s", memory_id)

            elif response == "supersede":
                # Mark old as superseded, create placeholder for new
                mem.status = "superseded"
                mem.valid_until = now
                mem.updated_at = now

                new_mem = Memory(
                    content=f"[Superseded] {mem.content}",
                    reasoning=f"Superseded memory {memory_id} after belief challenge",
                    tags=mem.tags,
                    properties={
                        **(mem.properties or {}),
                        "supersedes_id": str(mem.id),
                        "challenge_response": "supersede",
                    },
                    importance=mem.importance,
                    importance_tier=mem.importance_tier,
                    source_type="belief_challenge",
                    supersedes=mem.id,
                )
                mem.superseded_by = new_mem.id
                session.add(new_mem)
                logger.info("Belief superseded: %s → %s", memory_id, new_mem.id)

            elif response == "uncertain":
                mem.status = "uncertain"
                mem.updated_at = now
                mem.properties = {
                    **(mem.properties or {}),
                    "marked_uncertain_at": now.isoformat(),
                }
                logger.info("Belief marked uncertain: %s", memory_id)

            elif response == "retire":
                mem.status = "retired"
                mem.valid_until = now
                mem.updated_at = now
                logger.info("Belief retired: %s", memory_id)

            await session.commit()
