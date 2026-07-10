"""PostgreSQL implementation of the MemoryStore protocol.

Uses async SQLAlchemy with asyncpg and pgvector for embedding
similarity search via cosine distance (``<=>``)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import array



from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import Memory, MemorySession, Session
from life_graph.models.schemas import MemoryCreate, MemoryUpdate
from life_graph.storage.database import async_session


class PostgresMemoryStore:
    """Async PostgreSQL-backed memory store.

    All public methods open their own session via ``async_session()`` so
    they are safe to call from any async context (routes, services, CLI).
    """

    # ── Store ─────────────────────────────────────────────────

    async def store(self, memory: MemoryCreate, *, embedding: list[float] | None = None) -> Memory:
        """Persist a new memory from a creation payload."""
        from life_graph.config import settings

        content_hash = hashlib.sha256(
            memory.content.strip().lower().encode()
        ).hexdigest()

        row = Memory(
            content=memory.content,
            reasoning=memory.reasoning,
            tags=memory.tags,
            properties=memory.properties or {},
            importance=memory.importance if memory.importance is not None else 0.5,
            source_type=memory.source_type or "inferred",
            content_hash=content_hash,
            tenant_id=get_current_tenant_id(),
        )
        if embedding:
            row.embedding = embedding
            row.embedding_model = (
                settings.lm_embedding_model if settings.use_local_llm
                else settings.embedding_model
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
            result = await session.execute(
                select(Memory).where(
                    Memory.id == memory_id,
                    Memory.tenant_id == get_current_tenant_id(),
                )
            )
            return result.scalar_one_or_none()

    # ── Update ────────────────────────────────────────────────

    async def update(self, memory_id: uuid.UUID, updates: MemoryUpdate) -> Memory:
        """Apply a partial update and return the refreshed instance.

        Raises:
            ValueError: If the memory does not exist.
        """
        tenant_id = get_current_tenant_id()
        async with async_session() as session:
            result = await session.execute(
                select(Memory).where(
                    Memory.id == memory_id,
                    Memory.tenant_id == tenant_id,
                )
            )
            row = result.scalar_one_or_none()
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
        tenant_id = get_current_tenant_id()
        async with async_session() as session:
            # Cascade: remove association rows first
            await session.execute(
                delete(MemorySession).where(
                    MemorySession.memory_id == memory_id,
                )
            )
            result = await session.execute(
                delete(Memory).where(
                    Memory.id == memory_id,
                    Memory.tenant_id == tenant_id,
                )
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
        stmt = select(Memory).where(
            Memory.embedding.is_not(None),
            Memory.tenant_id == get_current_tenant_id(),
        )
        stmt = self._apply_filters(stmt, Memory, filters)
        stmt = stmt.order_by(Memory.embedding.cosine_distance(embedding))
        stmt = stmt.limit(limit)

        async with async_session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def hybrid_search(
        self,
        embedding: list[float],
        query_text: str,
        limit: int = 10,
        filters: dict | None = None,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
    ) -> list[tuple[Memory, float]]:
        """Hybrid search combining vector similarity with BM25 keyword matching.

        Fuses two signals into a single score:
        - **Vector** (cosine similarity via pgvector): captures semantic meaning
        - **BM25** (ts_rank via tsvector/GIN): captures exact keyword matches

        This catches cases pure vector search misses — e.g., searching "FastAPI"
        should boost exact string matches, not just semantically similar concepts.

        Args:
            embedding: Query embedding vector.
            query_text: Original query text for BM25 matching.
            limit: Maximum results to return.
            filters: Optional filter criteria (same as search_similar).
            vector_weight: Weight for cosine similarity score (0-1).
            bm25_weight: Weight for BM25 keyword score (0-1).

        Returns:
            List of (Memory, hybrid_score) tuples, sorted by hybrid_score desc.
        """
        from sqlalchemy import case, literal_column, text
        from sqlalchemy.sql import func as sqlfunc

        tenant_id = get_current_tenant_id()

        # Subquery: get vector scores (top 100 candidates by cosine)
        # Then left-join with BM25 scores and fuse
        #
        # We use raw SQL for the tsvector column since it's a GENERATED column
        # not mapped in the ORM.
        raw_sql = text("""
            WITH vector_candidates AS (
                SELECT id,
                       1.0 - (embedding <=> :query_embedding) AS v_score
                FROM memories
                WHERE embedding IS NOT NULL
                  AND tenant_id = :tenant_id
                  AND status = 'active'
                ORDER BY embedding <=> :query_embedding
                LIMIT 100
            ),
            bm25_matches AS (
                SELECT id,
                       ts_rank(content_tsv, plainto_tsquery('english', :query_text)) AS b_score
                FROM memories
                WHERE tenant_id = :tenant_id
                  AND status = 'active'
                  AND content_tsv @@ plainto_tsquery('english', :query_text)
            )
            SELECT
                v.id,
                (
                    :vw * COALESCE(v.v_score, 0) +
                    :bw * COALESCE(b.b_score, 0)
                ) AS hybrid_score
            FROM vector_candidates v
            LEFT JOIN bm25_matches b ON v.id = b.id

            UNION

            SELECT
                b2.id,
                (
                    :vw * COALESCE(v2.v_score, 0) +
                    :bw * COALESCE(b2.b_score, 0)
                ) AS hybrid_score
            FROM bm25_matches b2
            LEFT JOIN vector_candidates v2 ON b2.id = v2.id
            WHERE v2.id IS NULL

            ORDER BY hybrid_score DESC
            LIMIT :result_limit
        """)

        async with async_session() as session:
            # Execute the hybrid query to get scored IDs
            result = await session.execute(
                raw_sql,
                {
                    "query_embedding": str(embedding),
                    "query_text": query_text,
                    "tenant_id": tenant_id,
                    "vw": vector_weight,
                    "bw": bm25_weight,
                    "result_limit": limit,
                },
            )
            scored_ids = [(row[0], float(row[1])) for row in result.fetchall()]

            if not scored_ids:
                return []

            # Fetch full ORM objects for the scored IDs
            id_list = [sid for sid, _ in scored_ids]
            score_map = {sid: score for sid, score in scored_ids}

            orm_result = await session.execute(
                select(Memory).where(Memory.id.in_(id_list))
            )
            rows = {r.id: r for r in orm_result.scalars().all()}

            # Return in hybrid_score order with ORM objects
            return [
                (rows[mid], score_map[mid])
                for mid in id_list
                if mid in rows
            ]

    # ── List ──────────────────────────────────────────────────

    async def list_memories(
        self,
        filters: dict | None = None,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Memory], bool]:
        """List memories with optional filtering and cursor-based pagination.

        When *cursor* is provided, keyset pagination is used and *offset*
        is ignored.  The cursor encodes ``(created_at, id)`` for
        deterministic, gap-free paging.

        Returns:
            A tuple of ``(memories, has_more)``.
        """
        stmt = select(Memory).where(
            Memory.tenant_id == get_current_tenant_id(),
        )
        stmt = self._apply_filters(stmt, Memory, filters)
        stmt = stmt.order_by(Memory.created_at.desc(), Memory.id.desc())

        if cursor:
            from life_graph.api.responses import decode_cursor

            cur = decode_cursor(cursor)
            cursor_ts = datetime.fromisoformat(cur["k"])
            cursor_id = uuid.UUID(cur["id"])
            stmt = stmt.where(
                tuple_(Memory.created_at, Memory.id)
                < tuple_(cursor_ts, cursor_id)
            )
        else:
            stmt = stmt.offset(offset)

        stmt = stmt.limit(limit + 1)

        async with async_session() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        return rows, has_more

    # ── Touch ─────────────────────────────────────────────────

    async def touch(self, memory_id: uuid.UUID) -> None:
        """Increment access_count and set last_accessed = now()."""
        async with async_session() as session:
            await session.execute(
                update(Memory)
                .where(
                    Memory.id == memory_id,
                    Memory.tenant_id == get_current_tenant_id(),
                )
                .values(
                    access_count=Memory.access_count + 1,
                    last_accessed=datetime.now(timezone.utc),
                )
            )
            await session.commit()

    # ── Private Helpers ───────────────────────────────────────

    @staticmethod
    def _apply_filters(stmt, model, filters: dict | None):
        """Apply optional filter criteria to a ``SELECT`` statement.

        Parameters
        ----------
        stmt : Select
            The base query to augment.
        model : type
            The SQLAlchemy model class (e.g. ``Memory``) whose
            columns should be referenced in the filter clauses.
        filters : dict | None
            Optional mapping of filter keys to values.

        Supported keys
        ──────────────
        - ``status`` (str)            – exact match
        - ``tags`` (list[str])        – PostgreSQL array overlap (``&&``)
        - ``properties`` (dict)       – JSONB containment (``@>``)
        - ``created_after`` (datetime)
        - ``created_before`` (datetime)
        - ``min_importance`` (float)
        - ``source_type`` (str)       – exact match on source_type column
        """
        if not filters:
            return stmt

        if "status" in filters:
            stmt = stmt.where(model.status == filters["status"])

        if "tags" in filters:
            tag_list = filters["tags"]
            if tag_list:
                stmt = stmt.where(model.tags.overlap(tag_list))

        if "properties" in filters:
            stmt = stmt.where(model.properties.contains(filters["properties"]))

        if "created_after" in filters:
            stmt = stmt.where(model.created_at >= filters["created_after"])

        if "created_before" in filters:
            stmt = stmt.where(model.created_at <= filters["created_before"])

        if "min_importance" in filters:
            stmt = stmt.where(model.importance >= filters["min_importance"])

        if "source_type" in filters:
            stmt = stmt.where(model.source_type == filters["source_type"])

        return stmt

    # ── Session Lifecycle ─────────────────────────────────────

    async def create_session(self, context: dict | None = None) -> Session:
        """Start a new session and return it."""
        row = Session(
            context=context or {},
            tenant_id=get_current_tenant_id(),
        )
        async with async_session() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row

    async def end_session(
        self,
        session_id: uuid.UUID,
        summary: str | None = None,
    ) -> Session | None:
        """End a session: set ended_at and optional summary."""
        tenant_id = get_current_tenant_id()
        async with async_session() as session:
            result = await session.execute(
                select(Session).where(
                    Session.id == session_id,
                    Session.tenant_id == tenant_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            row.ended_at = datetime.now(timezone.utc)
            if summary:
                row.summary = summary
            await session.commit()
            await session.refresh(row)
        return row

    async def get_session(self, session_id: uuid.UUID) -> Session | None:
        """Retrieve a session by ID."""
        async with async_session() as session:
            result = await session.execute(
                select(Session).where(
                    Session.id == session_id,
                    Session.tenant_id == get_current_tenant_id(),
                )
            )
            return result.scalar_one_or_none()

    async def list_sessions(
        self,
        limit: int = 10,
        cursor: str | None = None,
    ) -> tuple[list[Session], bool]:
        """List recent sessions ordered by started_at desc with cursor pagination.

        When *cursor* is provided, keyset pagination is used.  The
        cursor encodes ``(started_at, id)`` for deterministic paging.

        Returns:
            A tuple of ``(sessions, has_more)``.
        """
        stmt = (
            select(Session)
            .where(Session.tenant_id == get_current_tenant_id())
            .order_by(Session.started_at.desc(), Session.id.desc())
        )

        if cursor:
            from life_graph.api.responses import decode_cursor

            cur = decode_cursor(cursor)
            cursor_ts = datetime.fromisoformat(cur["k"])
            cursor_id = uuid.UUID(cur["id"])
            stmt = stmt.where(
                tuple_(Session.started_at, Session.id)
                < tuple_(cursor_ts, cursor_id)
            )

        stmt = stmt.limit(limit + 1)

        async with async_session() as session:
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        return rows, has_more

    async def update_session_context(
        self,
        session_id: uuid.UUID,
        context: dict,
    ) -> Session | None:
        """Update a session's context (heartbeat)."""
        tenant_id = get_current_tenant_id()
        async with async_session() as session:
            result = await session.execute(
                select(Session).where(
                    Session.id == session_id,
                    Session.tenant_id == tenant_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            row.context = context
            await session.commit()
            await session.refresh(row)
        return row

    async def link_memory_to_session(
        self,
        memory_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        """Create a MemorySession link and bump session counters."""
        tenant_id = get_current_tenant_id()
        async with async_session() as session:
            link = MemorySession(
                memory_id=memory_id,
                session_id=session_id,
                tenant_id=tenant_id,
            )
            session.add(link)
            await session.execute(
                update(Session)
                .where(
                    Session.id == session_id,
                    Session.tenant_id == tenant_id,
                )
                .values(memories_created=Session.memories_created + 1)
            )
            await session.commit()

    async def count_session_memories(self, session_id: uuid.UUID) -> int:
        """Count memories linked to a session."""
        tenant_id = get_current_tenant_id()
        async with async_session() as session:
            result = await session.scalar(
                select(func.count(MemorySession.memory_id))
                .where(
                    MemorySession.session_id == session_id,
                    MemorySession.tenant_id == tenant_id,
                )
            )
            return result or 0

    # ── Count ─────────────────────────────────────────────────

    async def count_memories(self, filters: dict | None = None) -> int:
        """Count memories matching the given filters.

        Uses the same filter vocabulary as :meth:`list_memories`.
        """
        async with async_session() as session:
            query = select(func.count(Memory.id)).where(
                Memory.tenant_id == get_current_tenant_id(),
            )
            query = self._apply_filters(query, Memory, filters)
            result = await session.execute(query)
            return result.scalar() or 0

    # ── Decay & Lifecycle ─────────────────────────────────────

    async def decay_sweep(self) -> int:
        """Archive memories whose importance has decayed below threshold.

        Scans all *active* memories for the current tenant and
        archives those whose ``importance`` has fallen to or below
        the configured ``decay_archive_threshold``.

        Returns:
            The number of memories archived.
        """
        from life_graph.config import settings

        threshold = settings.decay_archive_threshold
        async with async_session() as session:
            result = await session.execute(
                update(Memory)
                .where(
                    Memory.tenant_id == get_current_tenant_id(),
                    Memory.status == "active",
                    Memory.importance <= threshold,
                )
                .values(status="archived")
            )
            await session.commit()
            return result.rowcount

    async def unarchive(self, memory_id: uuid.UUID) -> Memory | None:
        """Resurrect an archived memory: set status='active', reset last_accessed."""
        async with async_session() as session:
            query = select(Memory).where(
                Memory.id == memory_id,
                Memory.tenant_id == get_current_tenant_id(),
            )
            result = await session.execute(query)
            memory = result.scalar_one_or_none()
            if not memory:
                return None
            memory.status = "active"
            memory.last_accessed = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(memory)
            return memory

    # ── Reinforcement (Confidence Decay) ─────────────────────

    async def reinforce(self, memory_id: uuid.UUID) -> Memory:
        """Reinforce a memory — user confirms it is still accurate.

        Resets confidence to 0.9, updates last_reinforced,
        increments reinforced_count, and touches last_accessed.

        Raises:
            ValueError: If the memory does not exist.
        """
        tenant_id = get_current_tenant_id()
        async with async_session() as session:
            result = await session.execute(
                select(Memory).where(
                    Memory.id == memory_id,
                    Memory.tenant_id == tenant_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise ValueError(f"Memory {memory_id} not found")

            now = datetime.now(timezone.utc)
            row.confidence = 0.9
            row.last_reinforced = now
            row.reinforced_count = (row.reinforced_count or 0) + 1
            row.last_accessed = now
            row.access_count = (row.access_count or 0) + 1
            row.updated_at = now

            await session.commit()
            await session.refresh(row)
        return row

    async def deny(
        self,
        memory_id: uuid.UUID,
        replacement_content: str | None = None,
    ) -> tuple[Memory, Memory | None]:
        """Deny a memory — user says it is no longer accurate.

        Marks the memory as 'superseded'. If replacement_content is provided,
        creates a new memory that supersedes the old one.

        Args:
            memory_id: The memory to deny.
            replacement_content: Optional replacement fact.

        Returns:
            Tuple of (denied_memory, new_replacement_memory_or_None).

        Raises:
            ValueError: If the memory does not exist.
        """
        tenant_id = get_current_tenant_id()
        async with async_session() as session:
            result = await session.execute(
                select(Memory).where(
                    Memory.id == memory_id,
                    Memory.tenant_id == tenant_id,
                )
            )
            old = result.scalar_one_or_none()
            if old is None:
                raise ValueError(f"Memory {memory_id} not found")

            now = datetime.now(timezone.utc)
            old.status = "superseded"
            old.valid_until = now
            old.updated_at = now

            replacement = None
            if replacement_content:
                new_id = uuid.uuid4()
                replacement = Memory(
                    id=new_id,
                    content=replacement_content,
                    tenant_id=tenant_id,
                    source_type="reinforcement",
                    importance=old.importance,
                    importance_tier=old.importance_tier,
                    confidence=0.9,
                    trust_score=old.trust_score,
                    tags=old.tags,
                    properties=old.properties or {},
                    supersedes=memory_id,
                    last_reinforced=now,
                    reinforced_count=1,
                    created_at=now,
                    updated_at=now,
                    valid_from=now,
                )
                session.add(replacement)
                old.superseded_by = new_id

            await session.commit()
            await session.refresh(old)
            if replacement:
                await session.refresh(replacement)
        return old, replacement

    # ── Deduplication ─────────────────────────────────────────

    async def find_exact_duplicate(self, content_hash: str) -> Memory | None:
        """Find a memory with matching content hash (O(1) via index)."""
        async with async_session() as session:
            query = select(Memory).where(
                Memory.tenant_id == get_current_tenant_id(),
                Memory.content_hash == content_hash,
                Memory.status == "active",
            ).limit(1)
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def find_similar(
        self,
        embedding: list[float],
        threshold: float = 0.92,
        limit: int = 5,
    ) -> list[tuple[Memory, float]]:
        """Find memories above cosine similarity threshold.

        Uses pgvector's cosine distance operator and converts to
        similarity (``1 - distance``).  Only active memories with
        an embedding are considered.

        Returns:
            List of ``(memory, similarity_score)`` tuples ordered
            by descending similarity.
        """
        async with async_session() as session:
            # cosine distance = 1 - cosine_similarity, so similarity = 1 - distance
            distance = Memory.embedding.cosine_distance(embedding)
            query = (
                select(Memory, (1 - distance).label("similarity"))
                .where(
                    Memory.tenant_id == get_current_tenant_id(),
                    Memory.embedding.isnot(None),
                    Memory.status == "active",
                    (1 - distance) >= threshold,
                )
                .order_by(distance)
                .limit(limit)
            )
            result = await session.execute(query)
            return [(row[0], float(row[1])) for row in result.fetchall()]

    # ── Impact Scoring (Feature 5) ────────────────────────────

    async def link_recall_to_session(
        self, memory_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        """Link a recalled memory to a session with role='recalled'.

        Uses INSERT ... ON CONFLICT DO NOTHING to handle the case where
        the memory was already linked (e.g., if it was created in the
        same session).
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        async with async_session() as session:
            stmt = pg_insert(MemorySession).values(
                memory_id=memory_id,
                session_id=session_id,
                role="recalled",
            ).on_conflict_do_nothing(
                index_elements=["memory_id", "session_id"]
            )
            await session.execute(stmt)
            await session.commit()

    async def get_recalled_memory_ids(
        self, session_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Get IDs of all memories recalled (not created) in a session."""
        async with async_session() as session:
            stmt = (
                select(MemorySession.memory_id)
                .where(
                    MemorySession.session_id == session_id,
                    MemorySession.role == "recalled",
                )
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

