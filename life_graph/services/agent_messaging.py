"""Agent messaging service — inter-agent communication.

Provides message sending, inbox queries, read receipts,
and threaded replies.  Integrates with Redis pub/sub for
real-time delivery and auto-creates tasks for task_request messages.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, and_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.core.events import EventType, event_bus
from life_graph.models.db import AgentMessage, AgentTask

logger = logging.getLogger(__name__)


class AgentMessagingService:
    """Inter-agent messaging with Redis pub/sub delivery."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def send(
        self, tenant_id: str, sender_agent: str, data: dict,
    ) -> AgentMessage:
        """Send a message between agents."""
        async with self._sf() as session:
            msg = AgentMessage(
                tenant_id=tenant_id,
                sender_agent=sender_agent,
                recipient_agent=data["recipient_agent"],
                message_type=data["message_type"],
                subject=data.get("subject"),
                body=data.get("body"),
                payload=data.get("payload", {}),
                attachments=data.get("attachments", []),
                priority=data.get("priority", "medium"),
                task_id=data.get("task_id"),
                expires_at=data.get("expires_at"),
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)

            # Auto-create task for task_request messages
            if data["message_type"] == "task_request" and data.get("payload"):
                try:
                    task = AgentTask(
                        tenant_id=tenant_id,
                        title=data["payload"].get(
                            "title", data.get("subject", "Untitled task"),
                        ),
                        description=data["payload"].get("description"),
                        assigned_agent=data["recipient_agent"],
                        created_by_agent=sender_agent,
                        source_message_id=msg.id,
                        status_history=[
                            {
                                "status": "pending",
                                "at": datetime.now(timezone.utc).isoformat(),
                            }
                        ],
                    )
                    session.add(task)
                    await session.commit()
                    msg.task_id = task.id
                    await session.commit()
                except Exception:
                    logger.warning(
                        "Failed to auto-create task from message", exc_info=True,
                    )

            # Publish to Redis for real-time delivery
            try:
                from life_graph.storage.redis import get_redis

                r = get_redis()
                if r:
                    channel = f"agent_messages:{tenant_id}:{data['recipient_agent']}"
                    await r.publish(
                        channel,
                        json.dumps(
                            {
                                "message_id": str(msg.id),
                                "sender": sender_agent,
                                "type": data["message_type"],
                                "subject": data.get("subject"),
                                "priority": data.get("priority", "medium"),
                            }
                        ),
                    )
            except Exception:
                logger.debug("Redis publish skipped", exc_info=True)

            await event_bus.emit(
                EventType.MESSAGE_SENT,
                {
                    "message_id": str(msg.id),
                    "sender": sender_agent,
                    "recipient": data["recipient_agent"],
                },
                source="messaging",
            )
            return msg

    async def get_inbox(
        self,
        tenant_id: str,
        agent: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AgentMessage]:
        """Get messages for an agent, sorted by priority DESC, created_at DESC."""
        async with self._sf() as session:
            q = select(AgentMessage).where(
                and_(
                    AgentMessage.tenant_id == tenant_id,
                    AgentMessage.recipient_agent == agent,
                )
            )
            if status:
                q = q.where(AgentMessage.status == status)

            priority_order = case(
                (AgentMessage.priority == "critical", 4),
                (AgentMessage.priority == "high", 3),
                (AgentMessage.priority == "medium", 2),
                (AgentMessage.priority == "low", 1),
                else_=0,
            )
            q = q.order_by(desc(priority_order), desc(AgentMessage.created_at))
            q = q.limit(limit)

            result = await session.execute(q)
            return list(result.scalars().all())

    async def mark_read(
        self, tenant_id: str, message_id: uuid.UUID,
    ) -> AgentMessage:
        """Mark a message as read."""
        async with self._sf() as session:
            msg = await session.get(AgentMessage, message_id)
            if not msg or msg.tenant_id != tenant_id:
                raise ValueError(f"Message {message_id} not found")

            msg.status = "read"
            msg.read_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(msg)

            await event_bus.emit(
                EventType.MESSAGE_READ,
                {"message_id": str(message_id), "agent": msg.recipient_agent},
                source="messaging",
            )
            return msg

    async def reply(
        self,
        tenant_id: str,
        message_id: uuid.UUID,
        sender_agent: str,
        data: dict,
    ) -> AgentMessage:
        """Reply to a message, auto-setting thread_id and reply_to_id."""
        async with self._sf() as session:
            original = await session.get(AgentMessage, message_id)
            if not original or original.tenant_id != tenant_id:
                raise ValueError(f"Message {message_id} not found")

            reply_msg = AgentMessage(
                tenant_id=tenant_id,
                sender_agent=sender_agent,
                recipient_agent=original.sender_agent,
                thread_id=original.thread_id or original.id,
                reply_to_id=message_id,
                message_type="reply",
                subject=f"Re: {original.subject}" if original.subject else None,
                body=data["body"],
                payload=data.get("payload", {}),
                attachments=data.get("attachments", []),
                priority=original.priority,
                task_id=original.task_id,
            )
            session.add(reply_msg)
            await session.commit()
            await session.refresh(reply_msg)

            await event_bus.emit(
                EventType.MESSAGE_SENT,
                {
                    "message_id": str(reply_msg.id),
                    "sender": sender_agent,
                    "recipient": original.sender_agent,
                    "reply_to": str(message_id),
                },
                source="messaging",
            )
            return reply_msg
