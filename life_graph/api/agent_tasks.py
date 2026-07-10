"""Agent task delegation endpoints — Era 7."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException

from life_graph.api.dependencies import get_delegation_engine
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import (
    AgentTaskCreate,
    AgentTaskResponse,
    AgentTaskTree,
    AgentTaskUpdate,
)
from life_graph.services.delegation import DelegationEngine

router = APIRouter(prefix="/agent-tasks", tags=["Agent Tasks"])


@router.post("", status_code=201)
async def create_task(
    data: AgentTaskCreate,
    tenant_id: str = Depends(get_current_tenant_id),
    engine: DelegationEngine = Depends(get_delegation_engine),
):
    """Create a new agent task (optionally with parent for delegation)."""
    task = await engine.create_task(tenant_id, data.model_dump(exclude_none=True))
    return success_response(data=AgentTaskResponse.model_validate(task))


@router.get("/{task_id}/children")
async def get_children(
    task_id: uuid.UUID,
    tenant_id: str = Depends(get_current_tenant_id),
    engine: DelegationEngine = Depends(get_delegation_engine),
):
    """Get direct children of a task."""
    from sqlalchemy import select, and_
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as session:
        result = await session.execute(
            select(AgentTask).where(
                and_(
                    AgentTask.parent_task_id == task_id,
                    AgentTask.tenant_id == tenant_id,
                )
            )
        )
        tasks = result.scalars().all()
        return success_response(data=[AgentTaskResponse.model_validate(t) for t in tasks])


@router.get("/{task_id}/tree")
async def get_task_tree(
    task_id: uuid.UUID,
    tenant_id: str = Depends(get_current_tenant_id),
    engine: DelegationEngine = Depends(get_delegation_engine),
):
    """Get the full task tree from a root task."""
    try:
        tree = await engine.get_task_tree(task_id, tenant_id)

        def serialize(node):
            task_resp = AgentTaskTree.model_validate(node["task"])
            task_resp.children = [serialize(c) for c in node["children"]]
            return task_resp

        return success_response(data=serialize(tree))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    data: AgentTaskUpdate,
    tenant_id: str = Depends(get_current_tenant_id),
    engine: DelegationEngine = Depends(get_delegation_engine),
):
    """Update a task (partial update with status history tracking)."""
    try:
        task = await engine.update_task(
            tenant_id, task_id, data.model_dump(exclude_none=True),
        )
        return success_response(data=AgentTaskResponse.model_validate(task))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: uuid.UUID,
    reason: str = "Cancelled by user",
    tenant_id: str = Depends(get_current_tenant_id),
    engine: DelegationEngine = Depends(get_delegation_engine),
):
    """Cancel a task and all its descendants."""
    try:
        task = await engine.cancel_task(task_id, tenant_id, reason)
        return success_response(data=AgentTaskResponse.model_validate(task))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

