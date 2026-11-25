"""A chat turn's "done" reaches the client only after its result is saved.

ProcessManager._run_agent used to publish the orchestrator's "done" to the
chat stream as it came, and _execute_task wrote the result to the database
afterwards. A client that regenerated or resent the moment it saw "done" then
found the row still running and got 409 "That reply is still being written."
Now the closing events wait until the row is completed.

Real ProcessManager and database; the model is a canned orchestrator run,
and saving the result is slowed down so the old order shows every time.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from life_graph.api.dependencies import get_process_manager
from life_graph.config import settings
from life_graph.core.tenant import tenant_scope
from life_graph.kernel.process_manager import ProcessManager
from life_graph.models.db import AgentTask
from life_graph.services.chat_turn import ChatStreamRequest, stream_turn
from tests.integration.conftest import skip_on_db_error

TENANT = f"chat_done_{uuid.uuid4().hex[:8]}"

_original_complete = ProcessManager._complete_task


async def _slow_complete(self, *args, **kwargs):
    await asyncio.sleep(0.3)
    await _original_complete(self, *args, **kwargs)


async def _fake_run(self, messages, system_prompt=None, tools=None, **kwargs):
    yield 'data: {"type": "token", "content": "hel"}\n\n'
    yield 'data: {"type": "token", "content": "lo"}\n\n'
    yield 'data: {"type": "done", "model": "m"}\n\n'


async def _fake_run_cites(self, messages, system_prompt=None, tools=None, **kwargs):
    # Cites a page no tool fetched in this run, so the answer gains a note.
    yield 'data: {"type": "token", "content": "See https://example.com/a"}\n\n'
    yield 'data: {"type": "done", "model": "m"}\n\n'


async def _turn_until_done(pm) -> tuple[list[dict], AgentTask]:
    """Stream one turn; read its row the moment the done frame arrives."""
    body = ChatStreamRequest(message="hi", target_agent="jarvis")
    frames: list[dict] = []
    row = None
    try:
        async with asyncio.timeout(10):
            async for raw in stream_turn(TENANT, body, pm):
                if not raw.startswith("data: "):
                    continue
                frame = json.loads(raw[6:])
                frames.append(frame)
                if frame["type"] == "done":
                    task_id = uuid.UUID(frames[0]["task_id"])
                    async with pm._session_factory() as session:
                        row = (
                            await session.execute(select(AgentTask).where(AgentTask.id == task_id))
                        ).scalar_one()
    except TimeoutError:
        # TimeoutError is an OSError, which skip_on_db_error would report as
        # "no database": a hung stream must fail instead.
        pytest.fail(f"stream never ended; frames so far: {frames}")
    assert row is not None, frames
    return frames, row


@pytest.mark.asyncio
@skip_on_db_error
async def test_done_arrives_after_the_turn_is_saved():
    pm = get_process_manager()
    with (
        tenant_scope(TENANT),
        patch("life_graph.agents.orchestrator.AgentOrchestrator.run", _fake_run),
        patch.object(ProcessManager, "_complete_task", _slow_complete),
    ):
        frames, row = await _turn_until_done(pm)

    deltas = [f["text"] for f in frames if f["type"] == "assistant_delta"]
    assert deltas == ["hel", "lo"]
    assert frames[-1]["type"] == "done"
    assert row.status == "completed"
    assert row.result["response"] == "hello"


@pytest.mark.asyncio
@skip_on_db_error
async def test_sources_note_still_comes_before_done_and_is_saved(monkeypatch):
    # A persona whose answers must cite a source: an answer citing a page it
    # never fetched gains a note at its end, streamed just before "done"
    # (services/sources.py).
    monkeypatch.setattr(settings, "require_sources_personas", "jarvis")
    pm = get_process_manager()
    with (
        tenant_scope(TENANT),
        patch("life_graph.agents.orchestrator.AgentOrchestrator.run", _fake_run_cites),
        patch.object(ProcessManager, "_complete_task", _slow_complete),
    ):
        frames, row = await _turn_until_done(pm)

    deltas = [f["text"] for f in frames if f["type"] == "assistant_delta"]
    assert len(deltas) == 2, deltas
    assert deltas[0] == "See https://example.com/a"
    assert "example.com/a" in deltas[1]  # the note names the unsourced page
    assert frames[-1]["type"] == "done"
    assert row.status == "completed"
    assert row.result["response"] == deltas[0] + deltas[1]
