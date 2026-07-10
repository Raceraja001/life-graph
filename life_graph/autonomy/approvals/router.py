"""FastAPI router for approval queue."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from life_graph.api.responses import success_response
from life_graph.autonomy.approvals.schemas import (
    ApprovalResponse,
    BatchResolveRequest,
    BatchResolveResponse,
    ResolveRequest,
)
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=None)
async def list_approvals(
    status: Optional[str] = Query("pending"),
    risk_level: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List approval queue entries with optional filters."""
    tenant_id = get_current_tenant_id()

    from life_graph.models.db import ApprovalQueue

    async with async_session() as session:
        q = select(ApprovalQueue).where(ApprovalQueue.tenant_id == tenant_id)

        if status:
            q = q.where(ApprovalQueue.status == status)
        if risk_level:
            q = q.where(ApprovalQueue.risk_level == risk_level)
        if agent_id:
            q = q.where(ApprovalQueue.agent_id == agent_id)

        q = q.order_by(ApprovalQueue.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(q)
        entries = result.scalars().all()

    return success_response(
        data=[
            ApprovalResponse(
                id=e.id,
                tenant_id=e.tenant_id,
                action_id=e.action_id,
                agent_id=e.agent_id,
                project_id=e.project_id,
                action_type=e.action_type,
                risk_level=e.risk_level,
                command=e.command,
                description=e.description,
                status=e.status,
                resolved_by=e.resolved_by,
                resolved_at=e.resolved_at,
                decision_note=e.decision_note,
                expires_at=e.expires_at,
                escalation_level=e.escalation_level or 0,
                created_at=e.created_at,
            ).model_dump(mode="json")
            for e in entries
        ],
    )


@router.post("/{approval_id}/resolve", response_model=None)
async def resolve_approval(approval_id: UUID, request: ResolveRequest):
    """Resolve (approve/reject) an approval entry."""
    tenant_id = get_current_tenant_id()

    from life_graph.api.dependencies import get_approval_service
    service = get_approval_service()

    try:
        await service.resolve(
            tenant_id=tenant_id,
            approval_id=approval_id,
            decision=request.decision,
            note=request.note,
            resolved_by=request.resolved_by,
            also_trust=request.also_trust,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return success_response(message=f"Approval {request.decision}d")


@router.post("/batch", response_model=None)
async def batch_resolve(request: BatchResolveRequest):
    """Batch resolve approvals by filter."""
    tenant_id = get_current_tenant_id()

    from life_graph.api.dependencies import get_approval_service
    service = get_approval_service()

    result = await service.batch_resolve(
        tenant_id=tenant_id,
        filter_criteria={
            "approval_ids": request.approval_ids,
            "agent_id": request.agent_id,
            "project_id": request.project_id,
            "risk_level": request.risk_level,
        },
        decision=request.decision,
        note=request.note,
        resolved_by=request.resolved_by,
    )

    return success_response(
        data=BatchResolveResponse(
            resolved_count=result["resolved_count"],
            resolved_ids=result["resolved_ids"],
        ).model_dump(mode="json"),
    )
