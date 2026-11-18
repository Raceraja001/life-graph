"""The dev-task runner: the only place dev tasks execute.

Work order: docs/work-orders/secure-execution-runtime.md, Stage 3.

One :class:`DevTaskRunner` runs in the process that holds the runner advisory
lock (services/dev/tasks.py ``acquire_runner_lock``): the API when
``dev_task_runner_mode=api``, or ``python -m life_graph.workers.dev_runner``
when ``worker``. Everything else only writes rows and wakes it:

- **Claiming** stays :func:`~life_graph.services.dev.tasks.claim_next_queued`
  (``FOR UPDATE SKIP LOCKED``) on the existing ``agent_tasks`` rows: no second
  queue, no second source of truth.
- **Concurrency**: at most ``dev_runner_max_concurrency`` tasks at once, at
  most one of them unattended (queued/nightly work shares one local GPU).
  Interactive starts may use the rest. Counted here, in one process, so two
  starts cannot both slip past a limit.
- **Lease**: each running task's ``properties.lease`` (runner id, claim and
  heartbeat times) is refreshed every ``dev_runner_heartbeat_seconds`` with an
  atomic JSONB merge, so it never races the dispatcher's checkpoint writes.
- **Cancellation**: ``properties.cancel_requested_at`` (set by
  :func:`~life_graph.services.dev.tasks.request_cancel`) is checked every few
  seconds and on NOTIFY; the run's asyncio task is cancelled, which stops the
  driver's process group or container (drivers/claude_code.py,
  drivers/opencode.py, services/dev/sandbox.py, task_runtime teardown), and
  the row is marked ``cancelled``.
- **Wake-ups**: in-process via :func:`notify_runner`; across processes via
  Postgres ``NOTIFY lg_dev_tasks``. Polling every ``QUEUE_POLL_SECONDS`` stays
  as the fallback, so a lost notification only delays a task.

A runner that stops (SIGTERM) drains first (``dev_runner_drain_seconds``);
what it then cancels stays ``running`` and is recovered by
``fail_interrupted`` on the next start, exactly as before.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
import uuid
from collections.abc import Awaitable, Callable  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from life_graph.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from life_graph.models.db import AgentTask

logger = logging.getLogger(__name__)

NOTIFY_CHANNEL = "lg_dev_tasks"

_local_runner: DevTaskRunner | None = None


def set_local_runner(runner: DevTaskRunner | None) -> None:
    """Register the runner living in this process (None when it stops)."""
    global _local_runner
    _local_runner = runner


def local_runner() -> DevTaskRunner | None:
    return _local_runner


async def notify_runner(*, cancel: bool = False) -> None:
    """Wake the runner: directly if it is in this process, else by NOTIFY.

    Best-effort: the runner also polls, so a failed notification only delays.
    """
    if _local_runner is not None:
        _local_runner.wake(cancel=cancel)
        return
    try:
        from life_graph.storage.database import engine

        async with engine.connect() as conn:
            await conn.execute(
                text("SELECT pg_notify(:ch, :payload)"),
                {"ch": NOTIFY_CHANNEL, "payload": "cancel" if cancel else "work"},
            )
            await conn.commit()
    except Exception:
        logger.debug("Could not notify the dev-task runner; it will poll", exc_info=True)


def lease_is_stale(lease: dict | None, now: datetime | None = None) -> bool:
    """Whether a running task's lease has not been refreshed recently."""
    if not isinstance(lease, dict) or not lease.get("heartbeat_at"):
        return True
    try:
        beat = datetime.fromisoformat(str(lease["heartbeat_at"]))
    except ValueError:
        return True
    now = now or datetime.now(UTC)
    return (now - beat).total_seconds() > settings.dev_runner_lease_stale_seconds


ClaimFn = Callable[..., Awaitable["AgentTask | None"]]
RunFn = Callable[["async_sessionmaker[AsyncSession]", "AgentTask"], Awaitable[None]]


