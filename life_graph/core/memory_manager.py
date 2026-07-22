"""Memory manager orchestrating ingestion with contradiction handling (T-027).

Full ingestion pipeline:
  1. Extract facts from text (via ExtractionPipeline)
  2. Score importance for each fact
  3. Generate embeddings (placeholder for sentence-transformers)
  4. Check for contradictions
  5. Handle contradictions: auto-supersede or flag for user
  6. Store memories
  7. Return stored memories

Also manages supersession chains for belief evolution tracking.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

from life_graph.extraction.pipeline import ExtractionPipeline
from life_graph.extraction.rules import ExtractedFact
from life_graph.models.db import Memory
from life_graph.models.schemas import MemoryCreate, MemoryUpdate
from life_graph.scoring.importance import ImportanceTagger
from life_graph.services.contradiction import Contradiction, ContradictionDetector
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)


class MemoryManager:
    """Orchestrates memory ingestion, contradiction resolution, and supersession.

    This is the primary high-level interface for storing new information.
    It coordinates extraction, scoring, embedding, contradiction detection,
    and persistence into a single ``ingest()`` call.

    Usage::

        manager = MemoryManager(store, extractor, tagger, detector)
        memories = await manager.ingest(
            "I prefer PostgreSQL over MongoDB for everything",
            context={"project": "life_graph"},
        )
    """

    def __init__(
        self,
        store: PostgresMemoryStore,
        extractor: ExtractionPipeline,
        tagger: ImportanceTagger,
        contradiction_detector: ContradictionDetector,
    ) -> None:
        self._store = store
        self._extractor = extractor
        self._tagger = tagger
        self._contradiction_detector = contradiction_detector

    @property
    def store(self) -> PostgresMemoryStore:
        """The underlying memory store — for callers that need a raw-persist
        fallback (e.g. when ``ingest()`` extracts no facts and the caller
        wants to save the original text as-is rather than lose it)."""
        return self._store

    async def ingest(
        self,
        text: str,
        context: dict[str, Any] | None = None,
        source: str | None = None,
        skip_dedup: bool = False,
        trust_tier: str | None = None,
    ) -> list[Memory]:
        """Full ingestion pipeline for new text.

        Steps:
            1. Extract facts from text
            2. Score importance for each fact
            3. Generate embeddings (placeholder)
            4. Check for contradictions against existing memories
            5. Auto-resolve contradictions where possible
            6. Store new memories
            7. Return list of stored Memory objects

        Args:
            text: Raw input text to process.
            context: Optional context dict (project, module, etc.).
            source: Source identifier (e.g. 'chat', 'git', 'manual').

        Returns:
            List of stored Memory ORM objects.
        """
        if not text.strip():
            return []

        # Step 1: Extract facts
        extraction_result = await self._extractor.extract(text)
        facts = extraction_result.facts

        if not facts:
            logger.debug("No facts extracted from text: %s", text[:80])
            return []

        logger.info("Extracted %d facts from input text", len(facts))

        # Steps 2-6: Process each fact
        stored_memories: list[Memory] = []
        for fact in facts:
            memory = await self._process_fact(fact, context, source, skip_dedup, trust_tier)
            if memory:
                stored_memories.append(memory)

        logger.info("Ingested %d memories from %d facts", len(stored_memories), len(facts))
        return stored_memories

    async def supersede(
        self,
        old_memory_id: str,
        new_memory_id: str,
        reason: str,
    ) -> None:
        """Mark an old memory as superseded by a new one.

        Creates a bidirectional supersession chain:
            - Old memory: status='superseded', superseded_by=new_id
            - New memory: supersedes=old_id

        Both memories are preserved in history for audit trail.

        Args:
            old_memory_id: UUID string of the memory being superseded.
            new_memory_id: UUID string of the replacing memory.
            reason: Human-readable reason for the supersession.
        """
        old_uuid = uuid.UUID(old_memory_id)
        new_uuid = uuid.UUID(new_memory_id)

        # Mark old as superseded
        await self._store.update(
            old_uuid,
            MemoryUpdate(
                status="superseded",
            ),
        )

        # Update supersession chain via direct attribute patching
        # (MemoryUpdate doesn't expose superseded_by, so we update directly)
        from sqlalchemy import update

        from life_graph.storage.database import async_session

        async with async_session() as session:
            # Set superseded_by on old memory
            await session.execute(
                update(Memory).where(Memory.id == old_uuid).values(superseded_by=new_uuid)
            )
            # Set supersedes on new memory
            await session.execute(
                update(Memory).where(Memory.id == new_uuid).values(supersedes=old_uuid)
            )
            await session.commit()

        logger.info(
            "Superseded memory %s → %s (reason: %s)",
            old_memory_id[:8],
            new_memory_id[:8],
            reason,
        )

    # ── Internal Helpers ──────────────────────────────────────

    async def _process_fact(
        self,
        fact: ExtractedFact,
        context: dict[str, Any] | None,
        source: str | None,
        skip_dedup: bool = False,
        trust_tier: str | None = None,
    ) -> Memory | None:
        """Process a single extracted fact through scoring, embedding, and storage.

        Returns:
            Stored Memory object, or None if the fact was a duplicate.
        """
        # Step 2: Score importance
        importance, tier = self._tagger.score(fact.content, context)

        # Step 3: Generate embedding (placeholder)
        embedding = await self._generate_embedding(fact.content)

        # Step 3b: Deduplication check
        content_hash = hashlib.sha256(
            fact.content.strip().lower().encode(),
        ).hexdigest()

        from life_graph.config import settings

        if settings.dedup_enabled and not skip_dedup:
            # Exact match (cheap, always runs first)
            existing = await self._store.find_exact_duplicate(content_hash)
            if existing:
                logger.info("Dedup: exact match found for memory %s", existing.id)
                await self._store.touch(existing.id)
                return existing

            # Near-match (expensive, only if no exact match and embedding available)
            if embedding:
                similar = await self._store.find_similar(
                    embedding,
                    threshold=settings.dedup_threshold,
                )
                if similar:
                    existing_memory, score = similar[0]  # highest similarity
                    logger.info(
                        "Dedup: near-match (%.2f) found, merging with %s",
                        score,
                        existing_memory.id,
                    )

                    # Merge: higher importance wins, union tags, merge properties
                    merged_importance = max(
                        existing_memory.importance,
                        importance or 0.5,
                    )
                    merged_tags = list(
                        set(
                            (existing_memory.tags or []) + _infer_tags(fact, tier),
                        )
                    )

                    new_props: dict[str, Any] = {}
                    if context:
                        new_props.update(context)
                    new_props["fact_type"] = fact.fact_type
                    new_props["extraction_confidence"] = fact.confidence
                    if fact.entities:
                        new_props["entities"] = fact.entities
                    merged_props = {
                        **(existing_memory.properties or {}),
                        **new_props,
                    }

                    update = MemoryUpdate(
                        importance=merged_importance,
                        tags=merged_tags,
                        properties=merged_props,
                    )
                    updated = await self._store.update(existing_memory.id, update)
                    await self._store.touch(existing_memory.id)
                    return updated

        # Step 4: Check for contradictions
        contradictions: list[Contradiction] = []
        if embedding:
            contradictions = await self._contradiction_detector.check(
                fact.content,
                embedding,
            )

        # Step 5: Handle contradictions
        auto_supersede_targets = self._resolve_contradictions(contradictions)

        # Step 6: Store the new memory
        properties: dict[str, Any] = {}
        if context:
            properties.update(context)
        properties["fact_type"] = fact.fact_type
        properties["extraction_confidence"] = fact.confidence
        if fact.entities:
            properties["entities"] = fact.entities

        # Add contradiction info if any
        if contradictions:
            properties["contradictions"] = [
                {
                    "existing_id": c.existing_memory_id,
                    "conflict_type": c.conflict_type,
                    "resolution": c.resolution,
                    "reason": c.reason,
                }
                for c in contradictions
            ]

        memory_create = MemoryCreate(
            content=fact.content,
            reasoning=fact.source_text or None,
            tags=_infer_tags(fact, tier),
            properties=properties,
            importance=importance,
            source_type=source or "inferred",
        )

        stored = await self._store.store(
            memory_create,
            embedding=embedding,
            trust_tier=trust_tier,
        )

        # Step 5b: Execute auto-supersessions, queuing an approval for each so
        # the user can confirm or undo it (additive — the supersede still happens).
        for old_id, reason in auto_supersede_targets:
            await self.supersede(old_id, str(stored.id), reason)
            await self._queue_contradiction_approval(old_id, str(stored.id), reason)

        return stored

    async def _queue_contradiction_approval(
        self,
        old_id: str,
        new_id: str,
        reason: str,
    ) -> None:
        """Record an auto-supersede as a contradiction approval (confirm/undo).

        Additive and non-blocking: any failure here is logged, never raised,
        so contradiction handling can't break ingestion.
        """
        from sqlalchemy import select

        from life_graph.core.tenant import get_current_tenant_id
        from life_graph.models.db import Approval
        from life_graph.storage.database import async_session

        try:
            tenant_id = get_current_tenant_id()
            ref = f"{old_id}|{new_id}"
            async with async_session() as session:
                exists = (
                    await session.execute(
                        select(Approval.id).where(
                            Approval.tenant_id == tenant_id,
                            Approval.source == "judgment",
                            Approval.source_ref == ref,
                        )
                    )
                ).first()
                if exists:
                    return
                session.add(
                    Approval(
                        tenant_id=tenant_id,
                        kind="contradiction",
                        source="judgment",
                        source_ref=ref,
                        title="Review a resolved contradiction",
                        detail=reason,
                        payload={"memory_id_old": str(old_id), "memory_id_new": str(new_id)},
                    )
                )
                await session.commit()
        except Exception:
            logger.warning(
                "Failed to queue contradiction approval for %s→%s",
                str(old_id)[:8],
                str(new_id)[:8],
            )

    def _resolve_contradictions(
        self,
        contradictions: list[Contradiction],
    ) -> list[tuple[str, str]]:
        """Determine which contradictions to auto-resolve via supersession.

        Returns:
            List of (old_memory_id, reason) tuples for memories to supersede.
        """
        supersede_targets: list[tuple[str, str]] = []

        for contradiction in contradictions:
            if contradiction.resolution == "supersede":
                supersede_targets.append(
                    (
                        contradiction.existing_memory_id,
                        contradiction.reason,
                    )
                )
                logger.info(
                    "Auto-superseding memory %s: %s",
                    contradiction.existing_memory_id[:8],
                    contradiction.reason,
                )
            elif contradiction.resolution == "ask_user":
                logger.warning(
                    "Contradiction requires user input: %s vs %s — %s",
                    contradiction.new_content[:40],
                    contradiction.existing_content[:40],
                    contradiction.reason,
                )
            elif contradiction.resolution == "scope":
                logger.info(
                    "Scope-based contradiction: both valid — %s",
                    contradiction.reason,
                )

        return supersede_targets

    async def _generate_embedding(self, text: str) -> list[float] | None:
        """Generate an embedding vector for the given text.

        Uses LM Studio (local) when configured, otherwise falls back
        to sentence-transformers.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector or None if generation fails.
        """
        from life_graph.config import settings

        if settings.use_local_llm:
            try:
                from life_graph.services.llm_client import LMStudioClient

                if not hasattr(self, "_lm_client"):
                    self._lm_client = LMStudioClient()

                vector = await self._lm_client.embed(text)
                return vector if vector else None
            except Exception as exc:
                logger.warning("LM Studio embedding failed: %s", exc)
                return None

        try:
            from sentence_transformers import SentenceTransformer

            from life_graph.config import settings

            # Lazy-load the configured model (cached after first call)
            if not hasattr(self, "_embed_model"):
                self._embed_model = SentenceTransformer(settings.embedding_model)

            vector = self._embed_model.encode(text).tolist()
            return vector
        except ImportError:
            logger.debug("sentence-transformers not available, skipping embedding")
            return None
        except Exception as exc:
            logger.warning("Embedding generation failed: %s", exc)
            return None


def _infer_tags(fact: ExtractedFact, importance_tier: str) -> list[str]:
    """Infer tags from fact type, entities, and importance tier.

    Args:
        fact: The extracted fact.
        importance_tier: Computed importance tier label.

    Returns:
        List of tag strings.
    """
    tags: list[str] = []

    # Map fact types to tags
    type_tag_map: dict[str, str] = {
        "preference": "preference",
        "anti_preference": "preference",
        "decision": "decision",
        "lesson": "lesson",
        "tool_usage": "tool",
        "constraint": "constraint",
        "identity": "identity",
        "experience": "experience",
    }

    mapped_tag = type_tag_map.get(fact.fact_type)
    if mapped_tag:
        tags.append(mapped_tag)
    else:
        tags.append(fact.fact_type)

    # Add importance tier as tag
    if importance_tier in ("critical", "high"):
        tags.append(importance_tier)

    return tags
