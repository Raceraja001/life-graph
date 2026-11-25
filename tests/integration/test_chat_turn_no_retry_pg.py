"""A streamed chat turn that raises is not retried behind the client's back.

Every chat stream (the dashboard's /kernel/chat/stream, the phone's
/jarvis/chat) runs services/chat_turn.py stream_turn. It used to spawn with
the kernel default of 2 retries: on an exception the kernel slept out a
backoff, spawned a new task with its own stream nobody reads (and which could
run memory_save or reminder_set again), and only then told this stream its
turn had failed. Now a streamed turn spawns with max_retries=0, so the client
gets one error frame at once and no second task appears.

Real ProcessManager and database; only the model run itself is replaced by
one that raises.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from life_graph.api.dependencies import get_process_manager
from life_graph.core.tenant import tenant_scope
from life_graph.kernel.process_manager import ProcessManager
from life_graph.models.db import AgentTask
from life_graph.services.chat_turn import ChatStreamRequest, stream_turn
from tests.integration.conftest import skip_on_db_error

TENANT = f"chat_noretry_{uuid.uuid4().hex[:8]}"


async def _boom(self, *args, **kwargs):
    raise RuntimeError("model blew up")


@pytest.mark.asyncio
@skip_on_db_error
async def test_raising_chat_turn_sends_one_prompt_error_and_spawns_no_retry():
    pm = get_process_manager()
    body = ChatStreamRequest(message="hello", target_agent="jarvis")

    frames: list[dict] = []
    with tenant_scope(TENANT), patch.object(ProcessManager, "_run_agent", _boom):
        started = time.monotonic()
        try:
            async with asyncio.timeout(10):
                async for raw in stream_turn(TENANT, body, pm):
                    if raw.startswith("data: "):
                        frames.append(json.loads(raw[6:]))
        except TimeoutError:
            # TimeoutError is an OSError, which skip_on_db_error would
            # report as "no database": a hung stream must fail instead.
            pytest.fail(f"stream never ended; frames so far: {frames}")
        elapsed = time.monotonic() - started

        types = [f["type"] for f in frames]
        assert types == ["start", "error"], frames
        assert "model blew up" in frames[1]["message"]
        # Prompt: no backoff sleep (the first retry waited 2**0 = 1 s) ran
        # before the error reached the stream.
        assert elapsed < 0.9, elapsed

        task_id = uuid.UUID(frames[0]["task_id"])
        # Long enough for a first retry (1 s backoff) to have been spawned.
        await asyncio.sleep(1.5)

    async with pm._session_factory() as session:
        row = (await session.execute(select(AgentTask).where(AgentTask.id == task_id))).scalar_one()
        retries = (
            (await session.execute(select(AgentTask).where(AgentTask.parent_task_id == task_id)))
            .scalars()
            .all()
        )
    assert row.status == "failed"
    assert row.max_retries == 0
    assert row.retry_count == 0
    assert retries == []
