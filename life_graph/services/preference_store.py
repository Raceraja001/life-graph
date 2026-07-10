"""Preference store service (Era 4 Personal AI).

Manages CRUD, search, and validation for user preferences.
All operations are tenant-scoped and emit events.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.core.events import EventType, event_bus
from life_graph.models.db import Evidence, Preference
from life_graph.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class PreferenceStore:
    """Manage preferences with embedding search, validation tracking,
    and confidence history.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_service: EmbeddingService,
    ) -> None:
        self._session_factory = session_factory
        self._embedding = embedding_service

    # ── Create ────────────────────────────────────────────────

    async def create(self, tenant_id: str, data: dict[str, Any]) -> Preference:
        """Create a new preference with embedding and confidence capping."""
        # Generate embedding from topic + choice
        embed_text = f"{data['topic']}: {data['choice']}"
        if data.get("reason"):
            embed_text += f" — {data['reason']}"
        embedding = self._embedding.embed(embed_text)

        # Cap confidence at 0.7 for inferred sources
        confidence = data.get("confidence", 0.5)
        source = data.get("source", "explicit")
        if source in ("inferred", "observed", "cold_start") and confidence > 0.7:
            confidence = 0.7

        pref = Preference(
            tenant_id=tenant_id,
            topic=data["topic"],
            choice=data["choice"],
            reason=data.get("reason"),
            context=data.get("context"),
            confidence=confidence,
            confidence_history=[{
                "value": confidence,
                "at": datetime.now(timezone.utc).isoformat(),
                "reason": "initial",
            }],
            source=source,
            source_detail=data.get("source_detail"),
            tags=data.get("tags"),
            category=data.get("category"),
            properties=data.get("properties", {}),
            embedding=embedding if embedding else None,
        )

        async with self._session_factory() as session:
            session.add(pref)
            await session.commit()
            await session.refresh(pref)

        await event_bus.emit(
            EventType.PREFERENCE_CREATED,
            {"id": str(pref.id), "tenant_id": tenant_id, "topic": pref.topic},
            source="preference_store",
        )
        logger.info("Created preference %s for tenant %s", pref.id, tenant_id)
        return pref

    # ── List ──────────────────────────────────────────────────

    async def list(
        self,
        tenant_id: str,
        *,
        status: str | None = "active",
        tags: list[str] | None = None,
        category: str | None = None,
        source: str | None = None,
        min_confidence: float | None = None,
        stale_days: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Preference]:
        """List preferences with optional filters."""
        stmt = select(Preference).where(Preference.tenant_id == tenant_id)

        if status:
            stmt = stmt.where(Preference.status == status)
        if tags:
            stmt = stmt.where(Preference.tags.overlap(tags))
        if category:
            stmt = stmt.where(Preference.category == category)
        if source:
            stmt = stmt.where(Preference.source == source)
        if min_confidence is not None:
            stmt = stmt.where(Preference.confidence >= min_confidence)
        if stale_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
            stmt = stmt.where(Preference.last_validated_at < cutoff)

        stmt = stmt.order_by(Preference.updated_at.desc()).limit(limit).offset(offset)

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ── Get ───────────────────────────────────────────────────

    async def get(self, tenant_id: str, preference_id: uuid.UUID) -> Preference | None:
        """Get a single preference by ID."""
        stmt = (
            select(Preference)
            .where(Preference.id == preference_id)
            .where(Preference.tenant_id == tenant_id)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    # ── Update ────────────────────────────────────────────────

    async def update(
        self, tenant_id: str, preference_id: uuid.UUID, data: dict[str, Any]
    ) -> Preference:
        """Partially update a preference, appending to confidence_history."""
        async with self._session_factory() as session:
            pref = await session.get(Preference, preference_id)
            if pref is None or pref.tenant_id != tenant_id:
                raise ValueError(f"Preference {preference_id} not found")

            for field, value in data.items():
                if value is not None and hasattr(pref, field):
                    setattr(pref, field, value)

            # Track confidence changes
            if "confidence" in data and data["confidence"] is not None:
                history = list(pref.confidence_history or [])
                history.append({
                    "value": data["confidence"],
                    "at": datetime.now(timezone.utc).isoformat(),
                    "reason": "manual_update",
                })
                pref.confidence_history = history

            # Regenerate embedding if topic/choice changed
            if "choice" in data or "topic" in data:
                embed_text = f"{pref.topic}: {pref.choice}"
                if pref.reason:
                    embed_text += f" — {pref.reason}"
                pref.embedding = self._embedding.embed(embed_text) or None

            pref.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(pref)

        await event_bus.emit(
            EventType.PREFERENCE_UPDATED,
            {"id": str(pref.id), "tenant_id": tenant_id},
            source="preference_store",
        )
        return pref

    # ── Delete (soft) ─────────────────────────────────────────

    async def delete(self, tenant_id: str, preference_id: uuid.UUID) -> bool:
        """Soft-delete a preference by setting status to 'archived'."""
        async with self._session_factory() as session:
            pref = await session.get(Preference, preference_id)
            if pref is None or pref.tenant_id != tenant_id:
                return False
            pref.status = "archived"
            pref.updated_at = datetime.now(timezone.utc)
            await session.commit()
        return True

    # ── Semantic Search ───────────────────────────────────────

    async def search(
        self,
        tenant_id: str,
        query: str,
        *,
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search preferences using pgvector cosine similarity."""
        query_embedding = self._embedding.embed(query)
        if not query_embedding:
            return []

        # Cosine distance: smaller = more similar
        # Cosine similarity = 1 - cosine_distance
        distance = Preference.embedding.cosine_distance(query_embedding)

        stmt = (
            select(Preference, (1 - distance).label("similarity"))
            .where(Preference.tenant_id == tenant_id)
            .where(Preference.status == "active")
            .where(Preference.embedding.isnot(None))
            .where((1 - distance) >= min_similarity)
            .order_by(distance)
            .limit(limit)
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        return [
            {"preference": row[0], "similarity": float(row[1])}
            for row in rows
        ]

    # ── Stale Preferences ────────────────────────────────────

    async def get_stale(
        self, tenant_id: str, stale_days: int = 90
    ) -> list[Preference]:
        """Get preferences not validated in N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
        stmt = (
            select(Preference)
            .where(Preference.tenant_id == tenant_id)
            .where(Preference.status == "active")
            .where(Preference.last_validated_at < cutoff)
            .order_by(Preference.last_validated_at.asc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())
