"""FastAPI router for approval queue.

Who resolved comes from how the server recognised the caller
(api/approval_identity.py, shared with the unified ``/approvals`` feed), never
from ``resolved_by`` in the body; with ``approvals_require_owner`` on, only the
owner may resolve, singly or in a batch. Whatever the setting, a caller that
is not the owner cannot decide an entry it asked for itself (``requested_by``,
migration 061), and a batch with no ids and no filter must say ``all: true``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from life_graph.api.approval_identity import (
    note_with_claim,
    refuse_self_approval,
    require_owner,
    resolver,
)
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
    status: str | None = Query("pending"),
    risk_level: str | None = Query(None),
    agent_id: str | None = Query(None),
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
        data=[ApprovalResponse(**_serialize(e)).model_dump(mode="json") for e in entries],
    )


@router.post("/{approval_id}/resolve", response_model=None)
async def resolve_approval(approval_id: str, body: ResolveRequest, request: Request):
    """Resolve (approve/reject) an approval entry."""
    require_owner(request)
    tenant_id = get_current_tenant_id()

    from life_graph.runtime import get_approval_service

    service = get_approval_service()

    try:
        await service.resolve(
            tenant_id=tenant_id,
            approval_id=approval_id,
            decision=body.decision,
            note=note_with_claim(body.note, body.resolved_by),
            resolved_by=resolver(request),
            also_trust=body.also_trust,
            guard=lambda requested_by: refuse_self_approval(request, requested_by),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    resolved_status = "approved" if body.decision == "approve" else "rejected"
    return success_response(
        data={"id": approval_id, "status": resolved_status},
    )


@router.post("/batch", response_model=None)
async def batch_resolve(body: BatchResolveRequest, request: Request):
    """Batch resolve approvals by ids or filter (or every pending one with ``all``)."""
    require_owner(request)
    if not body.has_filter() and not body.all:
        raise HTTPException(
            status_code=422,
            detail=(
                "Name the approvals (approval_ids) or a filter (agent_id, project_id,"
                " risk_level); to resolve every pending approval, send all: true."
            ),
        )
    tenant_id = get_current_tenant_id()

    from life_graph.runtime import get_approval_service

    service = get_approval_service()

    result = await service.batch_resolve(
        tenant_id=tenant_id,
        filter_criteria={
            "approval_ids": body.approval_ids,
            "agent_id": body.agent_id,
            "project_id": body.project_id,
            "risk_level": body.risk_level,
        },
        decision=body.decision,
        note=note_with_claim(body.note, body.resolved_by),
        resolved_by=resolver(request),
        guard=lambda requested_by: refuse_self_approval(request, requested_by),
    )

    return success_response(
        data=BatchResolveResponse(
            resolved_count=result["resolved_count"],
            resolved_ids=result["resolved_ids"],
        ).model_dump(mode="json"),
    )
