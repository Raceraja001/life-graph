"""Self-Improving Agent API Router — Phase 6.

25 endpoints covering eval suites, eval runs, prompt versions,
optimization, and dashboard analytics.

Prefix: /self-improving
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import (
    get_dashboard_service,
    get_eval_service,
    get_optimizer_service,
    get_prompt_version_service,
)
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.self_improving.schemas import (
    EvalCaseCreate,
    EvalSuiteCreate,
    PromptVersionCreate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/self-improving", tags=["self-improving"])


# ── Request / Response Schemas ────────────────────────────────


class CreateEvalSuiteRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    task_type: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    auto_optimize_enabled: bool = False
    accuracy_threshold_pct: float | None = None
    max_consecutive_fails: int = 3


class AddEvalCaseRequest(BaseModel):
    input_text: str
    expected_output: str
    tags: list[str] | None = None
    weight: float = 1.0


class BulkImportCasesRequest(BaseModel):
    cases: list[AddEvalCaseRequest]


class CreatePromptVersionRequest(BaseModel):
    task_type: str = Field(..., min_length=1, max_length=100)
    prompt_text: str = Field(..., min_length=1)
    few_shot_examples: list[dict] | None = None
    created_by: str = "manual"
    description: str | None = None


class ReviewDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    reviewer_notes: str | None = None


class RunEvalSuiteRequest(BaseModel):
    prompt_version_id: uuid.UUID | None = None


# ── Eval Suites ──────────────────────────────────────────────


@router.post(
    "/eval-suites",
    status_code=status.HTTP_201_CREATED,
    summary="Create an eval suite",
)
async def create_eval_suite(
    body: CreateEvalSuiteRequest,
    eval_service=Depends(get_eval_service),
):
    """Create a new evaluation suite for a task type."""
    tenant_id = get_current_tenant_id()
    data = EvalSuiteCreate(
        name=body.name,
        task_type=body.task_type,
        description=body.description,
        auto_optimize_enabled=body.auto_optimize_enabled,
        accuracy_threshold_pct=body.accuracy_threshold_pct or 90.0,
        max_consecutive_fails=body.max_consecutive_fails,
    )
    suite = await eval_service.create_suite(tenant_id=tenant_id, data=data)
    return success_response(data=_serialize(suite))


@router.get(
    "/eval-suites",
    summary="List eval suites",
)
async def list_eval_suites(
    eval_service=Depends(get_eval_service),
):
    """List all eval suites for the current tenant."""
    tenant_id = get_current_tenant_id()
    suites = await eval_service.list_suites(tenant_id)
    return success_response(data=[_serialize(s) for s in suites])


@router.post(
    "/eval-suites/{suite_id}/cases",
    status_code=status.HTTP_201_CREATED,
    summary="Add eval case to suite",
)
async def add_eval_case(
    suite_id: uuid.UUID,
    body: AddEvalCaseRequest,
    eval_service=Depends(get_eval_service),
):
    """Add a single evaluation case to a suite."""
    data = EvalCaseCreate(
        input_text=body.input_text,
        expected_output=body.expected_output,
    )
    case = await eval_service.add_case(suite_id=suite_id, data=data)
    return success_response(data=_serialize(case))


@router.post(
    "/eval-suites/{suite_id}/cases/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk import eval cases",
)
async def bulk_import_cases(
    suite_id: uuid.UUID,
    body: BulkImportCasesRequest,
    eval_service=Depends(get_eval_service),
):
    """Bulk import evaluation cases into a suite."""
    from life_graph.self_improving.schemas import EvalCaseBulkCreate

    bulk_data = EvalCaseBulkCreate(
        cases=[
            EvalCaseCreate(
                input_text=c.input_text,
                expected_output=c.expected_output,
            )
            for c in body.cases
        ]
    )
    cases = await eval_service.bulk_add_cases(
        suite_id=suite_id, data=bulk_data,
    )
    return success_response(
        data={"imported": len(cases), "cases": [_serialize(c) for c in cases]}
    )


@router.post(
    "/eval-suites/{suite_id}/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger eval run",
)
async def trigger_eval_run(
    suite_id: uuid.UUID,
    body: RunEvalSuiteRequest = RunEvalSuiteRequest(),
    eval_service=Depends(get_eval_service),
):
    """Trigger an evaluation run for a suite.

    If prompt_version_id is not provided, uses the active prompt
    for the suite's task_type.
    """
    tenant_id = get_current_tenant_id()
    run = await eval_service.run_suite(
        tenant_id=tenant_id,
        suite_id=suite_id,
        prompt_version_id=body.prompt_version_id,
    )
    return success_response(data=_serialize(run))


# ── Eval Runs ────────────────────────────────────────────────


@router.get(
    "/eval-runs/{run_id}",
    summary="Get eval run with results",
)
async def get_eval_run(
    run_id: uuid.UUID,
    eval_service=Depends(get_eval_service),
):
    """Get an eval run by ID, including results."""
    try:
        run = await eval_service.get_run(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EvalRun {run_id} not found",
        )
    return success_response(data=_serialize(run))


@router.get(
    "/eval-runs/{run_id}/failures",
    summary="Failure analysis for eval run",
)
async def get_eval_run_failures(
    run_id: uuid.UUID,
    eval_service=Depends(get_eval_service),
):
    """Get failure analysis for an eval run."""
    failures = await eval_service.get_failures(run_id)
    return success_response(data=[f.model_dump() for f in failures])


# ── Prompt Versions ──────────────────────────────────────────


@router.post(
    "/prompt-versions",
    status_code=status.HTTP_201_CREATED,
    summary="Create prompt version",
)
async def create_prompt_version(
    body: CreatePromptVersionRequest,
    prompt_service=Depends(get_prompt_version_service),
):
    """Create a new prompt version for a task type."""
    tenant_id = get_current_tenant_id()
    data = PromptVersionCreate(
        task_type=body.task_type,
        prompt_text=body.prompt_text,
        few_shot_examples=body.few_shot_examples or [],
        created_by=body.created_by,
        change_note=body.description,
    )
    version = await prompt_service.create(
        tenant_id=tenant_id,
        data=data,
    )
    return success_response(data=_serialize(version))


@router.get(
    "/prompt-versions",
    summary="List prompt versions",
)
async def list_prompt_versions(
    task_type: str | None = Query(None, description="Filter by task type"),
    prompt_service=Depends(get_prompt_version_service),
):
    """List prompt versions, optionally filtered by task_type."""
    tenant_id = get_current_tenant_id()
    if task_type:
        versions = await prompt_service.list_versions(tenant_id, task_type)
    else:
        versions = []  # task_type is required for list_versions
    return success_response(data=[_serialize(v) for v in versions])


@router.post(
    "/prompt-versions/{version_id}/activate",
    summary="Activate a prompt version",
)
async def activate_prompt_version(
    version_id: uuid.UUID,
    prompt_service=Depends(get_prompt_version_service),
):
    """Activate a specific prompt version (deactivates others for same task_type)."""
    tenant_id = get_current_tenant_id()
    try:
        version = await prompt_service.activate(tenant_id, version_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PromptVersion {version_id} not found",
        )
    return success_response(data=_serialize(version))


@router.post(
    "/prompt-versions/{version_id}/rollback",
    summary="Rollback to a previous prompt version",
)
async def rollback_prompt_version(
    version_id: uuid.UUID,
    prompt_service=Depends(get_prompt_version_service),
):
    """Rollback to a specific previous prompt version."""
    tenant_id = get_current_tenant_id()
    try:
        version = await prompt_service.rollback(tenant_id, version_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PromptVersion {version_id} not found",
        )
    return success_response(data=_serialize(version))


# ── Optimization ─────────────────────────────────────────────


@router.post(
    "/optimize/{suite_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger optimization",
)
async def trigger_optimization(
    suite_id: uuid.UUID,
    eval_service=Depends(get_eval_service),
    optimizer=Depends(get_optimizer_service),
):
    """Manually trigger DSPy optimization for a suite.

    First runs an eval, then if accuracy is below threshold,
    triggers the full optimization pipeline.
    """
    tenant_id = get_current_tenant_id()

    # Run eval first to get a baseline
    run = await eval_service.run_suite(
        tenant_id=tenant_id, suite_id=suite_id
    )

    result = await optimizer.optimize(
        tenant_id=tenant_id,
        suite_id=suite_id,
        trigger_eval_run_id=run.id,
    )
    return success_response(data=result)


@router.get(
    "/optimization-runs/{run_id}",
    summary="Get optimization run details",
)
async def get_optimization_run(
    run_id: uuid.UUID,
    eval_service=Depends(get_eval_service),
):
    """Get details of a specific optimization run."""
    from life_graph.self_improving.models import OptimizationRun
    from life_graph.storage.database import async_session

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        opt_run = await session.get(OptimizationRun, run_id)
        if opt_run is None or opt_run.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"OptimizationRun {run_id} not found",
            )
        return success_response(data=_serialize(opt_run))


@router.post(
    "/optimization-runs/{run_id}/review",
    summary="Approve or reject an optimization",
)
async def review_optimization(
    run_id: uuid.UUID,
    body: ReviewDecisionRequest,
    prompt_service=Depends(get_prompt_version_service),
):
    """Approve or reject a needs_review optimization run."""
    from life_graph.self_improving.models import OptimizationRun
    from life_graph.storage.database import async_session
    from datetime import datetime, timezone

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        opt_run = await session.get(OptimizationRun, run_id)
        if opt_run is None or opt_run.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"OptimizationRun {run_id} not found",
            )

        if opt_run.status != "needs_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Run status is '{opt_run.status}', expected 'needs_review'",
            )

        if body.decision == "approve":
            # Deploy the candidate prompt
            result = opt_run.result or {}
            candidate_id = result.get("candidate_version_id")
            if candidate_id:
                await prompt_service.activate_version(
                    tenant_id, uuid.UUID(candidate_id)
                )
            opt_run.status = "deployed"
        else:
            opt_run.status = "rejected"

        opt_run.reviewer_notes = body.reviewer_notes
        opt_run.reviewed_at = datetime.now(timezone.utc)
        await session.commit()

        return success_response(data=_serialize(opt_run))


# ── Dashboard ────────────────────────────────────────────────


@router.get(
    "/dashboard/overview",
    summary="Dashboard overview",
)
async def dashboard_overview(
    dashboard=Depends(get_dashboard_service),
):
    """Overall accuracy, tasks monitored, auto-fixes, pending reviews, costs."""
    tenant_id = get_current_tenant_id()
    data = await dashboard.get_overview(tenant_id)
    return success_response(data=data)


@router.get(
    "/dashboard/accuracy-trends",
    summary="Accuracy trends over time",
)
async def dashboard_accuracy_trends(
    days: int = Query(30, ge=1, le=365),
    dashboard=Depends(get_dashboard_service),
):
    """Time series of accuracy per task_type."""
    tenant_id = get_current_tenant_id()
    data = await dashboard.get_accuracy_trends(tenant_id, days=days)
    return success_response(data=data)


@router.get(
    "/dashboard/per-task-accuracy",
    summary="Per-task accuracy with status",
)
async def dashboard_per_task_accuracy(
    dashboard=Depends(get_dashboard_service),
):
    """Current accuracy per task_type with color-coded status."""
    tenant_id = get_current_tenant_id()
    data = await dashboard.get_per_task_accuracy(tenant_id)
    return success_response(data=data)


@router.get(
    "/dashboard/auto-fixes",
    summary="Recent auto-fixes",
)
async def dashboard_auto_fixes(
    days: int = Query(7, ge=1, le=90),
    dashboard=Depends(get_dashboard_service),
):
    """Deployed optimizations in the last N days."""
    tenant_id = get_current_tenant_id()
    data = await dashboard.get_auto_fixes(tenant_id, days=days)
    return success_response(data=data)


@router.get(
    "/dashboard/cost-trends",
    summary="Eval cost trends",
)
async def dashboard_cost_trends(
    days: int = Query(30, ge=1, le=365),
    dashboard=Depends(get_dashboard_service),
):
    """Daily eval + optimization costs over time."""
    tenant_id = get_current_tenant_id()
    data = await dashboard.get_cost_trends(tenant_id, days=days)
    return success_response(data=data)


@router.get(
    "/dashboard/pending-reviews",
    summary="Pending optimization reviews",
)
async def dashboard_pending_reviews(
    dashboard=Depends(get_dashboard_service),
):
    """Optimization runs awaiting review."""
    tenant_id = get_current_tenant_id()
    data = await dashboard.get_pending_reviews(tenant_id)
    return success_response(data=data)


# ── Serialization Helpers ─────────────────────────────────────


def _serialize(obj: Any) -> dict:
    """Convert an ORM model to a JSON-safe dict.

    Handles UUID, datetime, and nested dict/list fields.
    """
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return obj

    data = {}
    for key in dir(obj):
        if key.startswith("_") or key == "metadata" or key == "registry":
            continue
        try:
            val = getattr(obj, key)
        except Exception:
            continue
        if callable(val):
            continue

        if isinstance(val, uuid.UUID):
            data[key] = str(val)
        elif hasattr(val, "isoformat"):
            data[key] = val.isoformat()
        elif isinstance(val, (str, int, float, bool, type(None))):
            data[key] = val
        elif isinstance(val, (list, dict)):
            data[key] = val

    return data
