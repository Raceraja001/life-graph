"""Ask-your-memories chat API."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from life_graph.api.dependencies import get_conversation_service, get_store
from life_graph.api.responses import success_response
from life_graph.models.schemas import MemoryResponse
from life_graph.services.conversation import ConversationNotFoundError, ConversationService
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


class MessageBody(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("content must not be empty")
        return v


@router.post("")
async def create_conversation(svc: ConversationService = Depends(get_conversation_service)):
    conv = await svc.create()
    return success_response(
        data={"id": str(conv.id), "title": conv.title, "created_at": str(conv.created_at)}
    )


@router.get("")
async def list_conversations(svc: ConversationService = Depends(get_conversation_service)):
    convs = await svc.list_recent()
    return success_response(
        data=[{"id": str(c.id), "title": c.title, "updated_at": str(c.updated_at)} for c in convs]
    )


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: UUID, svc: ConversationService = Depends(get_conversation_service)
):
    thread = await svc.get_thread(conversation_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv, messages = thread
    return success_response(
        data={
            "id": str(conv.id),
            "title": conv.title,
            "messages": [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "cited_memory_ids": [str(x) for x in m.cited_memory_ids],
                    "model": m.model,
                    "created_at": str(m.created_at),
                }
                for m in messages
            ],
        }
    )


@router.post("/{conversation_id}/messages")
async def post_message(
    conversation_id: UUID,
    body: MessageBody,
    svc: ConversationService = Depends(get_conversation_service),
    store: PostgresMemoryStore = Depends(get_store),
):
    try:
        result = await svc.ask(conversation_id, body.content)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    msg = result["message"]
    # resolve citation ids to full memories for chips
    citations = []
    for mid in result["citations"]:
        row = await store.retrieve(UUID(mid))
        if row is not None:
            citations.append(MemoryResponse.model_validate(row))
    return success_response(
        data={
            "message": {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "cited_memory_ids": [str(x) for x in msg.cited_memory_ids],
                "model": msg.model,
                "created_at": str(msg.created_at),
            },
            "citations": [c.model_dump(mode="json") for c in citations],
        }
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID, svc: ConversationService = Depends(get_conversation_service)
):
    deleted = await svc.delete(conversation_id)
    return success_response(data={"deleted": deleted})


@router.post("/{conversation_id}/distill")
async def distill_conversation_endpoint(
    conversation_id: UUID,
    svc: ConversationService = Depends(get_conversation_service),
):
    """Distill this conversation's new facts into pending memories + archive.

    Enqueues a background job (results arrive via the CONVERSATION_DISTILLED
    event); falls back to running inline if the ARQ pool is unavailable so a
    manual tap still works.
    """
    from life_graph.core.tenant import get_current_tenant_id
    from life_graph.workers.distill import DISTILL_JOB_NAME

    thread = await svc.get_thread(conversation_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    tenant_id = get_current_tenant_id()
    try:
        from arq import create_pool

        from life_graph.workers.settings import parse_redis_settings

        pool = await create_pool(parse_redis_settings())
        try:
            await pool.enqueue_job(DISTILL_JOB_NAME, str(conversation_id), tenant_id)
        finally:
            await pool.close()
    except Exception as e:
        logger.warning(
            "ARQ enqueue failed for distill of conversation %s: %s — running inline",
            conversation_id,
            e,
        )
        # Redis/pool unavailable — run inline so a manual tap still works.
        from life_graph.api.dependencies import get_distillation_service

        await get_distillation_service().distill(conversation_id)

    return success_response({"status": "distilling"})
