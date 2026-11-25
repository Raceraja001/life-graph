"""A cancel made in another process stops the run (M2).

The kernel cancel route marks rows cancelled and stops the run with
stop_local, which only reaches a run held by the same process. A run in the
ARQ worker (Telegram turns, scheduled jobs) went on to its end. Each run now
re-reads its row's status every CANCEL_POLL_SECONDS and stops itself when it
reads 'cancelled'.

Real ProcessManager and database. The cancel is written straight to the
row, as one from another process would be: stop_local is never called.
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
from life_graph.services.chat_stream import get_chat_stream_bus
from tests.integration.conftest import skip_on_db_error

TENANT = f"remote_cancel_{uuid.uuid4().hex[:8]}"
POLL = 0.2


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


def _watches(task_id: uuid.UUID) -> list[asyncio.Task]:
    name = f"cancel-watch-{task_id!s:.8}"
    return [t for t in asyncio.all_tasks() if t.get_name() == name and not t.done()]


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_run_whose_row_is_cancelled_elsewhere_stops_within_the_poll():
    pm = get_process_manager()
    bus = get_chat_stream_bus()
    started = asyncio.Event()
    finished = asyncio.Event()

    async def run(self, *args, **kwargs):
        started.set()
        await asyncio.sleep(60)  # a long turn
        finished.set()
        return {"response": "should not finish", "token_count": 1}

    with (
        tenant_scope(TENANT),
        patch.object(ProcessManager, "_run_agent", run),
        patch.object(ProcessManager, "CANCEL_POLL_SECONDS", POLL),
    ):
        spawn = await pm.spawn(TENANT, "scout", {"message": "hi"}, max_retries=0)
        task_id = uuid.UUID(spawn["task_id"])
        bg = pm._running[task_id]
        events = bus.subscribe(str(task_id)).__aiter__()
        try:
            await asyncio.wait_for(started.wait(), 10)
            await _cancel_row(pm, task_id)
            try:
                await asyncio.wait_for(asyncio.shield(bg), POLL * 5)
            except asyncio.CancelledError:
                pass
            except TimeoutError:
                # An OSError, which skip_on_db_error would call "no database".
                pytest.fail("the run did not stop after its row was cancelled")
            first = await asyncio.wait_for(events.__anext__(), 5)
        finally:
            await events.aclose()

    assert bg.cancelled()
    assert not finished.is_set()
    assert first["event"] == {"type": "partial_error", "error": "Task cancelled"}
    row = await _row(pm, task_id)
    assert row.status == "cancelled"
    assert row.result == {}
    assert _watches(task_id) == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_normal_run_is_not_stopped_and_its_watch_ends_with_it():
    pm = get_process_manager()

    async def run(self, *args, **kwargs):
        await asyncio.sleep(POLL * 5)  # several polls while running
        return {"response": "done", "token_count": 1}

    with (
        tenant_scope(TENANT),
        patch.object(ProcessManager, "_run_agent", run),
        patch.object(ProcessManager, "CANCEL_POLL_SECONDS", POLL),
    ):
        spawn = await pm.spawn(TENANT, "scout", {"message": "hi"}, max_retries=0)
        task_id = uuid.UUID(spawn["task_id"])
        bg = pm._running[task_id]
        await asyncio.sleep(POLL * 2)
        assert len(_watches(task_id)) == 1
        try:
            await asyncio.wait_for(asyncio.shield(bg), 10)
        except TimeoutError:
            pytest.fail("the run never finished")
        await asyncio.sleep(0)  # let the cancelled watch unwind

    assert not bg.cancelled()
    assert (await _row(pm, task_id)).status == "completed"
    assert _watches(task_id) == []
