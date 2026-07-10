"""Agent integration routes (Phase B — T-051).

Provides endpoints for AI agent frameworks to build context
before a task and to learn memories from completed tasks.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import (
    get_intention_service,
    get_memory_manager,
    get_recall_engine,
    get_store,
)
from life_graph.api.responses import success_response
from life_graph.models.schemas import MemoryResponse
from life_graph.services.agent_bridge import LifeGraphBridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ── Dependency ───────────────────────────────────────────────


def get_bridge():
    """Return a LifeGraphBridge wired to all required services."""
    return LifeGraphBridge(
        store=get_store(),
        recall_engine=get_recall_engine(),
        memory_manager=get_memory_manager(),
        intention_service=get_intention_service(),
    )


# ── Request schemas ──────────────────────────────────────────


class BuildContextRequest(BaseModel):
    """Body for building agent context before a task."""

    task: str = Field(..., min_length=1, description="Natural-language task description")
    project: str | None = Field(None, description="Optional project scope")


class LearnRequest(BaseModel):
    """Body for learning memories from a completed task."""

    conversation: str = Field(
        ..., min_length=1, description="Full text of the agent conversation"
    )
    context: dict[str, Any] | None = Field(
        None, description="Optional context metadata (project, tool, etc.)"
    )


# ── Routes ───────────────────────────────────────────────────


@router.post(
    "/context",
    summary="Build agent context for a task",
)
async def build_context(
    body: BuildContextRequest,
    bridge: LifeGraphBridge = Depends(get_bridge),
):
    """Build rich context for an agent starting a task.

    Runs the proactive recall pipeline and formats identity,
    decisions, intentions, and warnings into a dict suitable
    for injection into an agent's system prompt.
    """
    ctx = await bridge.build_agent_context(
        task=body.task,
        project=body.project,
    )
    logger.info(
        "Built agent context for task (project=%s)",
        body.project,
    )
    return success_response(data=ctx)


@router.post(
    "/learn",
    status_code=status.HTTP_201_CREATED,
    summary="Learn from a completed task",
)
async def learn_from_task(
    body: LearnRequest,
    bridge: LifeGraphBridge = Depends(get_bridge),
):
    """Extract and store memories from an agent's completed conversation.

    Runs the full ingestion pipeline (extract → score →
    contradiction check → store) on the conversation text.
    """
    source = "agent_task"
    if body.context and body.context.get("source"):
        source = body.context["source"]

    memories = await bridge.learn_from_task(
        conversation=body.conversation,
        source=source,
    )
    logger.info("Learned %d memories from agent task", len(memories))
    return success_response(data=memories)
