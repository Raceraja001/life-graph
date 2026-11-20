"""FastAPI router for approval queue.

Who resolved comes from how the server recognised the caller
(api/approval_identity.py, shared with the unified ``/approvals`` feed), never
from ``resolved_by`` in the body; with ``approvals_require_owner`` on, only the
owner may resolve, singly or in a batch. Whatever the setting, a caller that
is not the owner cannot decide an entry it asked for itself (``requested_by``,
migration 061), and a batch with no ids and no filter must say ``all: true``.

An entry with a linked action is decided through its copy in the unified
feed (``_decide_in_feed``), the single path that runs the action; both
stores then hold the same decision (docs/specs/approvals-feed.md, "Which
store is authoritative per kind"). Conflicts answer 409.
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


async def _decide_in_feed(
    tenant_id: str, feed_id: str, decision: str, note: str | None, resolved_by: str
) -> dict:
    """Decide an entry through its feed copy; HTTP errors as the feed's routes give them.

    An entry with a linked action has a copy in the unified feed, and the
    feed's approve is the one path that runs the action (with the
    at-most-once claim, services/approvals.py); it resolves this queue entry
    too. Approving here directly used to mark the entry approved and run
    nothing, and its copy stayed pending (audit H9).
    """
    from life_graph.services.approvals import (
        ApprovalActionError,
        ApprovalAlreadyResolvedError,
        resolve_feed_copy,
    )

    try:
        return await resolve_feed_copy(
            async_session, tenant_id, feed_id, decision, note, resolved_by
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Approval not found") from None
    except ApprovalAlreadyResolvedError as exc:
        raise HTTPException(status_code=409, detail=f"Approval already {exc}") from None
    except ApprovalActionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@router.post("/{approval_id}/resolve", response_model=None)
async def resolve_approval(approval_id: str, body: ResolveRequest, request: Request):
    """Resolve (approve/reject) an approval entry.

    An entry with a linked action is decided through its feed copy (approve
    runs the action there); anything else is resolved here. Either way both
    stores end with the same decision.
    """
    require_owner(request)
    tenant_id = get_current_tenant_id()

    from life_graph.autonomy.approvals.service import QueueConflictError
    from life_graph.runtime import get_approval_service

    service = get_approval_service()
    note = note_with_claim(body.note, body.resolved_by)
    who = resolver(request)

    copies = await service.pending_feed_copies(tenant_id, [approval_id])
    if approval_id in copies:
        entries = await service.match_pending(tenant_id, {"approval_ids": [approval_id]})
        for entry in entries:
            refuse_self_approval(request, getattr(entry, "requested_by", None))
        result = await _decide_in_feed(tenant_id, copies[approval_id], body.decision, note, who)
        return success_response(data={"id": approval_id, "status": result["status"]})

    try:
        await service.resolve(
            tenant_id=tenant_id,
            approval_id=approval_id,
            decision=body.decision,
            note=note,
            resolved_by=who,
            guard=lambda requested_by: refuse_self_approval(request, requested_by),
        )
    except QueueConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
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

    from life_graph.autonomy.approvals.service import QueueConflictError
    from life_graph.runtime import get_approval_service

    service = get_approval_service()
    note = note_with_claim(body.note, body.resolved_by)
    who = resolver(request)
    filter_criteria = {
        "approval_ids": body.approval_ids,
        "agent_id": body.agent_id,
        "project_id": body.project_id,
        "risk_level": body.risk_level,
    }

    # The self-approval check covers every matched entry before anything is
    # decided, as before; entries with a linked action then go through the
    # feed one by one (each may run its action), the rest in one transaction.
    entries = await service.match_pending(tenant_id, filter_criteria)
    for entry in entries:
        refuse_self_approval(request, getattr(entry, "requested_by", None))
    copies = await service.pending_feed_copies(tenant_id, [str(e.id) for e in entries])
    plain = [str(e.id) for e in entries if str(e.id) not in copies]

    resolved_ids: list[str] = []
    if not copies or plain:
        try:
            result = await service.batch_resolve(
                tenant_id=tenant_id,
                # Unchanged when nothing goes through the feed; otherwise
                # exactly the entries that do not.
                filter_criteria={"approval_ids": plain} if copies else filter_criteria,
                decision=body.decision,
                note=note,
                resolved_by=who,
                guard=lambda requested_by: refuse_self_approval(request, requested_by),
            )
        except QueueConflictError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        resolved_ids.extend(result["resolved_ids"])

    failed: list[dict] = []
    for entry_id, feed_id in copies.items():
        try:
            await _decide_in_feed(tenant_id, feed_id, body.decision, note, who)
        except HTTPException as exc:
            failed.append({"id": entry_id, "status_code": exc.status_code, "error": exc.detail})
            continue
        resolved_ids.append(entry_id)

    return success_response(
        data=BatchResolveResponse(
            resolved_count=len(resolved_ids),
            resolved_ids=resolved_ids,
            failed=failed,
        ).model_dump(mode="json"),
    )
