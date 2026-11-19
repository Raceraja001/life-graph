"""Fire-and-forget tasks are kept referenced until they finish (audit L6).

The event loop holds only a weak reference to a task, so a task nobody keeps
can be garbage-collected before it completes ("Task was destroyed but it is
pending"). Each site keeps a module-level set and drops the task when done.
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from life_graph.api import sessions as sessions_api
from life_graph.core import events
from life_graph.core.events import EventBus, EventType, emit_after_commit
from life_graph.services.dev import runner as runner_mod
from life_graph.services.dev.runner import DevTaskRunner


async def _drain() -> None:
    for _ in range(4):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_a_deferred_emit_is_referenced_while_it_runs():
    release = asyncio.Event()

    class _SlowBus(EventBus):
        async def emit(self, event_type, payload, source="system") -> None:  # type: ignore[override]
            await release.wait()

    sync = Session()
    await emit_after_commit(
        SimpleNamespace(sync_session=sync), EventType.CAPTURE_RECEIVED, {}, bus=_SlowBus()
    )
    sync.commit()
    await _drain()

    assert len(events._pending_emits) == 1
    release.set()
    await _drain()
    assert events._pending_emits == set()


@pytest.mark.asyncio
async def test_micro_consolidation_after_session_end_is_referenced(monkeypatch):
    release = asyncio.Event()
    sid = uuid.uuid4()

    async def close_session(session_id, **_kw):
        return SimpleNamespace(
            id=session_id,
            memories_created=0,
        )

    async def consolidate(_session_id):
        await release.wait()

    monkeypatch.setattr(sessions_api, "close_session", close_session)
    monkeypatch.setattr(sessions_api, "_run_micro_consolidation", consolidate)
    monkeypatch.setattr(sessions_api.SessionResponse, "model_validate", lambda s: {})
    monkeypatch.setattr(sessions_api, "success_response", lambda data: data)

    await sessions_api.end_session(sid, None)

    (task,) = sessions_api._background
    assert task.get_name() == f"micro-consolidate-{sid}"
    release.set()
    await _drain()
    assert sessions_api._background == set()


@pytest.mark.asyncio
async def test_the_lost_lock_stop_task_is_referenced(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "dev_runner_heartbeat_seconds", 0)

    async def gone():
        return False

    async def claim(_sf, **_kw):
        return None

    async def run(_sf, _task):  # pragma: no cover - nothing is claimed
        return None

    async def noop(*_a, **_kw):
        return None

    r = DevTaskRunner(None, claim=claim, run_task=run, listen=False, lock_alive=gone)
    r.heartbeat = noop

    await r._check_lock()

    assert len(runner_mod._detached) == 1
    await asyncio.sleep(0.05)
    assert r._stopping is True
    assert runner_mod._detached == set()
