"""Process Manager — the core task scheduler for Life Graph.

Spawns agent tasks as asyncio background tasks with concurrency
control, timeout enforcement, retry logic, and event emission.
Think of it as the OS kernel's process table.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.models.db import AgentTask

logger = logging.getLogger(__name__)


class ProcessManager:
    """Manages agent task lifecycle — spawn, execute, cancel.

    Enforces concurrency limits via an asyncio semaphore,
    per-task timeouts, and automatic retries with exponential
    backoff.  Every state transition is persisted to the DB
    and emitted as an event.

    Args:
        session_factory: Async session maker for DB access.
        persona_service: PersonaService to validate agent names.
    """

    # Coupled with settings.kernel_max_concurrent_tasks (see config.py):
    # a delegate_to_persona(wait=True) chain at full depth holds one
    # semaphore permit per hop for the duration of the wait, so the
    # concurrency limit must exceed this depth or a single delegation
    # chain can deadlock waiting on its own last permit.
    MAX_DELEGATION_DEPTH = 5

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        persona_service: Any,
    ) -> None:
        self._session_factory = session_factory
        self._persona_service = persona_service
        self._max_concurrent = settings.kernel_max_concurrent_tasks
        self._default_timeout = settings.kernel_default_timeout
        self._default_max_retries = settings.kernel_default_max_retries
        if self._max_concurrent <= self.MAX_DELEGATION_DEPTH:
            raise ValueError(
                "kernel_max_concurrent_tasks"
                f" ({self._max_concurrent}) must be greater than"
                f" ProcessManager.MAX_DELEGATION_DEPTH"
                f" ({self.MAX_DELEGATION_DEPTH}), otherwise a full-depth"
                " delegate_to_persona(wait=True) chain can deadlock on"
                " the concurrency semaphore."
            )
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        # task_id → asyncio.Task for cancellation support
        self._running: dict[uuid.UUID, asyncio.Task[None]] = {}

    # ── Public API ────────────────────────────────────────

    async def spawn(
        self,
        tenant_id: str,
        agent_name: str,
        input_data: dict[str, Any],
        *,
        task_name: str | None = None,
        priority: str = "normal",
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
        parent_task_id: uuid.UUID | None = None,
        root_task_id: uuid.UUID | None = None,
        depth: int = 0,
        session_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        tool_override: list[str] | None = None,
    ) -> dict[str, Any]:
        """Spawn a new agent task (like fork + exec).

        Validates the persona exists, creates a DB record,
        launches an asyncio background task, and emits
        TASK_SPAWNED.

        Args:
            tenant_id: Tenant scope.
            agent_name: Name of the persona to execute as.
            input_data: Input payload for the agent.
            task_name: Optional human-readable task label.
            priority: One of low|normal|high|critical.
            timeout_seconds: Override default timeout.
            max_retries: Override default max retries.
            parent_task_id: Parent task for sub-task trees.
            root_task_id: The top-level task in this delegation
                tree. Callers building a delegation chain (see
                delegate_to_persona) should pass the parent's own
                root_task_id (or the parent's id, if the parent
                is itself the root).
            depth: How many delegation hops deep this task is.
                0 = root. Raises ValueError past MAX_DELEGATION_DEPTH.
            session_id: Associated agent session.
            project_id: Associated project.
            tool_override: When not None, replaces the persona's
                own `allowed_tools` as the tool allowlist for this
                run only. Not persisted to the DB task record — an
                in-memory-only override threaded straight through
                to `_run_agent` for this execution. NOTE: automatic
                retries (`_retry_task`) re-spawn from the persisted
                `AgentTask.input` and do not currently carry
                `tool_override` forward; a failed read-only run
                retries under the persona's own `allowed_tools`.
                Safety-load-bearing: this is how scheduled
                action-role runs are forced read-only.

        Returns:
            Dict with the created task's id and status.

        Raises:
            ValueError: If the persona doesn't exist, or depth
                exceeds MAX_DELEGATION_DEPTH.
        """
        if depth > self.MAX_DELEGATION_DEPTH:
            raise ValueError(
                f"Maximum delegation depth ({self.MAX_DELEGATION_DEPTH})"
                f" exceeded: attempted depth {depth}"
            )

        # Validate persona exists
        persona = await self._persona_service.get_by_name(tenant_id, agent_name)
        if persona is None:
            raise ValueError(f"Unknown agent persona: {agent_name!r}")

        task_id = uuid.uuid4()
        timeout = timeout_seconds or self._default_timeout
        retries = max_retries if max_retries is not None else self._default_max_retries

        # Create DB record
        async with self._session_factory() as session:
            task = AgentTask(
                id=task_id,
                tenant_id=tenant_id,
                task_name=task_name,
                agent_name=agent_name,
                status="queued",
                priority=priority,
                input=input_data,
                timeout_seconds=timeout,
                max_retries=retries,
                parent_task_id=parent_task_id,
                root_task_id=root_task_id,
                depth=depth,
                session_id=session_id,
                project_id=project_id,
                model_used=persona.get("model"),
            )
            session.add(task)
            await session.commit()

        # Launch background execution
        bg_task = asyncio.create_task(
            self._execute_task(
                task_id,
                tenant_id,
                agent_name,
                input_data,
                persona,
                timeout,
                root_task_id=root_task_id or task_id,
                depth=depth,
                tool_override=tool_override,
            ),
            name=f"task-{task_id!s:.8}",
        )
        self._running[task_id] = bg_task

        # Fire-and-forget cleanup when done
        bg_task.add_done_callback(lambda _t: self._running.pop(task_id, None))

        await event_bus.emit(
            EventType.TASK_SPAWNED,
            {
                "task_id": str(task_id),
                "tenant_id": tenant_id,
                "agent_name": agent_name,
                "priority": priority,
            },
            source="process_manager",
        )

        logger.info(
            "Spawned task %s for agent %s (tenant=%s)",
            task_id,
            agent_name,
            tenant_id,
        )

        return {
            "task_id": str(task_id),
            "agent_name": agent_name,
            "status": "queued",
        }

    async def cancel(self, task_id: uuid.UUID, tenant_id: str) -> bool:
        """Cancel a running or queued task.

        Args:
            task_id: The task to cancel.
            tenant_id: Tenant scope for validation.

        Returns:
            True if the task was cancelled, False if not found.
        """
        bg_task = self._running.get(task_id)
        if bg_task is not None:
            bg_task.cancel()
            self._running.pop(task_id, None)

        await self._update_task_status(
            task_id,
            "cancelled",
            completed_at=datetime.now(timezone.utc),
        )

        await event_bus.emit(
            EventType.TASK_CANCELLED,
            {
                "task_id": str(task_id),
                "tenant_id": tenant_id,
            },
            source="process_manager",
        )

        logger.info("Cancelled task %s", task_id)
        return True

    @property
    def running_count(self) -> int:
        """Number of currently running tasks."""
        return len(self._running)

    @property
    def available_slots(self) -> int:
        """Number of available concurrency slots."""
        return max(0, self._max_concurrent - len(self._running))

    async def get_task(
        self,
        tenant_id: str,
        task_id: str,
    ) -> Any | None:
        """Get a task record by tenant and ID.

        Args:
            tenant_id: Tenant scope.
            task_id: Task UUID string.

        Returns:
            AgentTask ORM object or None.
        """
        async with self._session_factory() as session:
            stmt = select(AgentTask).where(
                AgentTask.id == uuid.UUID(task_id),
                AgentTask.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_tasks(
        self,
        tenant_id: str,
        *,
        status: str | None = None,
        agent_name: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Any], int]:
        """List tasks for a tenant with optional filters.

        Args:
            tenant_id: Tenant scope.
            status: Optional status filter.
            agent_name: Optional agent name filter.
            limit: Max results per page.
            offset: Pagination offset.

        Returns:
            Tuple of (task list, total count).
        """
        async with self._session_factory() as session:
            base = select(AgentTask).where(
                AgentTask.tenant_id == tenant_id,
            )
            count_base = (
                select(func.count()).select_from(AgentTask).where(AgentTask.tenant_id == tenant_id)
            )

            if status:
                base = base.where(
                    AgentTask.status == status,
                )
                count_base = count_base.where(
                    AgentTask.status == status,
                )
            if agent_name:
                base = base.where(
                    AgentTask.agent_name == agent_name,
                )
                count_base = count_base.where(
                    AgentTask.agent_name == agent_name,
                )

            count_result = await session.execute(count_base)
            total = count_result.scalar() or 0

            stmt = base.order_by(AgentTask.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            tasks = list(result.scalars().all())
            return tasks, total

    async def cancel_queued(
        self,
        task_id: str,
    ) -> None:
        """Cancel a queued (not-yet-running) task.

        Args:
            task_id: The task UUID string to cancel.
        """
        await self._update_task_status(
            uuid.UUID(task_id),
            "cancelled",
            completed_at=datetime.now(timezone.utc),
        )
        await event_bus.emit(
            EventType.TASK_CANCELLED,
            {"task_id": task_id},
            source="process_manager",
        )

    # ── Internal Execution ────────────────────────────────

    async def _execute_task(
        self,
        task_id: uuid.UUID,
        tenant_id: str,
        agent_name: str,
        input_data: dict[str, Any],
        persona: dict[str, Any],
        timeout: int,
        root_task_id: uuid.UUID | None = None,
        depth: int = 0,
        tool_override: list[str] | None = None,
    ) -> None:
        """Run the agent under semaphore + timeout control."""
        async with self._semaphore:
            from life_graph.core.task_context import set_task_context

            set_task_context(
                task_id=task_id,
                tenant_id=tenant_id,
                root_task_id=root_task_id or task_id,
                depth=depth,
            )

            await self._update_task_status(
                task_id,
                "running",
                started_at=datetime.now(timezone.utc),
            )

            stream_key = str(root_task_id or task_id)

            try:
                async with asyncio.timeout(timeout):
                    result = await self._run_agent(
                        tenant_id,
                        agent_name,
                        input_data,
                        persona,
                        tool_override=tool_override,
                    )
                await self._complete_task(
                    task_id,
                    tenant_id,
                    agent_name,
                    result,
                )
                # Success: the orchestrator's own "done" event was already
                # published to the bus by _run_agent -- nothing more to do.

            except TimeoutError:
                error_msg = f"Task {task_id} timed out after {timeout}s"
                logger.warning(error_msg)
                await self._fail_task(
                    task_id,
                    tenant_id,
                    agent_name,
                    error_msg,
                    timed_out=True,
                )
                self._publish_terminal_bus_event(stream_key, task_id, agent_name, depth, error_msg)

            except asyncio.CancelledError:
                logger.info("Task %s was cancelled", task_id)
                # Status already set by cancel()
                self._publish_terminal_bus_event(
                    stream_key, task_id, agent_name, depth, "Task cancelled"
                )
                raise

            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                logger.error(
                    "Task %s failed: %s",
                    task_id,
                    error_msg,
                    exc_info=True,
                )
                await self._fail_task(
                    task_id,
                    tenant_id,
                    agent_name,
                    error_msg,
                )
                self._publish_terminal_bus_event(stream_key, task_id, agent_name, depth, error_msg)

            finally:
                # Reclaim bus state for tasks nobody streamed (route/cron/
                # watchers) -- a no-op if an SSE subscriber is attached, since
                # that path's own close()/cleanup already handles it.
                from life_graph.services.chat_stream import get_chat_stream_bus

                get_chat_stream_bus().discard(stream_key)

    def _publish_terminal_bus_event(
        self,
        stream_key: str,
        task_id: uuid.UUID,
        agent_name: str,
        depth: int,
        error_msg: str,
    ) -> None:
        """Publish a terminal bus event for a task that failed WITHOUT the
        orchestrator itself ever emitting a top-level "done" (timeout,
        cancellation, or an exception outside the orchestrator's own
        error handling).

        Without this, an SSE subscriber's `async for raw in bus.subscribe(...)`
        would block forever waiting for a done/error event that will never
        arrive, hanging the UI on "coordinating...". `map_bus_event` turns a
        depth-0 partial_error into a fatal `error` (which the endpoint breaks
        the stream on), while a depth>=1 partial_error maps to the existing
        non-fatal `child_error` -- so a delegated child dying this way still
        just fails its one step chip instead of cutting off Jarvis's own
        stream. The "error" key (not "content") matches both map_bus_event's
        `event.get("error") or event.get("message", "error")` lookup and the
        key the orchestrator itself uses for its own partial_error events.
        """
        from life_graph.services.chat_stream import get_chat_stream_bus

        get_chat_stream_bus().publish(
            stream_key,
            {
                "task_id": str(task_id),
                "agent_name": agent_name,
                "depth": depth or 0,
                "event": {"type": "partial_error", "error": error_msg[:500]},
            },
        )

    async def _run_agent(
        self,
        tenant_id: str,
        agent_name: str,
        input_data: dict[str, Any],
        persona: dict[str, Any],
        tool_override: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute the agent via the orchestrator.

        Collects the full streamed output into a result dict.

        Args:
            tenant_id: Tenant scope.
            agent_name: Persona name.
            input_data: The task input payload.
            persona: Persona configuration dict.
            tool_override: When not None, REPLACES the persona's
                own `allowed_tools` as the tool allowlist for this
                run (rather than merging with it). Used to force
                scheduled action-role runs onto a read-only tool
                set — safety-load-bearing, do not remove.

        Returns:
            Dict with 'response' text and 'token_count'.
        """
        from life_graph.agents.orchestrator import (
            AgentOrchestrator,
        )
        from life_graph.tools.registry import registry as tool_registry

        orchestrator = AgentOrchestrator(
            model=persona.get("model"),
            temperature=persona.get("temperature"),
            max_tokens=persona.get("max_tokens"),
        )

        messages = [
            {"role": "user", "content": input_data.get("message", str(input_data))},
        ]
        system_prompt = persona.get("system_prompt")

        allow = tool_override if tool_override is not None else persona.get("allowed_tools")
        if allow is not None:
            allowed_set = set(allow)
            tools = [t for t in tool_registry.get_tools() if t["function"]["name"] in allowed_set]
        else:
            tools = None

        import json as _json

        from life_graph.core.task_context import get_current_task_context
        from life_graph.services.chat_stream import get_chat_stream_bus

        ctx = get_current_task_context()
        bus = get_chat_stream_bus()
        stream_key = str(ctx.root_task_id or ctx.task_id) if ctx else None
        meta = (
            {"task_id": str(ctx.task_id), "agent_name": agent_name, "depth": ctx.depth}
            if ctx
            else None
        )

        # Collect streamed output
        response_parts: list[str] = []
        token_count = 0

        async for event_str in orchestrator.run(messages, system_prompt=system_prompt, tools=tools):
            # Each event is an SSE string; extract content
            try:
                data = _json.loads(event_str.removeprefix("data: ").strip())
            except (ValueError, KeyError):
                continue
            if stream_key is not None:
                bus.publish(stream_key, {**meta, "event": data})
            if data.get("type") == "token":
                content = data.get("content", "")
                response_parts.append(content)
                token_count += 1

        return {
            "response": "".join(response_parts),
            "token_count": token_count,
        }

    # ── State Transitions ─────────────────────────────────

    async def _complete_task(
        self,
        task_id: uuid.UUID,
        tenant_id: str,
        agent_name: str,
        result: dict[str, Any],
    ) -> None:
        """Mark a task as completed and emit event."""
        now = datetime.now(timezone.utc)
        token_usage = {
            "total_tokens": result.get("token_count", 0),
        }

        async with self._session_factory() as session:
            stmt = (
                update(AgentTask)
                .where(AgentTask.id == task_id)
                .values(
                    status="completed",
                    result=result,
                    token_usage=token_usage,
                    completed_at=now,
                    updated_at=now,
                )
            )
            await session.execute(stmt)
            await session.commit()

        await event_bus.emit(
            EventType.TASK_COMPLETED,
            {
                "task_id": str(task_id),
                "tenant_id": tenant_id,
                "agent_name": agent_name,
                "token_usage": token_usage,
            },
            source="process_manager",
        )
        logger.info("Task %s completed (agent=%s)", task_id, agent_name)

    async def _fail_task(
        self,
        task_id: uuid.UUID,
        tenant_id: str,
        agent_name: str,
        error: str,
        *,
        timed_out: bool = False,
    ) -> None:
        """Mark a task as failed, attempt retry if eligible."""
        now = datetime.now(timezone.utc)
        status = "timeout" if timed_out else "failed"
        event_type = EventType.TASK_TIMEOUT if timed_out else EventType.TASK_FAILED

        # Read current retry state
        retry_count = 0
        max_retries = 0
        input_data: dict[str, Any] = {}

        async with self._session_factory() as session:
            stmt = select(AgentTask).where(AgentTask.id == task_id)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            if task is not None:
                retry_count = task.retry_count
                max_retries = task.max_retries
                input_data = task.input or {}

        # Update status
        async with self._session_factory() as session:
            stmt = (
                update(AgentTask)
                .where(AgentTask.id == task_id)
                .values(
                    status=status,
                    error=error,
                    completed_at=now,
                    updated_at=now,
                )
            )
            await session.execute(stmt)
            await session.commit()

        await event_bus.emit(
            event_type,
            {
                "task_id": str(task_id),
                "tenant_id": tenant_id,
                "agent_name": agent_name,
                "error": error,
            },
            source="process_manager",
        )

        # Attempt retry
        if retry_count < max_retries and not timed_out:
            await self._retry_task(
                task_id,
                tenant_id,
                agent_name,
                input_data,
                retry_count,
            )

    async def _retry_task(
        self,
        original_task_id: uuid.UUID,
        tenant_id: str,
        agent_name: str,
        input_data: dict[str, Any],
        retry_count: int,
    ) -> None:
        """Schedule a retry with exponential backoff.

        Creates a new task linked to the original via
        parent_task_id. Backoff delay = 2^retry_count seconds.
        """
        delay = 2**retry_count
        new_retry = retry_count + 1

        logger.info(
            "Retrying task %s (attempt %d) in %ds",
            original_task_id,
            new_retry,
            delay,
        )

        await asyncio.sleep(delay)

        # Update retry count on original
        async with self._session_factory() as session:
            stmt = (
                update(AgentTask)
                .where(AgentTask.id == original_task_id)
                .values(
                    retry_count=new_retry,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.execute(stmt)
            await session.commit()

        # Spawn a new task as a child
        await self.spawn(
            tenant_id,
            agent_name,
            input_data,
            task_name=f"retry-{new_retry}-of-{original_task_id!s:.8}",
            parent_task_id=original_task_id,
        )

    # ── Helpers ───────────────────────────────────────────

    async def _update_task_status(
        self,
        task_id: uuid.UUID,
        status: str,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Update task status and optional timestamps."""
        values: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at

        async with self._session_factory() as session:
            stmt = update(AgentTask).where(AgentTask.id == task_id).values(**values)
            await session.execute(stmt)
            await session.commit()
