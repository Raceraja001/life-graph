"""FastAPI router for autonomy levels."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from life_graph.api.responses import success_response
from life_graph.autonomy.levels.schemas import (
    AutonomyLevelResponse,
    LEVEL_DESCRIPTIONS,
    SetLevelRequest,
)
from life_graph.core.tenant import get_current_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/levels", tags=["autonomy-levels"])


@router.get("/{project_id}", response_model=None)
async def get_autonomy_level(project_id: str):
    """Get the autonomy level for a project, with promotion progress."""
    tenant_id = get_current_tenant_id()

    from life_graph.api.dependencies import get_autonomy_level_service
    service = get_autonomy_level_service()

    level = await service.get_level(tenant_id, project_id)
    check = await service.check_promotion(tenant_id, project_id)

    return success_response(
        data=AutonomyLevelResponse(
            id=level.id,
            tenant_id=level.tenant_id,
            project_id=level.project_id,
            current_level=level.current_level,
            level_name=LEVEL_DESCRIPTIONS.get(level.current_level, "Unknown"),
            safe_count=level.safe_count,
            moderate_count=level.moderate_count,
            failure_count=level.failure_count,
            promotion_eligible=check.eligible,
            promotion_reason=check.reason,
            created_at=level.created_at,
            updated_at=level.updated_at,
        ).model_dump(mode="json"),
    )


@router.post("/{project_id}/set", response_model=None)
async def set_autonomy_level(project_id: str, request: SetLevelRequest):
    """Manually set the autonomy level for a project."""
    tenant_id = get_current_tenant_id()

    from life_graph.api.dependencies import get_autonomy_level_service
    service = get_autonomy_level_service()

    try:
        new_level = await service.set_manual(
            tenant_id=tenant_id,
            project_id=project_id,
            level=request.level,
            reason=request.reason,
            by=request.set_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return success_response(
        data={
            "project_id": project_id,
            "level": new_level,
            "level_name": LEVEL_DESCRIPTIONS.get(new_level, "Unknown"),
        },
        message=f"Autonomy level set to L{new_level}",
    )
