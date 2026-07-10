"""Agent Drivers API — list drivers, view stats, test dispatch.

Prefix: /kernel/drivers
Tags: [drivers]
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import async_session

router = APIRouter(prefix="/kernel/drivers", tags=["drivers"])


# ── Pydantic Schemas ─────────────────────────────────────────


class DriverInfo(BaseModel):
    """Summary of a registered driver."""

    name: str
    available: bool
    capabilities: list[str]
    cost_per_task: float


class DriverStatResponse(BaseModel):
    """Driver performance statistics."""

    driver_name: str
    success_count: int = 0
    failure_count: int = 0
    total_tasks: int = 0
    success_rate: float = 0.0
    total_cost_usd: float = 0.0
    avg_cost_usd: float = 0.0
    total_duration_ms: int = 0
    avg_duration_ms: int = 0
    last_used_at: datetime | None = None


class DispatchRequest(BaseModel):
    """Request body for test dispatch."""

    instruction: str = Field(
        ..., min_length=1,
        description="Natural language task description",
    )
    task_type: str = Field("general", description="Task type (code, research, etc.)")
    project_id: str | None = Field(None, description="Optional project context")
    persona_name: str | None = Field(None, description="Optional persona pin")
    private: bool = Field(False, description="Strip memories/preferences")
    verify_chain: list[str] | None = Field(
        None,
        description="Verifier names to run (default: build_ok, lint_clean)",
    )


class DispatchResponse(BaseModel):
    """Response from a test dispatch."""

    success: bool
    output: str = ""
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: str | None = None
    driver: str = ""
    metadata: dict = {}


# ── Endpoints ────────────────────────────────────────────────


@router.get(
    "",
    summary="List registered drivers",
)
async def list_drivers():
    """List all registered drivers with availability and capabilities.

    Returns each driver's name, current availability status,
    supported task types, and estimated cost per task.
    """
    from life_graph.drivers.registry import driver_registry

    drivers = driver_registry.list_all()
    result = []
    for d in drivers:
        try:
            avail = await d.available()
        except Exception:
            avail = False

        result.append(
            DriverInfo(
                name=d.name,
                available=avail,
                capabilities=d.capabilities(),
                cost_per_task=d.cost_per_task(),
            ).model_dump()
        )

    return success_response(data={"drivers": result, "total": len(result)})


@router.get(
    "/stats",
    summary="Driver performance stats",
)
async def driver_stats(
    window: int = Query(30, ge=1, le=365, description="Stats window in days"),
):
    """Get performance statistics for all drivers.

    Includes success rate, total tasks, cost, and duration metrics
    within the specified time window.
    """
    tenant_id = get_current_tenant_id()

    try:
        from life_graph.models.db import DriverStat
        from sqlalchemy import func, select

        async with async_session() as session:
            # Aggregate across day-bucketed rows, grouped by driver
            result = await session.execute(
                select(
                    DriverStat.driver,
                    func.sum(DriverStat.dispatched).label("dispatched"),
                    func.sum(DriverStat.verified_landed).label("landed"),
                    func.sum(DriverStat.failed).label("failed"),
                    func.sum(DriverStat.total_cost_usd).label("cost"),
                    func.sum(DriverStat.total_duration_ms).label("duration"),
                    func.max(DriverStat.window_start).label("last_window"),
                ).where(
                    DriverStat.tenant_id == tenant_id,
                ).group_by(DriverStat.driver)
            )
            rows = result.all()

            stat_list = []
            for row in rows:
                dispatched = row.dispatched or 0
                landed = row.landed or 0
                failed = row.failed or 0
                cost = row.cost or 0.0
                duration = row.duration or 0
                stat_list.append(
                    DriverStatResponse(
                        driver_name=row.driver,
                        success_count=landed,
                        failure_count=failed,
                        total_tasks=dispatched,
                        success_rate=landed / dispatched if dispatched > 0 else 0.0,
                        total_cost_usd=cost,
                        avg_cost_usd=cost / dispatched if dispatched > 0 else 0.0,
                        total_duration_ms=duration,
                        avg_duration_ms=duration // dispatched if dispatched > 0 else 0,
                        last_used_at=None,  # Day-bucketed, no precise timestamp
                    ).model_dump()
                )

            return success_response(
                data={"stats": stat_list, "window_days": window}
            )
    except Exception as e:
        # DriverStat table may not exist yet
        return success_response(
            data={"stats": [], "window_days": window, "note": "No stats available yet"}
        )


@router.post(
    "/dispatch",
    status_code=status.HTTP_201_CREATED,
    summary="Dispatch a task to a driver (testing)",
)
async def dispatch_task(body: DispatchRequest):
    """Dispatch a task to a driver for testing purposes.

    Uses the full dispatch pipeline: driver selection, context building,
    verification chain, and one-bounce rule. Useful for testing driver
    integration without going through the kernel task system.
    """
    tenant_id = get_current_tenant_id()

    try:
        import uuid
        from life_graph.drivers.dispatcher import TaskDispatcher
        from life_graph.core.events import event_bus

        dispatcher = TaskDispatcher(
            session_factory=async_session,
            event_bus=event_bus,
        )

        task_id = str(uuid.uuid4())

        async with async_session() as session:
            result = await dispatcher.dispatch_task(
                tenant_id=tenant_id,
                task_id=task_id,
                instruction=body.instruction,
                task_type=body.task_type,
                project_id=body.project_id,
                session=session,
                persona_name=body.persona_name,
                private=body.private,
                verify_chain=body.verify_chain,
            )
            await session.commit()

        return success_response(
            data=DispatchResponse(
                success=result.success,
                output=result.output[:2000],  # Cap response size
                cost_usd=result.cost_usd,
                duration_ms=result.duration_ms,
                error=result.error,
                driver=result.metadata.get("driver", "unknown"),
                metadata=result.metadata,
            ).model_dump()
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dispatch failed: {str(e)}",
        )
