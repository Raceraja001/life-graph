"""Kernel retries end, and a stop during the slot wait ends the stream (M2).

Retries: `_retry_task` used to spawn each retry as a fresh row with
retry_count 0 and the default max_retries, so a task that always raised was
retried for ever (about one new row a second). It now carries the chain's
place: retry_count + 1, the original's max_retries, root_task_id and depth.

Slot wait: a queued task stopped by `stop_local` while waiting for a
concurrency slot raised CancelledError before any handler, so a stream
waiting on it never got a terminal event.

Real ProcessManager and database; only the model run is replaced.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from life_graph.api.dependencies import get_process_manager
from life_graph.core.tenant import tenant_scope
from life_graph.kernel.process_manager import ProcessManager
from life_graph.models.db import AgentTask
from life_graph.services.chat_stream import get_chat_stream_bus
from tests.integration.conftest import skip_on_db_error

TENANT = f"bounded_retry_{uuid.uuid4().hex[:8]}"


async def _boom(self, *args, **kwargs):
    raise RuntimeError("always fails")


async def _chain(pm, first: uuid.UUID) -> list[AgentTask]:
    """The task and its retries, oldest first (each retry is a child of the one before)."""
    rows: list[AgentTask] = []
    current: uuid.UUID | None = first
    async with pm._session_factory() as session:
        while current is not None:
            row = (
                await session.execute(select(AgentTask).where(AgentTask.id == current))
            ).scalar_one()
            rows.append(row)
            nxt = (
                (
                    await session.execute(
                        select(AgentTask).where(AgentTask.parent_task_id == current)
                    )
                )
                .scalars()
                .all()
            )
            assert len(nxt) <= 1, "a failure spawned more than one retry"
            current = nxt[0].id if nxt else None
    return rows


async def _settled(pm, first: uuid.UUID, length: int) -> list[AgentTask]:
    """Wait (backoffs are 1 s, 2 s, ...) until the chain has `length` failed rows."""
    for _ in range(200):
        rows = await _chain(pm, first)
        if len(rows) >= length and all(r.status == "failed" for r in rows):
            return rows
        await asyncio.sleep(0.1)
    pytest.fail(f"chain never settled: {[(r.task_name, r.status) for r in rows]}")


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_always_raising_task_is_retried_max_retries_times_then_stops():
    pm = get_process_manager()
    with tenant_scope(TENANT), patch.object(ProcessManager, "_run_agent", _boom):
        spawn = await pm.spawn(TENANT, "scout", {"message": "go"}, max_retries=2)
        first = uuid.UUID(spawn["task_id"])
        await _settled(pm, first, 3)
        # The next backoff would be 2**2 = 4 s: wait past it.
        await asyncio.sleep(4.5)
        rows = await _chain(pm, first)

    assert len(rows) == 3, [(r.task_name, r.status) for r in rows]
    assert all(r.status == "failed" for r in rows)
    assert [r.task_name.split("-of-")[0] for r in rows[1:]] == ["retry-1", "retry-2"]
    assert all(r.max_retries == 2 for r in rows)
    # The last attempt carries the count that stopped the chain.
    assert rows[-1].retry_count == 2


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_retried_child_stays_in_its_tree():
    pm = get_process_manager()
    root = AgentTask(
        id=uuid.uuid4(), tenant_id=TENANT, agent_name="jarvis", status="running", input={}
    )
    async with pm._session_factory() as session:
        session.add(root)
        await session.commit()

    with tenant_scope(TENANT), patch.object(ProcessManager, "_run_agent", _boom):
        spawn = await pm.spawn(
            TENANT,
            "scout",
            {"message": "child"},
            max_retries=1,
            parent_task_id=root.id,
            root_task_id=root.id,
            depth=1,
        )
        rows = await _settled(pm, uuid.UUID(spawn["task_id"]), 2)

    retry = rows[1]
    assert retry.root_task_id == root.id
    assert retry.depth == 1
    assert retry.retry_count == 1 and retry.max_retries == 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_stop_while_waiting_for_a_slot_ends_the_stream():
    pm = get_process_manager()
    bus = get_chat_stream_bus()
    held = pm._max_concurrent
    for _ in range(held):
        await pm._semaphore.acquire()
    try:
        with tenant_scope(TENANT), patch.object(ProcessManager, "_run_agent", _boom):
            spawn = await pm.spawn(TENANT, "scout", {"message": "hi"}, max_retries=0)
            task_id = uuid.UUID(spawn["task_id"])
            events = bus.subscribe(str(task_id)).__aiter__()
            await asyncio.sleep(0.1)  # now waiting on the semaphore
            assert pm.stop_local(task_id)
            try:
                first = await asyncio.wait_for(events.__anext__(), 5)
            except TimeoutError:
                # An OSError, which skip_on_db_error would call "no database".
                pytest.fail("no terminal event reached the stream")
            finally:
                await events.aclose()
    finally:
        for _ in range(held):
            pm._semaphore.release()

    assert first["event"] == {"type": "partial_error", "error": "Task cancelled"}
    assert first["depth"] == 0
