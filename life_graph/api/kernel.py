"""OS Kernel API endpoints — full kernel surface.

Phase 1: Task CRUD (Process Manager).
Phase 2: Persona CRUD, tool permission filtering.
Phase 3: Chief Router — intent classification and routing.
Phase 4: Scheduler — cron-based job management.
Phase 5: Project Registry — codebase registration and scanning.
Phase 6: Notification Engine — priority-routed alerts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import (
    get_process_manager,
    get_persona_service,
    get_chief_router,
    get_scheduler_service,
    get_project_registry,
    get_notification_engine,
)
from life_graph.api.responses import paginated_response, success_response
from life_graph.core.tenant import get_current_tenant_id

router = APIRouter(prefix="/kernel", tags=["kernel"])


# ── Pydantic Schemas ─────────────────────────────────────────


class TaskCreate(BaseModel):
    """Request body for creating a new agent task."""

    agent_name: str = Field(..., description="Persona name to execute the task")
    task_name: str | None = Field(None, description="Human-readable label")
    input: dict[str, Any] = Field(
        default_factory=dict, description="Task input (message, context, etc.)"
    )
    priority: str = Field("normal", description="low|normal|high|critical")
    timeout_seconds: int = Field(300, ge=10, le=3600, description="Max execution time")
    max_retries: int = Field(2, ge=0, le=5)
    parent_task_id: str | None = Field(None, description="Parent task for handoff chains")
    session_id: str | None = Field(None, description="Agent session ID")
    project_id: str | None = Field(None, description="Project context ID")


class TaskSummary(BaseModel):
    """Compact task representation for list responses."""

    id: str
    task_name: str | None = None
    agent_name: str
    status: str
    priority: str
    model_used: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskDetail(BaseModel):
    """Full task representation with result and logs."""

    id: str
    tenant_id: str
    task_name: str | None = None
    agent_name: str
    status: str
    priority: str
    input: dict[str, Any] = {}
    result: dict[str, Any] = {}
    error: str | None = None
    logs: list[Any] = []
    token_usage: dict[str, Any] = {}
    model_used: str | None = None
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 2
    parent_task_id: str | None = None
    session_id: str | None = None
    project_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskCancelResponse(BaseModel):
    """Response for task cancellation."""

    id: str
    status: str
    message: str


# ── Helper ───────────────────────────────────────────────────


def _task_row_to_summary(row: Any) -> dict:
    """Convert an AgentTask ORM row to a TaskSummary-compatible dict."""
    return {
        "id": str(row.id),
        "task_name": row.task_name,
        "agent_name": row.agent_name,
        "status": row.status,
        "priority": row.priority,
        "model_used": row.model_used,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "created_at": row.created_at,
    }


def _task_row_to_detail(row: Any) -> dict:
    """Convert an AgentTask ORM row to a TaskDetail-compatible dict."""
    return {
        "id": str(row.id),
        "tenant_id": row.tenant_id,
        "task_name": row.task_name,
        "agent_name": row.agent_name,
        "status": row.status,
        "priority": row.priority,
        "input": row.input or {},
        "result": row.result or {},
        "error": row.error,
        "logs": row.logs or [],
        "token_usage": row.token_usage or {},
        "model_used": row.model_used,
        "timeout_seconds": row.timeout_seconds,
        "retry_count": row.retry_count,
        "max_retries": row.max_retries,
        "parent_task_id": str(row.parent_task_id) if row.parent_task_id else None,
        "session_id": str(row.session_id) if row.session_id else None,
        "project_id": str(row.project_id) if row.project_id else None,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


# ── Task Endpoints ───────────────────────────────────────────


@router.post(
    "/tasks",
    status_code=status.HTTP_201_CREATED,
    summary="Create and queue a new agent task",
)
async def create_task(
    body: TaskCreate,
    pm: Any = Depends(get_process_manager),
):
    """Spawn a new agent task via the Process Manager.

    The task is created with status 'queued' and picked up
    asynchronously by the process manager for execution.
    """
    tenant_id = get_current_tenant_id()

    # Validate priority
    valid_priorities = {"low", "normal", "high", "critical"}
    if body.priority not in valid_priorities:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid priority '{body.priority}'. "
            f"Must be one of: {', '.join(sorted(valid_priorities))}",
        )

    try:
        spawn_result = await pm.spawn(
            tenant_id=tenant_id,
            agent_name=body.agent_name,
            input_data=body.input,
            task_name=body.task_name,
            priority=body.priority,
            timeout_seconds=body.timeout_seconds,
            max_retries=body.max_retries,
            parent_task_id=body.parent_task_id,
            session_id=body.session_id,
            project_id=body.project_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # spawn() returns dict or string depending on implementation
    if isinstance(spawn_result, dict):
        task_id = spawn_result.get("task_id", str(spawn_result))
    else:
        task_id = str(spawn_result)

    # Fetch the created record for the response
    task = await pm.get_task(tenant_id, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task created but could not be retrieved",
        )

    return success_response(data=_task_row_to_summary(task))


@router.get(
    "/tasks",
    summary="List agent tasks with optional filters",
)
async def list_tasks(
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status"
    ),
    agent_name: str | None = Query(
        None, description="Filter by agent/persona name"
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    pm: Any = Depends(get_process_manager),
):
    """List tasks for the current tenant with optional filters."""
    tenant_id = get_current_tenant_id()

    tasks, total = await pm.list_tasks(
        tenant_id=tenant_id,
        status=status_filter,
        agent_name=agent_name,
        limit=limit,
        offset=offset,
    )

    return paginated_response(
        data=[_task_row_to_summary(t) for t in tasks],
        total=total,
        page_size=limit,
        has_more=(offset + limit) < total,
    )


@router.get(
    "/tasks/{task_id}",
    summary="Get full task details",
)
async def get_task(
    task_id: uuid.UUID,
    pm: Any = Depends(get_process_manager),
):
    """Get the full detail of a specific task including result, logs, and token usage."""
    tenant_id = get_current_tenant_id()

    task = await pm.get_task(tenant_id, str(task_id))
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return success_response(data=_task_row_to_detail(task))


@router.post(
    "/tasks/{task_id}/cancel",
    summary="Cancel a running task",
)
async def cancel_task(
    task_id: uuid.UUID,
    pm: Any = Depends(get_process_manager),
):
    """Cancel a running or queued task.

    Returns 409 if the task is already in a terminal state
    (completed, failed, cancelled, timeout).
    """
    tenant_id = get_current_tenant_id()

    task = await pm.get_task(tenant_id, str(task_id))
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    terminal_states = {"completed", "failed", "cancelled", "timeout"}
    if task.status in terminal_states:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task {task_id} is already {task.status} — cannot cancel",
        )

    cancelled = await pm.cancel(task_id, tenant_id)
    if not cancelled and task.status == "queued":
        # For queued tasks not yet running, update status directly
        await pm.cancel_queued(str(task_id))

    return success_response(
        data={
            "id": str(task_id),
            "status": "cancelled",
            "message": "Task cancelled successfully",
        }
    )


# ── Persona Schemas ──────────────────────────────────────────


class PersonaCreate(BaseModel):
    """Request body for creating a new persona."""

    name: str = Field(
        ..., min_length=1, max_length=100,
        description="Unique persona name (e.g., 'analyst')",
    )
    system_prompt: str = Field(
        ..., min_length=1,
        description="System prompt defining agent behavior",
    )
    display_name: str | None = Field(
        None, max_length=200,
    )
    description: str | None = None
    model: str = Field(
        "gemini/gemini-2.5-flash", max_length=100,
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1, le=128000)
    allowed_tools: list[str] | None = None
    intent_tags: list[str] | None = None
    icon: str | None = Field(None, max_length=10)
    properties: dict[str, Any] | None = None


class PersonaUpdate(BaseModel):
    """Partial update for a persona."""

    display_name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=128000)
    allowed_tools: list[str] | None = None
    intent_tags: list[str] | None = None
    icon: str | None = None
    properties: dict[str, Any] | None = None


class PersonaSummary(BaseModel):
    """Compact persona representation for list responses."""

    id: str
    name: str
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    model: str
    intent_tags: list[str] | None = None
    is_builtin: bool = False
    is_active: bool = True
    use_count: int = 0


# ── Persona Endpoints ────────────────────────────────────────


def _persona_to_summary(p: dict) -> dict:
    """Extract summary fields from a persona dict."""
    return {
        "id": p["id"],
        "name": p["name"],
        "display_name": p.get("display_name"),
        "description": p.get("description"),
        "icon": p.get("icon"),
        "model": p.get("model", ""),
        "intent_tags": p.get("intent_tags"),
        "is_builtin": p.get("is_builtin", False),
        "is_active": p.get("is_active", True),
        "use_count": p.get("use_count", 0),
    }


@router.post(
    "/personas",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new agent persona",
)
async def create_persona(
    body: PersonaCreate,
    svc: Any = Depends(get_persona_service),
):
    """Create a custom persona for the current tenant.

    Returns 409 if the name already exists.
    """
    tenant_id = get_current_tenant_id()

    try:
        persona = await svc.create(
            tenant_id,
            body.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return success_response(data=persona)


@router.get(
    "/personas",
    summary="List all personas for the current tenant",
)
async def list_personas(
    include_inactive: bool = Query(
        False, description="Include soft-deleted personas",
    ),
    svc: Any = Depends(get_persona_service),
):
    """List all personas (built-in + custom) for the tenant."""
    tenant_id = get_current_tenant_id()

    personas, total = await svc.list_all(
        tenant_id, include_inactive=include_inactive,
    )

    return success_response(
        data={
            "personas": [
                _persona_to_summary(p) for p in personas
            ],
            "total": total,
        }
    )


@router.get(
    "/personas/{persona_id}",
    summary="Get full persona details",
)
async def get_persona(
    persona_id: uuid.UUID,
    svc: Any = Depends(get_persona_service),
):
    """Get the full configuration of a specific persona."""
    tenant_id = get_current_tenant_id()

    persona = await svc.get_by_id(
        tenant_id, str(persona_id),
    )
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )

    return success_response(data=persona)


@router.patch(
    "/personas/{persona_id}",
    summary="Update a persona",
)
async def update_persona(
    persona_id: uuid.UUID,
    body: PersonaUpdate,
    svc: Any = Depends(get_persona_service),
):
    """Partially update a persona's configuration.

    Changes take effect on the next task spawn — running
    tasks use the config they started with.
    """
    tenant_id = get_current_tenant_id()

    updated = await svc.update(
        tenant_id,
        str(persona_id),
        body.model_dump(exclude_none=True),
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )

    return success_response(
        data={
            "id": updated["id"],
            "name": updated["name"],
            "updated_at": updated["updated_at"],
            "message": (
                "Persona updated. Changes take effect"
                " on next task spawn."
            ),
        }
    )


@router.delete(
    "/personas/{persona_id}",
    summary="Deactivate (soft-delete) a persona",
)
async def delete_persona(
    persona_id: uuid.UUID,
    svc: Any = Depends(get_persona_service),
):
    """Soft-delete a custom persona.

    Built-in personas cannot be deleted (returns 403).
    """
    tenant_id = get_current_tenant_id()

    try:
        result = await svc.delete(
            tenant_id, str(persona_id),
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )

    return success_response(data=result)


# ── Router Schemas ───────────────────────────────────────────


class RouteRequest(BaseModel):
    """Request body for routing a message."""

    message: str = Field(
        ..., min_length=1,
        description="User message to classify and route",
    )
    project_id: uuid.UUID | None = None


class ClassifyRequest(BaseModel):
    """Request body for intent classification only."""

    message: str = Field(
        ..., min_length=1,
        description="Message to classify",
    )


# ── Router Endpoints ─────────────────────────────────────────


@router.post(
    "/route",
    status_code=status.HTTP_201_CREATED,
    summary="Route a message to the best agent",
)
async def route_message(
    body: RouteRequest,
    chief: Any = Depends(get_chief_router),
):
    """Classify the user's intent and route to a specialist.

    Creates an AgentSession, spawns a task for the matched
    persona, and returns routing metadata.
    """
    tenant_id = get_current_tenant_id()

    try:
        result = await chief.route(
            tenant_id=tenant_id,
            message=body.message,
            project_id=body.project_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return success_response(data=result)


@router.post(
    "/classify",
    summary="Classify intent without routing",
)
async def classify_message(
    body: ClassifyRequest,
    chief: Any = Depends(get_chief_router),
):
    """Classify the intent of a message without spawning a task.

    Useful for debugging classification or previewing routing
    decisions before committing.
    """
    result = await chief.classify_detailed(body.message)
    return success_response(data=result)


@router.get(
    "/sessions",
    summary="List routing sessions",
)
async def list_sessions(
    intent: str | None = Query(
        None, description="Filter by classified intent",
    ),
    session_status: str | None = Query(
        None, alias="status",
        description="Filter by session status",
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    chief: Any = Depends(get_chief_router),
):
    """List routing sessions for the current tenant."""
    tenant_id = get_current_tenant_id()

    sessions, total = await chief.list_sessions(
        tenant_id,
        intent=intent,
        status=session_status,
        limit=limit,
        offset=offset,
    )

    return paginated_response(
        data=sessions,
        total=total,
        page_size=limit,
        has_more=(offset + limit) < total,
    )


# ── Schedule Schemas ─────────────────────────────────────────


class ScheduleCreate(BaseModel):
    """Request body for creating a scheduled job."""

    name: str = Field(
        ..., min_length=1, max_length=200,
        description="Human-readable job name",
    )
    cron_expression: str = Field(
        ..., min_length=5, max_length=100,
        description="Standard 5-field cron expression",
    )
    agent_name: str = Field(
        ..., min_length=1, max_length=100,
        description="Persona to run this job",
    )
    description: str | None = None
    input: dict[str, Any] | None = Field(
        None, description="Task input for the agent",
    )
    timeout_seconds: int = Field(
        600, ge=1, le=86400,
    )
    max_retries: int = Field(3, ge=0, le=10)
    properties: dict[str, Any] | None = None


class ScheduleUpdate(BaseModel):
    """Partial update for a scheduled job."""

    description: str | None = None
    cron_expression: str | None = None
    agent_name: str | None = None
    input: dict[str, Any] | None = None
    is_active: bool | None = None
    timeout_seconds: int | None = Field(
        None, ge=1, le=86400,
    )
    max_retries: int | None = Field(None, ge=0, le=10)
    properties: dict[str, Any] | None = None


# ── Schedule Endpoints ───────────────────────────────────────


@router.post(
    "/schedules",
    status_code=status.HTTP_201_CREATED,
    summary="Create a scheduled job",
)
async def create_schedule(
    body: ScheduleCreate,
    svc: Any = Depends(get_scheduler_service),
):
    """Create a new cron-based scheduled job.

    Returns 409 if name already exists, 400 if cron is invalid.
    """
    tenant_id = get_current_tenant_id()

    try:
        job = await svc.create(
            tenant_id,
            body.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        detail = str(exc)
        code = (
            status.HTTP_409_CONFLICT
            if "already exists" in detail
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=code, detail=detail,
        )

    return success_response(data=job)


@router.get(
    "/schedules",
    summary="List scheduled jobs",
)
async def list_schedules(
    include_inactive: bool = Query(
        False,
        description="Include disabled schedules",
    ),
    svc: Any = Depends(get_scheduler_service),
):
    """List all scheduled jobs for the current tenant."""
    tenant_id = get_current_tenant_id()

    jobs, total = await svc.list_all(
        tenant_id,
        include_inactive=include_inactive,
    )

    return success_response(
        data={"schedules": jobs, "total": total},
    )


@router.get(
    "/schedules/{schedule_id}",
    summary="Get schedule details",
)
async def get_schedule(
    schedule_id: uuid.UUID,
    svc: Any = Depends(get_scheduler_service),
):
    """Get full details of a scheduled job."""
    tenant_id = get_current_tenant_id()

    job = await svc.get_by_id(
        tenant_id, str(schedule_id),
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found",
        )

    return success_response(data=job)


@router.patch(
    "/schedules/{schedule_id}",
    summary="Update a scheduled job",
)
async def update_schedule(
    schedule_id: uuid.UUID,
    body: ScheduleUpdate,
    svc: Any = Depends(get_scheduler_service),
):
    """Update a scheduled job's configuration.

    If cron_expression changes, next_run_at is recomputed.
    Setting is_active=true resets consecutive_failures.
    """
    tenant_id = get_current_tenant_id()

    try:
        updated = await svc.update(
            tenant_id,
            str(schedule_id),
            body.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found",
        )

    return success_response(
        data={
            "id": updated["id"],
            "cron_expression": updated["cron_expression"],
            "next_run_at": updated["next_run_at"],
            "message": "Schedule updated and rescheduled",
        }
    )


@router.delete(
    "/schedules/{schedule_id}",
    summary="Delete (deactivate) a scheduled job",
)
async def delete_schedule(
    schedule_id: uuid.UUID,
    svc: Any = Depends(get_scheduler_service),
):
    """Soft-delete a scheduled job."""
    tenant_id = get_current_tenant_id()

    result = await svc.delete(
        tenant_id, str(schedule_id),
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found",
        )

    return success_response(data=result)


# ── Project Schemas ──────────────────────────────────────────


class ProjectRegister(BaseModel):
    """Request body for registering a project."""

    name: str = Field(
        ..., min_length=1, max_length=200,
        description="Project name (e.g., 'life-graph')",
    )
    path: str = Field(
        ..., min_length=1,
        description="Absolute path on host",
    )
    description: str | None = None
    git_url: str | None = None


# ── Project Endpoints ────────────────────────────────────────


@router.post(
    "/projects",
    status_code=status.HTTP_201_CREATED,
    summary="Register a project codebase",
)
async def register_project(
    body: ProjectRegister,
    svc: Any = Depends(get_project_registry),
):
    """Register a new project and auto-scan it.

    Detects language, framework, git info, and file counts.
    Returns 409 if name already exists.
    """
    tenant_id = get_current_tenant_id()

    try:
        project = await svc.register(
            tenant_id,
            body.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        detail = str(exc)
        code = (
            status.HTTP_409_CONFLICT
            if "already exists" in detail
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=code, detail=detail,
        )

    return success_response(data=project)


@router.post(
    "/projects/{project_id}/scan",
    summary="Re-scan a project",
)
async def scan_project(
    project_id: uuid.UUID,
    svc: Any = Depends(get_project_registry),
):
    """Re-scan a project for updated metadata."""
    tenant_id = get_current_tenant_id()

    result = await svc.scan(
        tenant_id, str(project_id),
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    return success_response(data=result)


@router.get(
    "/projects",
    summary="List registered projects",
)
async def list_projects(
    language: str | None = Query(
        None, description="Filter by language",
    ),
    svc: Any = Depends(get_project_registry),
):
    """List all active projects for the current tenant."""
    tenant_id = get_current_tenant_id()

    projects, total = await svc.list_all(
        tenant_id, language=language,
    )

    return success_response(
        data={"projects": projects, "total": total},
    )


@router.get(
    "/projects/{project_id}",
    summary="Get project details",
)
async def get_project(
    project_id: uuid.UUID,
    svc: Any = Depends(get_project_registry),
):
    """Get full project details including scan data."""
    tenant_id = get_current_tenant_id()

    project = await svc.get_by_id(
        tenant_id, str(project_id),
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    return success_response(data=project)


@router.delete(
    "/projects/{project_id}",
    summary="Remove a project",
)
async def delete_project(
    project_id: uuid.UUID,
    svc: Any = Depends(get_project_registry),
):
    """Soft-delete a registered project."""
    tenant_id = get_current_tenant_id()

    result = await svc.delete(
        tenant_id, str(project_id),
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    return success_response(data=result)


# ── Notification Endpoints ───────────────────────────────────


@router.get(
    "/notifications",
    summary="List notifications",
)
async def list_notifications(
    priority: str | None = Query(
        None, description="Filter: critical|important|info",
    ),
    read: bool | None = Query(
        None, description="Filter by read status",
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    svc: Any = Depends(get_notification_engine),
):
    """List notifications for the current tenant."""
    tenant_id = get_current_tenant_id()

    is_read = read  # None = show all
    notifs, total, unread = await svc.list_all(
        tenant_id,
        priority=priority,
        is_read=is_read,
        limit=limit,
        offset=offset,
    )

    return success_response(
        data={
            "notifications": notifs,
            "total": total,
            "unread_count": unread,
        },
    )


@router.patch(
    "/notifications/{notification_id}/read",
    summary="Mark notification as read",
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    svc: Any = Depends(get_notification_engine),
):
    """Mark a single notification as read."""
    tenant_id = get_current_tenant_id()

    result = await svc.mark_read(
        tenant_id, str(notification_id),
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Notification {notification_id}"
                " not found"
            ),
        )

    return success_response(data=result)


@router.post(
    "/notifications/read-all",
    summary="Mark all notifications as read",
)
async def mark_all_read(
    svc: Any = Depends(get_notification_engine),
):
    """Mark all unread notifications as read."""
    tenant_id = get_current_tenant_id()

    count = await svc.mark_all_read(tenant_id)
    return success_response(
        data={
            "marked_read": count,
            "marked_count": count,
            "message": f"{count} notifications marked as read",
        },
    )

