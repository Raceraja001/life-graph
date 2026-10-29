"""Memory manager orchestrating ingestion with contradiction handling (T-027).

Full ingestion pipeline:
  1. Extract facts from text (via ExtractionPipeline)
  2. Score importance for each fact
  3. Generate embeddings (placeholder for sentence-transformers)
  4. Check for contradictions
  5. Handle contradictions: queue a contradiction approval; supersede at
     once only for an already-active memory, else when the owner approves
  6. Store memories
  7. Return stored memories

Also manages supersession chains for belief evolution tracking.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from typing import TYPE_CHECKING, Any

from life_graph.core.evidence import UNKNOWN_SOURCE
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import Memory
from life_graph.models.schemas import MemoryCreate, MemoryUpdate
from life_graph.services.contradiction import differs_by_negation

if TYPE_CHECKING:
    from life_graph.extraction.pipeline import ExtractionPipeline
    from life_graph.extraction.rules import ExtractedFact
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
        capture: bool = False,
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
            capture: True when *text* is a genuine user capture (voice,
                image, document, or manually-typed memory). Passed through
                to the extractor so the LLM can be used as the primary
                extractor instead of the rules/nlp tiers.

        Returns:
            List of stored Memory ORM objects.
        """
        if not text.strip():
            return []

        # Step 1: Extract facts
        extraction_result = await self._extractor.extract(text, capture=capture)
        facts = extraction_result.facts

        if not facts:
            logger.debug("No facts extracted from text: %s", text[:80])
            return []

        logger.info("Extracted %d facts from input text", len(facts))

        from life_graph.config import settings

        # Cheap exact-hash check up front, in parallel — safe because the
        # extraction pipeline already dedups facts against each other within
        # this batch (pipeline.py's _deduplicate), so no two facts here share
        # normalised content. This lets us skip the expensive embedding call
        # entirely for facts that turn out to be exact duplicates of memories
        # we already have.
        exact_matches: list[Memory | None] = [None] * len(facts)
        if settings.dedup_enabled and not skip_dedup:
            content_hashes = [
                hashlib.sha256(fact.content.strip().lower().encode()).hexdigest() for fact in facts
            ]
            exact_matches = list(
                await asyncio.gather(*(self._store.find_exact_duplicate(h) for h in content_hashes))
            )

        # Steps 2-6: Process each non-duplicate fact. Embeddings are independent
        # per fact, so generate them all concurrently up front (this is the
        # expensive network call); dedup/contradiction/store must stay
        # sequential per fact since sibling facts from the same input can be
        # near-duplicates of each other.
        pending = [i for i, m in enumerate(exact_matches) if m is None]
        embeddings: list[list[float] | None] = [None] * len(facts)
        if pending:
            computed = await asyncio.gather(
                *(self._generate_embedding(facts[i].content) for i in pending)
            )
            for i, emb in zip(pending, computed, strict=False):
                embeddings[i] = emb

        stored_memories: list[Memory] = []
        for fact, embedding, existing in zip(facts, embeddings, exact_matches, strict=False):
            if existing is not None:
                stored_memories.append(await self._reuse_exact_duplicate(existing))
                continue
            memory = await self._process_fact(
                fact, context, source, skip_dedup, trust_tier, embedding=embedding
            )
            if memory:
                stored_memories.append(memory)

        logger.info("Ingested %d memories from %d facts", len(stored_memories), len(facts))
        return stored_memories

    async def store_facts(
        self,
        facts: list[ExtractedFact],
        context: dict[str, Any] | None = None,
        source: str | None = None,
        trust_tier: str | None = None,
    ) -> list[Memory]:
        """Persist already-extracted facts through the store-side path (embed,
        dedup, score, pending) — bypassing the note-tuned extraction tiers.

        Used by transcript distillation and the capture spine, both of which
        extract their own facts.

        Args:
            facts: Already-extracted facts to persist.
            context: Extra properties merged onto every stored memory.
            source: ``source_type`` recorded on every stored memory.
            trust_tier: Provenance of these facts, decided server-side by the
                caller (e.g. ``classify_surface()`` on a capture surface). It is
                recorded on each memory so untrusted content can be fenced or
                withheld from acting agents later. ``None`` leaves the store's
                default ("verified", i.e. system-produced).

        Returns:
            The memories actually stored (duplicates dropped by dedup are not
            included).
        """
        embeddings = await asyncio.gather(
            *(self._generate_embedding(fact.content) for fact in facts)
        )

        stored: list[Memory] = []
        for fact, embedding in zip(facts, embeddings, strict=False):
            memory = await self._process_fact(
                fact, context, source, skip_dedup=False, trust_tier=trust_tier, embedding=embedding
            )
            if memory:
                stored.append(memory)
        return stored

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
                update(Memory)
                .where(Memory.id == old_uuid)
                .where(Memory.tenant_id == get_current_tenant_id())
                .values(superseded_by=new_uuid)
            )
            # Set supersedes on new memory
            await session.execute(
                update(Memory)
                .where(Memory.id == new_uuid)
                .where(Memory.tenant_id == get_current_tenant_id())
                .values(supersedes=old_uuid)
            )
            await session.commit()

        logger.info(
            "Superseded memory %s → %s (reason: %s)",
            old_memory_id[:8],
            new_memory_id[:8],
            reason,
        )

    async def generate_embedding(self, text: str) -> list[float] | None:
        """Public wrapper for embedding generation (used by fallback persistence paths)."""
        return await self._generate_embedding(text)

    # ── Internal Helpers ──────────────────────────────────────

    async def _reuse_exact_duplicate(self, existing: Memory) -> Memory:
        """Touch and return an existing memory found via exact-hash dedup."""
        logger.info("Dedup: exact match found for memory %s", existing.id)
        await self._store.touch(existing.id)
        return existing

    async def _process_fact(
        self,
        fact: ExtractedFact,
        context: dict[str, Any] | None,
        source: str | None,
        skip_dedup: bool = False,
        trust_tier: str | None = None,
        embedding: list[float] | None = None,
    ) -> Memory | None:
        """Process a single extracted fact through scoring, embedding, and storage.

        Args:
            embedding: Precomputed embedding for ``fact.content``, when the
                caller already generated it (e.g. batched across facts in
                ``ingest()``). If not provided, it's generated here.

        Returns:
            Stored Memory object, or None if the fact was a duplicate.
        """
        # Step 2: Score importance
        importance, tier = self._tagger.score(fact.content, context)

        # Step 3: Generate embedding (placeholder), unless already provided
        if embedding is None:
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
                return await self._reuse_exact_duplicate(existing)

        # Shared candidate pool for near-match dedup below and the
        # contradiction check in Step 4 — one pgvector query instead of two
        # (find_similar + ContradictionDetector's own search_similar), since
        # both were querying the same table/tenant/embedding back to back.
        candidates: list[tuple[Memory, float]] = []
        if embedding:
            candidates = await self._store.find_similarity_candidates(embedding)

        # Near-match dedup — only when an embedding produced candidates,
        # i.e. no exact hash match short-circuited above.
        if settings.dedup_enabled and not skip_dedup and candidates:
            # A negation barely moves the embedding, so "I don't use X" can
            # score as a near-duplicate of "I use X" and used to be merged
            # into it, losing the "not" (review 2026-10-22). Such a pair goes
            # to the contradiction check below instead.
            similar = [
                (m, s)
                for m, s in candidates
                if s >= settings.dedup_threshold
                and not differs_by_negation(fact.content, m.content)
            ][:5]
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

        # Step 4: Check for contradictions, derived from the same candidate
        # pool fetched above (active memories only — candidates also include
        # "pending", which is dedup-only).
        contradictions: list[Contradiction] = []
        if candidates:
            active_candidates = [m for m, _ in candidates if m.status == "active"][:10]
            contradictions = await self._contradiction_detector.check_candidates(
                fact.content,
                active_candidates,
                embedding,
                new_properties=context or {},
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
        if fact.changes_over_time:
            properties["changes_over_time"] = True
        if fact.trace_id:
            # How the user resolves this memory is the self-improvement label
            # for that extraction call (self_improving/suite_builder.py).
            properties["extraction_trace_id"] = fact.trace_id
            properties["extraction_fact_index"] = fact.trace_index

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

        # Only a clash that would retire an active memory: a "scope" one keeps both.
        kept_because = _auto_approved(fact, trust_tier, contradicts=bool(auto_supersede_targets))
        active_now = kept_because is not None
        if kept_because:
            # Which rule let it skip review, so a wrong one can be traced.
            properties["auto_kept"] = kept_because

        memory_create = MemoryCreate(
            content=fact.content,
            reasoning=fact.source_text or None,
            tags=_infer_tags(fact, tier),
            properties=properties,
            importance=importance,
            source_type=source or UNKNOWN_SOURCE,
        )

        stored = await self._store.store(
            memory_create,
            embedding=embedding,
            trust_tier=trust_tier,
            status="active" if active_now else "pending",
            # Provenance: which tier produced this fact, how sure it was, and
            # which capture event it came from (the capture spine puts that id
            # in context/properties).
            extraction_tier=fact.tier or None,
            extraction_confidence=fact.confidence,
            capture_event_id=properties.get("capture_event_id"),
            # The tier scored in Step 2 belongs on the row, not only in the
            # tags: decay exempts importance_tier='critical', and without this
            # every new memory was stored 'normal' (code review, 2026-10-22).
            importance_tier=tier,
            valid_until=_end_of_day(fact.valid_until),
        )

        # The people, projects and things it mentions (services/entities.py).
        # Best-effort: a failed link never costs the memory.
        if fact.entities:
            try:
                from life_graph.services import entities

                await entities.link(stored.tenant_id, stored.id, fact.entities)
            except Exception:
                logger.warning("Entity linking failed for memory %s", stored.id, exc_info=True)

        # Step 5b: Queue a contradiction approval for each supersede target.
        # Only a memory that is already active (the owner's explicit "remember
        # this") supersedes at once, undoable by rejecting the approval. A
        # pending memory supersedes nothing yet: the supersede is applied when
        # the owner approves the new memory or the approval
        # (ApprovalService.on_memory_approved / _apply_contradiction). Until
        # 2026-10-22 it was applied here for pending memories too, so an
        # unreviewed extraction could retire an active memory, and rejecting
        # the new memory never brought the old one back.
        for old_id, reason in auto_supersede_targets:
            if active_now:
                await self.supersede(old_id, str(stored.id), reason)
            await self._queue_contradiction_approval(
                old_id, str(stored.id), reason, applied=active_now
            )

        return stored

    async def _queue_contradiction_approval(
        self,
        old_id: str,
        new_id: str,
        reason: str,
        *,
        applied: bool = True,
    ) -> None:
        """Record a supersede as a contradiction approval.

        ``applied`` says whether the supersede already happened (approve
        confirms, reject undoes) or is only suspected (approve applies it,
        reject leaves the old memory as it is).

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
                        title=(
                            "Review a resolved contradiction"
                            if applied
                            else "Review a suspected contradiction"
                        ),
                        detail=reason,
                        payload={
                            "memory_id_old": str(old_id),
                            "memory_id_new": str(new_id),
                            "applied": applied,
                        },
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
        """Determine which contradictions are supersede candidates.

        Returns:
            List of (old_memory_id, reason) tuples for memories to supersede
            (at once or on approval — see _process_fact Step 5b).
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
                    "Supersede candidate %s: %s",
                    contradiction.existing_memory_id[:8],
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


def _end_of_day(day: str | None):
    """End of *day* (YYYY-MM-DD) in the owner's timezone, as an aware datetime, or None.

    A fact "true until Friday" is still true all of Friday.
    """
    if not day:
        return None
    from datetime import date, datetime, time

    from life_graph.connectors.tools import user_tz

    try:
        return datetime.combine(date.fromisoformat(day), time.max, tzinfo=user_tz())
    except ValueError:
        return None


#: How sure the extractor must be that the owner asked to remember it.
AUTO_APPROVE_MIN_CONFIDENCE = 0.8
#: How sure it must be of a firm fact the owner stated without asking.
AUTO_KEEP_MIN_CONFIDENCE = 0.9
#: What the owner states firmly. Not ``intention``: plans change, and those
#: wait for the owner's Keep or Drop in the Memory check (services/memory_check.py).
AUTO_KEEP_TYPES = frozenset({"fact", "preference", "anti_preference", "decision"})
#: Wording of a thought in progress, not a settled fact: "is considering…",
#: "for now". On 2026-10-28 "The owner prefers using existing tools like Dify"
#: came from exploring options, and the owner chose the opposite an hour later.
HEDGED = re.compile(
    r"\b(consider(s|ed|ing)?|explor(e|es|ed|ing)|thinking (about|of)|might|maybe|perhaps|"
    r"possibl[ey]|potential(ly)?|wonder(s|ed|ing)?|whether|not sure|unsure|for now|"
    r"for the time being)\b",
    re.IGNORECASE,
)


def _auto_approved(
    fact: ExtractedFact, trust_tier: str | None, *, contradicts: bool = False
) -> str | None:
    """Why a new memory skips the review queue, or None when it waits for review.

    Only what the owner said in their own words (trust tier ``self``):

    - ``explicit_save``: what they asked to be remembered;
    - ``firm_owner_fact``: a fact, preference or decision they stated plainly,
      with no hedge and no clash with an active memory. A clash is the owner's
      call: keeping the new one would retire the old one.

    Everything else waits for the owner's Keep or Drop. On 2026-10-22 the
    queue jammed at 3,668 when every memory waited; five days after the
    2026-10-23 fresh start only day summaries were active, with lasting facts
    ("prefers local HTML files") left pending.
    """
    if trust_tier != "self":
        return None
    if fact.fact_type == "explicit_save" and fact.confidence >= AUTO_APPROVE_MIN_CONFIDENCE:
        return "explicit_save"
    if (
        fact.fact_type in AUTO_KEEP_TYPES
        and fact.confidence >= AUTO_KEEP_MIN_CONFIDENCE
        and not contradicts
        and not HEDGED.search(fact.content)
    ):
        return "firm_owner_fact"
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
