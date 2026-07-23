"""Memory CRUD routes (T-043).

Provides create, read, update, delete, and list endpoints for
memories. Text-based creation is routed through the full ingestion
pipeline (extraction → scoring → contradiction → store); structured
creation goes directly to the store.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_memory_manager, get_store
from life_graph.api.openapi_examples import MEMORY_CREATED, MEMORY_DETAIL, PAGINATED_MEMORIES
from life_graph.api.responses import success_response, paginated_response, encode_cursor
from life_graph.core.memory_manager import MemoryManager
from life_graph.models.schemas import MemoryCreate, MemoryResponse, MemoryUpdate
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.postgres import PostgresMemoryStore

router = APIRouter(prefix="/memories", tags=["memories"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create memories from text or structured input",
    responses=MEMORY_CREATED,
)
async def create_memory(
    body: MemoryCreate,
    manager: MemoryManager = Depends(get_memory_manager),
    store: PostgresMemoryStore = Depends(get_store),
):
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
        embedding = await manager.generate_embedding(body.content)
        row = await store.store(body, embedding=embedding)
        return [MemoryResponse.model_validate(row)]

    return success_response(
        data=[MemoryResponse.model_validate(m) for m in memories],
    )


@router.get(
    "/{memory_id}",
    summary="Get a memory by ID",
)
async def get_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Retrieve a single memory by its UUID."""
    row = await store.retrieve(memory_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    return success_response(data=MemoryResponse.model_validate(row))


@router.patch(
    "/{memory_id}",
    summary="Update a memory",
)
async def update_memory(
    memory_id: uuid.UUID,
    body: MemoryUpdate,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Apply a partial update to an existing memory."""
    try:
        row = await store.update(memory_id, body)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    return success_response(data=MemoryResponse.model_validate(row))


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a memory",
    response_class=Response,
)
async def delete_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Delete a memory and cascade to association tables."""
    deleted = await store.delete(memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{memory_id}/unarchive",
    summary="Unarchive a memory",
)
async def unarchive_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Restore an archived memory back to active status.

    Changes the memory's status from 'archived' to 'active',
    making it available for search and recall again.
    """
    try:
        row = await store.unarchive(memory_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory {memory_id} not found",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    return success_response(data=MemoryResponse.model_validate(row))



@router.get(
    "/",
    summary="List memories with optional filters",
)
async def list_memories(
    store: PostgresMemoryStore = Depends(get_store),
    memory_status: str | None = Query(None, alias="status", description="Filter by status"),
    tags: str | None = Query(None, description="Comma-separated tags (array overlap)"),
    min_importance: float | None = Query(None, ge=0.0, le=1.0, description="Minimum importance"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    cursor: str | None = Query(None, description="Cursor for keyset pagination"),
    include_total: bool = Query(False, description="Include total count (may be slow)"),
):
    """List memories with optional status, tag, and importance filters.

    Supports both offset and cursor-based pagination. When a cursor is
    provided, offset is ignored and keyset pagination is used for
    consistent performance on large datasets.
    """
    filters: dict = {}

    if memory_status is not None:
        filters["status"] = memory_status
    if tags is not None:
        filters["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if min_importance is not None:
        filters["min_importance"] = min_importance

    rows, has_more = await store.list_memories(
        filters=filters or None,
        offset=offset,
        limit=limit,
        cursor=cursor,
    )
    memories = [MemoryResponse.model_validate(r) for r in rows]

    # Build next cursor from last item
    next_cursor = None
    if has_more and memories:
        last = memories[-1]
        next_cursor = encode_cursor(
            last.created_at.isoformat(),
            str(last.id),
        )

    # Optional total count
    total = None
    if include_total:
        total = await store.count_memories(filters=filters or None)

    return paginated_response(
        data=memories,
        total=total,
        page_size=limit,
        next_cursor=next_cursor,
        has_more=has_more,
    )


# ── Confidence Decay (Feature 4) ─────────────────────────────────────────────


class DenyRequest(BaseModel):
    """Payload for denying a memory — optionally replacing it with a new fact."""
    replacement: str | None = Field(
        None, description="New content that replaces the denied memory"
    )


@router.post(
    "/{memory_id}/reinforce",
    summary="Reinforce a memory — confirm it is still accurate",
)
async def reinforce_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Confirm that a memory is still accurate.

    Resets confidence to 0.9, updates last_reinforced timestamp,
    and increments the reinforcement counter. Use this when the
    system asks "is this still true?" and the user confirms.
    """
    try:
        row = await store.reinforce(memory_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    return success_response(data=MemoryResponse.model_validate(row))


@router.post(
    "/{memory_id}/deny",
    summary="Deny a memory — mark as no longer accurate",
)
async def deny_memory(
    memory_id: uuid.UUID,
    body: DenyRequest = DenyRequest(),
    store: PostgresMemoryStore = Depends(get_store),
):
    """Mark a memory as superseded because the user says it is no longer true.

    If a replacement string is provided, creates a new memory that
    supersedes the old one (with full provenance chain). The old memory
    is kept in the supersession chain for history.
    """
    try:
        denied, replacement = await store.deny(memory_id, body.replacement)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )

    result = {
        "denied": MemoryResponse.model_validate(denied),
        "replacement": MemoryResponse.model_validate(replacement) if replacement else None,
    }
    return success_response(data=result)

