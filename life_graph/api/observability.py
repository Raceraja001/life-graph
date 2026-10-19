"""Observability API: budget, system health, agents console, decision gaps.

Read-only views for running Life Graph unattended
(docs/specs/agent-observability.md). Every route is tenant-scoped except
the system view's process-level facts (subsystems, runner, Ollama), which
describe this deployment rather than any tenant's data.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services import observability
from life_graph.storage.database import async_session

router = APIRouter(prefix="/kernel/observability", tags=["observability"])


@router.get("/budget", summary="Month-to-date spend against the cap, with the top tasks")
async def get_budget(top: int = Query(10, ge=1, le=100)):
    async with async_session() as session:
        data = await observability.budget(session, get_current_tenant_id(), top=top)
    return success_response(data=data)


@router.get("/system", summary="Subsystems, dev-task runner, queue, drivers and local models")
async def get_system(request: Request):
    async with async_session() as session:
        data = await observability.system(session, request.app.state)
    return success_response(data=data)


@router.get("/agents", summary="Every persona, its model, and tools it lists that do not exist")
async def get_agents():
    return success_response(data=await observability.agents(get_current_tenant_id()))


@router.get("/decision-gaps", summary="Topics discussed often with no recorded decision")
async def get_decision_gaps(
    days: int = Query(90, ge=7, le=730),
    min_mentions: int = Query(4, ge=2, le=50),
    limit: int = Query(20, ge=1, le=100),
):
    async with async_session() as session:
        data = await observability.decision_gaps(
            session, get_current_tenant_id(), days=days, min_mentions=min_mentions, limit=limit
        )
    return success_response(data=data)
