"""Delegation engine — hierarchical task decomposition for agent networks.

Manages task creation, child delegation, completion handling,
cancellation cascading, and task tree queries.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.core.events import EventType, event_bus
from life_graph.models.db import AgentTask

logger = logging.getLogger(__name__)


class DelegationEngine:
    """Manages hierarchical agent task delegation."""

    MAX_DEPTH = 5

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create_task(self, tenant_id: str, data: dict) -> AgentTask:
        """Create a top-level or child task with depth tracking."""
        async with self._sf() as session:
            task = AgentTask(
                tenant_id=tenant_id,
                title=data.get("title") or data.get("task_name", "Untitled Task"),
                description=data.get("description"),
                task_type=data.get("task_type", "general"),
                instructions=data.get("instructions"),
                assigned_agent=data.get("assigned_agent"),
                created_by_agent=data.get("created_by_agent"),
                project_id=data.get("project_id"),
                priority=data.get("priority", "medium"),
                timeout_seconds=data.get("timeout_seconds", 3600),
                max_retries=data.get("max_retries", 2),
                on_child_failure=data.get("on_child_failure", "continue"),
                deadline=data.get("deadline"),
                tags=data.get("tags"),
                properties=data.get("properties", {}),
                status_history=[{"status": "pending", "at": datetime.now(timezone.utc).isoformat()}],
            )

            parent_id = data.get("parent_task_id")
            if parent_id:
                parent = await session.get(AgentTask, parent_id)
                if not parent or parent.tenant_id != tenant_id:
                    raise ValueError(f"Parent task {parent_id} not found")
                depth = (parent.depth or 0) + 1
                if depth > self.MAX_DEPTH:
                    raise ValueError(f"Max delegation depth ({self.MAX_DEPTH}) exceeded")
                task.parent_task_id = parent_id
                task.root_task_id = parent.root_task_id or parent.id
                task.depth = depth

            session.add(task)
            await session.commit()
            await session.refresh(task)

            await event_bus.emit(
                EventType.TASK_DELEGATED,
                {"task_id": str(task.id), "tenant_id": tenant_id, "assigned_agent": task.assigned_agent},
                source="delegation",
            )
            return task

    async def create_child_task(
        self, tenant_id: str, parent_task_id: uuid.UUID, data: dict,
    ) -> AgentTask:
        """Create a child task delegated from a parent."""
        data["parent_task_id"] = parent_task_id
        return await self.create_task(tenant_id, data)

    async def on_task_completed(self, task_id: uuid.UUID, tenant_id: str) -> None:
        """Handle task completion — check siblings and notify parent."""
        async with self._sf() as session:
            task = await session.get(AgentTask, task_id)
            if not task or task.tenant_id != tenant_id:
                return
            if not task.parent_task_id:
                return

            siblings = (
                await session.execute(
                    select(AgentTask).where(
                        and_(
                            AgentTask.parent_task_id == task.parent_task_id,
                            AgentTask.tenant_id == tenant_id,
                        )
                    )
                )
            ).scalars().all()

            all_done = all(
                s.status in ("completed", "failed", "cancelled") for s in siblings
            )
            any_failed = any(s.status == "failed" for s in siblings)

            if any_failed:
                parent = await session.get(AgentTask, task.parent_task_id)
                if parent and parent.on_child_failure == "abort":
                    for s in siblings:
                        if s.status in ("pending", "running"):
                            s.status = "cancelled"
                            s.cancel_reason = "Parent aborted on child failure"
                    await session.commit()

                await event_bus.emit(
                    EventType.TASK_CHILD_FAILED,
                    {
                        "parent_task_id": str(task.parent_task_id),
                        "failed_task_id": str(task_id),
                    },
                    source="delegation",
                )

            if all_done:
                await event_bus.emit(
                    EventType.TASK_CHILDREN_COMPLETE,
                    {
                        "parent_task_id": str(task.parent_task_id),
                        "tenant_id": tenant_id,
                    },
                    source="delegation",
                )

    async def cancel_task(
        self, task_id: uuid.UUID, tenant_id: str, reason: str = "Cancelled by user",
    ) -> AgentTask:
        """Cancel a task and all its descendants recursively."""
        async with self._sf() as session:
            task = await session.get(AgentTask, task_id)
            if not task or task.tenant_id != tenant_id:
                raise ValueError(f"Task {task_id} not found")

            now = datetime.now(timezone.utc)
            task.status = "cancelled"
            task.cancel_reason = reason
            task.completed_at = now
            history = list(task.status_history or [])
            history.append({"status": "cancelled", "at": now.isoformat(), "reason": reason})
            task.status_history = history

            children = (
                await session.execute(
                    select(AgentTask).where(
                        and_(
                            AgentTask.parent_task_id == task_id,
                            AgentTask.tenant_id == tenant_id,
                            AgentTask.status.in_(["pending", "running"]),
                        )
                    )
                )
            ).scalars().all()

            for child in children:
                child.status = "cancelled"
                child.cancel_reason = f"Parent {task_id} cancelled"
                child.completed_at = now

            await session.commit()
            await session.refresh(task)

            await event_bus.emit(
                EventType.TASK_AGENT_CANCELLED,
                {"task_id": str(task_id), "tenant_id": tenant_id, "reason": reason},
                source="delegation",
            )
            return task

    async def get_task_tree(self, root_task_id: uuid.UUID, tenant_id: str) -> dict:
        """Build a recursive task tree from root."""
        async with self._sf() as session:
            all_tasks = (
                await session.execute(
                    select(AgentTask).where(
                        and_(
                            AgentTask.tenant_id == tenant_id,
                            (
                                (AgentTask.id == root_task_id)
                                | (AgentTask.root_task_id == root_task_id)
                            ),
                        )
                    )
                )
            ).scalars().all()

            task_map = {t.id: t for t in all_tasks}
            children_map: dict[uuid.UUID, list] = {}
            for t in all_tasks:
                if t.parent_task_id:
                    children_map.setdefault(t.parent_task_id, []).append(t)

            def build(task_node):
                node = {"task": task_node, "children": []}
                for child in children_map.get(task_node.id, []):
                    node["children"].append(build(child))
                return node

            root = task_map.get(root_task_id)
            if not root:
                raise ValueError(f"Root task {root_task_id} not found")
            return build(root)

    async def update_task(
        self, tenant_id: str, task_id: uuid.UUID, data: dict,
    ) -> AgentTask:
        """Partially update a task with status history tracking."""
        async with self._sf() as session:
            task = await session.get(AgentTask, task_id)
            if not task or task.tenant_id != tenant_id:
                raise ValueError(f"Task {task_id} not found")

            now = datetime.now(timezone.utc)
            for key, value in data.items():
                if key == "status" and value != task.status:
                    history = list(task.status_history or [])
                    history.append({"status": value, "at": now.isoformat()})
                    task.status_history = history
                    if value == "running" and not task.started_at:
                        task.started_at = now
                    elif value in ("completed", "failed"):
                        task.completed_at = now
                if hasattr(task, key):
                    setattr(task, key, value)

            await session.commit()
            await session.refresh(task)

            if data.get("status") == "completed":
                await event_bus.emit(
                    EventType.TASK_AGENT_COMPLETED,
                    {"task_id": str(task_id), "tenant_id": tenant_id},
                    source="delegation",
                )
                await self.on_task_completed(task_id, tenant_id)
            elif data.get("status") == "failed":
                await event_bus.emit(
                    EventType.TASK_AGENT_FAILED,
                    {
                        "task_id": str(task_id),
                        "tenant_id": tenant_id,
                        "error": data.get("error"),
                    },
                    source="delegation",
                )
                await self.on_task_completed(task_id, tenant_id)

            return task
