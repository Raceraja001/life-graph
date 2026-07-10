"""Evidence store service (Era 4 Personal AI).

Manages CRUD, deduplication, and search for evidence items.
Applies credibility multipliers based on source type and
recalculates parent preference confidence on changes.
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.core.events import EventType, event_bus
from life_graph.models.db import Evidence, Preference
from life_graph.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

# Credibility multipliers by source type
_CREDIBILITY: dict[str, float] = {
    "benchmark": 1.2,
    "paper": 1.1,
    "article": 1.0,
    "hn_discussion": 0.95,
    "blog": 0.9,
    "github_trend": 0.85,
    "reddit": 0.8,
    "ai_opinion": 0.7,
}


class EvidenceStore:
    """Manage evidence items with deduplication, credibility scoring,
    and cross-preference semantic search.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_service: EmbeddingService,
    ) -> None:
        self._session_factory = session_factory
        self._embedding = embedding_service

    # ── Create ────────────────────────────────────────────────

    async def create(self, tenant_id: str, data: dict[str, Any]) -> Evidence:
        """Create evidence with deduplication, credibility multiplier, and embedding."""
        preference_id = data["preference_id"]
        if isinstance(preference_id, str):
            preference_id = uuid.UUID(preference_id)

        # Verify preference exists and belongs to tenant
        async with self._session_factory() as session:
            pref = await session.get(Preference, preference_id)
            if pref is None or pref.tenant_id != tenant_id:
                raise ValueError(f"Preference {preference_id} not found")

        # Check dedup by source_url
        source_url = data.get("source_url")
        if source_url:
            async with self._session_factory() as session:
                existing = await session.execute(
                    select(Evidence)
                    .where(Evidence.preference_id == preference_id)
                    .where(Evidence.source_url == source_url)
                    .where(Evidence.status == "active")
                )
                if existing.scalar_one_or_none() is not None:
                    raise ValueError(
                        f"Evidence with source_url '{source_url}' already exists "
                        f"for preference {preference_id}"
                    )

        # Generate embedding
        embed_text = data["summary"]
        if data.get("source_title"):
            embed_text = f"{data['source_title']}: {embed_text}"
        embedding = self._embedding.embed(embed_text)

        # Apply credibility multiplier
        source_type = data["source_type"]
        credibility = _CREDIBILITY.get(source_type, 1.0)
        weight = credibility  # Initial weight = credibility

        evidence = Evidence(
            tenant_id=tenant_id,
            preference_id=preference_id,
            source_type=source_type,
            source_url=source_url,
            source_title=data.get("source_title"),
            stance=data.get("stance", "supports"),
            summary=data["summary"],
            raw_content=data.get("raw_content"),
            credibility=credibility,
            weight=weight,
            properties=data.get("properties", {}),
            embedding=embedding if embedding else None,
        )

        async with self._session_factory() as session:
            session.add(evidence)
            await session.commit()
            await session.refresh(evidence)

        await event_bus.emit(
            EventType.EVIDENCE_ADDED,
            {
                "id": str(evidence.id),
                "tenant_id": tenant_id,
                "preference_id": str(preference_id),
                "stance": evidence.stance,
            },
            source="evidence_store",
        )
        logger.info(
            "Created evidence %s (%s) for preference %s",
            evidence.id, evidence.stance, preference_id,
        )
        return evidence

    # ── List for Preference ───────────────────────────────────

    async def list_for_preference(
        self, tenant_id: str, preference_id: uuid.UUID
    ) -> dict[str, Any]:
        """List evidence grouped by stance with net score calculation."""
        stmt = (
            select(Evidence)
            .where(Evidence.preference_id == preference_id)
            .where(Evidence.tenant_id == tenant_id)
            .where(Evidence.status == "active")
            .order_by(Evidence.created_at.desc())
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            items = list(result.scalars().all())

        # Group by stance
        grouped: dict[str, list[Evidence]] = {
            "supports": [],
            "contradicts": [],
            "neutral": [],
        }
        for item in items:
            grouped.setdefault(item.stance, []).append(item)

        # Net score = sum(supporting weights) - sum(contradicting weights)
        support_score = sum(
            e.weight * self.freshness_score(e) for e in grouped["supports"]
        )
        contradict_score = sum(
            e.weight * self.freshness_score(e) for e in grouped["contradicts"]
        )
        net_score = support_score - contradict_score

        return {
            "supports": grouped["supports"],
            "contradicts": grouped["contradicts"],
            "neutral": grouped["neutral"],
            "net_score": net_score,
            "total_count": len(items),
        }

    # ── Get ───────────────────────────────────────────────────

    async def get(
        self, tenant_id: str, evidence_id: uuid.UUID
    ) -> Evidence | None:
        """Get a single evidence item."""
        stmt = (
            select(Evidence)
            .where(Evidence.id == evidence_id)
            .where(Evidence.tenant_id == tenant_id)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    # ── Semantic Search ───────────────────────────────────────

    async def search(
        self,
        tenant_id: str,
        query: str,
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Cross-preference semantic search over all evidence."""
        query_embedding = self._embedding.embed(query)
        if not query_embedding:
            return []

        distance = Evidence.embedding.cosine_distance(query_embedding)

        stmt = (
            select(Evidence, (1 - distance).label("similarity"))
            .where(Evidence.tenant_id == tenant_id)
            .where(Evidence.status == "active")
            .where(Evidence.embedding.isnot(None))
            .order_by(distance)
            .limit(limit)
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        return [
            {"evidence": row[0], "similarity": float(row[1])}
            for row in rows
        ]

    # ── Delete (soft) ─────────────────────────────────────────

    async def delete(
        self, tenant_id: str, evidence_id: uuid.UUID
    ) -> bool:
        """Soft-delete evidence and recalculate parent preference confidence."""
        async with self._session_factory() as session:
            evidence = await session.get(Evidence, evidence_id)
            if evidence is None or evidence.tenant_id != tenant_id:
                return False

            preference_id = evidence.preference_id
            evidence.status = "archived"
            await session.commit()

        # Recalculate parent preference confidence based on remaining evidence
        await self._recalculate_confidence(tenant_id, preference_id)
        return True

    # ── Freshness Score ───────────────────────────────────────

    @staticmethod
    def freshness_score(evidence: Evidence) -> float:
        """Age-based decay: 1.0 for brand new, decays over 365 days."""
        now = datetime.now(timezone.utc)
        age_days = max((now - evidence.created_at).total_seconds() / 86400, 0)
        # Exponential decay with half-life of ~180 days
        return math.exp(-0.00385 * age_days)

    # ── Internal: Recalculate Confidence ──────────────────────

    async def _recalculate_confidence(
        self, tenant_id: str, preference_id: uuid.UUID
    ) -> None:
        """Recalculate preference confidence based on active evidence."""
        async with self._session_factory() as session:
            pref = await session.get(Preference, preference_id)
            if pref is None:
                return

            result = await session.execute(
                select(Evidence)
                .where(Evidence.preference_id == preference_id)
                .where(Evidence.status == "active")
            )
            items = list(result.scalars().all())

            if not items:
                return  # Keep existing confidence if no evidence

            support = sum(
                e.weight * self.freshness_score(e)
                for e in items if e.stance == "supports"
            )
            contradict = sum(
                e.weight * self.freshness_score(e)
                for e in items if e.stance == "contradicts"
            )

            total = support + contradict
            if total > 0:
                # Confidence = proportion of supporting evidence
                new_confidence = min(support / total, 1.0)
            else:
                new_confidence = pref.confidence

            # Update confidence and history
            history = list(pref.confidence_history or [])
            history.append({
                "value": new_confidence,
                "at": datetime.now(timezone.utc).isoformat(),
                "reason": "evidence_recalc",
            })
            pref.confidence = new_confidence
            pref.confidence_history = history
            pref.updated_at = datetime.now(timezone.utc)
            await session.commit()
