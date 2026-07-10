"""Shared Context Service — agent knowledge sharing (Era 7).

Allows agents to share context entries (facts, decisions, observations)
with pgvector semantic search, SHA-256 content deduplication, and
near-duplicate merging via cosine similarity.

Usage::

    svc = SharedContextService(session_factory, embedding_service)
    entry = await svc.create(tenant_id, data)
    results = await svc.search(tenant_id, project_id, "deployment config")
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text, update

from life_graph.core.events import EventType, event_bus

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)


class SharedContextService:
    """Manage shared context entries across agents.

    Features:
    - Semantic embedding + SHA-256 content hashing
    - Cosine similarity dedup (≥ 0.95 → merge instead of create)
    - pgvector cosine similarity search
    - Access count tracking on search hits
    - Relevance decay for stale entries
    """

    # Similarity threshold for near-duplicate merging
    DEDUP_THRESHOLD = 0.95

    def __init__(self, session_factory, embedding_service) -> None:
        self._session_factory = session_factory
        self._embedding_service = embedding_service

    # ── Public API ───────────────────────────────────────────

    async def create(
        self,
        tenant_id: str,
        data: dict[str, Any],
    ):
        """Create a shared context entry with dedup check.

        Generates embedding and content hash. If a near-duplicate exists
        (cosine similarity ≥ 0.95), merges into the existing entry instead.

        Args:
            tenant_id: Tenant isolation key.
            data: Dict with ``content``, ``context_type``, ``project_id``,
                  ``source_agent``, ``source_task_id``, ``metadata``.

        Returns:
            The created (or merged) SharedContextEntry ORM instance.
        """
        from life_graph.models.db import SharedContext as SharedContextEntry

        content = data["content"]
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Generate embedding
        embedding = self._embedding_service.embed(content)

        async with self._session_factory() as session:
            # Exact hash dedup — fast path
            existing = await session.execute(
                select(SharedContextEntry).where(
                    SharedContextEntry.tenant_id == tenant_id,
                    SharedContextEntry.content_hash == content_hash,
                )
            )
            exact_match = existing.scalar_one_or_none()
            if exact_match:
                # Update access and return existing
                exact_match.access_count += 1
                exact_match.last_accessed = _utcnow()
                await session.commit()
                await session.refresh(exact_match)
                logger.info(
                    "Exact duplicate found for shared context (hash=%s), merged",
                    content_hash[:12],
                )
                return exact_match

            # Near-duplicate check via cosine similarity (if embedding available)
            if embedding and len(embedding) > 0:
                near_dup = await self._find_near_duplicate(
                    session, tenant_id, embedding,
                    data.get("project_id"),
                )
                if near_dup:
                    # Merge: update metadata, bump access count
                    near_dup.access_count += 1
                    near_dup.last_accessed = _utcnow()
                    existing_meta = near_dup.properties or {}
                    new_meta = data.get("metadata", {}) or {}
                    existing_meta.update(new_meta)
                    near_dup.properties = existing_meta
                    await session.commit()
                    await session.refresh(near_dup)
                    logger.info(
                        "Near-duplicate merged for shared context (id=%s)",
                        near_dup.id,
                    )
                    return near_dup

            # Create new entry
            entry = SharedContextEntry(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                project_id=data.get("project_id") if isinstance(data.get("project_id"), str) else (str(data.get("project_id")) if data.get("project_id") else None),
                title=data.get("title") or content[:50],
                content=content,
                content_hash=content_hash,
                context_type=data.get("context_type", "observation"),
                source_agent=data.get("source_agent"),
                source_task_id=data.get("source_task_id"),
                embedding=embedding if embedding else None,
                relevance_score=data.get("relevance_score", 1.0),
                properties=data.get("metadata", {}),
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)

        await event_bus.emit(
            EventType.MEMORY_CREATED,
            {
                "shared_context_id": str(entry.id),
                "context_type": entry.context_type,
                "project_id": str(entry.project_id) if entry.project_id else None,
            },
            source="shared_context",
        )

        logger.info(
            "Created shared context %s (type=%s) for tenant %s",
            entry.id, entry.context_type, tenant_id,
        )
        return entry

    async def search(
        self,
        tenant_id: str,
        project_id: uuid.UUID | str | None = None,
        query: str = "",
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search shared context entries by semantic similarity.

        Uses pgvector cosine distance for ranking. Increments
        access_count on returned results.

        Args:
            tenant_id: Tenant isolation key.
            project_id: Optional project scope.
            query: Natural language search query.
            limit: Maximum results to return.
            min_similarity: Minimum cosine similarity threshold.

        Returns:
            List of dicts with entry data and similarity score.
        """
        from life_graph.models.db import SharedContext as SharedContextEntry

        if not query:
            # Return recent entries without semantic search
            async with self._session_factory() as session:
                stmt = (
                    select(SharedContextEntry)
                    .where(SharedContextEntry.tenant_id == tenant_id)
                )
                if project_id:
                    stmt = stmt.where(SharedContextEntry.project_id == project_id)
                stmt = stmt.order_by(SharedContextEntry.created_at.desc()).limit(limit)

                result = await session.execute(stmt)
                entries = result.scalars().all()
                return [self._entry_to_dict(e, similarity=None) for e in entries]

        # Generate query embedding
        query_embedding = self._embedding_service.embed(query)
        if not query_embedding or len(query_embedding) == 0:
            logger.warning("Empty query embedding — falling back to recent entries")
            return await self.search(tenant_id, project_id, "", limit, min_similarity)

        async with self._session_factory() as session:
            # pgvector cosine distance: 1 - cosine_distance = similarity
            # Use <=> operator for cosine distance
            embedding_col = SharedContextEntry.embedding
            distance = embedding_col.cosine_distance(query_embedding)

            stmt = (
                select(SharedContextEntry, (1 - distance).label("similarity"))
                .where(
                    SharedContextEntry.tenant_id == tenant_id,
                    SharedContextEntry.embedding.isnot(None),
                )
            )
            if project_id:
                stmt = stmt.where(SharedContextEntry.project_id == project_id)

            stmt = (
                stmt
                .order_by(distance)
                .limit(limit)
            )

            result = await session.execute(stmt)
            rows = result.all()

            # Filter by minimum similarity and build results
            results = []
            entry_ids = []
            for entry, similarity in rows:
                if similarity >= min_similarity:
                    results.append(self._entry_to_dict(entry, similarity))
                    entry_ids.append(entry.id)

            # Increment access counts
            if entry_ids:
                await session.execute(
                    update(SharedContextEntry)
                    .where(SharedContextEntry.id.in_(entry_ids))
                    .values(
                        access_count=SharedContextEntry.access_count + 1,
                        last_accessed=_utcnow(),
                    )
                )
                await session.commit()

            return results

    async def get_thread_context(
        self,
        tenant_id: str,
        root_task_id: uuid.UUID | str,
    ) -> list[dict[str, Any]]:
        """Get all shared context entries from a task tree.

        Retrieves context entries where source_task_id matches the
        root task or any of its children.

        Args:
            tenant_id: Tenant isolation key.
            root_task_id: Root task ID to trace context from.

        Returns:
            List of context entry dicts.
        """
        from life_graph.models.db import AgentTask, SharedContext as SharedContextEntry

        async with self._session_factory() as session:
            # Get all task IDs in the tree (root + descendants)
            task_ids = [uuid.UUID(str(root_task_id))]

            # Walk the task tree (breadth-first)
            queue = [uuid.UUID(str(root_task_id))]
            while queue:
                current_id = queue.pop(0)
                result = await session.execute(
                    select(AgentTask.id).where(
                        AgentTask.parent_task_id == current_id,
                        AgentTask.tenant_id == tenant_id,
                    )
                )
                child_ids = [r[0] for r in result.all()]
                task_ids.extend(child_ids)
                queue.extend(child_ids)

            # Fetch context entries for all task IDs
            result = await session.execute(
                select(SharedContextEntry)
                .where(
                    SharedContextEntry.tenant_id == tenant_id,
                    SharedContextEntry.source_task_id.in_(task_ids),
                )
                .order_by(SharedContextEntry.created_at.asc())
            )
            entries = result.scalars().all()
            return [self._entry_to_dict(e, similarity=None) for e in entries]

    async def decay_stale(
        self,
        tenant_id: str,
        days: int = 30,
    ) -> int:
        """Reduce relevance_score for entries not accessed in N days.

        Applies a multiplicative decay factor of 0.9 to entries that
        haven't been accessed within the specified period.

        Args:
            tenant_id: Tenant isolation key.
            days: Number of days of inactivity before decay.

        Returns:
            Number of entries affected.
        """
        from life_graph.models.db import SharedContext as SharedContextEntry

        cutoff = _utcnow() - timedelta(days=days)

        async with self._session_factory() as session:
            result = await session.execute(
                update(SharedContextEntry)
                .where(
                    SharedContextEntry.tenant_id == tenant_id,
                    SharedContextEntry.relevance_score > 0.1,
                    (
                        (SharedContextEntry.last_accessed < cutoff)
                        | (SharedContextEntry.last_accessed.is_(None))
                    ),
                    SharedContextEntry.created_at < cutoff,
                )
                .values(
                    relevance_score=SharedContextEntry.relevance_score * 0.9,
                )
            )
            affected = result.rowcount
            await session.commit()

        if affected:
            logger.info(
                "Decayed relevance for %d stale context entries (tenant=%s, days=%d)",
                affected, tenant_id, days,
            )
        return affected

    # ── Internal Helpers ─────────────────────────────────────

    async def _find_near_duplicate(
        self, session, tenant_id: str, embedding: list[float],
        project_id=None,
    ):
        """Find a near-duplicate entry by cosine similarity."""
        from life_graph.models.db import SharedContext as SharedContextEntry

        embedding_col = SharedContextEntry.embedding
        distance = embedding_col.cosine_distance(embedding)

        stmt = (
            select(SharedContextEntry, (1 - distance).label("similarity"))
            .where(
                SharedContextEntry.tenant_id == tenant_id,
                SharedContextEntry.embedding.isnot(None),
            )
        )
        if project_id:
            stmt = stmt.where(SharedContextEntry.project_id == project_id)

        stmt = stmt.order_by(distance).limit(1)
        result = await session.execute(stmt)
        row = result.first()

        if row and row[1] >= self.DEDUP_THRESHOLD:
            return row[0]
        return None

    @staticmethod
    def _entry_to_dict(entry, similarity: float | None = None) -> dict[str, Any]:
        """Convert a SharedContextEntry ORM instance to a dict."""
        d = {
            "id": str(entry.id),
            "tenant_id": entry.tenant_id,
            "project_id": str(entry.project_id) if entry.project_id else None,
            "content": entry.content,
            "context_type": entry.context_type,
            "source_agent": entry.source_agent,
            "source_task_id": str(entry.source_task_id) if entry.source_task_id else None,
            "relevance_score": entry.relevance_score,
            "access_count": entry.access_count,
            "metadata": entry.properties if getattr(entry, "properties", None) is not None else {},
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "last_accessed": entry.last_accessed.isoformat() if entry.last_accessed else None,
        }
        if similarity is not None:
            d["similarity"] = round(float(similarity), 4)
        return d
