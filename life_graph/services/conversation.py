"""ConversationService — grounded, multi-turn chat over approved memories."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import Conversation, ConversationMessage, _utcnow

_TITLE_MAX = 60
_HISTORY_TURNS = 6
_RETRIEVE_LIMIT = 8


class ConversationNotFound(Exception):
    """Raised when a conversation doesn't exist or belongs to another tenant."""


class ConversationService:
    """Retrieve → synthesize → persist a chat turn, all approved-only."""

    def __init__(self, session_factory, hybrid_engine, synthesis) -> None:
        self._session_factory = session_factory
        self._engine = hybrid_engine
        self._synthesis = synthesis

    async def create(self) -> Conversation:
        tenant_id = get_current_tenant_id()
        async with self._session_factory() as session:
            conv = Conversation(tenant_id=tenant_id, title=None)
            session.add(conv)
            await session.commit()
            return conv

    async def list_recent(self, limit: int = 20) -> list[Conversation]:
        tenant_id = get_current_tenant_id()
        async with self._session_factory() as session:
            rows = await session.execute(
                select(Conversation)
                .where(Conversation.tenant_id == tenant_id)
                .order_by(Conversation.updated_at.desc())
                .limit(limit)
            )
            return list(rows.scalars().all())

    async def get_thread(
        self, conversation_id: uuid.UUID
    ) -> tuple[Conversation, list[ConversationMessage]] | None:
        tenant_id = get_current_tenant_id()
        async with self._session_factory() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.tenant_id != tenant_id:
                return None
            rows = await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.created_at.asc())
            )
            return conv, list(rows.scalars().all())

    async def delete(self, conversation_id: uuid.UUID) -> bool:
        tenant_id = get_current_tenant_id()
        async with self._session_factory() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.tenant_id != tenant_id:
                return False
            await session.delete(conv)
            await session.commit()
            return True

    async def ask(self, conversation_id: uuid.UUID, question: str) -> dict[str, Any]:
        tenant_id = get_current_tenant_id()

        async with self._session_factory() as session:
            # 0. ownership/existence check FIRST — fail fast before spending
            # a retrieval (embedding + DB search) on a conversation we're
            # about to reject anyway.
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.tenant_id != tenant_id:
                raise ConversationNotFound("Conversation not found")

            # 1. retrieve approved-only
            retrieval = await self._engine.tri_search(
                question, limit=_RETRIEVE_LIMIT, statuses=("active",)
            )
            memories = retrieval.get("memories", [])

            # prior turns → history for the LLM (most recent _HISTORY_TURNS,
            # restored to chronological order)
            prior = await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(_HISTORY_TURNS)
            )
            history = [
                {"role": m.role, "content": m.content} for m in reversed(prior.scalars().all())
            ]

            # 2. synthesize — synthesis.py filters memories with empty/missing
            # ids BEFORE numbering, so the citations it returns are already
            # in lockstep with the [Memory J] tokens in the answer text; no
            # post-hoc filtering needed (or safe to do) here.
            result = await self._synthesis.synthesize(question, memories, history=history or None)
            citations = result.get("citations", [])

            # 3. persist both turns
            user_turn = ConversationMessage(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                role="user",
                content=question,
                cited_memory_ids=[],
            )
            assistant_turn = ConversationMessage(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                role="assistant",
                content=result["answer"],
                cited_memory_ids=citations,
                model=result.get("model"),
            )
            session.add(user_turn)
            session.add(assistant_turn)
            if not conv.title:
                conv.title = question[:_TITLE_MAX]
            # Every turn touches the conversation, so ordering by
            # updated_at (list_recent) reflects recent activity — not just
            # the first turn, which is the only mutation onupdate would
            # otherwise catch.
            conv.updated_at = _utcnow()
            await session.commit()
            await session.refresh(assistant_turn)

        try:
            await event_bus.emit(
                EventType.CONVERSATION_MESSAGE,
                {
                    "conversation_id": str(conversation_id),
                    "tenant_id": tenant_id,
                    "preview": result["answer"][:80],
                },
                source="conversation",
            )
        except Exception:  # pragma: no cover - events must never break the reply
            pass

        return {"message": assistant_turn, "citations": citations}
