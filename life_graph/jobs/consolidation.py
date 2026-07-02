"""Nightly consolidation pipeline — brain-inspired sleep cycle analog (T-054 to T-057).

Runs seven sequential steps:
  1. Gather — collect memories created in the last 24 h
  2. Cluster — group by embedding similarity (cosine > 0.75)
  3. Dedup — remove near-identical entries (cosine > 0.95)
  4. Score — update importance via rule-based ImportanceTagger
  5. Distill — summarise large clusters into principles (ONE LLM call)
  6. Decay — update decay scores, archive below threshold
  7. Audit — detect contradictions within recent memories

Designed for cost efficiency: only step 5 uses an LLM (cheap model),
everything else is rule-based / local.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.models.db import Memory
from life_graph.scoring.decay import DecayCalculator
from life_graph.scoring.importance import ImportanceTagger
from life_graph.services.contradiction import ContradictionDetector
from life_graph.services.embeddings import EmbeddingService
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)


# ── Report ────────────────────────────────────────────────────────────────────


@dataclass
class ConsolidationReport:
    """Summary produced after a full consolidation run."""

    gathered: int = 0
    clusters_found: int = 0
    duplicates_removed: int = 0
    principles_created: int = 0
    memories_archived: int = 0
    contradictions_found: int = 0
    llm_cost_usd: float = 0.0
    duration_seconds: float = 0.0


# ── Cosine helper ─────────────────────────────────────────────────────────────


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns 0.0 when either vector is empty or has zero magnitude.
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Pipeline ──────────────────────────────────────────────────────────────────


class ConsolidationPipeline:
    """Nightly consolidation pipeline for the Life Graph memory system.

    Implements the brain-inspired sleep-cycle analog: memories created
    during the day are clustered, de-duplicated, importance-scored,
    distilled into principles, decay-updated, and contradiction-checked.

    Usage::

        pipeline = ConsolidationPipeline(session_factory, embedding_service)
        report = await pipeline.run()
    """

    _CLUSTER_THRESHOLD: float = 0.75
    _DEDUP_THRESHOLD: float = 0.95
    _DISTILL_MIN_CLUSTER_SIZE: int = 3

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_service: EmbeddingService,
    ) -> None:
        self._session_factory = session_factory
        self._embedding = embedding_service
        self._importance = ImportanceTagger()
        self._decay = DecayCalculator()
        self._store = PostgresMemoryStore()

    # ── Public entry point ────────────────────────────────────

    async def run(self) -> ConsolidationReport:
        """Execute the full consolidation pipeline.

        Returns a :class:`ConsolidationReport` summarising the run.
        """
        t0 = time.monotonic()
        report = ConsolidationReport()

        # Step 1 — Gather
        recent = await self._gather_recent()
        report.gathered = len(recent)
        if not recent:
            report.duration_seconds = time.monotonic() - t0
            logger.info("Consolidation: no recent memories — skipping")
            return report

        # Step 2 — Cluster
        clusters = self._cluster(recent)
        report.clusters_found = len(clusters)

        # Step 3 — Dedup
        deduped_clusters: list[list[Memory]] = []
        for cluster in clusters:
            deduped = self._dedup_cluster(cluster)
            report.duplicates_removed += len(cluster) - len(deduped)
            deduped_clusters.append(deduped)

        # Flatten for scoring
        all_deduped = [m for c in deduped_clusters for m in c]

        # Step 4 — Score
        scored = self._score(all_deduped)
        await self._persist_scores(scored)

        # Step 5 — Distill
        principles = await self._distill(deduped_clusters)
        report.principles_created = len(principles)
        for p in principles:
            report.llm_cost_usd += p.get("cost_usd", 0.0)

        # Step 6 — Decay
        archived = await self._update_decay_scores()
        report.memories_archived = archived

        # Step 7 — Audit
        contradictions = await self._audit_contradictions(all_deduped)
        report.contradictions_found = len(contradictions)

        report.duration_seconds = time.monotonic() - t0
        logger.info(
            "Consolidation complete: %d gathered, %d clusters, "
            "%d deduped, %d principles, %d archived, %d contradictions (%.2fs)",
            report.gathered,
            report.clusters_found,
            report.duplicates_removed,
            report.principles_created,
            report.memories_archived,
            report.contradictions_found,
            report.duration_seconds,
        )
        return report

    # ── Step 1: Gather ────────────────────────────────────────

    async def _gather_recent(self) -> list[Memory]:
        """Collect all active memories created in the last 24 hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = (
            select(Memory)
            .where(Memory.created_at > cutoff)
            .where(Memory.status == "active")
            .order_by(Memory.created_at.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            memories = list(result.scalars().all())
        logger.debug("Gathered %d recent memories", len(memories))
        return memories

    # ── Step 2: Cluster ───────────────────────────────────────

    def _cluster(self, memories: list[Memory]) -> list[list[Memory]]:
        """Group memories by embedding cosine similarity > threshold.

        Uses simple agglomerative clustering: each memory is assigned
        to the first existing cluster where it exceeds the threshold
        with any member. Otherwise a new cluster is created.
        """
        clusters: list[list[Memory]] = []

        for memory in memories:
            if memory.embedding is None:
                # No embedding — put in its own cluster
                clusters.append([memory])
                continue

            placed = False
            for cluster in clusters:
                for member in cluster:
                    if member.embedding is None:
                        continue
                    sim = _cosine_similarity(memory.embedding, member.embedding)
                    if sim > self._CLUSTER_THRESHOLD:
                        cluster.append(memory)
                        placed = True
                        break
                if placed:
                    break

            if not placed:
                clusters.append([memory])

        logger.debug("Formed %d clusters from %d memories", len(clusters), len(memories))
        return clusters

    # ── Step 3: Dedup ─────────────────────────────────────────

    def _dedup_cluster(self, cluster: list[Memory]) -> list[Memory]:
        """Remove near-identical memories (cosine > 0.95) from a cluster.

        Keeps the most detailed (longest content) version when a
        duplicate pair is found.
        """
        if len(cluster) <= 1:
            return cluster

        # Sort longest-first so we keep the most detailed
        sorted_mems = sorted(cluster, key=lambda m: len(m.content), reverse=True)
        kept: list[Memory] = []
        removed_ids: set[uuid.UUID] = set()

        for mem in sorted_mems:
            if mem.id in removed_ids:
                continue

            # Mark shorter duplicates for removal
            for other in sorted_mems:
                if other.id == mem.id or other.id in removed_ids:
                    continue
                if mem.embedding and other.embedding:
                    sim = _cosine_similarity(mem.embedding, other.embedding)
                    if sim > self._DEDUP_THRESHOLD:
                        removed_ids.add(other.id)

            kept.append(mem)

        if removed_ids:
            logger.debug(
                "Deduped cluster: kept %d, removed %d", len(kept), len(removed_ids)
            )
        return kept

    # ── Step 4: Score ─────────────────────────────────────────

    def _score(self, memories: list[Memory]) -> list[tuple[Memory, float, str]]:
        """Calculate importance for each memory using ImportanceTagger.

        Returns list of (memory, score, tier) tuples.
        """
        results: list[tuple[Memory, float, str]] = []
        for mem in memories:
            score, tier = self._importance.score(mem.content)
            results.append((mem, score, tier))
        return results

    async def _persist_scores(
        self, scored: list[tuple[Memory, float, str]]
    ) -> None:
        """Write updated importance scores back to the database."""
        if not scored:
            return
        async with self._session_factory() as session:
            for mem, score, tier in scored:
                await session.execute(
                    update(Memory)
                    .where(Memory.id == mem.id)
                    .values(importance=score, importance_tier=tier)
                )
            await session.commit()
        logger.debug("Persisted importance scores for %d memories", len(scored))

    # ── Step 5: Distill ───────────────────────────────────────

    async def _distill(
        self, clusters: list[list[Memory]]
    ) -> list[dict[str, Any]]:
        """Summarise large clusters into principle memories via LLM.

        Only clusters with >= 3 memories are distilled. Uses litellm
        with the cheap model to minimise cost. Returns a list of dicts
        describing each newly created principle.
        """
        large_clusters = [c for c in clusters if len(c) >= self._DISTILL_MIN_CLUSTER_SIZE]
        if not large_clusters:
            return []

        principles: list[dict[str, Any]] = []

        for cluster in large_clusters:
            contents = "\n".join(
                f"- {m.content}" for m in cluster
            )
            prompt = (
                "You are a personal knowledge distiller. "
                "Distill these related memories into ONE concise principle "
                "(max 2 sentences). Capture the core insight:\n\n"
                f"{contents}\n\n"
                "Principle:"
            )

            try:
                import litellm

                from life_graph.config import settings

                response = await litellm.acompletion(
                    model=settings.llm_model_cheap,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150,
                    temperature=0.3,
                )
                principle_text = response.choices[0].message.content.strip()
                cost = response._hidden_params.get("response_cost", 0.0) or 0.0

                # Store as new memory
                new_memory = Memory(
                    content=principle_text,
                    reasoning=f"Distilled from {len(cluster)} related memories",
                    tags=["principle", "distilled"],
                    properties={
                        "source_memories": [str(m.id) for m in cluster],
                        "distilled_at": datetime.now(timezone.utc).isoformat(),
                    },
                    importance=0.8,
                    importance_tier="high",
                    source_type="consolidation",
                    confidence=0.7,
                )

                # Generate embedding for the new principle
                emb = self._embedding.embed(principle_text)
                if emb:
                    new_memory.embedding = emb

                async with self._session_factory() as session:
                    session.add(new_memory)
                    await session.commit()
                    await session.refresh(new_memory)

                principles.append({
                    "id": str(new_memory.id),
                    "content": principle_text,
                    "source_count": len(cluster),
                    "cost_usd": cost,
                })
                logger.info(
                    "Distilled %d memories → principle: %s",
                    len(cluster),
                    principle_text[:80],
                )

            except Exception:
                logger.exception(
                    "Failed to distill cluster of %d memories", len(cluster)
                )

        return principles

    # ── Step 6: Decay ─────────────────────────────────────────

    async def _update_decay_scores(self) -> int:
        """Recalculate decay scores for all active memories.

        Archives memories that fall below the threshold, except
        those with importance_tier = 'critical'.

        Returns the number of memories archived.
        """
        stmt = select(Memory).where(Memory.status == "active")
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            active = list(result.scalars().all())

        if not active:
            return 0

        # Build dicts for batch_calculate
        mem_dicts: list[dict[str, Any]] = []
        for m in active:
            mem_dicts.append({
                "id": str(m.id),
                "importance": m.importance,
                "access_count": m.access_count,
                "last_accessed": m.last_accessed or m.created_at,
                "decay_rate": m.decay_rate,
                "importance_tier": m.importance_tier,
            })

        decay_results = self._decay.batch_calculate(mem_dicts)

        # Archive those that should be
        to_archive: list[str] = []
        for mem_id, _score, should_archive in decay_results:
            if should_archive:
                to_archive.append(mem_id)

        if to_archive:
            async with self._session_factory() as session:
                await session.execute(
                    update(Memory)
                    .where(Memory.id.in_([uuid.UUID(mid) for mid in to_archive]))
                    .values(status="archived")
                )
                await session.commit()
            logger.info("Archived %d decayed memories", len(to_archive))

        return len(to_archive)

    # ── Step 7: Audit ─────────────────────────────────────────

    async def _audit_contradictions(
        self, memories: list[Memory]
    ) -> list[dict[str, Any]]:
        """Check recent memories for contradictions with existing knowledge.

        Returns a list of dicts describing found contradictions (for
        logging / reporting only — no auto-resolution).
        """
        detector = ContradictionDetector(self._store)
        found: list[dict[str, Any]] = []

        for mem in memories:
            if not mem.embedding:
                continue
            try:
                contradictions = await detector.check(
                    new_content=mem.content,
                    new_embedding=mem.embedding,
                )
                for c in contradictions:
                    found.append({
                        "memory_id": str(mem.id),
                        "existing_id": c.existing_memory_id,
                        "conflict_type": c.conflict_type,
                        "resolution": c.resolution,
                        "reason": c.reason,
                    })
            except Exception:
                logger.exception(
                    "Contradiction check failed for memory %s", mem.id
                )

        if found:
            logger.warning(
                "Found %d contradictions during consolidation audit", len(found)
            )
        return found
