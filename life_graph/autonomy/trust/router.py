"""Trust score API router.

Endpoints for querying trust scores, manual overrides, and decay.
Prefix: /autonomy/trust

A manual override decides how much an agent may do on its own, so it is the
owner's alone (api/approval_identity.py ``owner_only``), and ``override_by``
is who the server saw calling, not the body's ``by``. Decay only ever lowers
scores (TrustCalculator.apply_decay), so it stays open to any service key.

Each override leaves one audit_log row (``trust_override``) with the score
before and after and who made it. The override is committed first; the
audit row is best effort, as for the kill switch: a failed write is logged
as an error and the override stands.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.api.approval_identity import note_with_claim, owner_only, resolver
from life_graph.api.responses import success_response
from life_graph.autonomy.models import TrustScore
from life_graph.autonomy.trust.schemas import TrustOverrideRequest, TrustScoreResponse
from life_graph.autonomy.trust.service import TrustScoreService
from life_graph.core.tenant import get_current_tenant_id
from life_graph.runtime import get_audit_service
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
    return success_response([TrustScoreResponse.model_validate(s) for s in scores])


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
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Manually override a trust score (owner only)."""
    owner_only(request, "Overriding a trust score")
    svc = TrustScoreService(session)
    old_score = await _score_in_force(session, tenant_id, body)
    reason = note_with_claim(body.reason, body.by)
    by = resolver(request)
    score = await svc.override(
        tenant_id=tenant_id,
        agent_id=body.agent_id,
        action_type=body.action_type,
        project_id=body.project_id,
        score=body.score,
        reason=reason,
        by=by,
    )
    await session.commit()
    try:
        await get_audit_service().log_trust_override(
            tenant_id=tenant_id,
            agent_id=body.agent_id,
            project_id=body.project_id,
            old_score=old_score,
            new_score=body.score,
            reason=reason,
            overridden_by=by,
            trust_action_type=body.action_type,
        )
    except Exception:
        # Best effort, like the kill switch: the override stands.
        logger.error("Trust override for %s not written to the audit log", tenant_id,
                     exc_info=True)  # fmt: skip
    return success_response(TrustScoreResponse.model_validate(score))


async def _score_in_force(
    session: AsyncSession, tenant_id: str, body: TrustOverrideRequest
) -> float | None:
    """The score that applied before this override, for the audit row.

    The old manual override if there was one, else the earned score; None when
    the agent has no score yet for this action (the override creates it).
    """
    stmt = select(TrustScore).where(
        TrustScore.tenant_id == tenant_id,
        TrustScore.agent_id == body.agent_id,
        TrustScore.action_type == body.action_type,
    )
    if body.project_id is not None:
        stmt = stmt.where(TrustScore.project_id == body.project_id)
    else:
        stmt = stmt.where(TrustScore.project_id.is_(None))
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    current = row.manual_override if row.manual_override is not None else row.score
    return float(current) if current is not None else None


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
