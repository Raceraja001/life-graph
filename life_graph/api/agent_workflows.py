"""Agent Workflow routes (Era 7 — Phase 5).

Provides CRUD for workflow DAG definitions and run lifecycle
management: create, start, inspect, and cancel workflow runs.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_workflow_engine
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ── Request Schemas ──────────────────────────────────────────


class WorkflowStepCreate(BaseModel):
    """A single step in a workflow DAG."""

    step_key: str = Field(..., min_length=1, description="Unique key for this step")
    agent_name: str = Field(..., min_length=1, description="Agent to execute this step")
    depends_on: list[str] = Field(default_factory=list, description="Step keys this step depends on")
    condition: str | None = Field(None, description="Condition expression for execution")
    config: dict[str, Any] = Field(default_factory=dict, description="Step configuration")
    timeout_seconds: int = Field(300, ge=10, le=7200, description="Step timeout")


class WorkflowCreate(BaseModel):
    """Payload for creating a workflow DAG."""

    name: str = Field(..., min_length=1, description="Workflow name")
    description: str | None = Field(None, description="Human-readable description")
    project_id: uuid.UUID | None = Field(None, description="Associated project")
    trigger_type: str = Field("manual", description="manual, schedule, or event")
    config: dict[str, Any] = Field(default_factory=dict, description="Workflow-level config")
    steps: list[WorkflowStepCreate] = Field(..., min_length=1, description="DAG steps")


class WorkflowRunStart(BaseModel):
    """Payload for starting a workflow run."""

    trigger: str = Field("manual", description="How the run was triggered")
    triggered_by: str | None = Field(None, description="User or system that triggered")
    input_params: dict[str, Any] = Field(default_factory=dict, description="Input parameters")


class CancelRequest(BaseModel):
    """Payload for cancelling a workflow run."""

    reason: str = Field("Cancelled by user", description="Cancellation reason")


# ── Routes ───────────────────────────────────────────────────


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a workflow DAG",
)
async def create_workflow(
    body: WorkflowCreate,
    engine: WorkflowEngine = Depends(get_workflow_engine),
):
    """Create a new workflow definition with validated DAG structure.

    Validates that the step graph is acyclic (using Kahn's algorithm),
    then stores the workflow and all its steps.
    """
    tenant_id = get_current_tenant_id()

    try:
        workflow = await engine.create_workflow(
            tenant_id=tenant_id,
            data=body.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return success_response(data={
        "id": str(workflow.id),
        "name": workflow.name,
        "description": workflow.description,
        "trigger_type": workflow.trigger_type,
        "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
    })


@router.post(
    "/{workflow_id}/run",
    status_code=status.HTTP_201_CREATED,
    summary="Start a workflow run",
)
async def start_run(
    workflow_id: uuid.UUID,
    body: WorkflowRunStart = WorkflowRunStart(),
    engine: WorkflowEngine = Depends(get_workflow_engine),
):
    """Start a new run of the specified workflow.

    Creates step runs for all steps and kicks off root steps
    (those with no dependencies).
    """
    tenant_id = get_current_tenant_id()

    try:
        run = await engine.start_run(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            trigger=body.trigger,
            triggered_by=body.triggered_by,
            input_params=body.input_params,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return success_response(data={
        "id": str(run.id),
        "workflow_id": str(run.workflow_id),
        "status": run.status,
        "trigger": run.trigger,
        "started_at": run.started_at.isoformat() if run.started_at else None,
    })


@router.get(
    "/{workflow_id}/runs/{run_id}",
    summary="Get workflow run with step details",
)
async def get_run(
    workflow_id: uuid.UUID,
    run_id: uuid.UUID,
    engine: WorkflowEngine = Depends(get_workflow_engine),
):
    """Retrieve a workflow run and all its step run details."""
    from life_graph.models.db import WorkflowRun, WorkflowStepRun
    from sqlalchemy import select
    from life_graph.storage.database import async_session

    tenant_id = get_current_tenant_id()

    async with async_session() as session:
        # Load the run
        result = await session.execute(
            select(WorkflowRun).where(
                WorkflowRun.id == run_id,
                WorkflowRun.workflow_id == workflow_id,
                WorkflowRun.tenant_id == tenant_id,
            )
        )
        run = result.scalar_one_or_none()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run {run_id} not found",
            )

        # Load step runs
        step_result = await session.execute(
            select(WorkflowStepRun)
            .where(WorkflowStepRun.run_id == run_id)
            .order_by(WorkflowStepRun.started_at.asc().nullslast())
        )
        step_runs = step_result.scalars().all()

    return success_response(data={
        "id": str(run.id),
        "workflow_id": str(run.workflow_id),
        "status": run.status,
        "trigger": run.trigger,
        "triggered_by": run.triggered_by,
        "input_params": run.input_params,
        "output_summary": run.output_summary,
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "steps": [
            {
                "id": str(sr.id),
                "step_key": sr.step_key,
                "status": sr.status,
                "output": sr.output,
                "error": sr.error,
                "task_id": str(sr.task_id) if sr.task_id else None,
                "started_at": sr.started_at.isoformat() if sr.started_at else None,
                "completed_at": sr.completed_at.isoformat() if sr.completed_at else None,
            }
            for sr in step_runs
        ],
    })


@router.post(
    "/{workflow_id}/runs/{run_id}/cancel",
    summary="Cancel a workflow run",
)
async def cancel_run(
    workflow_id: uuid.UUID,
    run_id: uuid.UUID,
    body: CancelRequest = CancelRequest(),
    engine: WorkflowEngine = Depends(get_workflow_engine),
):
    """Cancel a running workflow and all its pending/running steps."""
    tenant_id = get_current_tenant_id()

    await engine.cancel_run(
        run_id=run_id,
        tenant_id=tenant_id,
        reason=body.reason,
    )

    return success_response(data={
        "run_id": str(run_id),
        "status": "cancelled",
        "reason": body.reason,
    })
