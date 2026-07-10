"""Post-session micro-consolidation — event-triggered lightweight cleanup.

Runs automatically when a session ends, performing fast operations
that don't require LLM calls:

1. Gather — collect this session's new memories (small set)
2. Dedup — remove near-duplicates against existing memories (cosine >0.95)
3. Re-score — update importance scores via ImportanceTagger
4. Graph — extract entities from new memories → upsert vertices + edges
5. Report — return a summary of what happened

Expensive operations (LLM distillation, full decay sweep) are left
to the nightly :class:`ConsolidationPipeline`.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.models.db import Memory, MemorySession
from life_graph.scoring.importance import ImportanceTagger
from life_graph.services.embeddings import EmbeddingService
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)


# ── Report ────────────────────────────────────────────────────────────────────


@dataclass
class MicroConsolidationReport:
    """Summary produced after a micro-consolidation run."""

    session_id: str = ""
    memories_processed: int = 0
    duplicates_removed: int = 0
    importance_updated: int = 0
    entities_discovered: int = 0
    edges_created: int = 0
    duration_seconds: float = 0.0


# ── Cosine helper ─────────────────────────────────────────────────────────────


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Pipeline ──────────────────────────────────────────────────────────────────


class MicroConsolidator:
    """Lightweight consolidation triggered after a session ends.

    Performs fast, rule-based operations on the session's memories
    without any LLM calls. Designed to complete in under 2 seconds
    for typical sessions (5-20 memories).

    Usage::

        consolidator = MicroConsolidator(session_factory, embedding_service)
        report = await consolidator.run(session_id)
    """

    _DEDUP_THRESHOLD: float = 0.95

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_service: EmbeddingService,
    ) -> None:
        self._session_factory = session_factory
        self._embedding = embedding_service
        self._importance = ImportanceTagger()
        self._store = PostgresMemoryStore()

    # ── Public entry point ────────────────────────────────────

    async def run(self, session_id: uuid.UUID) -> MicroConsolidationReport:
        """Run micro-consolidation for a specific session.

        Returns a :class:`MicroConsolidationReport` summarising the run.
        """
        t0 = time.monotonic()
        report = MicroConsolidationReport(session_id=str(session_id))

        # Step 1 — Gather this session's memories
        session_memories = await self._gather_session_memories(session_id)
        report.memories_processed = len(session_memories)
        if not session_memories:
            report.duration_seconds = time.monotonic() - t0
            logger.info(
                "Micro-consolidation %s: no memories — skipping", session_id
            )
            return report

        # Step 2 — Dedup against existing memories
        dedup_count = await self._dedup_against_existing(session_memories)
        report.duplicates_removed = dedup_count

        # Refresh list if we removed any
        if dedup_count > 0:
            session_memories = await self._gather_session_memories(session_id)

        # Step 3 — Re-score importance
        if session_memories:
            scored = await self._rescore_importance(session_memories)
            report.importance_updated = scored

        # Step 4 — Graph entity extraction
        if session_memories:
            entities, edges = await self._update_graph(session_memories)
            report.entities_discovered = entities
            report.edges_created = edges

        report.duration_seconds = time.monotonic() - t0
        logger.info(
            "Micro-consolidation %s: %d processed, %d deduped, "
            "%d scored, %d entities, %d edges (%.2fs)",
            session_id,
            report.memories_processed,
            report.duplicates_removed,
            report.importance_updated,
            report.entities_discovered,
            report.edges_created,
            report.duration_seconds,
        )
        return report

    # ── Step 1: Gather ────────────────────────────────────────

    async def _gather_session_memories(
        self, session_id: uuid.UUID,
    ) -> list[Memory]:
        """Collect all active memories linked to this session."""
        stmt = (
            select(Memory)
            .join(MemorySession, Memory.id == MemorySession.memory_id)
            .where(
                MemorySession.session_id == session_id,
                Memory.status == "active",
            )
            .order_by(Memory.created_at.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            memories = list(result.scalars().all())
        logger.debug(
            "Gathered %d memories for session %s", len(memories), session_id
        )
        return memories

    # ── Step 2: Dedup ─────────────────────────────────────────

    async def _dedup_against_existing(
        self, session_memories: list[Memory],
    ) -> int:
        """Check session memories for near-duplicates against the full store.

        Marks duplicates as 'superseded' and links them to the
        existing memory they duplicate.

        Returns the count of duplicates removed.
        """
        removed = 0

        for mem in session_memories:
            if mem.embedding is None or mem.status != "active":
                continue

            # Search for similar memories (excluding self)
            try:
                similar = await self._store.search_by_embedding(
                    embedding=mem.embedding,
                    limit=5,
                    threshold=self._DEDUP_THRESHOLD,
                )
            except Exception:
                logger.debug("Dedup search failed for %s", mem.id)
                continue

            for existing, similarity in similar:
                if existing.id == mem.id:
                    continue
                if existing.status != "active":
                    continue

                # This memory is a near-duplicate of an existing one
                # Keep the older one (it has more history)
                if existing.created_at <= mem.created_at:
                    # Mark the new one as superseded
                    async with self._session_factory() as session:
                        await session.execute(
                            update(Memory)
                            .where(Memory.id == mem.id)
                            .values(
                                status="superseded",
                                superseded_by=existing.id,
                            )
                        )
                        await session.commit()
                    removed += 1
                    logger.debug(
                        "Dedup: %s superseded by %s (sim=%.3f)",
                        mem.id, existing.id, similarity,
                    )
                    break  # Only supersede once

        return removed

    # ── Step 3: Re-score ──────────────────────────────────────

    async def _rescore_importance(
        self, memories: list[Memory],
    ) -> int:
        """Recalculate importance scores for session memories.

        Returns the count of memories whose scores were updated.
        """
        updated = 0
        async with self._session_factory() as session:
            for mem in memories:
                if mem.status != "active":
                    continue
                new_score, new_tier = self._importance.score(mem.content)
                if abs(new_score - mem.importance) > 0.01:
                    await session.execute(
                        update(Memory)
                        .where(Memory.id == mem.id)
                        .values(
                            importance=new_score,
                            importance_tier=new_tier,
                        )
                    )
                    updated += 1
            if updated:
                await session.commit()
        return updated

    # ── Step 4: Graph ─────────────────────────────────────────

    async def _update_graph(
        self, memories: list[Memory],
    ) -> tuple[int, int]:
        """Extract entities from memories and create graph vertices/edges.

        Returns (entities_created, edges_created).
        """
        try:
            from life_graph.jobs.graph_migration import infer_label
            from life_graph.storage.graph import GraphStore
        except ImportError:
            logger.debug("Graph store not available — skipping graph step")
            return 0, 0

        graph = GraphStore()
        entities_created = 0
        edges_created = 0

        for mem in memories:
            if mem.status != "active":
                continue

            # Extract entity names from tags + properties
            entity_names: set[str] = set()

            if mem.tags:
                for tag in mem.tags:
                    tag_clean = tag.strip()
                    if tag_clean and len(tag_clean) >= 2:
                        entity_names.add(tag_clean)

            if mem.properties and isinstance(mem.properties, dict):
                entities_list = mem.properties.get("entities", [])
                if isinstance(entities_list, list):
                    for entity in entities_list:
                        if isinstance(entity, str) and len(entity.strip()) >= 2:
                            entity_names.add(entity.strip())
                        elif isinstance(entity, dict):
                            name = entity.get("name", "").strip()
                            if name and len(name) >= 2:
                                entity_names.add(name)

            if not entity_names:
                continue

            # Upsert vertices
            canonical_names: list[str] = []
            for name in entity_names:
                label = infer_label(name, context=mem.content)
                try:
                    await graph.upsert_vertex(
                        label=label,
                        name=name,
                        properties={
                            "memory_ids": [str(mem.id)],
                            "last_seen": mem.created_at.isoformat()
                            if mem.created_at else None,
                        },
                    )
                    canonical_names.append(name)
                    entities_created += 1
                except Exception:
                    logger.debug("Failed to upsert vertex: %s", name)

            # Create edges between co-occurring entities
            if len(canonical_names) >= 2:
                for i, src in enumerate(canonical_names):
                    for dst in canonical_names[i + 1:]:
                        try:
                            await graph.create_edge(
                                from_label="Entity",
                                from_name=src,
                                to_label="Entity",
                                to_name=dst,
                                edge_label="related_to",
                                properties={
                                    "source_memory": str(mem.id),
                                },
                            )
                            edges_created += 1
                        except Exception:
                            pass  # Edge may already exist

        try:
            await graph.close()
        except Exception:
            pass

        return entities_created, edges_created
