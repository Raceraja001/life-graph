"""FastAPI router for autonomous action pipeline."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from life_graph.api.responses import success_response
from life_graph.autonomy.pipeline.schemas import AutoFixRequest
from life_graph.autonomy.pipeline.service import _to_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-actions", tags=["auto-actions"])


@router.post("", status_code=201, response_model=None)
async def trigger_auto_action(request: AutoFixRequest):
    """Trigger an autonomous action — classify → route → execute/queue.

    Returns 201 if auto-executed, 202 if queued for approval.
    """
    tenant_id = get_current_tenant_id()

    from life_graph.api.dependencies import get_autofix_service
    service = get_autofix_service()

    result = await service.process(tenant_id, request)

    status_code = 201 if result.routing == "auto_executed" else 202
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content=success_response(
            data=result.model_dump(mode="json"),
            meta={"message": result.message},
        ),
    )


@router.get("", response_model=None)
async def list_auto_actions(
    agent_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List auto actions with optional filters."""
    tenant_id = get_current_tenant_id()

    from life_graph.autonomy.models import AutoAction

    async with async_session() as session:
        q = select(AutoAction).where(AutoAction.tenant_id == tenant_id)

        if agent_id:
            q = q.where(AutoAction.agent_id == agent_id)
        if project_id:
            q = q.where(AutoAction.project_id == project_id)
        if status:
            q = q.where(AutoAction.status == status)
        if risk_level:
            q = q.where(AutoAction.risk_level == risk_level)

        q = q.order_by(AutoAction.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(q)
        actions = result.scalars().all()

    return success_response(
        data=[_to_response(a).model_dump(mode="json") for a in actions],
    )


@router.post("/{action_id}/rollback", response_model=None)
async def rollback_action(action_id: str):
    """Rollback a previously executed auto action."""
    tenant_id = get_current_tenant_id()

    from life_graph.api.dependencies import get_autofix_service
    service = get_autofix_service()

    try:
        result = await service.rollback(tenant_id, action_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return success_response(
        data=result.model_dump(mode="json"),
        meta={"message": "Rollback completed"},
    )
