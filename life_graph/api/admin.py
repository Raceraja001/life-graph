"""Admin routes — health, stats, gaps, and raw ingestion (T-048).

Provides operational endpoints: system statistics (simple COUNT
queries), knowledge gap listing, and a raw text ingestion shortcut
that runs the full MemoryManager pipeline.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from life_graph.api.dependencies import get_memory_manager, get_metamemory
from life_graph.core.memory_manager import MemoryManager
from life_graph.models.db import Intention, KnowledgeGap, Memory, Session
from life_graph.models.schemas import MemoryResponse
from life_graph.services.metamemory import MetamemoryTracker
from life_graph.storage.database import async_session

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Request / Response schemas ───────────────────────────────


class SystemStats(BaseModel):
    """Aggregate counts for the system dashboard."""

    memory_count: int
    intention_count: int
    gap_count: int
    session_count: int


class GapResponse(BaseModel):
    """Serialized knowledge gap for the API."""

    model_config = {"from_attributes": True}

    id: Any
    topic: str
    query_count: int
    first_asked: Any
    last_asked: Any
    resolved: bool


class IngestRequest(BaseModel):
    """Body for raw text ingestion."""

    text: str = Field(..., min_length=1, description="Raw text to ingest")
    context: dict[str, Any] | None = Field(
        None, description="Optional context (project, module, etc.)"
    )
    source: str | None = Field(
        None, description="Source identifier (e.g. 'chat', 'git', 'manual')"
    )


# ── Routes ───────────────────────────────────────────────────


@router.get(
    "/stats",
    response_model=SystemStats,
    summary="System statistics",
)
async def get_stats() -> SystemStats:
    """Return aggregate counts for memories, intentions, gaps, and sessions."""
    async with async_session() as session:
        memory_count = await session.scalar(select(func.count(Memory.id)))
        intention_count = await session.scalar(select(func.count(Intention.id)))
        gap_count = await session.scalar(select(func.count(KnowledgeGap.id)))
        session_count = await session.scalar(select(func.count(Session.id)))

    return SystemStats(
        memory_count=memory_count or 0,
        intention_count=intention_count or 0,
        gap_count=gap_count or 0,
        session_count=session_count or 0,
    )


@router.get(
    "/gaps",
    response_model=list[GapResponse],
    summary="List knowledge gaps",
)
async def list_gaps(
    metamemory: MetamemoryTracker = Depends(get_metamemory),
) -> list[GapResponse]:
    """Return unresolved knowledge gaps, ordered by query count."""
    gaps = await metamemory.get_gaps()
    return [GapResponse.model_validate(g) for g in gaps]


@router.post(
    "/ingest",
    response_model=list[MemoryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Ingest raw text",
)
async def ingest_text(
    body: IngestRequest,
    manager: MemoryManager = Depends(get_memory_manager),
) -> list[MemoryResponse]:
    """Run raw text through the full ingestion pipeline.

    Extracts facts, scores importance, checks contradictions,
    and stores resulting memories.
    """
    memories = await manager.ingest(
        text=body.text,
        context=body.context,
        source=body.source,
    )
    return [MemoryResponse.model_validate(m) for m in memories]
