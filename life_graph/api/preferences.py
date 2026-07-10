"""Preference CRUD + semantic search routes (Era 4 Personal AI)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_preference_store
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import (
    PreferenceCreate,
    PreferenceResponse,
    PreferenceUpdate,
)
from life_graph.services.preference_store import PreferenceStore

router = APIRouter(prefix="/preferences", tags=["preferences"])


# ── Search request body ──────────────────────────────────────


class PreferenceSearchBody(BaseModel):
    """Body for semantic preference search."""

    query: str = Field(..., min_length=1, description="Natural language query")
    limit: int = Field(10, ge=1, le=50)
    min_similarity: float = Field(0.3, ge=0.0, le=1.0)


# ── Routes ───────────────────────────────────────────────────


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a preference",
)
async def create_preference(
    body: PreferenceCreate,
    store: PreferenceStore = Depends(get_preference_store),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Create a new user preference with embedding and confidence tracking."""
    pref = await store.create(tenant_id, body.model_dump(exclude_none=True))
    return success_response(data=PreferenceResponse.model_validate(pref))


@router.get(
    "/",
    summary="List preferences with filters",
)
async def list_preferences(
    store: PreferenceStore = Depends(get_preference_store),
    tenant_id: str = Depends(get_current_tenant_id),
    pref_status: str | None = Query(None, alias="status", description="Filter by status"),
    tags: str | None = Query(None, description="Comma-separated tags"),
    category: str | None = Query(None, description="Filter by category"),
    source: str | None = Query(None, description="Filter by source"),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    stale_days: int | None = Query(None, ge=1, description="Only stale preferences"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List preferences with optional filtering."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    rows = await store.list(
        tenant_id,
        status=pref_status,
        tags=tag_list,
        category=category,
        source=source,
        min_confidence=min_confidence,
        stale_days=stale_days,
        limit=limit,
        offset=offset,
    )
    return success_response(
        data=[PreferenceResponse.model_validate(r) for r in rows],
    )


@router.get(
    "/{preference_id}",
    summary="Get a preference by ID",
)
async def get_preference(
    preference_id: uuid.UUID,
    store: PreferenceStore = Depends(get_preference_store),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Retrieve a single preference."""
    pref = await store.get(tenant_id, preference_id)
    if pref is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference {preference_id} not found",
        )
    return success_response(data=PreferenceResponse.model_validate(pref))


@router.patch(
    "/{preference_id}",
    summary="Update a preference",
)
async def update_preference(
    preference_id: uuid.UUID,
    body: PreferenceUpdate,
    store: PreferenceStore = Depends(get_preference_store),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Partially update a preference."""
    try:
        pref = await store.update(
            tenant_id, preference_id, body.model_dump(exclude_none=True)
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference {preference_id} not found",
        )
    return success_response(data=PreferenceResponse.model_validate(pref))


@router.delete(
    "/{preference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a preference",
    response_class=Response,
)
async def delete_preference(
    preference_id: uuid.UUID,
    store: PreferenceStore = Depends(get_preference_store),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Soft-delete a preference (sets status to archived)."""
    deleted = await store.delete(tenant_id, preference_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference {preference_id} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/search",
    summary="Semantic preference search",
)
async def search_preferences(
    body: PreferenceSearchBody,
    store: PreferenceStore = Depends(get_preference_store),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Search preferences using natural language via pgvector cosine similarity."""
    results = await store.search(
        tenant_id,
        body.query,
        limit=body.limit,
        min_similarity=body.min_similarity,
    )
    return success_response(
        data=[
            {
                "preference": PreferenceResponse.model_validate(r["preference"]),
                "similarity": r["similarity"],
            }
            for r in results
        ],
    )
