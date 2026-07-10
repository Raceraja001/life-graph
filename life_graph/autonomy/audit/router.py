"""FastAPI router for audit log."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from life_graph.api.responses import success_response
from life_graph.autonomy.audit.schemas import (
    AuditEntryResponse,
    ExportRequest,
)
from life_graph.core.tenant import get_current_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=None)
async def query_audit_log(
    agent_id: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Query audit log with filters."""
    tenant_id = get_current_tenant_id()

    from life_graph.api.dependencies import get_audit_service
    service = get_audit_service()

    entries = await service.query(
        tenant_id=tenant_id,
        filters={
            "agent_id": agent_id,
            "action_type": action_type,
            "risk_level": risk_level,
            "result": result,
            "project_id": project_id,
            "limit": limit,
            "offset": offset,
        },
    )

    return success_response(
        data=[
            AuditEntryResponse(
                id=e.id,
                tenant_id=e.tenant_id,
                action_type=e.action_type,
                action_id=e.action_id,
                agent_id=e.agent_id,
                project_id=e.project_id,
                risk_level=e.risk_level,
                command=e.command,
                result=e.result,
                details=e.details,
                created_at=e.created_at,
            ).model_dump(mode="json")
            for e in entries
        ],
    )


@router.post("/export", response_model=None)
async def export_audit_log(request: ExportRequest):
    """Export audit log as NDJSON."""
    tenant_id = get_current_tenant_id()

    from life_graph.api.dependencies import get_audit_service
    service = get_audit_service()

    ndjson = await service.export_ndjson(
        tenant_id=tenant_id,
        start_date=request.start_date,
        end_date=request.end_date,
        project_id=request.project_id,
    )

    return PlainTextResponse(
        content=ndjson,
        media_type="application/x-ndjson",
    )


@router.post("/{action_id}/rollback", response_model=None)
async def rollback_from_audit(action_id: UUID):
    """Rollback an action referenced from audit log."""
    tenant_id = get_current_tenant_id()

    from life_graph.api.dependencies import get_autofix_service
    service = get_autofix_service()

    try:
        result = await service.rollback(tenant_id, action_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return success_response(
        data=result.model_dump(mode="json"),
        message="Rollback completed from audit",
    )
