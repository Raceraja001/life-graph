"""Intention routes — prospective memory management (T-045).

Provides CRUD for intentions, listing pending items, checking
triggered intentions against the current context, and marking
intentions as completed or dismissed.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_intention_service
from life_graph.api.responses import success_response
from life_graph.models.schemas import IntentionCreate, IntentionResponse
from life_graph.services.intentions import IntentionService

router = APIRouter(prefix="/intentions", tags=["intentions"])


# ── Request schema for triggered check ───────────────────────


class TriggeredCheckRequest(BaseModel):
    """Body for checking which intentions are triggered by current context."""

    context: dict[str, Any] = Field(
        ..., description="Current session context (project, topics, files, etc.)"
    )


# ── Routes ───────────────────────────────────────────────────


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new intention",
)
async def create_intention(
    body: IntentionCreate,
    service: IntentionService = Depends(get_intention_service),
):
    """Create a new prospective memory (intention).

    Supports time-based, event-based, and context-based triggers.
    """
    intention = await service.create(
        content=body.content,
        trigger_type=body.trigger_type or "event",
        trigger_condition=body.trigger_condition,
        trigger_time=body.trigger_time,
        context_match=body.context_match,
        priority=body.priority or "normal",
    )
    return success_response(data=IntentionResponse.model_validate(intention))


@router.get(
    "/",
    summary="List pending intentions",
)
async def list_pending(
    service: IntentionService = Depends(get_intention_service),
):
    """Return all pending intentions, newest first."""
    rows = await service.list_pending()
    return success_response(data=[IntentionResponse.model_validate(r) for r in rows])


@router.post(
    "/triggered",
    summary="Get currently triggered intentions",
)
async def get_triggered(
    body: TriggeredCheckRequest,
    service: IntentionService = Depends(get_intention_service),
):
    """Check which pending intentions are triggered by the given context.

    Evaluates time-based, event-based, and context-based triggers
    against the provided context dict.
    """
    rows = await service.get_triggered(body.context)
    return success_response(data=[IntentionResponse.model_validate(r) for r in rows])


@router.patch(
    "/{intention_id}/complete",
    summary="Mark an intention as completed",
)
async def complete_intention(
    intention_id: uuid.UUID,
    service: IntentionService = Depends(get_intention_service),
):
    """Mark a pending intention as completed."""
    try:
        intention = await service.complete(str(intention_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intention {intention_id} not found",
        )
    return success_response(data=IntentionResponse.model_validate(intention))


@router.patch(
    "/{intention_id}/dismiss",
    summary="Dismiss an intention",
)
async def dismiss_intention(
    intention_id: uuid.UUID,
    service: IntentionService = Depends(get_intention_service),
):
    """Dismiss a pending intention without completing it."""
    try:
        intention = await service.dismiss(str(intention_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intention {intention_id} not found",
        )
    return success_response(data=IntentionResponse.model_validate(intention))
