"""A cancelled kernel task stays cancelled (audit M2).

A cancel writes status='cancelled' to the row. Before this, the run's own
later writes could undo it: a run that finished or failed after the cancel
(in another process such as the ARQ worker, or racing the cancel here) wrote
completed/failed over it, a queued task cancelled before it got a slot was
set running and run anyway, and a retry sleeping out its backoff spawned
after its tree was cancelled.

Real ProcessManager and database. The cancel is written straight to the row,
as one from another process would be, so the local asyncio task is not
stopped and its own writes are what is under test.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select, update

from life_graph.api.dependencies import get_process_manager
from life_graph.core.tenant import tenant_scope
from life_graph.kernel.process_manager import ProcessManager
from life_graph.models.db import AgentTask
from tests.integration.conftest import skip_on_db_error

TENANT = f"cancel_sticks_{uuid.uuid4().hex[:8]}"


async def _cancel_row(pm, task_id: uuid.UUID) -> None:
    async with pm._session_factory() as session:
        await session.execute(
            update(AgentTask).where(AgentTask.id == task_id).values(status="cancelled")
        )
        await session.commit()


async def _row(pm, task_id: uuid.UUID) -> AgentTask:
    async with pm._session_factory() as session:
        return (
            await session.execute(select(AgentTask).where(AgentTask.id == task_id))
        ).scalar_one()


async def _children(pm, task_id: uuid.UUID) -> list[AgentTask]:
    async with pm._session_factory() as session:
        return list(
            (await session.execute(select(AgentTask).where(AgentTask.parent_task_id == task_id)))
            .scalars()
            .all()
        )


async def _wait_status(pm, task_id: uuid.UUID, status: str) -> None:
    for _ in range(100):
        if (await _row(pm, task_id)).status == status:
            return
        await asyncio.sleep(0.05)
    pytest.fail(f"task never reached {status}")


async def _finish(pm, task_id: uuid.UUID) -> None:
    bg = pm._running.get(task_id)
    if bg is not None:
        try:
            await asyncio.wait_for(asyncio.shield(bg), 10)
        except TimeoutError:
            # An OSError, which skip_on_db_error would call "no database".
            pytest.fail("the task never finished")


def _gated(outcome: str):
    """A _run_agent that waits for `release`, then returns or raises."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def run(self, *args, **kwargs):
        started.set()
        await release.wait()
        if outcome == "raise":
            raise RuntimeError("died after the cancel")
        return {"response": "late answer", "token_count": 2}

    return run, started, release


@pytest.mark.asyncio
@skip_on_db_error
@pytest.mark.parametrize("outcome", ["return", "raise"])
async def test_a_run_ending_after_its_cancel_leaves_it_cancelled(outcome):
    pm = get_process_manager()
    run, started, release = _gated(outcome)
    with tenant_scope(TENANT), patch.object(ProcessManager, "_run_agent", run):
        spawn = await pm.spawn(TENANT, "scout", {"message": "hi"}, max_retries=2)
        task_id = uuid.UUID(spawn["task_id"])
        await asyncio.wait_for(started.wait(), 10)
        await _cancel_row(pm, task_id)
        release.set()
        await _finish(pm, task_id)
        # A retry (if one were spawned) waits 1 s first.
        await asyncio.sleep(1.5)

    row = await _row(pm, task_id)
    assert row.status == "cancelled"
    assert row.result == {}
    assert row.error is None
    assert await _children(pm, task_id) == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_task_cancelled_while_queued_never_runs():
    pm = get_process_manager()
    ran = asyncio.Event()

    async def run(self, *args, **kwargs):
        ran.set()
        return {"response": "should not run", "token_count": 0}

    held = pm._max_concurrent
    for _ in range(held):
        await pm._semaphore.acquire()
    try:
        with tenant_scope(TENANT), patch.object(ProcessManager, "_run_agent", run):
            spawn = await pm.spawn(TENANT, "scout", {"message": "hi"}, max_retries=0)
            task_id = uuid.UUID(spawn["task_id"])
            await _cancel_row(pm, task_id)
            for _ in range(held):
                pm._semaphore.release()
            held = 0
            await _finish(pm, task_id)
    finally:
        for _ in range(held):
            pm._semaphore.release()

    row = await _row(pm, task_id)
    assert not ran.is_set()
    assert row.status == "cancelled"
    assert row.started_at is None


@pytest.mark.asyncio
@skip_on_db_error
async def test_no_retry_spawns_after_the_tree_is_cancelled_during_backoff():
    pm = get_process_manager()

    async def boom(self, *args, **kwargs):
        raise RuntimeError("transient")

    # The tree's root, as a delegating parent's row would be.
    root = AgentTask(
        id=uuid.uuid4(), tenant_id=TENANT, agent_name="jarvis", status="running", input={}
    )
    async with pm._session_factory() as session:
        session.add(root)
        await session.commit()

    with tenant_scope(TENANT), patch.object(ProcessManager, "_run_agent", boom):
        spawn = await pm.spawn(
            TENANT,
            "scout",
            {"message": "child"},
            max_retries=1,
            parent_task_id=root.id,
            root_task_id=root.id,
            depth=1,
        )
        child_id = uuid.UUID(spawn["task_id"])
        # Failed, and now inside the 1 s backoff before its retry.
        await _wait_status(pm, child_id, "failed")
        await _cancel_row(pm, root.id)
        await _finish(pm, child_id)

    assert (await _row(pm, child_id)).status == "failed"
    assert await _children(pm, child_id) == []
