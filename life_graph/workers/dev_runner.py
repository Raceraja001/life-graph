"""The dedicated dev-task worker: ``python -m life_graph.workers.dev_runner``.

Work order Stage 3. With ``LIFE_GRAPH_DEV_TASK_RUNNER_MODE=worker`` the API
processes only queue and inspect dev tasks; this process holds the runner
advisory lock and runs them (services/dev/runner.py), so restarting or
redeploying the API no longer cuts a running coding agent off.

What it sets up is what a dispatch needs in-process, and nothing else:

- the agent tools and drivers (LocalDriver runs the tool registry in-process);
- the event handlers whose events a dispatch emits HERE: the approval-filed
  notifications (push/Telegram) and the trajectory recorder (driver:steps);
- Redis, best-effort.

Then: take the runner lock (wait for it while another process has it — a
second worker is a hot standby, never a second runner), recover what the last
runner left (``fail_interrupted``), sweep leftover runtimes, and run. SIGTERM
drains running tasks for up to ``dev_runner_drain_seconds`` before stopping.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from life_graph.config import settings

logger = logging.getLogger("life_graph.workers.dev_runner")

LOCK_RETRY_SECONDS = 15


async def _prepare_process() -> None:
    try:
        from life_graph.storage.redis import init_redis

        await init_redis()
    except Exception:
        logger.warning("Redis not available in the dev-task worker", exc_info=True)
    try:
        from life_graph.tools.load import register_all

        logger.info("Dev-task worker agent tools: %d", len(register_all()))
    except Exception:
        logger.warning("Agent tools not available in the dev-task worker", exc_info=True)
    from life_graph.drivers.setup import register_default_drivers

    logger.info("Dev-task worker drivers: %s", register_default_drivers())
    # A dispatch files approvals (APPROVAL_FILED) and records steps
    # (DRIVER_STEPS) on this process's event bus: only handlers subscribed
    # here hear them.
    try:
        from life_graph.services.notifications.approval import approval_notification_handler

        approval_notification_handler.subscribe()
    except Exception:
        logger.warning("Approval notifications not available in the worker", exc_info=True)
    try:
        from life_graph.services.dev.trajectories import trajectory_recorder

        trajectory_recorder.subscribe()
    except Exception:
        logger.warning("Trajectory recorder not available in the worker", exc_info=True)


async def _acquire_lock(stop: asyncio.Event):
    from life_graph.services.dev.tasks import acquire_runner_lock
    from life_graph.storage.database import engine

    while not stop.is_set():
        conn = await acquire_runner_lock(engine)
        if conn is not None:
            return conn
        logger.info("Another process is the dev-task runner; standing by")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=LOCK_RETRY_SECONDS)
    return None


async def main() -> int:
    from life_graph.core.logging import setup_logging

    setup_logging(level=getattr(settings, "log_level", "INFO") or "INFO")
    if not settings.dev_task_runner_enabled:
        logger.error("LIFE_GRAPH_DEV_TASK_RUNNER_ENABLED=false: not starting a dev-task runner")
        return 1
    if settings.dev_task_runner_mode != "worker":
        logger.warning(
            "dev_task_runner_mode=%s: the API may also try to be the runner; the lock "
            "keeps only one of you running tasks",
            settings.dev_task_runner_mode,
        )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    await _prepare_process()
    lock = await _acquire_lock(stop)
    if lock is None:
        return 0

    from life_graph.services.dev.runner import DevTaskRunner, set_local_runner
    from life_graph.services.dev.task_runtime import sweep_orphans
    from life_graph.services.dev.tasks import (
        fail_interrupted,
        release_runner_lock,
        runner_lock_alive,
    )
    from life_graph.storage.database import async_session

    try:
        runner = DevTaskRunner(async_session, lock_alive=lambda: runner_lock_alive(lock))
        interrupted = await fail_interrupted(async_session, runner_id=runner.id)
        if interrupted:
            logger.warning("Marked %d interrupted dev task(s) as failed", interrupted)
        await sweep_orphans(async_session)

        set_local_runner(runner)
        forever = asyncio.create_task(runner.run_forever(), name="dev-runner")
        stopper = asyncio.create_task(stop.wait())
        await asyncio.wait({forever, stopper}, return_when=asyncio.FIRST_COMPLETED)
        if not forever.done():
            logger.info("Dev-task worker stopping")
            await runner.stop()
            forever.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await forever
        stopper.cancel()
        if runner.lock_lost:
            # Non-zero so a supervisor restarts us; the restart re-takes the lock.
            return 3
    finally:
        set_local_runner(None)
        try:
            await release_runner_lock(lock)
        except Exception:
            logger.warning("Releasing the dev-task runner lock failed", exc_info=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
