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

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from life_graph.api.dependencies import (
    get_memory_manager,
    get_metamemory,
    get_recall_engine,
    get_store,
    get_synthesis_service,
)
from life_graph.api.responses import success_response
from life_graph.api.token_meta import token_meta
from life_graph.core.memory_manager import MemoryManager
from life_graph.models.schemas import (
    MemoryIndexItem,
    MemoryResponse,
    SearchQuery,
    SearchResult,
)
from life_graph.scoring.ranking import to_index
from life_graph.services.metamemory import MetamemoryTracker
from life_graph.services.recall import RecallEngine
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


# ── Request schemas specific to these routes ─────────────────


_INDEX_ONLY_DESCRIPTION = (
    "Opt-in: return a compact index (id, truncated content, tags, score, "
    "status) instead of full memory objects — roughly a tenth of the tokens. "
    "Off by default so existing callers keep the shape they parse today. "
    "Expand the ids you actually want via POST /api/v1/memories/batch, which "
    "is also where the recall cooldown and access count are recorded."
)


class RecallRequest(BaseModel):
    """Body for session-start proactive recall."""

    context: dict[str, Any] = Field(
        ..., description="Session context (project, tools, files, etc.)"
    )
    index_only: bool = Field(False, description=_INDEX_ONLY_DESCRIPTION)


class MidSessionRecallRequest(BaseModel):
    """Body for mid-session event-driven recall."""

    context: dict[str, Any] = Field(..., description="Current session context")
    event: str = Field(..., min_length=1, description="Event that triggered the recall")
    index_only: bool = Field(False, description=_INDEX_ONLY_DESCRIPTION)


class AskRequest(BaseModel):
    """Body for natural language question."""

    question: str = Field(..., min_length=1, description="Natural language question")
    limit: int = Field(default=10, ge=1, le=50, description="Max memories to use")
    index_only: bool = Field(
        False,
        description=(
            "Opt-in: drop the source memories from the response and return a "
            "compact index of them instead. `answer` already summarises them, "
            "so returning both is near-pure duplication — the answer IS the "
            "disclosure. Off by default to keep the existing response shape."
        ),
    )


class AskResponse(BaseModel):
    """Response with synthesized answer."""

    answer: str
    source_count: int
    model: str | None = None
    memories: list[MemoryResponse] = []
    query_time_ms: float = 0.0
    # Echoed back like SearchResult.search_mode: the mode actually used.
    result_mode: str = "full"
    index: list[MemoryIndexItem] = []


# ── Projection helpers ───────────────────────────────────────
#
# A "hit" is (row-or-dict, relevance score). The three search paths produce
# different shapes — ORM rows from the vector and hybrid stores, scored dicts
# from tri-hybrid — so both projections normalise here rather than in each
# branch.


def _to_memory_responses(hits: list[tuple[Any, float]]) -> list[MemoryResponse]:
    """Full twenty-field objects, the pre-existing response shape."""
    from life_graph.services.recall import _dict_to_memory_response

    out: list[MemoryResponse] = []
    for obj, _score in hits:
        if isinstance(obj, dict):
            # Tri-hybrid dicts are assembled from a graph join and have
            # always been allowed to be individually unconvertible.
            try:
                resp = _dict_to_memory_response(obj)
            except Exception:
                resp = None
            if resp:
                out.append(resp)
        else:
            out.append(MemoryResponse.model_validate(obj))
    return out


