"""Shadow Mode API router.

Grading queue + one-tap grading + enrollment states.
Prefix: /autonomy/shadow
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from life_graph.api.responses import success_response
from life_graph.autonomy.shadow.schemas import (
    GradeRequest,
    ShadowEnrollmentResponse,
    ShadowRunResponse,
)
from life_graph.autonomy.shadow.service import shadow_service
from life_graph.core.tenant import get_current_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shadow", tags=["autonomy-shadow"])


@router.get("/runs")
async def list_runs(
    ungraded_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """List would-have-done shadow runs (the grading queue by default)."""
    runs = await shadow_service.list_runs(
        tenant_id, ungraded_only=ungraded_only, limit=limit
    )
    return success_response(
        data=[ShadowRunResponse.model_validate(r) for r in runs]
    )


@router.post("/runs/{run_id}/grade")
async def grade_run(
    run_id: str,
    body: GradeRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Grade a would-have-done run good/bad. Feeds trust + drives graduation."""
    try:
        result = await shadow_service.grade(tenant_id, run_id, body.grade)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_response(data={
        "graded": result.graded,
        "graduated": result.graduated,
        "status": result.status,
        "graded_good": result.graded_good,
        "graded_bad": result.graded_bad,
    })


@router.get("/enrollments")
async def list_enrollments(
    tenant_id: str = Depends(get_current_tenant_id),
):
    """List actor enrollments and their progress toward graduation."""
    enrollments = await shadow_service.list_enrollments(tenant_id)
    return success_response(
        data=[ShadowEnrollmentResponse.model_validate(e) for e in enrollments]
    )
