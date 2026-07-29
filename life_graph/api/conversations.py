"""Ask-your-memories chat API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from life_graph.api.dependencies import get_conversation_service, get_store
from life_graph.api.responses import success_response
from life_graph.models.schemas import MemoryResponse
from life_graph.services.conversation import ConversationNotFound, ConversationService
from life_graph.storage.postgres import PostgresMemoryStore

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
        data=[
            {"id": str(c.id), "title": c.title, "updated_at": str(c.updated_at)}
            for c in convs
        ]
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
    except ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation not found")
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
