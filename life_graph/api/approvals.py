"""Approvals API — the unified human-in-the-loop feed.

`GET /approvals` lists items awaiting a decision (reconciling producers first);
`POST /approvals/{id}/approve|reject` resolves one and runs its side-effect.

See docs/specs/approvals-feed.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.api.responses import success_response
from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.approvals import ApprovalAlreadyResolvedError, ApprovalService
from life_graph.storage.database import get_session

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ResolveBody(BaseModel):
    """Optional metadata for an approve/reject."""

    note: str | None = None
    resolved_by: str | None = None


@router.get("", summary="List items awaiting a decision")
async def list_approvals(
    status: str = Query("pending", description="pending | approved | rejected | all"),
    limit: int = Query(100, ge=1, le=500),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Reconcile producers, then return approvals newest-first."""
    service = ApprovalService(session)
    data = await service.list_approvals(tenant_id, status=status, limit=limit)
    return success_response(data)


async def _resolve(
    approval_id: str,
    decision: str,
    body: ResolveBody | None,
    tenant_id: str,
    session: AsyncSession,
):
    service = ApprovalService(session)
    note = body.note if body else None
    resolved_by = body.resolved_by if body else None
    try:
        result = await service.resolve(
            tenant_id, approval_id, decision, note=note, resolved_by=resolved_by
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Approval not found") from None
    except ApprovalAlreadyResolvedError as exc:
        raise HTTPException(status_code=409, detail=f"Approval already {exc}") from None

    await session.commit()  # commit before emitting so subscribers see the change
    await event_bus.emit(
        EventType.APPROVAL_RESOLVED,
        {
            "id": result["id"],
            "kind": result["kind"],
            "status": result["status"],
            "tenant_id": tenant_id,
        },
        source="approvals",
    )
    return success_response(result)


@router.post("/{approval_id}/approve", summary="Approve an item (runs its side-effect)")
async def approve_approval(
    approval_id: str,
    body: ResolveBody | None = Body(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    return await _resolve(approval_id, "approve", body, tenant_id, session)


@router.post("/{approval_id}/reject", summary="Reject an item")
async def reject_approval(
    approval_id: str,
    body: ResolveBody | None = Body(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    return await _resolve(approval_id, "reject", body, tenant_id, session)
