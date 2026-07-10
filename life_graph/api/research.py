"""Research engine API routes (Era 4 Personal AI — Phase 6).

Provides endpoints to list research runs, get run details,
and manually trigger a research cycle.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_research_engine
from life_graph.api.responses import success_response, paginated_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.research_engine import ResearchEngine

router = APIRouter(prefix="/research", tags=["research"])


# ── Schemas ──────────────────────────────────────────────────


class ResearchTriggerRequest(BaseModel):
    """Request body for manually triggering research."""
    preference_id: uuid.UUID | None = Field(
        None, description="Research a specific preference (omit for stale scan)"
    )


# ── Endpoints ────────────────────────────────────────────────


@router.get(
    "/runs",
    summary="List research runs",
)
async def list_research_runs(
    engine: ResearchEngine = Depends(get_research_engine),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    run_status: str | None = Query(None, alias="status", description="Filter by status"),
):
    """List research runs for the current tenant.

    Supports pagination and optional status filtering.
    """
    from sqlalchemy import select
    from life_graph.models.db import ResearchRun

    tenant_id = get_current_tenant_id()

    stmt = (
        select(ResearchRun)
        .where(ResearchRun.tenant_id == tenant_id)
    )
    if run_status:
        stmt = stmt.where(ResearchRun.status == run_status)

    stmt = stmt.order_by(ResearchRun.started_at.desc()).limit(limit).offset(offset)

    async with engine._session_factory() as session:
        result = await session.execute(stmt)
        runs = list(result.scalars().all())

    data = [
        {
            "id": str(r.id),
            "query": r.query,
            "status": r.status,
            "evidence_found": r.evidence_found,
            "evidence_added": r.evidence_added,
            "preferences_affected": r.preferences_affected,
            "sources_searched": r.sources_searched,
            "error": r.error,
            "started_at": r.started_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]

    return paginated_response(
        data=data,
        total=None,
        page_size=limit,
        has_more=len(data) == limit,
    )


@router.get(
    "/runs/{run_id}",
    summary="Get research run detail",
)
async def get_research_run(
    run_id: uuid.UUID,
    engine: ResearchEngine = Depends(get_research_engine),
):
    """Get a single research run by ID."""
    from sqlalchemy import select
    from life_graph.models.db import ResearchRun

    tenant_id = get_current_tenant_id()

    async with engine._session_factory() as session:
        stmt = (
            select(ResearchRun)
            .where(ResearchRun.id == run_id)
            .where(ResearchRun.tenant_id == tenant_id)
        )
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run {run_id} not found",
        )

    return success_response(data={
        "id": str(run.id),
        "query": run.query,
        "status": run.status,
        "evidence_found": run.evidence_found,
        "evidence_added": run.evidence_added,
        "preferences_affected": run.preferences_affected,
        "sources_searched": run.sources_searched,
        "properties": run.properties,
        "error": run.error,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    })


@router.post(
    "/trigger",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a research cycle",
)
async def trigger_research(
    body: ResearchTriggerRequest = ResearchTriggerRequest(),
    engine: ResearchEngine = Depends(get_research_engine),
):
    """Manually trigger a research cycle.

    Optionally target a specific preference by ID. Returns 202 Accepted
    with initial status while research runs asynchronously.
    """
    tenant_id = get_current_tenant_id()

    # Run inline for simplicity (could enqueue to ARQ for truly async)
    result = await engine.run_research_cycle(
        tenant_id, preference_id=body.preference_id
    )

    return success_response(data=result)
