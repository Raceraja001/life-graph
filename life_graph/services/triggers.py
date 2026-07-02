"""Trigger matcher for intentions and stale memory detection (T-023).

Checks three trigger types:
  1. Time triggers — intentions scheduled for a specific time
  2. Context triggers — intentions matching current working context
  3. Stale memories — important memories not accessed in a long time

All queries use async SQLAlchemy with raw selects for efficiency.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from life_graph.models.db import Intention, Memory
from life_graph.services.context import ContextFingerprint
from life_graph.storage.database import async_session
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)


class TriggerMatcher:
    """Checks for triggered intentions and stale memories.

    Designed to run at session start and periodically during sessions.
    All methods are async and open their own database sessions.

    Usage::

        matcher = TriggerMatcher(store)
        results = await matcher.check_all(fingerprint)
    """

    def __init__(self, store: PostgresMemoryStore) -> None:
        self._store = store

    async def check_time_triggers(self) -> list[Intention]:
        """Find pending intentions whose trigger time has arrived.

        Returns intentions where:
            - trigger_type = 'time'
            - trigger_time <= now()
            - status = 'pending'

        Returns:
            List of Intention ORM objects ready to fire.
        """
        now = datetime.now(timezone.utc)

        stmt = (
            select(Intention)
            .where(Intention.trigger_type == "time")
            .where(Intention.status == "pending")
            .where(Intention.trigger_time <= now)
            .order_by(Intention.trigger_time.asc())
        )

        async with async_session() as session:
            result = await session.execute(stmt)
            intentions = list(result.scalars().all())

        logger.debug("Found %d time-triggered intentions", len(intentions))
        return intentions

    async def check_context_triggers(
        self, context: ContextFingerprint,
    ) -> list[Intention]:
        """Find pending intentions matching the current context.

        Checks intentions with trigger_type in ('event', 'context')
        and compares their context_match JSONB against the current
        context fingerprint fields.

        Args:
            context: Current session context fingerprint.

        Returns:
            List of matching Intention ORM objects.
        """
        stmt = (
            select(Intention)
            .where(Intention.trigger_type.in_(["event", "context"]))
            .where(Intention.status == "pending")
            .where(Intention.context_match.is_not(None))
        )

        async with async_session() as session:
            result = await session.execute(stmt)
            all_intentions = list(result.scalars().all())

        # Filter by context overlap in Python (JSONB matching is flexible)
        matched: list[Intention] = []
        for intention in all_intentions:
            if self._context_matches(intention.context_match, context):
                matched.append(intention)

        logger.debug(
            "Found %d context-triggered intentions (checked %d)",
            len(matched), len(all_intentions),
        )
        return matched

    async def check_stale_memories(
        self,
        min_importance: float = 0.7,
        stale_days: int = 180,
    ) -> list[Memory]:
        """Find important memories that haven't been accessed recently.

        These memories may need re-consolidation or proactive surfacing
        to prevent important knowledge from being forgotten.

        Args:
            min_importance: Minimum importance threshold (default 0.7).
            stale_days: Days since last access to consider stale (default 180).

        Returns:
            List of stale Memory ORM objects.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)

        stmt = (
            select(Memory)
            .where(Memory.status == "active")
            .where(Memory.importance >= min_importance)
            .where(
                (Memory.last_accessed <= cutoff)
                | (Memory.last_accessed.is_(None))
            )
            .order_by(Memory.importance.desc())
            .limit(20)
        )

        async with async_session() as session:
            result = await session.execute(stmt)
            memories = list(result.scalars().all())

        logger.debug(
            "Found %d stale memories (importance >= %.2f, not accessed in %d days)",
            len(memories), min_importance, stale_days,
        )
        return memories

    async def check_all(
        self, context: ContextFingerprint,
    ) -> dict[str, list[Any]]:
        """Run all trigger checks and return grouped results.

        Args:
            context: Current session context fingerprint.

        Returns:
            Dict with keys 'time', 'context', 'stale', each mapping
            to a list of triggered Intention or Memory objects.
        """
        time_triggers = await self.check_time_triggers()
        context_triggers = await self.check_context_triggers(context)
        stale_memories = await self.check_stale_memories()

        return {
            "time": time_triggers,
            "context": context_triggers,
            "stale": stale_memories,
        }

    # ── Internal Helpers ──────────────────────────────────────

    @staticmethod
    def _context_matches(
        intention_context: dict[str, Any] | None,
        current: ContextFingerprint,
    ) -> bool:
        """Check if an intention's context_match overlaps the current context.

        Matching rules (any match = True):
            - project matches current.project
            - module matches current.module
            - any tool in tools overlaps current.tools
            - any topic overlaps current.topics
        """
        if not intention_context:
            return False

        # Project match
        intent_project = intention_context.get("project")
        if intent_project and current.project and intent_project == current.project:
            return True

        # Module match
        intent_module = intention_context.get("module")
        if intent_module and current.module and intent_module == current.module:
            return True

        # Tools overlap
        intent_tools = set(intention_context.get("tools", []))
        if intent_tools and set(current.tools) & intent_tools:
            return True

        # Topics overlap
        intent_topics = set(intention_context.get("topics", []))
        if intent_topics and set(current.topics) & intent_topics:
            return True

        return False