def _to_index_items(hits: list[tuple[Any, float]]) -> list[MemoryIndexItem]:
    """Compact index lines — the same projection recall uses, same truncation."""
    flat: list[dict[str, Any]] = []
    for obj, score in hits:
        read = obj.get if isinstance(obj, dict) else (lambda k, _o=obj: getattr(_o, k, None))
        flat.append(
            {
                "id": read("id"),
                "content": read("content"),
                "tags": read("tags"),
                "status": read("status"),
                "final_score": score,
            }
        )
    return [MemoryIndexItem.model_validate(item) for item in to_index(flat)]


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
        # Same envelope as the happy path: this branch is still a 200, and a
        # caller that unwraps `data` must not have to special-case the one
        # response shape it gets when the embedding provider is down.
        empty = SearchResult(
            memories=[],
            total_count=0,
            query_time_ms=query_time_ms,
            result_mode="index" if body.index_only else "full",
        )
        return success_response(data=empty, meta=token_meta(empty))

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
    # Pending visibility is opt-in only. Agents/automation (e.g. the MCP
    # `search` tool) never pass include_pending, so they stay active-only —
    # the core approval-gate invariant. The dashboard sets include_pending=true
    # explicitly so it can still show pending items (badged).
    statuses: tuple[str, ...] = ("active", "pending") if body.include_pending else ("active",)

    if body.status != "active":
        # User explicitly narrowed to a non-default status (e.g. "archived") —
        # honor it as-is for the vector/filters path; this does NOT widen to
        # pending even if include_pending was also set.
        filters["status"] = body.status
    else:
        # Keep the vector-mode fallback (below) and any other _apply_filters
        # consumer in sync with the same status set used by hybrid/tri_hybrid.
        filters["statuses"] = list(statuses)

    search_mode = body.search_mode
    # (row-or-dict, relevance score). Conversion to MemoryResponse is deferred
    # to the end so index mode can skip it entirely: model_post_init costs a
    # math.exp and a datetime.now() per item, and serializes twenty fields the
    # index does not carry.
    hits: list[tuple[Any, float]] = []

    if search_mode == "tri_hybrid":
        # ── Tri-hybrid: vector + BM25 + graph ────────────────
        try:
            from life_graph.storage.hybrid import HybridQueryEngine

            engine = HybridQueryEngine()
            result = await engine.tri_search(
                query=body.query,
                limit=body.limit,
                statuses=statuses,
            )
            hits = [
                (mem_dict, float(mem_dict.get("final_score", 0.0) or 0.0))
                for mem_dict in result.get("memories", [])
            ]
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
                statuses=statuses,
            )
            hits = [(mem, float(score or 0.0)) for mem, score in hybrid_results]
        except Exception:
            logger.warning("Hybrid search failed — falling back to vector", exc_info=True)
            search_mode = "vector"

    if search_mode == "vector":
        # ── Pure vector: cosine similarity only ──────────────
        rows = await store.search_similar(
            embedding=embedding,
            limit=body.limit,
            filters=filters or None,
            include_embedding=False,  # MemoryResponse never serializes it
        )
        # search_similar returns rows without a score; 0.0 is the honest value.
        hits = [(r, 0.0) for r in rows]

    memories: list[MemoryResponse] = []
    index: list[MemoryIndexItem] = []
    if body.index_only:
        index = _to_index_items(hits)
    else:
        memories = _to_memory_responses(hits)

    query_time_ms = (time.perf_counter() - t0) * 1000

    # Track in metamemory. Index mode has no confidence to report — the
    # compact line does not carry it — so the gap tracker sees 0.0 rather
    # than a number invented for it.
    max_confidence = max((m.confidence for m in memories), default=0.0)
    result_count = len(index) if body.index_only else len(memories)
    await metamemory.track_query(
        body.query,
        result_count,
        max_confidence,
        embedding=embedding,
    )

    payload = SearchResult(
        memories=memories,
        total_count=result_count,
        query_time_ms=round(query_time_ms, 2),
        search_mode=search_mode,
        result_mode="index" if body.index_only else "full",
        index=index,
    )
    # tokens_saved is a counterfactual, so measuring it honestly means
    # building the payload that was not sent. The rows are already in memory;
    # this is a serialize, not a query, and only happens in index mode.
    full = (
        SearchResult(
            memories=_to_memory_responses(hits),
            total_count=len(hits),
            query_time_ms=payload.query_time_ms,
            search_mode=search_mode,
        )
        if body.index_only
        else None
    )
    return success_response(data=payload, meta=token_meta(payload, full))


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

    With ``index_only``, returns a compact index instead of the four
    populated buckets and records nothing — no cooldown, no access count.
    Expand what you want via ``POST /api/v1/memories/batch``, which is where
    that bookkeeping then happens.
    """
    payload, full = await engine.session_start_recall_measured(
        body.context, index_only=body.index_only
    )
    return success_response(data=payload, meta=token_meta(payload, full))


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

    ``index_only`` behaves as it does at session start: compact lines, and
    no surfacing recorded until the caller expands.
    """
    results, full = await engine.mid_session_recall_measured(
        body.context, body.event, index_only=body.index_only
    )
    return success_response(
        data=results,
        meta=token_meta(
            results,
            full,
            result_mode="index" if body.index_only else "full",
        ),
    )


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
        include_embedding=False,  # MemoryResponse never serializes it
    )

    memories = [MemoryResponse.model_validate(r) for r in rows]

    # Track in metamemory
    max_confidence = max((m.confidence for m in memories), default=0.0)
    await metamemory.track_query(
        body.question,
        len(memories),
        max_confidence,
        embedding=embedding,
    )

    # Synthesize answer
    memory_dicts = [
        {
            "id": str(m.id),
            "content": m.content,
            "tags": m.tags,
            "importance": m.importance,
            "created_at": str(m.created_at) if m.created_at else "unknown",
        }
        for m in memories
    ]

    result = await synthesis.synthesize(body.question, memory_dicts)

    query_time_ms = (time.perf_counter() - t0) * 1000

    # The synthesized answer already contains what these memories said, so
    # returning both is near-pure duplication — the answer IS the disclosure.
    # index_only keeps the citation handles (ids) and drops the rest.
    payload = AskResponse(
        answer=result["answer"],
        source_count=result["source_count"],
        model=result["model"],
        memories=[] if body.index_only else memories,
        query_time_ms=round(query_time_ms, 2),
        result_mode="index" if body.index_only else "full",
        index=_to_index_items([(r, 0.0) for r in rows]) if body.index_only else [],
    )
    full = (
        AskResponse(
            answer=result["answer"],
            source_count=result["source_count"],
            model=result["model"],
            memories=memories,
            query_time_ms=payload.query_time_ms,
        )
        if body.index_only
        else None
    )
    return success_response(data=payload, meta=token_meta(payload, full))
