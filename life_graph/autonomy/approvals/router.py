"""FastAPI router for approval queue."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from life_graph.api.responses import success_response
from life_graph.autonomy.approvals.schemas import (
    ApprovalResponse,
    BatchResolveRequest,
    BatchResolveResponse,
    ResolveRequest,
)
from life_graph.autonomy.approvals.service import _serialize
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

    from life_graph.autonomy.models import ApprovalQueueEntry

    async with async_session() as session:
        q = select(ApprovalQueueEntry).where(ApprovalQueueEntry.tenant_id == tenant_id)

        if status:
            q = q.where(ApprovalQueueEntry.status == status)
        if risk_level:
            q = q.where(ApprovalQueueEntry.risk_level == risk_level)
        if agent_id:
            q = q.where(ApprovalQueueEntry.agent_id == agent_id)

        q = q.order_by(ApprovalQueueEntry.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(q)
        entries = result.scalars().all()

    return success_response(
        data=[
            ApprovalResponse(**_serialize(e)).model_dump(mode="json")
            for e in entries
        ],
    )


@router.post("/{approval_id}/resolve", response_model=None)
async def resolve_approval(approval_id: str, request: ResolveRequest):
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

    resolved_status = "approved" if request.decision == "approve" else "rejected"
    return success_response(
        data={"id": approval_id, "status": resolved_status},
    )


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
