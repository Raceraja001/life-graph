"""Memory Links API routes — bidirectional Zettelkasten-style links.

Provides endpoints for creating, listing, deleting, and traversing
typed relationships between memories.

All routes are prefixed with ``/memories`` and tagged for OpenAPI docs.
"""

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, HTTPException, Query, status

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import MemoryLinkCreate, MemoryLinkResponse
from life_graph.services import memory_links as link_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memory-links"])


@router.post(
    "/{memory_id}/links",
    status_code=status.HTTP_201_CREATED,
    summary="Create a link between two memories",
)
async def create_link(
    memory_id: uuid.UUID,
    body: MemoryLinkCreate,
):
    """Create a typed link from this memory to another.

    The source_memory_id in the body is ignored — the path parameter
    is used as the source. Link types: BECAUSE, EVIDENCED_BY,
    RELATED_TO, CONTRADICTS, SUPERSEDES, LEADS_TO.
    """
    tenant_id = get_current_tenant_id()
    try:
        target_id = uuid.UUID(body.target_memory_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid target_memory_id format",
        )

    try:
        link = await link_service.create_link(
            source_id=memory_id,
            target_id=target_id,
            link_type=body.link_type,
            strength=body.strength,
            tenant_id=tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        # Catch unique constraint violations
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Link already exists between these memories with this type",
            )
        raise

    return success_response(data=MemoryLinkResponse.model_validate(link))


@router.get(
    "/{memory_id}/links",
    summary="List links for a memory",
)
async def list_links(
    memory_id: uuid.UUID,
    direction: str = Query("both", description="Filter direction: outgoing, incoming, both"),
    link_type: str | None = Query(None, description="Filter by link type"),
):
    """List all links associated with a memory.

    Optionally filter by direction (outgoing/incoming/both) and link type.
    """
    tenant_id = get_current_tenant_id()
    links = await link_service.get_links(
        memory_id=memory_id,
        direction=direction,
        link_type=link_type,
        tenant_id=tenant_id,
    )
    return success_response(
        data=[MemoryLinkResponse.model_validate(link) for link in links]
    )


@router.delete(
    "/links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a memory link",
)
async def delete_link(link_id: uuid.UUID):
    """Remove a link between two memories."""
    deleted = await link_service.delete_link(link_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Link {link_id} not found",
        )


@router.get(
    "/{memory_id}/linked",
    summary="Get linked memories (context expansion)",
)
async def get_linked_memories(
    memory_id: uuid.UUID,
    depth: int = Query(2, ge=1, le=5, description="Traversal depth"),
):
    """Get memories linked to this one via BFS traversal.

    Returns linked memories with their link types, strengths,
    and traversal depth for context expansion.
    """
    tenant_id = get_current_tenant_id()
    linked = await link_service.get_link_graph(
        memory_id=memory_id,
        depth=depth,
        tenant_id=tenant_id,
    )
    return success_response(data=linked)
