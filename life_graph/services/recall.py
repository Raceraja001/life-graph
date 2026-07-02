"""Proactive recall engine for push-based memory surfacing (T-022, T-024).

Orchestrates the three-stage recall pipeline:
  1. Retrieve — query store for active memories matching context
  2. Rank — apply multi-signal scoring
  3. Rerank — diversity-aware filtering

Includes anti-annoyance controls: cooldown periods, session caps,
and dismissal tracking to avoid spamming the user.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from life_graph.config import settings
from life_graph.models.schemas import (
    IntentionResponse,
    MemoryResponse,
    RecallContext,
)
from life_graph.scoring.ranking import RecallRanker
from life_graph.services.context import ContextBuilder, ContextFingerprint
from life_graph.services.triggers import TriggerMatcher
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)

# Cooldown: minimum seconds before resurfacing the same memory
_COOLDOWN_SECONDS: int = settings.recall_cooldown_days * 86400
_MAX_SESSION_SURFACES: int = 10


class RecallEngine:
    """Push-based memory recall engine.

    Proactively surfaces relevant memories at session start and during
    mid-session events, without waiting for the user to search.

    Anti-annoyance controls:
        - Per-memory cooldown (won't resurface within cooldown window)
        - Session surface cap (max total memories surfaced per session)
        - Dismissal tracking (categories dismissed often get deprioritized)

    Usage::

        engine = RecallEngine(store, ranker, context_builder)
        recall = await engine.session_start_recall({"project": "life_graph"})
    """

    def __init__(
        self,
        store: PostgresMemoryStore,
        ranker: RecallRanker,
        context_builder: ContextBuilder,
    ) -> None:
        self._store = store
        self._ranker = ranker
        self._context_builder = context_builder
        self._trigger_matcher = TriggerMatcher(store)

        # Anti-annoyance state (per engine instance = per session)
        self._surfaced_memory_ids: dict[str, datetime] = {}
        self._session_surface_count: int = 0
        self._dismissed_categories: Counter[str] = Counter()

    # ── Main Entry: Session Start ─────────────────────────────

    async def session_start_recall(
        self, context: dict[str, Any],
    ) -> RecallContext:
        """Proactively recall memories at session start.

        Pipeline stages:
            1. Build context fingerprint
            2. Retrieve: query store for top-50 active memories
            3. Rank: apply multi-signal scoring
            4. Rerank: diversity-aware filter to max 5
            5. Check triggered intentions
            6. Bundle into RecallContext

        Args:
            context: Raw session context dict.

        Returns:
            RecallContext with identity, decisions, intentions, warnings.
        """
        fingerprint = self._context_builder.build(context)
        logger.info("Session start recall — fingerprint: %s", fingerprint.as_dict())

        # Stage 1: Retrieve candidates
        candidates = await self._retrieve_candidates(fingerprint, limit=50)
        if not candidates:
            logger.info("No candidate memories found for context")

        # Stage 2: Rank
        ranked = self._ranker.rank(candidates, current_context=context)

        # Stage 3: Rerank (max 5)
        reranked = self._ranker.rerank(
            ranked,
            max_results=settings.recall_max_session_start,
        )

        # Filter through anti-annoyance
        filtered = self._apply_anti_annoyance(reranked)

        # Categorize memories by purpose
        identity, decisions, warnings = self._categorize_memories(filtered)

        # Check intentions
        triggered_intentions = await self._check_intentions(fingerprint)

        # Track surfaced memories
        for mem in filtered:
            mem_id = str(mem.get("id", ""))
            if mem_id:
                self._surfaced_memory_ids[mem_id] = datetime.now(timezone.utc)
                self._session_surface_count += 1

        recall_ctx = RecallContext(
            identity=identity,
            decisions=decisions,
            intentions=triggered_intentions,
            warnings=warnings,
        )

        logger.info(
            "Session recall: %d identity, %d decisions, %d intentions, %d warnings",
            len(identity), len(decisions), len(triggered_intentions), len(warnings),
        )
        return recall_ctx

    # ── Mid-Session Recall ────────────────────────────────────

    async def mid_session_recall(
        self,
        context: dict[str, Any],
        event: str,
    ) -> list[MemoryResponse]:
        """Lighter recall for mid-session events.

        Triggered by events like ``file_opened`` or ``error_encountered``.
        Returns at most 2 memories to minimize interruption.

        Args:
            context: Current session context dict.
            event: Event type that triggered the recall.

        Returns:
            List of up to 2 relevant MemoryResponse objects.
        """
        if self._session_surface_count >= _MAX_SESSION_SURFACES:
            logger.debug("Session surface cap reached, skipping mid-session recall")
            return []

        fingerprint = self._context_builder.build(context)
        logger.debug("Mid-session recall for event=%s", event)

        # Lighter retrieval: fewer candidates
        candidates = await self._retrieve_candidates(fingerprint, limit=20)
        ranked = self._ranker.rank(candidates, current_context=context)
        reranked = self._ranker.rerank(
            ranked,
            max_results=settings.recall_max_during_session,
        )

        filtered = self._apply_anti_annoyance(reranked)
        results: list[MemoryResponse] = []

        for mem_dict in filtered[:settings.recall_max_during_session]:
            response = _dict_to_memory_response(mem_dict)
            if response:
                results.append(response)
                mem_id = str(mem_dict.get("id", ""))
                if mem_id:
                    self._surfaced_memory_ids[mem_id] = datetime.now(timezone.utc)
                    self._session_surface_count += 1

        return results

    # ── Dismiss ───────────────────────────────────────────────

    def dismiss(self, memory_id: str, category: str) -> None:
        """Record that the user dismissed a surfaced memory.

        Increments the dismissal counter for the given category
        so future recalls can deprioritize it.

        Args:
            memory_id: UUID string of the dismissed memory.
            category: Category/tag of the dismissed memory.
        """
        self._dismissed_categories[category] += 1
        self._surfaced_memory_ids[memory_id] = datetime.now(timezone.utc)
        logger.debug(
            "Dismissed memory %s (category=%s, total dismissals=%d)",
            memory_id, category, self._dismissed_categories[category],
        )

    # ── Internal Helpers ──────────────────────────────────────

    async def _retrieve_candidates(
        self, fingerprint: ContextFingerprint, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query store for active memories matching the context fingerprint."""
        filters: dict[str, Any] = {"status": "active"}

        # Add project filter if available
        if fingerprint.project:
            filters["properties"] = {"project": fingerprint.project}

        memories = await self._store.list_memories(
            filters=filters,
            limit=limit,
        )

        # Convert ORM objects to dicts for the ranker
        candidates: list[dict[str, Any]] = []
        for mem in memories:
            cand: dict[str, Any] = {
                "id": str(mem.id),
                "content": mem.content,
                "tags": mem.tags or [],
                "properties": mem.properties or {},
                "importance": mem.importance,
                "trust_score": mem.trust_score,
                "access_count": mem.access_count,
                "last_accessed": mem.last_accessed,
                "created_at": mem.created_at,
                "source_type": mem.source_type,
                "status": mem.status,
                "confidence": mem.confidence,
                "reasoning": mem.reasoning,
                # Context fields from properties for ranker
                "project": (mem.properties or {}).get("project", ""),
                "module": (mem.properties or {}).get("module", ""),
                "tools": (mem.properties or {}).get("tools", []),
                "files": (mem.properties or {}).get("files", []),
                # Semantic score placeholder — 0.5 for non-vector retrieval
                "semantic_score": 0.5,
            }
            candidates.append(cand)

        return candidates

    def _apply_anti_annoyance(
        self, candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Filter candidates through anti-annoyance controls."""
        now = datetime.now(timezone.utc)
        filtered: list[dict[str, Any]] = []

        for cand in candidates:
            # Session cap
            if self._session_surface_count + len(filtered) >= _MAX_SESSION_SURFACES:
                break

            mem_id = str(cand.get("id", ""))

            # Cooldown check
            if mem_id in self._surfaced_memory_ids:
                last_surfaced = self._surfaced_memory_ids[mem_id]
                elapsed = (now - last_surfaced).total_seconds()
                if elapsed < _COOLDOWN_SECONDS:
                    continue

            # Dismissed category deprioritization
            tags = cand.get("tags", [])
            if tags:
                primary_tag = tags[0] if isinstance(tags, list) and tags else ""
                if self._dismissed_categories.get(primary_tag, 0) >= 3:
                    continue

            filtered.append(cand)

        return filtered

    def _categorize_memories(
        self, candidates: list[dict[str, Any]],
    ) -> tuple[list[MemoryResponse], list[MemoryResponse], list[MemoryResponse]]:
        """Sort memories into identity, decisions, and warnings buckets."""
        identity: list[MemoryResponse] = []
        decisions: list[MemoryResponse] = []
        warnings: list[MemoryResponse] = []

        for cand in candidates:
            response = _dict_to_memory_response(cand)
            if not response:
                continue

            tags = cand.get("tags", []) or []
            source_type = cand.get("source_type", "")

            # Categorize based on tags and source
            if _has_any_tag(tags, {"identity", "preference", "style", "value"}):
                identity.append(response)
            elif _has_any_tag(tags, {"decision", "architecture", "choice"}):
                decisions.append(response)
            elif _has_any_tag(tags, {"warning", "lesson", "bug", "contradiction"}):
                warnings.append(response)
            elif source_type in ("cold_start", "explicit"):
                identity.append(response)
            else:
                decisions.append(response)

        return identity, decisions, warnings

    async def _check_intentions(
        self, fingerprint: ContextFingerprint,
    ) -> list[IntentionResponse]:
        """Check for triggered intentions matching the current context."""
        trigger_results = await self._trigger_matcher.check_all(fingerprint)

        intentions: list[IntentionResponse] = []
        for intention in trigger_results.get("time", []):
            intentions.append(IntentionResponse.model_validate(intention))
        for intention in trigger_results.get("context", []):
            intentions.append(IntentionResponse.model_validate(intention))

        return intentions


# ── Module-Level Helpers ──────────────────────────────────────


def _dict_to_memory_response(mem_dict: dict[str, Any]) -> MemoryResponse | None:
    """Safely convert a candidate dict to a MemoryResponse."""
    try:
        mem_id = mem_dict.get("id", "")
        if isinstance(mem_id, str):
            mem_id = uuid.UUID(mem_id) if mem_id else uuid.uuid4()

        return MemoryResponse(
            id=mem_id,
            content=mem_dict.get("content", ""),
            reasoning=mem_dict.get("reasoning"),
            tags=mem_dict.get("tags"),
            properties=mem_dict.get("properties", {}),
            importance=float(mem_dict.get("importance", 0.5)),
            confidence=float(mem_dict.get("confidence", 0.5)),
            source_type=mem_dict.get("source_type", "inferred"),
            created_at=mem_dict.get("created_at", datetime.now(timezone.utc)),
            status=mem_dict.get("status", "active"),
            access_count=int(mem_dict.get("access_count", 0)),
        )
    except (ValueError, TypeError) as exc:
        logger.warning("Failed to convert memory dict to response: %s", exc)
        return None


def _has_any_tag(tags: list[str], target_tags: set[str]) -> bool:
    """Check if any tag in the list matches any target tag."""
    return bool(set(t.lower() for t in tags) & target_tags)
