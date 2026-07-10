"""Identity management routes (Phase B — T-061/T-062).

Exposes the IdentityService timeline, belief queries, stale-belief
detection, and challenge workflow as REST endpoints.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from life_graph.api.responses import success_response
from life_graph.models.schemas import MemoryResponse
from life_graph.services.identity import IdentityService
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/identity", tags=["identity"])


# ── Dependency ───────────────────────────────────────────────


def get_identity_service():
    """Return an IdentityService wired to the app session factory."""
    return IdentityService(session_factory=async_session)


# ── Response schemas ─────────────────────────────────────────


class TimelineChapter(BaseModel):
    """A single month-period chapter in the identity timeline."""

    period: str
    active: list[MemoryResponse] = Field(default_factory=list)
    superseded: list[MemoryResponse] = Field(default_factory=list)


class StaleBelief(BaseModel):
    """A stale belief with its challenge prompt."""

    memory: MemoryResponse
    prompt: str
    days_stale: int


class ChallengeRequest(BaseModel):
    """Body for challenging a stale belief."""

    memory_id: str = Field(..., description="UUID of the memory to challenge")


class ChallengeResponse(BaseModel):
    """Result of a belief challenge."""

    memory_id: str
    status: str
    message: str


# ── Routes ───────────────────────────────────────────────────


@router.get(
    "/timeline",
    summary="Get identity timeline",
)
async def get_timeline(
    domain: str | None = Query(None, description="Optional domain filter"),
    service: IdentityService = Depends(get_identity_service),
):
    """Return the full identity timeline grouped by month.

    Each chapter contains active and superseded beliefs for that
    time period.  An optional *domain* query param filters by tag.
    """
    # NOTE: IdentityService.get_timeline() does not yet support domain filtering.
    # The query param is accepted for forward compatibility.
    chapters = await service.get_timeline()

    return success_response(data=[
        TimelineChapter(
            period=ch["period"],
            active=[MemoryResponse.model_validate(m) for m in ch["active"]],
            superseded=[MemoryResponse.model_validate(m) for m in ch["superseded"]],
        )
        for ch in chapters
    ])


@router.get(
    "/beliefs",
    summary="Get active beliefs",
)
async def get_active_beliefs(
    domain: str | None = Query(None, description="Optional domain filter"),
    service: IdentityService = Depends(get_identity_service),
):
    """Return currently active identity / preference / belief memories.

    Ordered by importance (highest first).
    """
    memories = await service.get_current_identity()
    return success_response(data=[MemoryResponse.model_validate(m) for m in memories])


@router.get(
    "/stale",
    summary="Find stale beliefs",
)
async def find_stale_beliefs(
    days: int = Query(90, ge=1, description="Days since last access to consider stale"),
    service: IdentityService = Depends(get_identity_service),
):
    """Find identity beliefs not accessed in *days* days.

    Returns challenge prompts that can be shown to the user for
    review and confirmation/retirement.
    """
    # Convert days to months for the service API
    stale_months = max(days // 30, 1)
    challenges = await service.challenge_stale_beliefs(stale_months=stale_months)

    return success_response(data=[
        StaleBelief(
            memory=MemoryResponse.model_validate(ch["memory"]),
            prompt=ch["prompt"],
            days_stale=ch["days_stale"],
        )
        for ch in challenges
    ])


@router.post(
    "/challenge",
    summary="Challenge a belief",
)
async def challenge_belief(
    body: ChallengeRequest,
    service: IdentityService = Depends(get_identity_service),
):
    """Mark a belief as needing review by the user.

    Sets the memory's status to 'uncertain' so it surfaces
    in future stale-belief checks until confirmed or retired.
    """
    try:
        await service.respond_to_challenge(body.memory_id, "uncertain")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return success_response(data=ChallengeResponse(
        memory_id=body.memory_id,
        status="challenged",
        message=f"Memory {body.memory_id} marked as uncertain for review",
    ))
