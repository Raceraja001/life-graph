"""ConversationService — grounded, multi-turn chat over approved memories."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import Conversation, ConversationMessage

_TITLE_MAX = 60
_HISTORY_TURNS = 6
_RETRIEVE_LIMIT = 8


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

        # 1. retrieve approved-only
        retrieval = await self._engine.tri_search(
            question, limit=_RETRIEVE_LIMIT, statuses=("active",)
        )
        memories = retrieval.get("memories", [])

        async with self._session_factory() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.tenant_id != tenant_id:
                raise ValueError("Conversation not found")

            # prior turns → history for the LLM
            prior = await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.created_at.asc())
            )
            history = [
                {"role": m.role, "content": m.content}
                for m in prior.scalars().all()
            ]

            # 2. synthesize
            result = await self._synthesis.synthesize(
                question, memories, history=history or None
            )

            # 3. persist both turns
            user_turn = ConversationMessage(
                conversation_id=conversation_id, tenant_id=tenant_id,
                role="user", content=question, cited_memory_ids=[],
            )
            assistant_turn = ConversationMessage(
                conversation_id=conversation_id, tenant_id=tenant_id,
                role="assistant", content=result["answer"],
                cited_memory_ids=result.get("citations", []),
                model=result.get("model"),
            )
            session.add(user_turn)
            session.add(assistant_turn)
            if not conv.title:
                conv.title = question[:_TITLE_MAX]
            await session.commit()
            await session.refresh(assistant_turn)

        try:
            await event_bus.emit(
                EventType.CONVERSATION_MESSAGE,
                {"conversation_id": str(conversation_id), "tenant_id": tenant_id,
                 "preview": result["answer"][:80]},
                source="conversation",
            )
        except Exception:  # pragma: no cover - events must never break the reply
            pass

        return {"message": assistant_turn, "citations": result.get("citations", [])}
