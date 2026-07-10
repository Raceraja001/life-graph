"""Agent messaging endpoints — Era 7."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query

from life_graph.api.dependencies import get_messaging_service
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import (
    AgentMessageCreate,
    AgentMessageResponse,
    MessageReply,
)
from life_graph.services.agent_messaging import AgentMessagingService

router = APIRouter(prefix="/agent-messages", tags=["Agent Messages"])


@router.post("", status_code=201)
async def send_message(
    data: AgentMessageCreate,
    sender_agent: str = Query(..., description="Sender agent identifier"),
    tenant_id: str = Depends(get_current_tenant_id),
    svc: AgentMessagingService = Depends(get_messaging_service),
):
    """Send a message from one agent to another."""
    msg = await svc.send(
        tenant_id, sender_agent, data.model_dump(exclude_none=True),
    )
    return success_response(data=AgentMessageResponse.model_validate(msg))


@router.get("/inbox/{agent}")
async def get_inbox(
    agent: str,
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    tenant_id: str = Depends(get_current_tenant_id),
    svc: AgentMessagingService = Depends(get_messaging_service),
):
    """Get inbox for an agent."""
    msgs = await svc.get_inbox(tenant_id, agent, status=status, limit=limit)
    return success_response(data=[AgentMessageResponse.model_validate(m) for m in msgs])


@router.patch("/{message_id}/read")
async def mark_read(
    message_id: uuid.UUID,
    tenant_id: str = Depends(get_current_tenant_id),
    svc: AgentMessagingService = Depends(get_messaging_service),
):
    """Mark a message as read."""
    try:
        msg = await svc.mark_read(tenant_id, message_id)
        return success_response(data=AgentMessageResponse.model_validate(msg))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{message_id}/reply", status_code=201)
async def reply_to_message(
    message_id: uuid.UUID,
    data: MessageReply,
    sender_agent: str = Query(..., description="Sender agent identifier"),
    tenant_id: str = Depends(get_current_tenant_id),
    svc: AgentMessagingService = Depends(get_messaging_service),
):
    """Reply to a message."""
    try:
        msg = await svc.reply(
            tenant_id, message_id, sender_agent,
            data.model_dump(exclude_none=True),
        )
        return success_response(data=AgentMessageResponse.model_validate(msg))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

