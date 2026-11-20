"""Approvals API — the unified human-in-the-loop feed.

`GET /approvals` lists items awaiting a decision (reconciling producers first);
`POST /approvals/{id}/approve|reject` resolves one and runs its side-effect.

Who decided (``resolved_by``) comes from how the server recognised the
caller, never from the request body (api/approval_identity.py, shared with
the autonomy queue). With ``approvals_require_owner`` on, only the owner (an
owner key or a paired phone) may approve or reject; whatever the setting, a
non-owner caller may not approve an approval for a dev task it started.

See docs/specs/approvals-feed.md.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.api.approval_identity import (
    OWNER_REQUIRED,
    note_with_claim,
    refuse_self_approval,
    require_owner,
    resolver,
)
from life_graph.api.responses import success_response
from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import AgentTask, Approval
from life_graph.services.approvals import (
    ApprovalActionError,
    ApprovalAlreadyResolvedError,
    ApprovalService,
)
from life_graph.storage.database import get_session

router = APIRouter(prefix="/approvals", tags=["approvals"])

__all__ = ["OWNER_REQUIRED", "ResolveBody", "resolver", "router"]


class ResolveBody(BaseModel):
    """Optional metadata for an approve/reject."""

    note: str | None = None
    # Kept for old clients. Not trusted: who decided is the server's to say
    # (resolver); a value here is only recorded in the note.
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


def _note(body: ResolveBody | None) -> str | None:
    """The body's note, plus whatever name the client claimed (unverified)."""
    if body is None:
        return None
    return note_with_claim(body.note, body.resolved_by)


async def _requested_by(session: AsyncSession, tenant_id: str, approval_id: str) -> str | None:
    """Who asked for the work an approval is about, when that was recorded.

    Dev-task approvals (``driver_plan``, ``driver_pr``, ``driver_merge``,
    deploys) name their task in ``payload.task_id``; ``POST /drivers/tasks``
    stamps the starting caller on the task as ``properties.requested_by``. A
    task fanned out from an approved plan has no stamp of its own and inherits
    its plan's (``properties.plan_task_id``). None for everything else.
    """
    try:
        appr_id = uuid.UUID(str(approval_id))
    except ValueError:
        return None
    payload = (
        await session.execute(
            select(Approval.payload).where(Approval.id == appr_id, Approval.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    task_id = (payload or {}).get("task_id")
    for _ in range(2):  # the task itself, then the plan it came from
        try:
            task_uuid = uuid.UUID(str(task_id))
        except (TypeError, ValueError):
            return None
        props = (
            await session.execute(
                select(AgentTask.properties).where(
                    AgentTask.id == task_uuid, AgentTask.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none() or {}
        if props.get("requested_by"):
            return str(props["requested_by"])
        task_id = props.get("plan_task_id")
    return None


async def _resolve(
    approval_id: str,
    decision: str,
    body: ResolveBody | None,
    tenant_id: str,
    session: AsyncSession,
    resolved_by: str | None = None,
):
    service = ApprovalService(session)
    note = _note(body)
    try:
        result = await service.resolve(
            tenant_id, approval_id, decision, note=note, resolved_by=resolved_by
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Approval not found") from None
    except ApprovalAlreadyResolvedError as exc:
        raise HTTPException(status_code=409, detail=f"Approval already {exc}") from None
    except ApprovalActionError as exc:
        # Not committed: the item stays pending so it can be approved again.
        await session.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from None

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


async def _decide(
    approval_id: str,
    decision: str,
    request: Request,
    body: ResolveBody | None,
    tenant_id: str,
    session: AsyncSession,
):
    require_owner(request)
    if decision == "approve":
        # Withdrawing one's own request (reject) stays allowed: it can only
        # stop work, never start it.
        refuse_self_approval(request, await _requested_by(session, tenant_id, approval_id))
    return await _resolve(approval_id, decision, body, tenant_id, session, resolver(request))


@router.post("/{approval_id}/approve", summary="Approve an item (runs its side-effect)")
async def approve_approval(
    approval_id: str,
    request: Request,
    body: ResolveBody | None = Body(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    return await _decide(approval_id, "approve", request, body, tenant_id, session)


@router.post("/{approval_id}/reject", summary="Reject an item")
async def reject_approval(
    approval_id: str,
    request: Request,
    body: ResolveBody | None = Body(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    return await _decide(approval_id, "reject", request, body, tenant_id, session)
