"""Process Manager — the core task scheduler for Life Graph.

Spawns agent tasks as asyncio background tasks with concurrency
control, timeout enforcement, retry logic, and event emission.
Think of it as the OS kernel's process table.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import defer

from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.core.personal_run import PERSONAL_INPUT_KEY, personal_run_scope
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import AgentTask
from life_graph.services.memory import changes as context_changes

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
    )

logger = logging.getLogger(__name__)

# The label `_retry_task` gives a retry of a task that had no name of its own.
_RETRY_LABEL = re.compile(r"retry-\d+-of-[0-9a-f]{8}")


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

    # Coupled with settings.kernel_max_concurrent_tasks (see config/agents.py):
    # a delegate_to_persona(wait=True) chain at full depth holds one
    # semaphore permit per hop for the duration of the wait, so the
    # concurrency limit must exceed this depth or a single delegation
    # chain can deadlock waiting on its own last permit.
    MAX_DELEGATION_DEPTH = 5

    # How often a running task re-reads its own row's status, so a cancel
    # made by another process (the API, while the ARQ worker runs the task)
    # stops it. One primary-key read per running task per interval.
    CANCEL_POLL_SECONDS = 3.0

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
        retry_count: int = 0,
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
                to `_run_agent` for this execution, and re-applied
                on automatic retries too (`_fail_task` ->
                `_retry_task` -> `spawn`) so a retried run cannot
                fall back to the persona's own `allowed_tools`.
                Safety-load-bearing: this is how scheduled
                action-role runs are forced read-only.
            retry_count: Which retry this run is (0 = the first try). Set
                by `_retry_task` only; `_fail_task` stops retrying once a
                failed row's count reaches its max_retries.

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
                retry_count=retry_count,
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

    def stop_local(self, task_id: uuid.UUID) -> bool:
        """Stop this task's run if THIS process is running it. No DB write.

        Returns True if a live asyncio task was found and told to stop. False
        if this process does not hold it: already finished, never started
        here, or running in another process (e.g. the ARQ worker). The kernel
        cancel route calls this for the task and each delegated descendant;
        the DB status and capability revocation are done by
        DelegationEngine.cancel_task.
        """
        bg_task = self._running.pop(task_id, None)
        if bg_task is None or bg_task.done():
            return False
        bg_task.cancel()
        return True

    async def cancel(self, task_id: uuid.UUID, tenant_id: str) -> bool:
        """Cancel one task: stop its local run (if any) and mark it cancelled.

        Only this one task: delegated children are not touched. The kernel
        cancel route cascades with DelegationEngine.cancel_task + stop_local
        instead.

        Args:
            task_id: The task to cancel.
            tenant_id: Tenant scope for validation.

        Returns:
            True if this process was running the task and stopped it. False
            if it was not running here (queued, finished, or in another
            process); the row is marked cancelled either way.
        """
        held = self.stop_local(task_id)

        await self._update_task_status(
            task_id,
            "cancelled",
            completed_at=datetime.now(UTC),
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
        return held

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
        include_total: bool = False,
    ) -> tuple[list[Any], int | None, bool]:
        """List tasks for a tenant with optional filters.

        Args:
            tenant_id: Tenant scope.
            status: Optional status filter.
            agent_name: Optional agent name filter.
            limit: Max results per page.
            offset: Pagination offset.
            include_total: When True, also run a COUNT(*) query. The only
                caller (api/kernel.py's list endpoint) doesn't surface
                total/has_more in the mobile Tasks board, so this defaults
                to False — skips a second DB round trip on every request.
                has_more is derived from an over-fetch (limit+1 rows), not
                from total, so it's accurate either way.

        Returns:
            Tuple of (task list, total count or None, has_more).
        """
        async with self._session_factory() as session:
            base = select(AgentTask).where(
                AgentTask.tenant_id == tenant_id,
            )
            # The list view only ever renders _task_row_to_summary's 9
            # scalar fields — defer the JSONB blobs nothing here reads.
            base = base.options(
                defer(AgentTask.input),
                defer(AgentTask.result),
                defer(AgentTask.logs),
                defer(AgentTask.token_usage),
            )

            if status:
                base = base.where(AgentTask.status == status)
            if agent_name:
                base = base.where(AgentTask.agent_name == agent_name)

            stmt = base.order_by(AgentTask.created_at.desc()).limit(limit + 1).offset(offset)
            result = await session.execute(stmt)
            tasks = list(result.scalars().all())
            has_more = len(tasks) > limit
            if has_more:
                tasks = tasks[:limit]

            total = None
            if include_total:
                count_base = (
                    select(func.count())
                    .select_from(AgentTask)
                    .where(AgentTask.tenant_id == tenant_id)
                )
                if status:
                    count_base = count_base.where(AgentTask.status == status)
                if agent_name:
                    count_base = count_base.where(AgentTask.agent_name == agent_name)
                count_result = await session.execute(count_base)
                total = count_result.scalar() or 0

            return tasks, total, has_more

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
            completed_at=datetime.now(UTC),
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
        """Run the agent under semaphore + timeout control.

        On success the result is saved first and only then is the run's
        top-level "done" sent to the chat stream: a client that sees "done"
        and at once regenerates or resends must find the row completed, not
        get 409 "still being written".
        """
        from life_graph.core.task_context import set_task_context
        from life_graph.services.chat_stream import get_chat_stream_bus

        try:
            await self._semaphore.acquire()
        except asyncio.CancelledError:
            # Stopped while it waited for a slot (stop_local on a queued
            # task of a cancelled tree): end a stream that may be waiting on
            # it, as the cancel of a running task does below.
            stream_key = str(root_task_id or task_id)
            self._publish_terminal_bus_event(
                stream_key, task_id, agent_name, depth, "Task cancelled"
            )
            get_chat_stream_bus().discard(stream_key)
            raise
        try:
            set_task_context(
                task_id=task_id,
                tenant_id=tenant_id,
                root_task_id=root_task_id or task_id,
                depth=depth,
            )

            stream_key = str(root_task_id or task_id)
            bus = get_chat_stream_bus()
            # The run's closing events ("done", and the "partial_error" the
            # orchestrator sends just before a failed run's "done"), kept
            # back by _run_agent until the result is saved.
            terminal: list[dict[str, Any]] = []

            try:
                running = await self._mark_running(task_id)
            except asyncio.CancelledError:
                # Stopped during this write: end the stream like any cancel.
                # (Any other error here still propagates, as it always has.)
                self._publish_terminal_bus_event(
                    stream_key, task_id, agent_name, depth, "Task cancelled"
                )
                bus.discard(stream_key)
                raise
            if not running:
                # Cancelled while it waited for a slot (a cancelled tree's
                # queued child, or a cancel from another process): don't
                # run it, and end a stream that may be waiting on it.
                logger.info("Task %s was cancelled before it started", task_id)
                self._publish_terminal_bus_event(
                    stream_key, task_id, agent_name, depth, "Task cancelled"
                )
                bus.discard(stream_key)
                return

            try:
                # Stops this run if its row is cancelled from another process
                # (stop_local only reaches runs in the process that holds them).
                watch = self._start_cancel_watch(task_id, tenant_id)
                try:
                    async with asyncio.timeout(timeout):
                        result = await self._run_agent(
                            tenant_id,
                            agent_name,
                            input_data,
                            persona,
                            tool_override=tool_override,
                            terminal_sink=terminal,
                        )
                finally:
                    watch.cancel()
                await self._complete_task(
                    task_id,
                    tenant_id,
                    agent_name,
                    result,
                )
                # Saved, so now the stream may end. If saving raised, the
                # except below fails the task and sends its error instead.
                for payload in terminal:
                    bus.publish(stream_key, payload)

            except TimeoutError:
                error_msg = f"Task {task_id} timed out after {timeout}s"
                logger.warning(error_msg)
                await self._fail_task(
                    task_id,
                    tenant_id,
                    agent_name,
                    error_msg,
                    timed_out=True,
                    tool_override=tool_override,
                )
                self._publish_terminal_bus_event(stream_key, task_id, agent_name, depth, error_msg)

            except asyncio.CancelledError:
                logger.info("Task %s was cancelled", task_id)
                # Status already set by the cancel (here, or in another
                # process and seen by the cancel watch).
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
                    tool_override=tool_override,
                )
                self._publish_terminal_bus_event(stream_key, task_id, agent_name, depth, error_msg)

            finally:
                # Reclaim bus state for tasks nobody streamed (route/cron/
                # watchers) -- a no-op if an SSE subscriber is attached, since
                # that path's own close()/cleanup already handles it.
                bus.discard(stream_key)
        finally:
            self._semaphore.release()

    def _start_cancel_watch(self, task_id: uuid.UUID, tenant_id: str) -> asyncio.Task[None]:
        """Start the watch that stops the current run once its row is cancelled.

        The kernel cancel route marks rows cancelled and calls stop_local, but
        stop_local only reaches a run held by the same process. A run in the
        ARQ worker (Telegram turns, scheduled jobs) used to go on to the end.
        This background task reads the row's status every
        CANCEL_POLL_SECONDS and, when it is 'cancelled', cancels the run's
        asyncio task, which then ends as a local cancel does. The caller
        cancels the watch as soon as the run ends.
        """
        run = asyncio.current_task()
        assert run is not None  # called from inside the run's own task
        return asyncio.create_task(
            self._watch_for_cancel(task_id, tenant_id, run),
            name=f"cancel-watch-{task_id!s:.8}",
        )

    async def _watch_for_cancel(
        self, task_id: uuid.UUID, tenant_id: str, run: asyncio.Task[Any]
    ) -> None:
        """Poll the row's status; cancel `run` once it reads 'cancelled'."""
        while not run.done():
            await asyncio.sleep(self.CANCEL_POLL_SECONDS)
            try:
                async with self._session_factory() as session:
                    status = (
                        await session.execute(
                            select(AgentTask.status).where(
                                AgentTask.id == task_id, AgentTask.tenant_id == tenant_id
                            )
                        )
                    ).scalar_one_or_none()
            except Exception:
                # A failed read must not stop the run; try again next time.
                logger.debug("Cancel watch read failed for task %s", task_id, exc_info=True)
                continue
            if status == "cancelled":
                logger.info("Task %s was cancelled elsewhere; stopping its run", task_id)
                run.cancel()
                return

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
        terminal_sink: list[dict[str, Any]] | None = None,
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
            terminal_sink: When given (``_execute_task`` does), the run's
                closing events -- "done" and "partial_error" -- are not
                published here but appended to this list as bus payloads,
                in order, for the caller to publish once the result is
                saved. Without it they are published as they come, except
                that a sources-checked run's "done" still waits for its
                source note (below).

        Returns:
            Dict with 'response' text and 'token_count'.
        """
        import time

        from life_graph.agents.orchestrator import (
            AgentOrchestrator,
        )
        from life_graph.core.run_taint import TAINT_INPUT_KEY
        from life_graph.services import lead
        from life_graph.tools.registry import registry as tool_registry

        # Seconds per stage of this run, kept on the result: what a phone
        # question actually costs, measured where it happens.
        run_started = time.monotonic()
        timing: dict[str, float] = {}

        # Jarvis's model is chosen per request: personal work stays local,
        # the rest may go to its cloud model without the personal tools.
        lead_route = lead.route(persona, input_data) if agent_name == lead.LEAD else None
        if lead_route is not None:
            persona = {**persona, "model": lead_route.model, "allowed_tools": lead_route.tools}
            input_data = {
                **input_data,
                "message": lead_route.message,
                "history": lead_route.history,
            }
        general_cloud = lead_route is not None and lead_route.kind == "general"

        orchestrator = AgentOrchestrator(
            model=persona.get("model"),
            temperature=persona.get("temperature"),
            max_tokens=persona.get("max_tokens"),
        )

        # A task delegate_to_persona started from a personal run arrives
        # marked (core/personal_run.py) and stays on local models, as the
        # conversation did: Jarvis takes its personal route (lead.route), any
        # other persona is pinned to its own local model -- or, when it has
        # none, refused here, before its model sees a word.
        inherited_personal = bool(input_data.get(PERSONAL_INPUT_KEY))
        pinned = lead_route.pinned if lead_route is not None else None
        if inherited_personal and lead_route is None:
            pinned = lead.personal_pin(agent_name, orchestrator.model)
        # Marks this run's own delegations (tools/delegate.py).
        personal = inherited_personal or (lead_route is not None and lead_route.kind == "personal")

        # Earlier turns of this conversation, oldest first, as the caller
        # assembled them. Every chat turn used to be a single-message run, so a
        # persona could not answer "what did I just say?" — the UI showed a
        # thread the model had never seen. A task with no history (a scheduled
        # job, a delegated child) still sends exactly one message, as before.
        history = input_data.get("history") or []
        messages = [
            *({"role": m["role"], "content": m["content"]} for m in history),
            {"role": "user", "content": input_data.get("message", str(input_data))},
        ]
        system_prompt = persona.get("system_prompt")
        from life_graph.connectors.locality import run_is_local

        # Where this run's conversation can end up: off the machine unless a
        # personal route pinned it to local models (only_models below), or
        # its model and every model it may fail over to are local.
        pinned_local = bool(pinned)
        cloud_run = not (pinned_local or run_is_local(orchestrator.model))
        # general on a local model needs no note: nothing was taken away.
        general_cloud = general_cloud and cloud_run
        # Which runs lose PERSONAL_TOOLS. On (default): every cloud run, for
        # every persona, the rule drivers/local.py applies -- see the
        # setting's docstring (config/agents.py) for what that costs swe-lead
        # & co. Off: only Jarvis's general cloud route.
        strip_personal = cloud_run if settings.kernel_cloud_strip_personal_tools else general_cloud
        if general_cloud:
            system_prompt = f"{system_prompt or ''}\n\n{lead.GENERAL_NOTE}".strip()
        # Connector data inline is personal data: never on a general cloud run.
        if orchestrator.model == "claude-cli" and not general_cloud:
            # No tools on this path, so schedule/mail questions get connector
            # data inline — rendered for a cloud audience (connectors/exposure).
            try:
                from life_graph.connectors.chat_context import context_for

                extra = await context_for(tenant_id, messages[0]["content"], orchestrator.model)
                if extra:
                    system_prompt = f"{system_prompt or ''}\n\n{extra}".strip()
            except Exception:
                logger.warning("Connector chat context failed", exc_info=True)

        # An override never brings the personal tools back to a cloud run;
        # neither does "all tools" (None). A temporary chat leaves nothing
        # behind, and a personal run hands nothing to a cloud worker (a
        # marked child, or Jarvis's personal route on a local model, which
        # lead.route does not cut). One rule for this and drivers/local.py
        # (services/lead.py).
        allow = lead.resolve_run_tools(
            persona,
            tool_override,
            cloud=strip_personal,
            temporary=bool(input_data.get("temporary")),
            personal=personal,
            registry=tool_registry,
        )
        if allow is not None:
            allowed_set = set(allow)
            tools = [t for t in tool_registry.get_tools() if t["function"]["name"] in allowed_set]
        else:
            tools = None

        import json as _json
        from contextlib import nullcontext

        from life_graph.core.task_context import get_current_task_context
        from life_graph.services import persona_context
        from life_graph.services.chat_stream import get_chat_stream_bus
        from life_graph.tools._guards import confine_to

        ctx = get_current_task_context()
        confinement: Any = nullcontext()
        if agent_name in persona_context.DOCS_ONLY_PERSONAS:
            # Enforced, not just asked for in the prompt: the file tools reach
            # the project's README and docs/ and nothing else; no project, no files.
            roots = (
                await persona_context.docs_roots(self._session_factory, tenant_id, ctx.task_id)
                if ctx
                else []
            )
            confinement = confine_to(*roots)
            listing = "\n".join(f"- `{r}`" for r in roots) or "- (none: no project was given)"
            system_prompt = f"{system_prompt or ''}\n\n## Documentation you may read\n{listing}"
        # What changes from one request to the next goes in a note just before
        # the user's message, never in the system prompt: Ollama reuses the
        # cached start of a prompt (a 7,500-token prompt read in 0.05 s instead
        # of 2.2 s, measured 2026-10-22), and the time to the minute or this
        # question's memories at the top threw that away on every request,
        # tool descriptions included.
        volatile: list[str] = []
        if orchestrator.model != "claude-cli":
            # A local model has no idea what day it is: asked for "the latest
            # release", it called a two-week-old one "a future date".
            volatile.append(persona_context.today_line())
            if agent_name not in persona_context.DOCS_ONLY_PERSONAS and (
                persona_context.needs_projects(allow)
            ):
                try:
                    block = await persona_context.projects_block(self._session_factory, tenant_id)
                    if block:
                        system_prompt = f"{system_prompt or ''}\n\n{block}".strip()
                except Exception:
                    logger.warning("Project context for %s failed", agent_name, exc_info=True)
                # The recipes distilled from past sessions (services/skill_distiller.py):
                # a persona with code, shell or git tools is the one about to repeat
                # the mistake one of them records. Same gate as the projects block,
                # and in the system prompt for the same prompt-cache reason.
                try:
                    project = (
                        await persona_context.task_project_name(
                            self._session_factory, tenant_id, ctx.task_id
                        )
                        if ctx
                        else None
                    )
                    skills = await persona_context.procedural_skills_block(
                        self._session_factory, tenant_id, project
                    )
                    if skills:
                        system_prompt = f"{system_prompt or ''}\n\n{skills}".strip()
                except Exception:
                    logger.warning("Skill context for %s failed", agent_name, exc_info=True)
        # What shaped this answer (services/turn_trace.py): the memories put in
        # front of the model and the tools it called, kept on the result.
        used_memories: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        tool_started: float | None = None
        shadow: asyncio.Task[dict[str, Any]] | None = None
        if (
            lead_route is not None
            and lead_route.kind == "personal"
            and (lead_route.pinned or run_is_local(orchestrator.model))
        ):
            if settings.context_snapshot_shadow:
                # M8 shadow mode: built next to the memory block, kept only in
                # the trace (refs and labels); never changes the prompt, never
                # fails the turn (services/memory/snapshot.py shadow_compact).
                # With context_change_shadow too, the snapshot is compared with
                # this conversation's previous one (services/memory/changes.py).
                shadow = asyncio.create_task(
                    context_changes.shadow_trace(
                        tenant_id,
                        messages[-1]["content"],
                        history,
                        task_id=(ctx.root_task_id or ctx.task_id) if ctx else None,
                        compare=settings.context_change_shadow,
                        # M8 precision mode, shadow only: the configured mode
                        # (recall when none is set) next to the default snapshot.
                        precision=(settings.context_precision_mode or "recall")
                        if settings.context_precision_shadow
                        else "",
                    )
                )
            # The owner's memories, on a local run only (services/memory/context.py):
            # a personal route is pinned to local models (only_models below), or
            # its model and every fallback are local.
            from life_graph.services.memory.context import memory_block

            started = time.monotonic()
            remembered = await memory_block(
                tenant_id, messages[-1]["content"], history, used=used_memories
            )
            timing["memory_s"] = round(time.monotonic() - started, 2)
            if remembered:
                volatile.append(remembered)
        if volatile:
            messages.insert(len(messages) - 1, {"role": "system", "content": "\n\n".join(volatile)})

        bus = get_chat_stream_bus()
        stream_key = str(ctx.root_task_id or ctx.task_id) if ctx else None
        meta = (
            {"task_id": str(ctx.task_id), "agent_name": agent_name, "depth": ctx.depth}
            if ctx
            else None
        )
        if lead_route is not None and stream_key is not None:
            # Where Jarvis runs, known before the first token: a chat client
            # labels the reply with it (the phone app shows "on your PC").
            bus.publish(stream_key, {**meta, "event": {"type": "route", **lead_route.as_record()}})

        # Collect streamed output
        from life_graph.services import sources

        check_sources = sources.required_for(agent_name)
        response_parts: list[str] = []
        tool_results: list[str] = []
        # Events kept back from the stream until the end of the run: the
        # closing events when the caller asked for them (terminal_sink), and
        # a sources-checked run's "done", so its note can go first.
        held: list[dict[str, Any]] = []
        if terminal_sink is not None:
            hold_types = {"done", "partial_error"}
        elif check_sources:
            hold_types = {"done"}
        else:
            hold_types = set()
        token_count = 0

        from life_graph.services.llm.resilient import only_models

        # A personal request, or a task delegated from one, may fail over
        # only to local models.
        pin: Any = only_models(pinned) if pinned else nullcontext()
        timing["prepare_s"] = round(time.monotonic() - run_started, 2)
        with confinement, pin, personal_run_scope(personal):
            async for event_str in orchestrator.run(
                messages,
                system_prompt=system_prompt,
                tools=tools,
                # Set by delegate_to_persona on a tainted run's child.
                **({"outside_content_seen": True} if input_data.get(TAINT_INPUT_KEY) else {}),
            ):
                if "first_token_s" not in timing and '"token"' in event_str:
                    timing["first_token_s"] = round(time.monotonic() - run_started, 2)
                # Each event is an SSE string; extract content
                try:
                    data = _json.loads(event_str.removeprefix("data: ").strip())
                except (ValueError, KeyError):
                    continue
                if data.get("type") in hold_types:
                    held.append(data)
                    continue
                if stream_key is not None:
                    bus.publish(stream_key, {**meta, "event": data})
                if data.get("type") == "token":
                    content = data.get("content", "")
                    response_parts.append(content)
                    token_count += 1
                elif data.get("type") == "tool_call":
                    tool_started = time.monotonic()
                elif data.get("type") == "tool_result":
                    tool_results.append(str(data.get("result") or ""))
                    from life_graph.services.turn_trace import tool_ok

                    tool_calls.append(
                        {
                            "name": data.get("name"),
                            "ok": tool_ok(data.get("result")),
                            "ms": round((time.monotonic() - tool_started) * 1000)
                            if tool_started is not None
                            else 0,
                        }
                    )
                    tool_started = None

        response = "".join(response_parts)
        timing["total_s"] = round(time.monotonic() - run_started, 2)
        out: dict[str, Any] = {"response": response, "token_count": token_count, "timing": timing}
        from life_graph.services.turn_trace import build_trace

        # A pinned run may fail over only to local models (only_models above).
        stayed_local = not cloud_run
        out["trace"] = build_trace(
            lead_route.as_record()
            if lead_route is not None
            else {"kind": None, "model": orchestrator.model, "reason": ""},
            [{"model": orchestrator.model, "local": stayed_local}],
            used_memories,
            tool_calls,
        )
        if shadow is not None:
            # context_snapshot, and context_changes when comparing.
            out["trace"].update(await shadow)
        if lead_route is not None:
            out["route"] = lead_route.as_record()
            # No content: stage times and where it ran only.
            logger.info("Jarvis run (%s, %s): %s", lead_route.kind, orchestrator.model, timing)

        if check_sources:
            out["response"], out["sources"] = sources.apply(response, tool_results)
            # A prose answer gains a note at its end, which a streaming chat
            # still needs; a findings array is marked in place and read from
            # the result, so nothing more is streamed for it.
            checked = out["response"]
            note = checked[len(response) :] if checked.startswith(response) else ""
            if stream_key is not None and note:
                bus.publish(stream_key, {**meta, "event": {"type": "token", "content": note}})
        if stream_key is not None:
            for event in held:
                payload = {**meta, "event": event}
                if terminal_sink is not None:
                    terminal_sink.append(payload)
                else:
                    bus.publish(stream_key, payload)
        return out

    # ── State Transitions ─────────────────────────────────

    async def _complete_task(
        self,
        task_id: uuid.UUID,
        tenant_id: str,
        agent_name: str,
        result: dict[str, Any],
    ) -> None:
        """Mark a task as completed and emit event.

        A row already ``cancelled`` stays cancelled: a run that finishes
        after its cancel (it was in another process, such as the ARQ worker,
        or the cancel landed while this one was saving) does not turn it back
        into ``completed``, and no TASK_COMPLETED is emitted for it.
        """
        now = datetime.now(UTC)
        token_usage = {
            "total_tokens": result.get("token_count", 0),
        }

        async with self._session_factory() as session:
            stmt = (
                update(AgentTask)
                .where(AgentTask.id == task_id, AgentTask.status != "cancelled")
                .values(
                    status="completed",
                    result=result,
                    token_usage=token_usage,
                    completed_at=now,
                    updated_at=now,
                )
            )
            saved = (await session.execute(stmt)).rowcount
            await session.commit()
        if not saved:
            logger.info("Task %s finished after it was cancelled; left cancelled", task_id)
            return

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
        tool_override: list[str] | None = None,
    ) -> None:
        """Mark a task as failed, attempt retry if eligible.

        A row already ``cancelled`` stays cancelled, with no event and no
        retry: a run that dies after its cancel is not a failure to retry.

        Args:
            tool_override: Carried through from the original run so a
                retry (see `_retry_task`) re-spawns under the SAME tool
                allowlist rather than falling back to the persona's own
                `allowed_tools`. Safety-load-bearing for read-only
                scheduled action runs — do not drop on this path.
        """
        now = datetime.now(UTC)
        status = "timeout" if timed_out else "failed"
        event_type = EventType.TASK_TIMEOUT if timed_out else EventType.TASK_FAILED

        # Read current retry state
        retry_count = 0
        max_retries = 0
        input_data: dict[str, Any] = {}
        root_task_id: uuid.UUID | None = None
        depth = 0
        # The rest of the failed run's settings, given to its retry as they are.
        carry: dict[str, Any] = {}

        async with self._session_factory() as session:
            stmt = select(AgentTask).where(AgentTask.id == task_id)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            if task is not None:
                if task.status == "cancelled":
                    logger.info("Task %s failed after it was cancelled; left cancelled", task_id)
                    return
                retry_count = task.retry_count
                max_retries = task.max_retries
                input_data = task.input or {}
                root_task_id = task.root_task_id
                depth = task.depth
                carry = {
                    "task_name": task.task_name,
                    "priority": task.priority,
                    "timeout_seconds": task.timeout_seconds,
                    "session_id": task.session_id,
                    "project_id": task.project_id,
                }

        # Update status. The WHERE also covers a cancel that lands between
        # the read above and this write.
        async with self._session_factory() as session:
            stmt = (
                update(AgentTask)
                .where(AgentTask.id == task_id, AgentTask.status != "cancelled")
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
                tool_override=tool_override,
                max_retries=max_retries,
                root_task_id=root_task_id,
                depth=depth,
                **carry,
            )

    async def _retry_task(
        self,
        original_task_id: uuid.UUID,
        tenant_id: str,
        agent_name: str,
        input_data: dict[str, Any],
        retry_count: int,
        tool_override: list[str] | None = None,
        *,
        max_retries: int = 0,
        root_task_id: uuid.UUID | None = None,
        depth: int = 0,
        task_name: str | None = None,
        priority: str = "normal",
        timeout_seconds: int | None = None,
        session_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> None:
        """Schedule a retry with exponential backoff.

        Creates a new task linked to the original via
        parent_task_id. Backoff delay = 2^retry_count seconds.

        The retry keeps its place in the chain: it is spawned with
        ``retry_count + 1`` and the original's ``max_retries``, so a task that
        always raises stops after max_retries retries. Before, each retry was
        a fresh row with retry_count 0 and the default max_retries, and the
        chain never ended. It also keeps the original's ``root_task_id`` and
        ``depth``, so a retried delegated child stays in its tree (and in its
        root's stream) instead of becoming a new depth-0 task.

        It runs with the original's settings too: the same name, priority,
        timeout, session and project. Before, a retry got the default timeout
        and priority, no session or project, and the name
        ``retry-N-of-<id>``, which (for one) hid a retried scheduled run from
        the action-proposal bridge, which looks for the ``schedule:`` name.
        A task with no name still gets that ``retry-N-of-<id>`` label.

        Args:
            tool_override: Re-applied to the re-spawned task so a
                retried read-only scheduled run stays read-only
                instead of falling back to the persona's own
                `allowed_tools`.
            max_retries: The original's max_retries, carried to the retry.
            root_task_id: The original's root (None for a root task).
            depth: The original's delegation depth.
            task_name: The original's name (None: label it as a retry).
            priority: The original's priority.
            timeout_seconds: The original's timeout (None: the default).
            session_id: The original's agent session.
            project_id: The original's project.
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

        if await self._cancelled_in_tree(original_task_id, tenant_id):
            # Cancelled during the backoff, the task itself or a task above
            # it (a cancel cascades down from the tree it belongs to).
            logger.info("Not retrying task %s: it or its tree was cancelled", original_task_id)
            return

        # Update retry count on original
        async with self._session_factory() as session:
            stmt = (
                update(AgentTask)
                .where(AgentTask.id == original_task_id)
                .values(
                    retry_count=new_retry,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.execute(stmt)
            await session.commit()

        # Spawn a new task as a child. A name that is only an earlier retry's
        # label is relabelled, so an unnamed task's retries count up.
        if not task_name or _RETRY_LABEL.fullmatch(task_name):
            task_name = f"retry-{new_retry}-of-{original_task_id!s:.8}"
        await self.spawn(
            tenant_id,
            agent_name,
            input_data,
            task_name=task_name,
            priority=priority,
            timeout_seconds=timeout_seconds,
            session_id=session_id,
            project_id=project_id,
            parent_task_id=original_task_id,
            root_task_id=root_task_id,
            depth=depth,
            max_retries=max_retries,
            retry_count=new_retry,
            tool_override=tool_override,
        )

    # ── Helpers ───────────────────────────────────────────

    async def _mark_running(self, task_id: uuid.UUID) -> bool:
        """Set the task running, unless it was cancelled first.

        Returns False only when the row is ``cancelled``: then it must not
        run. Any other reason the update matched nothing (no row, another
        tenant's context) keeps the old behaviour and runs it.
        """
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            stmt = (
                update(AgentTask)
                .where(
                    AgentTask.id == task_id,
                    AgentTask.tenant_id == get_current_tenant_id(),
                    AgentTask.status != "cancelled",
                )
                .values(status="running", started_at=now, updated_at=now)
            )
            updated = (await session.execute(stmt)).rowcount
            await session.commit()
            if updated:
                return True
            current = (
                await session.execute(
                    select(AgentTask.status).where(
                        AgentTask.id == task_id,
                        AgentTask.tenant_id == get_current_tenant_id(),
                    )
                )
            ).scalar_one_or_none()
        return current != "cancelled"

    async def _cancelled_in_tree(self, task_id: uuid.UUID, tenant_id: str) -> bool:
        """True if this task or any task above it (parent chain) is cancelled."""
        seen: set[uuid.UUID] = set()
        current: uuid.UUID | None = task_id
        async with self._session_factory() as session:
            # Bounded: delegation depth plus a chain of retries is short, and
            # `seen` stops a malformed cycle.
            while current is not None and current not in seen and len(seen) < 50:
                seen.add(current)
                row = (
                    await session.execute(
                        select(AgentTask.status, AgentTask.parent_task_id).where(
                            AgentTask.id == current, AgentTask.tenant_id == tenant_id
                        )
                    )
                ).first()
                if row is None:
                    return False
                if row.status == "cancelled":
                    return True
                current = row.parent_task_id
        return False

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
            "updated_at": datetime.now(UTC),
        }
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at

        async with self._session_factory() as session:
            stmt = (
                update(AgentTask)
                .where(
                    AgentTask.id == task_id,
                    AgentTask.tenant_id == get_current_tenant_id(),
                )
                .values(**values)
            )
            await session.execute(stmt)
            await session.commit()
