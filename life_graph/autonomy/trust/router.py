"""Trust score API router.

Endpoints for querying trust scores, manual overrides, and decay.
Prefix: /autonomy/trust
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.api.responses import success_response
from life_graph.autonomy.models import TrustScore
from life_graph.autonomy.trust.schemas import TrustOverrideRequest, TrustScoreResponse
from life_graph.autonomy.trust.service import TrustScoreService
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trust", tags=["autonomy-trust"])


# ── Trust Scores ──────────────────────────────────────────────


@router.get("/scores")
async def list_scores(
    agent_id: str | None = Query(None),
    project_id: str | None = Query(None),
    action_type: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """List trust scores with optional filters."""
    svc = TrustScoreService(session)
    scores = await svc.get_scores(
        tenant_id=tenant_id,
        agent_id=agent_id,
        project_id=project_id,
        action_type=action_type,
    )
    return success_response(
        [TrustScoreResponse.model_validate(s) for s in scores]
    )


@router.get("/scores/{score_id}")
async def get_score(
    score_id: str,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Get a single trust score by ID."""
    stmt = select(TrustScore).where(
        TrustScore.id == score_id,
        TrustScore.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    score = result.scalar_one_or_none()
    if score is None:
        raise HTTPException(status_code=404, detail="Trust score not found")
    return success_response(TrustScoreResponse.model_validate(score))


# ── Manual Override ───────────────────────────────────────────


@router.post("/override")
async def override_trust(
    body: TrustOverrideRequest,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Manually override a trust score."""
    svc = TrustScoreService(session)
    score = await svc.override(
        tenant_id=tenant_id,
        agent_id=body.agent_id,
        action_type=body.action_type,
        project_id=body.project_id,
        score=body.score,
        reason=body.reason,
        by=body.by,
    )
    return success_response(TrustScoreResponse.model_validate(score))


# ── Decay ─────────────────────────────────────────────────────


@router.post("/decay")
async def trigger_decay(
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Trigger time-based decay for all stale trust scores."""
    svc = TrustScoreService(session)
    count = await svc.decay_all(tenant_id)
    return success_response({"decayed_count": count})
