"""Approvals API — the unified human-in-the-loop feed.

`GET /approvals` lists items awaiting a decision (reconciling producers first);
`POST /approvals/{id}/approve|reject` resolves one and runs its side-effect.

Who decided (``resolved_by``) comes from how the server recognised the
caller, never from the request body. With ``approvals_require_owner`` on,
only the owner (an owner key or a paired phone) may approve or reject.

See docs/specs/approvals-feed.md.
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.api.auth import extract_api_key, ingress_for
from life_graph.api.responses import success_response
from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.approvals import (
    ApprovalActionError,
    ApprovalAlreadyResolvedError,
    ApprovalService,
)
from life_graph.storage.database import get_session

router = APIRouter(prefix="/approvals", tags=["approvals"])

OWNER_REQUIRED = "Approving or rejecting needs the owner: an owner API key or a paired phone."


class ResolveBody(BaseModel):
    """Optional metadata for an approve/reject."""

    note: str | None = None
    # Kept for old clients. Not trusted: who decided is the server's to say
    # (resolver below); a value here is only recorded in the note.
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


def _key_label(request: Request) -> str:
    """A stable, non-secret name for the service key a caller presented.

    Keys have no names in configuration, so the audit trail gets a short
    fingerprint: enough to tell two keys apart, useless for recovering one.
    """
    key = extract_api_key(request.headers, request.query_params)
    if not key:
        return "service-key"
    return f"service-key:{hashlib.sha256(key.encode()).hexdigest()[:8]}"


def resolver(request: Request, body: ResolveBody | None = None) -> str:
    """Who decided, as the server saw the caller (api/auth.py ``ingress_for``).

    ``phone:<device id>`` for a paired phone, ``owner`` for an owner key
    (``owner:local`` on a dev stack with auth off), and otherwise the
    fingerprint of the service key used. ``body.resolved_by`` is never used:
    any client holding a service key could write the owner's name there.
    """
    ingress = ingress_for(request)
    if ingress.device_id:
        return f"phone:{ingress.device_id}"
    if ingress.actor == "owner:api_key":
        return "owner"
    if ingress.owner_verified:
        return ingress.actor  # "owner:local": no credential configured at all
    return _key_label(request)


def _require_owner(request: Request) -> None:
    """403 unless the caller is the owner — only when the setting is on."""
    if settings.approvals_require_owner and not ingress_for(request).is_owner:
        raise HTTPException(status_code=403, detail=OWNER_REQUIRED)


def _note(body: ResolveBody | None) -> str | None:
    """The body's note, plus whatever name the client claimed (unverified)."""
    if body is None:
        return None
    if not body.resolved_by:
        return body.note
    claimed = f"(client said: {body.resolved_by})"
    return f"{body.note}\n{claimed}" if body.note else claimed


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


@router.post("/{approval_id}/approve", summary="Approve an item (runs its side-effect)")
async def approve_approval(
    approval_id: str,
    request: Request,
    body: ResolveBody | None = Body(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    _require_owner(request)
    by = resolver(request, body)
    return await _resolve(approval_id, "approve", body, tenant_id, session, by)


@router.post("/{approval_id}/reject", summary="Reject an item")
async def reject_approval(
    approval_id: str,
    request: Request,
    body: ResolveBody | None = Body(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    _require_owner(request)
    by = resolver(request, body)
    return await _resolve(approval_id, "reject", body, tenant_id, session, by)
