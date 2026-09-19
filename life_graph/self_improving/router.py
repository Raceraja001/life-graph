"""Self-Improving Agent API Router — Phase 6.

25 endpoints covering eval suites, eval runs, prompt versions,
optimization, and dashboard analytics.

Prefix: /self-improving
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import inspect as sa_inspect

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
        suite_id=suite_id,
        data=bulk_data,
    )
    return success_response(data={"imported": len(cases), "cases": [_serialize(c) for c in cases]})


@router.post(
    "/eval-suites/{suite_id}/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger eval run",
)
async def trigger_eval_run(
    suite_id: uuid.UUID,
    body: RunEvalSuiteRequest | None = None,
    eval_service=Depends(get_eval_service),
    prompt_service=Depends(get_prompt_version_service),
):
    """Run a suite's cases through its task and score them.

    Uses the given prompt version, else the active one for the suite's task,
    else the task's built-in prompt. Runs synchronously — on a local model a
    run takes roughly (cases x seconds per extraction).
    """
    from life_graph.self_improving.models import EvalSuite
    from life_graph.storage.database import async_session

    body = body or RunEvalSuiteRequest()
    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        suite = await session.get(EvalSuite, suite_id)
    if suite is None or suite.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suite not found")

    if body.prompt_version_id is not None:
        version_id = str(body.prompt_version_id)
    else:
        active = await prompt_service.get_active(tenant_id, suite.task_type)
        version_id = str(active.id) if active else "default"
    try:
        run = await eval_service.run_eval(tenant_id, suite_id, version_id, trigger="manual")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EvalRun {run_id} not found",
        ) from exc
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
    # Confirm the run exists first. Returning 200 with an empty list for a
    # run that does not exist makes "this run had no failures" — a good
    # result — indistinguishable from "there is no such run". The sibling
    # GET /eval-runs/{run_id} already 404s this way.
    try:
        await eval_service.get_run(run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EvalRun {run_id} not found",
        ) from exc

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
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PromptVersion {version_id} not found",
        ) from exc
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
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PromptVersion {version_id} not found",
        ) from exc
    return success_response(data=_serialize(version))


# ── Optimization ─────────────────────────────────────────────


@router.post(
    "/optimize/{suite_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger optimization",
)
async def trigger_optimization(
    suite_id: uuid.UUID,
    optimizer=Depends(get_optimizer_service),
):
    """Run one optimization for a suite now (same as the nightly pass).

    Evaluates the active prompt, tries few-shot candidates built from reviewed
    captures, and deploys the best only if it clears the gate. Synchronous;
    expect minutes on a local model.
    """
    tenant_id = get_current_tenant_id()
    result = await optimizer.optimize(tenant_id, suite_id)
    if result.get("status") == "error" and result.get("optimization_run_id") is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(result["details"]))
    return success_response(data=_serialize(result))


@router.post(
    "/prompt-versions/deactivate",
    summary="Return a task to its built-in prompt",
)
async def deactivate_prompt_versions(
    task_type: str = Query(..., description="Task type, e.g. capture_extraction"),
    prompt_service=Depends(get_prompt_version_service),
):
    """Undo for an auto-deploy made on top of the built-in prompt: deactivate
    whatever version is active, so the task uses its built-in prompt again."""
    tenant_id = get_current_tenant_id()
    changed = await prompt_service.deactivate_active(tenant_id, task_type)
    return success_response(data={"task_type": task_type, "deactivated": changed})


@router.get(
    "/status",
    summary="How much the loop has to learn from",
)
async def self_improving_status(
    prompt_service=Depends(get_prompt_version_service),
):
    """Data readiness and the active prompt, for the extraction task.

    Counts are live: traces recorded, traces usable as labels (every fact
    reviewed), the held-out/training split, and what the nightly pass needs.
    """
    from sqlalchemy import func, select

    from life_graph.config import settings
    from life_graph.self_improving.models import ExtractionTrace
    from life_graph.self_improving.suite_builder import TASK_TYPE, labelled_traces
    from life_graph.storage.database import async_session

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        traces = await session.scalar(
            select(func.count())
            .select_from(ExtractionTrace)
            .where(ExtractionTrace.tenant_id == tenant_id, ExtractionTrace.task_type == TASK_TYPE)
        )
    usable = await labelled_traces(tenant_id)
    holdout = sum(1 for t in usable if t.split == "holdout")
    active = await prompt_service.get_active(tenant_id, TASK_TYPE)
    return success_response(
        data={
            "task_type": TASK_TYPE,
            "enabled": settings.self_improving_enabled,
            "traces_recorded": traces or 0,
            "traces_labelled": len(usable),
            "holdout": holdout,
            "train": len(usable) - holdout,
            "holdout_needed": settings.optimization_min_holdout,
            "ready": holdout >= settings.optimization_min_holdout,
            "active_prompt_version": str(active.id) if active else "default",
        }
    )


@router.post(
    "/extraction/sync",
    summary="Rebuild the extraction eval suite from reviews now",
)
async def sync_extraction_suite():
    """Build or refresh the extraction suite from reviewed captures (the nightly
    pass does this first anyway)."""
    from life_graph.self_improving.suite_builder import sync_suite

    tenant_id = get_current_tenant_id()
    result = await sync_suite(tenant_id)
    result["train_pool"] = len(result["train_pool"])
    return success_response(data=_serialize(result))


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
    from datetime import datetime

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

        if opt_run.status != "needs_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Run status is '{opt_run.status}', expected 'needs_review'",
            )

        if body.decision == "approve":
            # Deploy the candidate prompt. (It previously read `result` and
            # wrote `reviewer_notes` — neither is a column — and called a
            # method that does not exist, so approving always failed.)
            if opt_run.candidate_version_id:
                await prompt_service.activate(
                    tenant_id,
                    uuid.UUID(opt_run.candidate_version_id),
                    reason=f"Approved from optimization run {run_id}",
                )
            opt_run.status = "deployed"
        else:
            opt_run.status = "rejected"

        opt_run.review_decision = body.decision
        opt_run.review_reason = body.reviewer_notes
        opt_run.reviewed_by = "user"
        opt_run.reviewed_at = datetime.now(UTC)
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

    Column names come from the SQLAlchemy mapper rather than dir(). Walking
    dir() swept up framework internals as if they were data: `model_fields`
    is a dict of Pydantic FieldInfo objects, which passed the isinstance
    check for dict and went straight into the response, where
    jsonable_encoder failed with "'FieldInfo' object is not iterable" and
    the whole endpoint 500'd. Every route in this router that serialized an
    ORM row was affected. Naming the columns explicitly cannot regress that
    way when a dependency adds another dunder-free attribute.
    """
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return obj

    try:
        keys = [attr.key for attr in sa_inspect(obj).mapper.column_attrs]
    except Exception:
        # Not a mapped instance — fall back to the public attribute scan,
        # minus the framework internals that caused the original failure.
        keys = [
            k
            for k in dir(obj)
            if not k.startswith("_")
            and k
            not in {
                "metadata",
                "registry",
                "model_fields",
                "model_config",
                "model_computed_fields",
                "model_extra",
                "model_fields_set",
            }
        ]

    data = {}
    for key in keys:
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
        elif isinstance(val, (str, int, float, bool, type(None), list, dict)):
            data[key] = val

    return data
