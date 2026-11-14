"""ConversationDistiller — promote a chat's new user-facts into pending memories
and archive the whole thread to MinIO.

Tier 1: the user's turns created since ``Conversation.last_distilled_at`` run
through ``MemoryManager.ingest`` (3-tier extract + dedup), landing as
``status="pending"`` memories tagged ``"chat"`` with ``conversation_id``
provenance — the approval gate then applies.

Tier 2: the complete thread is written to the ``conversations`` MinIO bucket as
a JSON snapshot (overwritten each run) — a durable, reprocessable backup.

The marker is advanced on every run (even a no-op) so the idle cron cannot
re-enqueue the same conversation forever; a new chat message bumps
``updated_at`` and re-makes it eligible.

Only the owner's own words are distilled. A user turn can carry text the
owner shared from another app or a page an agent read, fenced as data
(core/trust.py ``with_shared`` / ``fence_untrusted``); Jarvis reads it as
information, and :func:`owner_words` takes it out before extraction so it
cannot cross into memory as the owner's word and reach the always-loaded
profile card (core/evidence.py, learn-only-from-owner). A turn that was
nothing but shared text distils nothing.
"""

from __future__ import annotations

import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.core.trust import classify_surface, strip_fenced
from life_graph.models.db import Conversation, ConversationMessage, _utcnow
from life_graph.models.schemas import MemoryUpdate
from life_graph.services.conversation import ConversationNotFoundError

if TYPE_CHECKING:
    import uuid

logger = logging.getLogger(__name__)

ARCHIVE_BUCKET = "conversations"


def build_snapshot(conv: Any, messages: list[Any], distilled_memory_ids: list[uuid.UUID]) -> bytes:
    """Serialize the whole thread to a UTF-8 JSON snapshot (bytes)."""
    doc = {
        "conversation_id": str(conv.id),
        "tenant_id": conv.tenant_id,
        "title": conv.title,
        "distilled_at": _utcnow().isoformat(),
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "cited_memory_ids": [str(c) for c in (m.cited_memory_ids or [])],
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "distilled_memory_ids": [str(m) for m in distilled_memory_ids],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")


def owner_words(turns: list[Any]) -> tuple[str, int]:
    """``(the owner's own words from *turns*, how many carried outside text)``.

    The fenced blocks are dropped turn by turn, so a turn that mixed a
    question with a pasted email still contributes the question.
    """
    kept: list[str] = []
    fenced = 0
    for turn in turns:
        text, removed = strip_fenced(getattr(turn, "content", None))
        fenced += 1 if removed else 0
        if text:
            kept.append(text)
    return "\n".join(kept), fenced


class ConversationDistiller:
    """Distill new facts from a conversation and archive the thread."""

    def __init__(self, session_factory, memory_manager, minio, store) -> None:
        self._session_factory = session_factory
        self._manager = memory_manager
        self._minio = minio
        self._store = store

    async def distill(self, conversation_id: uuid.UUID) -> dict:
        """Extract new user-facts → pending memories; archive the thread.

        Returns ``{"new_facts": int, "archived": bool, "skipped": bool}``.
        Raises ``ConversationNotFoundError`` if the conversation is missing or owned
        by another tenant.
        """
        tenant_id = get_current_tenant_id()

        async with self._session_factory() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.tenant_id != tenant_id:
                raise ConversationNotFoundError("Conversation not found")

            rows = await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.created_at.asc())
            )
            messages = list(rows.scalars().all())

            prev_marker = conv.last_distilled_at
            new_user_turns = [
                m
                for m in messages
                if m.role == "user" and (prev_marker is None or m.created_at > prev_marker)
            ]

            if not new_user_turns:
                conv.last_distilled_at = _utcnow()  # advance to avoid re-enqueue
                await session.commit()
                return {"new_facts": 0, "archived": False, "skipped": True}

            # Tier 1: extract new facts (pending, deduped) with provenance.
            # The owner's own words only — never the text a turn quoted.
            text, fenced_turns = owner_words(new_user_turns)
            if fenced_turns:
                logger.info(
                    "Distilling conversation %s: outside text dropped from %d of %d turns",
                    conversation_id,
                    fenced_turns,
                    len(new_user_turns),
                )
            if not text.strip():
                # Every new turn was shared text: there is nothing the owner
                # said to learn from, and the marker still advances.
                conv.last_distilled_at = _utcnow()
                await session.commit()
                return {"new_facts": 0, "archived": False, "skipped": True}
            memories = await self._manager.ingest(
                text,
                context={"conversation_id": str(conversation_id)},
                source="chat",
                # These are the user's own conversation turns, so they resolve
                # to SELF via the surface map rather than inheriting the
                # store's "verified" default. Passed through classify_surface
                # so the map stays the single source of truth for the policy.
                trust_tier=classify_surface("chat").value,
            )
            # Append the "chat" tag to each distilled memory for identification.
            for mem in memories:
                tags = list(mem.tags or [])
                if "chat" not in tags:
                    tags.append("chat")
                    await self._store.update(mem.id, MemoryUpdate(tags=tags))

            # Tier 2: archive the whole current thread (best-effort).
            archived = False
            try:
                data = build_snapshot(conv, messages, [m.id for m in memories])
                key = f"{tenant_id}/{conversation_id}.json"
                self._minio.upload(ARCHIVE_BUCKET, key, data, content_type="application/json")
                archived = True
            except Exception:  # pragma: no cover - archive must never lose facts
                logger.exception("Archive upload failed for conversation %s", conversation_id)

            conv.last_distilled_at = _utcnow()
            await session.commit()

        with contextlib.suppress(Exception):  # events must never break the job
            await event_bus.emit(
                EventType.CONVERSATION_DISTILLED,
                {
                    "conversation_id": str(conversation_id),
                    "tenant_id": tenant_id,
                    "new_facts": len(memories),
                },
                source="distillation",
            )

        return {"new_facts": len(memories), "archived": archived, "skipped": False}
