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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update

from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import Memory
from life_graph.models.schemas import MemoryCreate
from life_graph.scoring.decay import DecayCalculator
from life_graph.scoring.importance import ImportanceTagger, _importance_tier
from life_graph.services.contradiction import ContradictionDetector
from life_graph.storage.postgres import PostgresMemoryStore

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from life_graph.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


# ── Report ────────────────────────────────────────────────────────────────────


@dataclass
class ConsolidationReport:
    """Summary produced after a full consolidation run."""

    gathered: int = 0
    clusters_found: int = 0
    # Near-identical memories found. Nothing is removed: each pair is queued
    # as a 'merge' approval (see merge_suggestions_queued). The name is kept
    # for the JobRun result / API shape.
    duplicates_removed: int = 0
    merge_suggestions_queued: int = 0
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
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


_TIER_RANK: dict[str, int] = {"low": 0, "normal": 1, "high": 2, "critical": 3}


def _higher_tier(a: str | None, b: str | None) -> str:
    """The more important of two importance tiers (unknown ranks as 'normal')."""
    a, b = a or "normal", b or "normal"
    return a if _TIER_RANK.get(a, 1) >= _TIER_RANK.get(b, 1) else b


def _is_distilled(memory: Memory) -> bool:
    """A principle produced by this pipeline's distill step.

    New principles carry ``properties.distilled``; older ones (stored before
    2026-10-22) only had ``source_type='consolidation'`` and the tag.
    """
    props = memory.properties or {}
    return bool(props.get("distilled")) or memory.source_type == "consolidation"