class DevTaskRunner:
    """Claims queued dev tasks and runs them under the limits above."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        runner_id: str | None = None,
        max_concurrency: int | None = None,
        claim: ClaimFn | None = None,
        run_task: RunFn | None = None,
        listen: bool = True,
        lock_alive: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        from life_graph.services.dev import tasks as dev_tasks

        self._sf = session_factory
        self.id = runner_id or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self.max = max(1, int(max_concurrency or settings.dev_runner_max_concurrency))
        self._claim = claim or dev_tasks.claim_next_queued
        self._run_task = run_task or dev_tasks.run_claimed
        self._listen = listen
        self._lock_alive = lock_alive
        self.lock_lost = False
        self._beats = 0
        self._running: dict[str, asyncio.Task] = {}
        self._unattended: set[str] = set()
        self._cancelling: set[str] = set()
        self._wake = asyncio.Event()
        self._cancel_wake = asyncio.Event()
        self._stopping = False
        self._bg: list[asyncio.Task] = []

    # ── Public ────────────────────────────────────────────────

    @property
    def running(self) -> list[str]:
        return list(self._running)

    def wake(self, *, cancel: bool = False) -> None:
        (self._cancel_wake if cancel else self._wake).set()

    async def run_forever(self) -> None:
        """Claim and run until cancelled or :meth:`stop` is called."""
        from life_graph.services.dev.tasks import QUEUE_POLL_SECONDS

        self._bg = [
            asyncio.create_task(self._heartbeat_loop(), name="dev-runner-heartbeat"),
            asyncio.create_task(self._cancel_loop(), name="dev-runner-cancel"),
        ]
        if self._listen:
            self._bg.append(asyncio.create_task(self._listen_loop(), name="dev-runner-listen"))
        logger.info("Dev-task runner %s started (max %d concurrent)", self.id, self.max)
        try:
            while not self._stopping:
                await self.fill()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), timeout=QUEUE_POLL_SECONDS)
                self._wake.clear()
        finally:
            # Cancelled from outside (API shutdown): stop everything now. Left
            # by stop(): that call drains running tasks itself, with the
            # heartbeat and cancel loops still on (cancelling either here
            # would defeat the drain or make cancels wait for it -- both found
            # in review / the worker smoke test, 2026-11-18).
            if not self._stopping:
                self._stop_background()
                await self._cancel_all()

    async def fill(self) -> int:
        """Claim tasks until the limits are reached or nothing is runnable."""
        started = 0
        while not self._stopping and len(self._running) < self.max:
            try:
                task = await self._claim(
                    self._sf, runner_id=self.id, allow_unattended=not self._unattended
                )
            except Exception:
                logger.warning("Dev-task claim failed", exc_info=True)
                break
            if task is None:
                break
            self._launch(task)
            started += 1
        return started

    async def run_until_idle(self) -> None:
        """Run everything runnable now, then return (tests, one-shot use)."""
        while True:
            await self.fill()
            if not self._running:
                return
            await asyncio.wait(list(self._running.values()), return_when=asyncio.FIRST_COMPLETED)
            # Let done-callbacks run before the next fill.
            await asyncio.sleep(0)

    async def stop(self, drain_seconds: float | None = None) -> None:
        """Stop claiming; wait for running tasks up to *drain_seconds*, then cancel."""
        self._stopping = True
        self._wake.set()
        drain = settings.dev_runner_drain_seconds if drain_seconds is None else drain_seconds
        if self._running and drain > 0:
            logger.info("Dev-task runner draining %d task(s), up to %ss", len(self._running), drain)
            await asyncio.wait(list(self._running.values()), timeout=drain)
        await self._cancel_all()
        self._stop_background()

    def _stop_background(self) -> None:
        for t in self._bg:
            t.cancel()
        self._bg = []

    async def check_cancels(self) -> list[str]:
        """Cancel every running task whose row asks for it. Returns their ids."""
        if not self._running:
            return []
        ids = [uuid.UUID(t) for t in self._running if t not in self._cancelling]
        if not ids:
            return []
        async with self._sf() as session:
            rows = await session.execute(
                text(
                    "SELECT id FROM agent_tasks WHERE id = ANY(CAST(:ids AS uuid[]))"
                    " AND (properties->>'cancel_requested_at') IS NOT NULL"
                ),
                {"ids": ids},
            )
            wanted = [str(r[0]) for r in rows]
        for tid in wanted:
            task = self._running.get(tid)
            if task is not None and not task.done():
                logger.info("Cancelling dev task %s on request", tid)
                self._cancelling.add(tid)
                task.cancel()
        return wanted

    async def heartbeat(self) -> None:
        """Refresh the lease of every task this runner is running."""
        if not self._running:
            return
        now = datetime.now(UTC).isoformat()
        async with self._sf() as session:
            await session.execute(
                text(
                    "UPDATE agent_tasks SET properties = properties || jsonb_build_object("
                    "'lease', coalesce(properties->'lease', '{}'::jsonb) || jsonb_build_object("
                    "'runner', CAST(:runner AS text), 'heartbeat_at', CAST(:now AS text)))"
                    " WHERE id = ANY(CAST(:ids AS uuid[])) AND status = 'running'"
                ),
                {"runner": self.id, "now": now, "ids": [uuid.UUID(t) for t in self._running]},
            )
            await session.commit()

    # ── Internals ─────────────────────────────────────────────

    def _launch(self, task: AgentTask) -> None:
        tid = str(task.id)
        if not (task.properties or {}).get("interactive"):
            self._unattended.add(tid)
        run = asyncio.create_task(self._execute(task), name=f"dev-task-{tid[:8]}")
        self._running[tid] = run
        run.add_done_callback(lambda _t, tid=tid: self._done(tid))
        logger.info("Dev-task runner %s started task %s (%s)", self.id, tid, task.title)
        from life_graph.services.dev import task_events

        task_events.emit(
            getattr(task, "tenant_id", None), tid, "status", "running",
            data={"runner": self.id, "unattended": tid in self._unattended},
        )  # fmt: skip

    def _done(self, tid: str) -> None:
        self._running.pop(tid, None)
        self._unattended.discard(tid)
        self._cancelling.discard(tid)
        self._wake.set()

    async def _execute(self, task: AgentTask) -> None:
        tid = str(task.id)
        try:
            await self._run_task(self._sf, task)
        except asyncio.CancelledError:
            if tid in self._cancelling:
                # We cancelled it on request: record that, and end quietly.
                await self._mark_cancelled(tid)
                return
            # Runner shutdown: the row stays "running"; fail_interrupted
            # recovers it on the next start.
            raise
        except Exception:
            logger.warning("Dev task %s crashed in the runner", tid, exc_info=True)

    async def _mark_cancelled(self, tid: str) -> None:
        from life_graph.models.db import AgentTask
        from life_graph.services.dev.tasks import _history

        try:
            async with self._sf() as session:
                task = await session.get(AgentTask, uuid.UUID(tid))
                if task is None or task.status != "running":
                    return
                from life_graph.services.dev import task_events

                # Events first, then the terminal status (see tasks._run).
                task_events.emit(task.tenant_id, tid, "status", "cancelled")
                await task_events.flush()
                task.status = "cancelled"
                task.error = "Cancelled on request"
                task.completed_at = datetime.now(UTC)
                task.status_history = _history(task, "cancelled", "cancelled while running")
                await session.commit()
        except Exception:
            logger.warning("Could not record the cancel of dev task %s", tid, exc_info=True)

    async def _cancel_all(self) -> None:
        tasks = [t for t in self._running.values() if not t.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(max(1, settings.dev_runner_heartbeat_seconds))
            try:
                await self.heartbeat()
            except Exception:
                logger.debug("Lease heartbeat failed", exc_info=True)
            await self._check_lock()
            self._beats += 1
            # Every few beats: recover runs whose lease went stale (a runner
            # that died without a restart of this one).
            if self._beats % 4 == 0 and not self.lock_lost:
                try:
                    from life_graph.services.dev.tasks import fail_interrupted

                    await fail_interrupted(self._sf, runner_id=self.id)
                except Exception:
                    logger.debug("Stale-lease recovery failed", exc_info=True)

    async def _check_lock(self) -> None:
        if self._lock_alive is None or self.lock_lost or self._stopping:
            return
        if await self._lock_alive():
            return
        # Another process may now hold the lock and claim work. Our running
        # tasks keep heartbeating (their leases stay fresh, so nobody else
        # recovers them); we stop claiming and drain.
        self.lock_lost = True
        logger.error("Dev-task runner %s lost the runner lock; draining and stopping", self.id)
        asyncio.get_running_loop().create_task(self.stop())

    async def _cancel_loop(self) -> None:
        while True:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._cancel_wake.wait(),
                    timeout=max(1, settings.dev_runner_cancel_poll_seconds),
                )
            self._cancel_wake.clear()
            try:
                await self.check_cancels()
            except Exception:
                logger.debug("Cancel check failed", exc_info=True)

    async def _listen_loop(self) -> None:
        """LISTEN lg_dev_tasks on a dedicated connection; reconnect on failure."""
        from life_graph.storage.database import engine

        def on_notify(_conn: Any, _pid: int, _channel: str, payload: str) -> None:
            self.wake(cancel=payload == "cancel")

        while True:
            try:
                async with engine.connect() as conn:
                    raw = await conn.get_raw_connection()
                    driver_conn = raw.driver_connection
                    await driver_conn.add_listener(NOTIFY_CHANNEL, on_notify)
                    try:
                        # A dropped connection loses the listener silently:
                        # ping it, and reconnect when the ping fails.
                        while True:
                            await asyncio.sleep(30)
                            await asyncio.wait_for(driver_conn.fetchval("SELECT 1"), 10)
                            # Anything announced while we were not listening.
                            self.wake()
                    finally:
                        with contextlib.suppress(Exception):
                            await driver_conn.remove_listener(NOTIFY_CHANNEL, on_notify)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug("Runner LISTEN failed; polling only for 30s", exc_info=True)
                await asyncio.sleep(30)
