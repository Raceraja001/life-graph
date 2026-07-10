"""Evidence CRUD + semantic search routes (Era 4 Personal AI)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_evidence_store
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import EvidenceCreate, EvidenceResponse
from life_graph.services.evidence_store import EvidenceStore

router = APIRouter(prefix="/evidence", tags=["evidence"])


# ── Search request body ──────────────────────────────────────


class EvidenceSearchBody(BaseModel):
    """Body for semantic evidence search."""

    query: str = Field(..., min_length=1, description="Natural language query")
    limit: int = Field(10, ge=1, le=50)


# ── Routes ───────────────────────────────────────────────────


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Add evidence to a preference",
)
async def create_evidence(
    body: EvidenceCreate,
    store: EvidenceStore = Depends(get_evidence_store),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Create a new evidence item linked to a preference.

    Deduplicates by source_url (returns 409 if duplicate).
    Applies credibility multiplier based on source_type.
    """
    try:
        evidence = await store.create(tenant_id, body.model_dump(exclude_none=True))
    except ValueError as e:
        err_msg = str(e)
        if "already exists" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=err_msg,
        )
    return success_response(data=EvidenceResponse.model_validate(evidence))


@router.get(
    "/for-preference/{preference_id}",
    summary="List evidence for a preference",
)
async def list_evidence_for_preference(
    preference_id: uuid.UUID,
    store: EvidenceStore = Depends(get_evidence_store),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """List all evidence for a preference, grouped by stance."""
    result = await store.list_for_preference(tenant_id, preference_id)
    return success_response(
        data={
            "supports": [EvidenceResponse.model_validate(e) for e in result["supports"]],
            "contradicts": [EvidenceResponse.model_validate(e) for e in result["contradicts"]],
            "neutral": [EvidenceResponse.model_validate(e) for e in result["neutral"]],
            "net_score": result["net_score"],
            "total_count": result["total_count"],
        },
    )


@router.get(
    "/{evidence_id}",
    summary="Get a single evidence item",
)
async def get_evidence(
    evidence_id: uuid.UUID,
    store: EvidenceStore = Depends(get_evidence_store),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Retrieve a single evidence item by ID."""
    evidence = await store.get(tenant_id, evidence_id)
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence {evidence_id} not found",
        )
    return success_response(data=EvidenceResponse.model_validate(evidence))


@router.post(
    "/search",
    summary="Semantic evidence search",
)
async def search_evidence(
    body: EvidenceSearchBody,
    store: EvidenceStore = Depends(get_evidence_store),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Search evidence across all preferences using natural language."""
    results = await store.search(tenant_id, body.query, limit=body.limit)
    return success_response(
        data=[
            {
                "evidence": EvidenceResponse.model_validate(r["evidence"]),
                "similarity": r["similarity"],
            }
            for r in results
        ],
    )


@router.delete(
    "/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete evidence",
    response_class=Response,
)
async def delete_evidence(
    evidence_id: uuid.UUID,
    store: EvidenceStore = Depends(get_evidence_store),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Soft-delete evidence and recalculate parent preference confidence."""
    deleted = await store.delete(tenant_id, evidence_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence {evidence_id} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