def _tenant() -> str:
    """Tenant this consolidation run belongs to.

    Fails closed: the pipeline is invoked once per tenant by
    ``run_all_consolidations``, so a missing context must raise rather than
    silently widen every query to all tenants.
    """
    return get_current_tenant_id()


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

        # Step 2 — Cluster. Principles this pipeline distilled are left out:
        # an approved principle sits right next to its sources in embedding
        # space, so clustering it would re-distill the same cluster (a
        # principle of a principle) on the next run.
        distilled = [m for m in recent if _is_distilled(m)]
        clusters = self._cluster([m for m in recent if not _is_distilled(m)])
        report.clusters_found = len(clusters)

        # Step 3 — Dedup. Duplicates are proposed as merges, never deleted.
        deduped_clusters: list[list[Memory]] = []
        dup_pairs: list[tuple[Memory, Memory, float]] = []
        for cluster in clusters:
            deduped = self._dedup_cluster(cluster, pairs=dup_pairs)
            report.duplicates_removed += len(cluster) - len(deduped)
            deduped_clusters.append(deduped)
        report.merge_suggestions_queued = await self._queue_merge_suggestions(dup_pairs)

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
        contradictions = await self._audit_contradictions(all_deduped + distilled)
        report.contradictions_found = len(contradictions)

        report.duration_seconds = time.monotonic() - t0
        logger.info(
            "Consolidation complete: %d gathered, %d clusters, "
            "%d duplicates (%d merge suggestions queued), %d principles, "
            "%d archived, %d contradictions (%.2fs)",
            report.gathered,
            report.clusters_found,
            report.duplicates_removed,
            report.merge_suggestions_queued,
            report.principles_created,
            report.memories_archived,
            report.contradictions_found,
            report.duration_seconds,
        )
        return report

    # ── Step 1: Gather ────────────────────────────────────────

    async def _gather_recent(self) -> list[Memory]:
        """Collect all active memories created in the last 24 hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        stmt = (
            select(Memory)
            .where(Memory.tenant_id == _tenant())
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

    def _dedup_cluster(
        self,
        cluster: list[Memory],
        pairs: list[tuple[Memory, Memory, float]] | None = None,
    ) -> list[Memory]:
        """Drop near-identical memories (cosine > 0.95) from this run's view.

        Keeps the most detailed (longest content) version when a duplicate
        pair is found, so the score / distill / audit steps see each fact
        once. This only filters the in-memory list: the duplicates stay in
        the database. ``removed_ids`` used to be computed and then thrown
        away while the report claimed "duplicates removed" (code review,
        2026-10-22). Each (kept, duplicate, similarity) pair is appended to
        *pairs* so :meth:`_queue_merge_suggestions` can propose the merge for
        approval — consolidation never deletes on its own.
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
                        if pairs is not None:
                            pairs.append((mem, other, sim))

            kept.append(mem)

        if removed_ids:
            logger.debug(
                "Deduped cluster: kept %d, %d duplicates left for merge review",
                len(kept),
                len(removed_ids),
            )
        return kept

    async def _queue_merge_suggestions(self, pairs: list[tuple[Memory, Memory, float]]) -> int:
        """Queue each duplicate pair as a ``kind='merge'`` approval.

        Same shape and key as ``services/merge_suggestions.py`` (source
        'curator', order-independent pair key), so ``ApprovalService.
        _apply_merge`` handles the approval and a pair the curator already
        queued — or the user already resolved — is not queued twice.
        Returns the number of approvals queued.
        """
        if not pairs:
            return 0

        from life_graph.models.db import Approval
        from life_graph.services.merge_suggestions import _pair_key

        tenant_id = _tenant()
        by_ref: dict[str, tuple[Memory, Memory, float]] = {}
        for kept, dup, sim in pairs:
            by_ref.setdefault(_pair_key(str(kept.id), str(dup.id)), (kept, dup, sim))

        try:
            async with self._session_factory() as session:
                existing = set(
                    (
                        await session.execute(
                            select(Approval.source_ref).where(
                                Approval.tenant_id == tenant_id,
                                Approval.source == "curator",
                                Approval.source_ref.in_(list(by_ref)),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                queued = 0
                for ref, (kept, dup, sim) in by_ref.items():
                    if ref in existing:
                        continue
                    session.add(
                        Approval(
                            tenant_id=tenant_id,
                            kind="merge",
                            source="curator",
                            source_ref=ref,
                            title="Merge 2 near-duplicate memories",
                            detail=(
                                f"consolidation · {round(sim * 100)}% similar · "
                                f"“{(kept.content or '')[:60]}” ~ “{(dup.content or '')[:60]}”"
                            ),
                            payload={
                                "memory_id_a": str(kept.id),
                                "memory_id_b": str(dup.id),
                                "similarity": round(float(sim), 4),
                            },
                        )
                    )
                    queued += 1
                if queued:
                    await session.commit()
        except Exception:
            logger.exception("Failed to queue %d consolidation merge suggestions", len(by_ref))
            return 0
        if queued:
            logger.info("Consolidation: queued %d merge suggestions for approval", queued)
        return queued

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

    async def _persist_scores(self, scored: list[tuple[Memory, float, str]]) -> None:
        """Raise stored importance where the rescore is higher; never lower it.

        The rescore is the context-free keyword ``ImportanceTagger`` score. It
        used to overwrite ``importance`` outright, which destroyed a value the
        user set by hand, the ingest-time score (computed *with* context) and
        the "higher importance wins" result of an ingest dedup merge (code
        review, 2026-10-22).

        Two fixes were possible: rescore only memories whose importance was
        never set explicitly, or only ever raise. Nothing on the row records
        whether importance was set explicitly (0.5 is both the default and a
        legitimate choice), so the first would rest on a guess. Raising only
        is safe without that knowledge: every existing value is kept unless
        the keyword rules find more importance in the text. The tier follows
        the same rule. ``GREATEST`` in SQL keeps a concurrent edit that raised
        it in the meantime. Rows where nothing would rise are not touched.
        """
        if not scored:
            return
        updates = 0
        async with self._session_factory() as session:
            for mem, score, tier in scored:
                old = mem.importance if mem.importance is not None else 0.0
                # Tier of the resulting importance, but never below the stored
                # tier (rows from before 2026-10-22 were all stored 'normal').
                new_tier = _higher_tier(
                    mem.importance_tier, _higher_tier(tier, _importance_tier(max(old, score)))
                )
                if score <= old and new_tier == (mem.importance_tier or "normal"):
                    continue
                await session.execute(
                    update(Memory)
                    .where(Memory.id == mem.id)
                    .where(Memory.tenant_id == _tenant())
                    .values(
                        importance=func.greatest(Memory.importance, score),
                        importance_tier=new_tier,
                    )
                )
                updates += 1
            if updates:
                await session.commit()
        logger.debug("Raised importance on %d of %d scored memories", updates, len(scored))

    # ── Step 5: Distill ───────────────────────────────────────

    async def _distill(self, clusters: list[list[Memory]]) -> list[dict[str, Any]]:
        """Summarise large clusters into principle memories via LLM.

        Only clusters with >= 3 memories are distilled. Uses litellm
        with the cheap model to minimise cost. Returns a list of dicts
        describing each newly created principle.

        Memories already named as a source of an existing principle are
        dropped from their cluster first, so a second run over the same
        24-hour window (the manual /admin/consolidate, or tomorrow night for
        memories near the cutoff) does not distill the same cluster again.
        """
        candidates = [c for c in clusters if len(c) >= self._DISTILL_MIN_CLUSTER_SIZE]
        if not candidates:
            return []

        already = await self._already_distilled_sources()
        large_clusters = [
            kept
            for c in candidates
            if len(kept := [m for m in c if str(m.id) not in already])
            >= self._DISTILL_MIN_CLUSTER_SIZE
        ]
        if not large_clusters:
            return []

        principles: list[dict[str, Any]] = []

        for cluster in large_clusters:
            contents = "\n".join(f"- {m.content}" for m in cluster)
            prompt = (
                "You are a personal knowledge distiller. "
                "Distill these related memories into ONE concise principle "
                "(max 2 sentences). Capture the core insight:\n\n"
                f"{contents}\n\n"
                "Principle:"
            )

            try:
                from life_graph.api.dependencies import get_resilient_llm
                from life_graph.config import settings

                response = await get_resilient_llm().acompletion(
                    messages=[{"role": "user", "content": prompt}],
                    model=settings.llm_model_cheap,
                    max_tokens=150,
                    temperature=0.3,
                )
                principle_text = response.choices[0].message.content.strip()
                cost = response._hidden_params.get("response_cost", 0.0) or 0.0

                if not principle_text:
                    logger.warning("Distill returned no text for a cluster of %d", len(cluster))
                    continue

                # Embed through the async path. The sync embed() returns []
                # inside the event loop in local-LLM mode, so principles were
                # stored with no vector and never surfaced in semantic search
                # (code review, 2026-10-22).
                emb = await self._embedding.embed_async(principle_text)

                # Through the normal store path, as a *pending* memory: an
                # LLM-written generalisation is exactly what the approval gate
                # is for. It was inserted 'active' directly, with no
                # content_hash (exact dedup could not see it), the default
                # trust tier and no embedding (code review, 2026-10-22).
                new_memory = await self._store.store(
                    MemoryCreate(
                        content=principle_text,
                        reasoning=f"Distilled from {len(cluster)} related memories",
                        tags=["principle", "distilled"],
                        properties={
                            "distilled": True,
                            "source_memories": [str(m.id) for m in cluster],
                            "distilled_at": datetime.now(UTC).isoformat(),
                        },
                        importance=0.8,
                        source_type="consolidation",
                    ),
                    embedding=emb or None,
                    trust_tier="verified",
                    status="pending",
                    extraction_tier="llm",
                    importance_tier="high",
                )

                principles.append(
                    {
                        "id": str(new_memory.id),
                        "content": principle_text,
                        "source_count": len(cluster),
                        "cost_usd": cost,
                    }
                )
                logger.info(
                    "Distilled %d memories → principle: %s",
                    len(cluster),
                    principle_text[:80],
                )

            except Exception:
                logger.exception("Failed to distill cluster of %d memories", len(cluster))

        return principles

    async def _already_distilled_sources(self) -> set[str]:
        """Ids of memories that a recent principle was distilled from.

        Any status counts: a rejected principle is the user saying "not this",
        and distilling the same cluster again would only re-ask. Bounded to
        principles from the last 48 h — sources are gathered from the last
        24 h, so an older principle cannot name one.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=48)
        stmt = (
            select(Memory.properties)
            .where(Memory.tenant_id == _tenant())
            .where(Memory.created_at > cutoff)
            .where(Memory.source_type == "consolidation")
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        ids: set[str] = set()
        for props in rows:
            if isinstance(props, dict):
                ids.update(str(i) for i in props.get("source_memories") or [])
        return ids

    # ── Step 6: Decay ─────────────────────────────────────────

    async def _update_decay_scores(self) -> int:
        """Recalculate decay scores for all active memories.

        Reports how many have fallen below the decay threshold. Nothing is
        archived here: ``workers/decay.py`` queues those as approvals, and
        only an approved proposal changes a memory's status.

        Returns the number of memories below the threshold.
        """
        stmt = select(Memory).where(
            Memory.tenant_id == _tenant(),
            Memory.status == "active",
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            active = list(result.scalars().all())

        if not active:
            return 0

        # Build dicts for batch_calculate
        mem_dicts: list[dict[str, Any]] = []
        for m in active:
            mem_dicts.append(
                {
                    "id": str(m.id),
                    "importance": m.importance,
                    "access_count": m.access_count,
                    "last_accessed": m.last_accessed or m.created_at,
                    "decay_rate": m.decay_rate,
                    "importance_tier": m.importance_tier,
                }
            )

        decay_results = self._decay.batch_calculate(mem_dicts)

        # Decay demotes; it does not remove.
        #
        # This used to flip status to 'archived' in place. Every recall query
        # filters on status = 'active', so a decayed memory silently vanished
        # from recall with no record of the decision and no way back short of
        # a manual unarchive(). Ranking already handles the demotion on its
        # own — recency and frequency are computed from the same inputs decay
        # uses, so an untouched memory sinks in the order without being
        # hidden.
        #
        # Removal is proposed, not performed. workers/decay.py queues the
        # approvals; this step only reports what qualified, so the nightly
        # consolidation and the decay sweep cannot both queue the same thing.
        decayed = [mem_id for mem_id, _score, should_archive in decay_results if should_archive]

        if decayed:
            logger.info(
                "Consolidation: %d memories are below the decay threshold "
                "(left active; workers.decay proposes removal for approval)",
                len(decayed),
            )

        return len(decayed)

    # ── Step 7: Audit ─────────────────────────────────────────

    async def _audit_contradictions(self, memories: list[Memory]) -> list[dict[str, Any]]:
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
                    new_properties=mem.properties,
                )
                for c in contradictions:
                    found.append(
                        {
                            "memory_id": str(mem.id),
                            "existing_id": c.existing_memory_id,
                            "conflict_type": c.conflict_type,
                            "resolution": c.resolution,
                            "reason": c.reason,
                        }
                    )
            except Exception:
                logger.exception("Contradiction check failed for memory %s", mem.id)

        if found:
            logger.warning("Found %d contradictions during consolidation audit", len(found))
        return found
