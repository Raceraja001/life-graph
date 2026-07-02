"""Search and proactive recall routes (T-044).

Provides semantic search over the memory store (pgvector cosine),
session-start proactive recall, and mid-session event-driven recall.
All search queries are tracked by the metamemory tracker so knowledge
gaps can be surfaced.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import (
    get_memory_manager,
    get_metamemory,
    get_recall_engine,
    get_store,
)
from life_graph.core.memory_manager import MemoryManager
from life_graph.models.schemas import (
    MemoryResponse,
    RecallContext,
    SearchQuery,
    SearchResult,
)
from life_graph.services.metamemory import MetamemoryTracker
from life_graph.services.recall import RecallEngine
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


# ── Request schemas specific to these routes ─────────────────


class RecallRequest(BaseModel):
    """Body for session-start proactive recall."""

    context: dict[str, Any] = Field(
        ..., description="Session context (project, tools, files, etc.)"
    )


class MidSessionRecallRequest(BaseModel):
    """Body for mid-session event-driven recall."""

    context: dict[str, Any] = Field(
        ..., description="Current session context"
    )
    event: str = Field(
        ..., min_length=1, description="Event that triggered the recall"
    )


# ── Routes ───────────────────────────────────────────────────


@router.post(
    "/",
    response_model=SearchResult,
    summary="Semantic search across memories",
)
async def semantic_search(
    body: SearchQuery,
    store: PostgresMemoryStore = Depends(get_store),
    metamemory: MetamemoryTracker = Depends(get_metamemory),
    manager: MemoryManager = Depends(get_memory_manager),
) -> SearchResult:
    """Embed the query, search pgvector, and track in metamemory.

    If sentence-transformers is unavailable, returns an empty result
    set with a zero query time.
    """
    t0 = time.perf_counter()

    # Generate embedding for the query
    embedding = await manager._generate_embedding(body.query)
    if embedding is None:
        logger.warning("Embedding generation unavailable — returning empty results")
        query_time_ms = (time.perf_counter() - t0) * 1000
        await metamemory.track_query(body.query, 0, 0.0, embedding=None)
        return SearchResult(memories=[], total_count=0, query_time_ms=query_time_ms)

    # Build filters from search query
    filters: dict[str, Any] = {}
    if body.filters:
        filters.update(body.filters)
    if body.tags:
        filters["tags"] = body.tags
    if body.min_importance is not None:
        filters["min_importance"] = body.min_importance

    rows = await store.search_similar(
        embedding=embedding,
        limit=body.limit,
        filters=filters or None,
    )

    query_time_ms = (time.perf_counter() - t0) * 1000
    memories = [MemoryResponse.model_validate(r) for r in rows]

    # Track in metamemory
    max_confidence = max((m.confidence for m in memories), default=0.0)
    await metamemory.track_query(
        body.query, len(memories), max_confidence, embedding=embedding,
    )

    return SearchResult(
        memories=memories,
        total_count=len(memories),
        query_time_ms=round(query_time_ms, 2),
    )


@router.post(
    "/recall",
    response_model=RecallContext,
    summary="Proactive recall at session start",
)
async def session_start_recall(
    body: RecallRequest,
    engine: RecallEngine = Depends(get_recall_engine),
) -> RecallContext:
    """Surface relevant memories, decisions, intentions, and warnings.

    Runs the full proactive recall pipeline: retrieve → rank → rerank
    → anti-annoyance filtering → categorize.
    """
    return await engine.session_start_recall(body.context)


@router.post(
    "/recall/event",
    response_model=list[MemoryResponse],
    summary="Mid-session event-driven recall",
)
async def mid_session_recall(
    body: MidSessionRecallRequest,
    engine: RecallEngine = Depends(get_recall_engine),
) -> list[MemoryResponse]:
    """Surface up to 2 relevant memories for a mid-session event.

    Lighter than session-start recall — fewer candidates, smaller
    result set, respects session surface cap.
    """
    return await engine.mid_session_recall(body.context, body.event)
