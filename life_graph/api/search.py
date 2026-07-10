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
    get_synthesis_service,
)
from life_graph.api.responses import success_response
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


class AskRequest(BaseModel):
    """Body for natural language question."""

    question: str = Field(..., min_length=1, description="Natural language question")
    limit: int = Field(default=10, ge=1, le=50, description="Max memories to use")


class AskResponse(BaseModel):
    """Response with synthesized answer."""

    answer: str
    source_count: int
    model: str | None = None
    memories: list[MemoryResponse] = []
    query_time_ms: float = 0.0


# ── Routes ───────────────────────────────────────────────────


@router.post(
    "/",
    summary="Search across memories (vector, hybrid, or tri-hybrid)",
)
async def semantic_search(
    body: SearchQuery,
    store: PostgresMemoryStore = Depends(get_store),
    metamemory: MetamemoryTracker = Depends(get_metamemory),
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Search memories using configurable strategy.

    Modes:
    - ``vector``: Pure cosine similarity (fastest, semantic only)
    - ``hybrid``: Vector + BM25 keyword matching (default, best balance)
    - ``tri_hybrid``: Vector + BM25 + graph entity proximity (most comprehensive)
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
    if body.created_after:
        filters["created_after"] = body.created_after
    if body.created_before:
        filters["created_before"] = body.created_before
    if body.source_type:
        filters["source_type"] = body.source_type
    if body.status:
        filters["status"] = body.status

    search_mode = body.search_mode
    memories: list[MemoryResponse] = []

    if search_mode == "tri_hybrid":
        # ── Tri-hybrid: vector + BM25 + graph ────────────────
        try:
            from life_graph.storage.hybrid import HybridQueryEngine
            engine = HybridQueryEngine()
            result = await engine.tri_search(
                query=body.query,
                limit=body.limit,
            )
            # Convert scored dicts to MemoryResponse
            for mem_dict in result.get("memories", []):
                try:
                    from life_graph.services.recall import _dict_to_memory_response
                    resp = _dict_to_memory_response(mem_dict)
                    if resp:
                        memories.append(resp)
                except Exception:
                    pass
        except Exception:
            logger.warning("Tri-hybrid search failed — falling back to hybrid", exc_info=True)
            search_mode = "hybrid"

    if search_mode == "hybrid":
        # ── Hybrid: vector + BM25 ────────────────────────────
        try:
            hybrid_results = await store.hybrid_search(
                embedding=embedding,
                query_text=body.query,
                limit=body.limit,
                filters=filters or None,
            )
            memories = [MemoryResponse.model_validate(mem) for mem, _score in hybrid_results]
        except Exception:
            logger.warning("Hybrid search failed — falling back to vector", exc_info=True)
            search_mode = "vector"

    if search_mode == "vector":
        # ── Pure vector: cosine similarity only ──────────────
        rows = await store.search_similar(
            embedding=embedding,
            limit=body.limit,
            filters=filters or None,
        )
        memories = [MemoryResponse.model_validate(r) for r in rows]

    query_time_ms = (time.perf_counter() - t0) * 1000

    # Track in metamemory
    max_confidence = max((m.confidence for m in memories), default=0.0)
    await metamemory.track_query(
        body.query, len(memories), max_confidence, embedding=embedding,
    )

    return success_response(data=SearchResult(
        memories=memories,
        total_count=len(memories),
        query_time_ms=round(query_time_ms, 2),
        search_mode=search_mode,
    ))


@router.post(
    "/recall",
    summary="Proactive recall at session start",
)
async def session_start_recall(
    body: RecallRequest,
    engine: RecallEngine = Depends(get_recall_engine),
):
    """Surface relevant memories, decisions, intentions, and warnings.

    Runs the full proactive recall pipeline: retrieve → rank → rerank
    → anti-annoyance filtering → categorize.
    """
    return success_response(data=await engine.session_start_recall(body.context))


@router.post(
    "/recall/event",
    summary="Mid-session event-driven recall",
)
async def mid_session_recall(
    body: MidSessionRecallRequest,
    engine: RecallEngine = Depends(get_recall_engine),
):
    """Surface up to 2 relevant memories for a mid-session event.

    Lighter than session-start recall — fewer candidates, smaller
    result set, respects session surface cap.
    """
    return success_response(data=await engine.mid_session_recall(body.context, body.event))


@router.post(
    "/ask",
    summary="Ask a question — get a synthesized answer from memories",
)
async def ask_brain(
    body: AskRequest,
    store: PostgresMemoryStore = Depends(get_store),
    manager: MemoryManager = Depends(get_memory_manager),
    metamemory: MetamemoryTracker = Depends(get_metamemory),
    synthesis=Depends(get_synthesis_service),
):
    """Ask a natural language question and get a synthesized answer.

    Runs semantic search, then passes results to the LLM for synthesis.
    """
    t0 = time.perf_counter()

    # Generate embedding for the question
    embedding = await manager._generate_embedding(body.question)
    if embedding is None:
        return AskResponse(
            answer="Embedding service is unavailable. Cannot search memories.",
            source_count=0,
        )

    # Search for relevant memories
    rows = await store.search_similar(
        embedding=embedding,
        limit=body.limit,
    )

    memories = [MemoryResponse.model_validate(r) for r in rows]

    # Track in metamemory
    max_confidence = max((m.confidence for m in memories), default=0.0)
    await metamemory.track_query(
        body.question, len(memories), max_confidence, embedding=embedding,
    )

    # Synthesize answer
    memory_dicts = [
        {
            "content": m.content,
            "tags": m.tags,
            "importance": m.importance,
            "created_at": str(m.created_at) if m.created_at else "unknown",
        }
        for m in memories
    ]

    result = await synthesis.synthesize(body.question, memory_dicts)

    query_time_ms = (time.perf_counter() - t0) * 1000

    return success_response(data=AskResponse(
        answer=result["answer"],
        source_count=result["source_count"],
        model=result["model"],
        memories=memories,
        query_time_ms=round(query_time_ms, 2),
    ))
