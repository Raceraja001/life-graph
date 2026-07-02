"""Memory CRUD routes (T-043).

Provides create, read, update, delete, and list endpoints for
memories. Text-based creation is routed through the full ingestion
pipeline (extraction → scoring → contradiction → store); structured
creation goes directly to the store.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from life_graph.api.dependencies import get_memory_manager, get_store
from life_graph.core.memory_manager import MemoryManager
from life_graph.models.schemas import MemoryCreate, MemoryResponse, MemoryUpdate
from life_graph.storage.postgres import PostgresMemoryStore

router = APIRouter(prefix="/memories", tags=["memories"])


@router.post(
    "/",
    response_model=list[MemoryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create memories from text or structured input",
)
async def create_memory(
    body: MemoryCreate,
    manager: MemoryManager = Depends(get_memory_manager),
    store: PostgresMemoryStore = Depends(get_store),
) -> list[MemoryResponse]:
    """Create one or more memories.

    If the body contains free-form text, it is routed through the
    full ingestion pipeline (extraction → importance scoring →
    contradiction detection → storage). Otherwise, the memory is
    stored directly.
    """
    # Heuristic: if tags/properties already provided and content is short,
    # treat as structured input and store directly.
    is_structured = (
        body.tags is not None
        and body.importance is not None
        and len(body.content.split()) <= 20
    )

    if is_structured:
        row = await store.store(body)
        return [MemoryResponse.model_validate(row)]

    # Full ingestion pipeline for free-form text
    memories = await manager.ingest(
        text=body.content,
        context=body.properties,
        source=body.source_type,
    )

    if not memories:
        # Nothing extracted — store as-is so the user's input isn't lost
        row = await store.store(body)
        return [MemoryResponse.model_validate(row)]

    return [MemoryResponse.model_validate(m) for m in memories]


@router.get(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="Get a memory by ID",
)
async def get_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
) -> MemoryResponse:
    """Retrieve a single memory by its UUID."""
    row = await store.retrieve(memory_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    return MemoryResponse.model_validate(row)


@router.patch(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="Update a memory",
)
async def update_memory(
    memory_id: uuid.UUID,
    body: MemoryUpdate,
    store: PostgresMemoryStore = Depends(get_store),
) -> MemoryResponse:
    """Apply a partial update to an existing memory."""
    try:
        row = await store.update(memory_id, body)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    return MemoryResponse.model_validate(row)


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a memory",
)
async def delete_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
) -> None:
    """Delete a memory and cascade to association tables."""
    deleted = await store.delete(memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )


@router.get(
    "/",
    response_model=list[MemoryResponse],
    summary="List memories with optional filters",
)
async def list_memories(
    store: PostgresMemoryStore = Depends(get_store),
    memory_status: str | None = Query(None, alias="status", description="Filter by status"),
    tags: str | None = Query(None, description="Comma-separated tags (array overlap)"),
    min_importance: float | None = Query(None, ge=0.0, le=1.0, description="Minimum importance"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> list[MemoryResponse]:
    """List memories with optional status, tag, and importance filters."""
    filters: dict = {}

    if memory_status is not None:
        filters["status"] = memory_status
    if tags is not None:
        filters["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if min_importance is not None:
        filters["min_importance"] = min_importance

    rows = await store.list_memories(
        filters=filters or None,
        offset=offset,
        limit=limit,
    )
    return [MemoryResponse.model_validate(r) for r in rows]
