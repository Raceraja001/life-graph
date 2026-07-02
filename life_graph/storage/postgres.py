"""PostgreSQL implementation of the MemoryStore protocol.

Uses async SQLAlchemy with asyncpg and pgvector for embedding
similarity search via cosine distance (``<=>``).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import array

from life_graph.models.db import Memory, MemorySession
from life_graph.models.schemas import MemoryCreate, MemoryUpdate
from life_graph.storage.database import async_session


class PostgresMemoryStore:
    """Async PostgreSQL-backed memory store.

    All public methods open their own session via ``async_session()`` so
    they are safe to call from any async context (routes, services, CLI).
    """

    # ── Store ─────────────────────────────────────────────────

    async def store(self, memory: MemoryCreate) -> Memory:
        """Persist a new memory from a creation payload."""
        row = Memory(
            content=memory.content,
            reasoning=memory.reasoning,
            tags=memory.tags,
            properties=memory.properties or {},
            importance=memory.importance if memory.importance is not None else 0.5,
            source_type=memory.source_type or "inferred",
        )
        async with async_session() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row

    # ── Retrieve ──────────────────────────────────────────────

    async def retrieve(self, memory_id: uuid.UUID) -> Memory | None:
        """Fetch a memory by primary key."""
        async with async_session() as session:
            return await session.get(Memory, memory_id)

    # ── Update ────────────────────────────────────────────────

    async def update(self, memory_id: uuid.UUID, updates: MemoryUpdate) -> Memory:
        """Apply a partial update and return the refreshed instance.

        Raises:
            ValueError: If the memory does not exist.
        """
        async with async_session() as session:
            row = await session.get(Memory, memory_id)
            if row is None:
                raise ValueError(f"Memory {memory_id} not found")

            patch = updates.model_dump(exclude_unset=True)
            for field, value in patch.items():
                setattr(row, field, value)

            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(row)
        return row

    # ── Delete ────────────────────────────────────────────────

    async def delete(self, memory_id: uuid.UUID) -> bool:
        """Delete a memory and cascade to memory_sessions.

        Returns ``True`` if the memory existed and was deleted.
        """
        async with async_session() as session:
            # Cascade: remove association rows first
            await session.execute(
                delete(MemorySession).where(MemorySession.memory_id == memory_id)
            )
            result = await session.execute(
                delete(Memory).where(Memory.id == memory_id)
            )
            await session.commit()
            return result.rowcount > 0

    # ── Similarity Search ─────────────────────────────────────

    async def search_similar(
        self,
        embedding: list[float],
        limit: int = 10,
        filters: dict | None = None,
    ) -> list[Memory]:
        """Find closest memories by cosine distance using pgvector ``<=>``.

        Applies the same optional filters as :meth:`list_memories`.
        """
        stmt = select(Memory).where(Memory.embedding.is_not(None))
        stmt = self._apply_filters(stmt, filters)
        stmt = stmt.order_by(Memory.embedding.cosine_distance(embedding))
        stmt = stmt.limit(limit)

        async with async_session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ── List ──────────────────────────────────────────────────

    async def list_memories(
        self,
        filters: dict | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Memory]:
        """List memories with optional filtering and pagination."""
        stmt = select(Memory)
        stmt = self._apply_filters(stmt, filters)
        stmt = stmt.order_by(Memory.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)

        async with async_session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ── Touch ─────────────────────────────────────────────────

    async def touch(self, memory_id: uuid.UUID) -> None:
        """Increment access_count and set last_accessed = now()."""
        async with async_session() as session:
            await session.execute(
                update(Memory)
                .where(Memory.id == memory_id)
                .values(
                    access_count=Memory.access_count + 1,
                    last_accessed=datetime.now(timezone.utc),
                )
            )
            await session.commit()

    # ── Private Helpers ───────────────────────────────────────

    @staticmethod
    def _apply_filters(stmt, filters: dict | None):
        """Apply optional filter criteria to a ``SELECT`` statement.

        Supported keys
        ──────────────
        - ``status`` (str)            – exact match
        - ``tags`` (list[str])        – PostgreSQL array overlap (``&&``)
        - ``properties`` (dict)       – JSONB containment (``@>``)
        - ``created_after`` (datetime)
        - ``created_before`` (datetime)
        - ``min_importance`` (float)
        """
        if not filters:
            return stmt

        if "status" in filters:
            stmt = stmt.where(Memory.status == filters["status"])

        if "tags" in filters:
            tag_list = filters["tags"]
            if tag_list:
                stmt = stmt.where(Memory.tags.overlap(tag_list))

        if "properties" in filters:
            stmt = stmt.where(Memory.properties.contains(filters["properties"]))

        if "created_after" in filters:
            stmt = stmt.where(Memory.created_at >= filters["created_after"])

        if "created_before" in filters:
            stmt = stmt.where(Memory.created_at <= filters["created_before"])

        if "min_importance" in filters:
            stmt = stmt.where(Memory.importance >= filters["min_importance"])

        return stmt
