"""Shared Context routes (Era 7 — Phase 6).

Provides endpoints for creating, searching, and retrieving
shared context entries across agents.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_shared_context_service
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.shared_context import SharedContextService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shared-context", tags=["shared-context"])


# ── Request Schemas ──────────────────────────────────────────


class SharedContextCreate(BaseModel):
    """Payload for creating a shared context entry."""

    content: str = Field(..., min_length=1, description="Context content text")
    context_type: str = Field("observation", description="Type: fact, decision, observation, insight")
    project_id: uuid.UUID | None = Field(None, description="Associated project ID")
    source_agent: str | None = Field(None, description="Agent that generated this context")
    source_task_id: uuid.UUID | None = Field(None, description="Task that generated this context")
    relevance_score: float = Field(1.0, ge=0.0, le=1.0, description="Initial relevance score")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# ── Routes ───────────────────────────────────────────────────


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a shared context entry",
)
async def create_context(
    body: SharedContextCreate,
    svc: SharedContextService = Depends(get_shared_context_service),
):
    """Create a new shared context entry.

    Generates an embedding, computes a content hash for dedup,
    and checks for near-duplicates (cosine ≥ 0.95 → merge).
    """
    tenant_id = get_current_tenant_id()

    entry = await svc.create(
        tenant_id=tenant_id,
        data=body.model_dump(),
    )

    return success_response(data={
        "id": str(entry.id),
        "content": entry.content,
        "context_type": entry.context_type,
        "project_id": str(entry.project_id) if entry.project_id else None,
        "source_agent": entry.source_agent,
        "relevance_score": entry.relevance_score,
        "access_count": entry.access_count,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    })


@router.get(
    "/{project_id}",
    summary="Search shared context by project",
)
async def search_context(
    project_id: uuid.UUID,
    query: str = Query("", description="Natural language search query"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    min_similarity: float = Query(0.3, ge=0.0, le=1.0, description="Minimum similarity"),
    svc: SharedContextService = Depends(get_shared_context_service),
):
    """Search shared context entries within a project.

    Uses pgvector cosine similarity for semantic search.
    Increments access_count on returned results.
    """
    tenant_id = get_current_tenant_id()

    results = await svc.search(
        tenant_id=tenant_id,
        project_id=project_id,
        query=query,
        limit=limit,
        min_similarity=min_similarity,
    )

    return success_response(data=results)


@router.get(
    "/thread/{root_task_id}",
    summary="Get context from a task thread",
)
async def get_thread_context(
    root_task_id: uuid.UUID,
    svc: SharedContextService = Depends(get_shared_context_service),
):
    """Retrieve all shared context entries from a task tree.

    Walks the task hierarchy starting from root_task_id and
    returns all context entries produced by tasks in the tree.
    """
    tenant_id = get_current_tenant_id()

    results = await svc.get_thread_context(
        tenant_id=tenant_id,
        root_task_id=root_task_id,
    )

    return success_response(data=results)
