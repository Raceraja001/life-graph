"""Events about a row must not fire before that row is committed.

Services that borrow the caller's session (capture spine, Telegram bridge,
interview engine, tool observation) emitted straight after ``flush()``, while
the transaction was still open. Handlers read in a session of their own, so the
row was invisible: ``CaptureProcessors`` logged "CaptureEvent ... not found"
and every ambient capture yielded zero memories. ``emit_after_commit`` defers
the emit to SQLAlchemy's ``after_commit`` hook.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from life_graph.core.events import EventBus, EventType, emit_after_commit


class _RecordingBus(EventBus):
    def __init__(self) -> None:
        super().__init__()
        self.emitted: list[tuple[EventType, dict, str]] = []

    async def emit(self, event_type, payload, source="system") -> None:  # type: ignore[override]
        self.emitted.append((event_type, payload, source))


def _fake_async_session() -> tuple[SimpleNamespace, Session]:
    """An AsyncSession stand-in: only ``.sync_session`` is needed for the hook."""
    sync = Session()
    return SimpleNamespace(sync_session=sync), sync


async def _drain() -> None:
    """Let the scheduled emit task run (call_soon_threadsafe -> create_task)."""
    for _ in range(4):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_nothing_is_emitted_before_commit():
    session, _sync = _fake_async_session()
    bus = _RecordingBus()

    await emit_after_commit(session, EventType.CAPTURE_RECEIVED, {"id": "x"}, bus=bus)
    await _drain()

    assert bus.emitted == []


@pytest.mark.asyncio
async def test_emitted_once_the_transaction_commits():
    session, sync = _fake_async_session()
    bus = _RecordingBus()

    await emit_after_commit(
        session, EventType.CAPTURE_RECEIVED, {"capture_event_id": "abc"}, "capture", bus=bus
    )
    sync.dispatch.after_commit(sync)  # what a real commit triggers
    await _drain()

    assert len(bus.emitted) == 1
    event_type, payload, source = bus.emitted[0]
    assert event_type is EventType.CAPTURE_RECEIVED
    assert payload == {"capture_event_id": "abc"}
    assert source == "capture"


@pytest.mark.asyncio
async def test_a_second_commit_does_not_re_emit():
    """The listener is one-shot: a later commit on the same session is not ours."""
    session, sync = _fake_async_session()
    bus = _RecordingBus()

    await emit_after_commit(session, EventType.CAPTURE_RECEIVED, {"id": "x"}, bus=bus)
    sync.dispatch.after_commit(sync)
    sync.dispatch.after_commit(sync)
    await _drain()

    assert len(bus.emitted) == 1


@pytest.mark.asyncio
async def test_handler_failure_is_logged_not_raised(caplog):
    session, sync = _fake_async_session()

    class _ExplodingBus(EventBus):
        async def emit(self, *a, **k):  # type: ignore[override]
            raise RuntimeError("handler exploded")

    await emit_after_commit(session, EventType.CAPTURE_RECEIVED, {}, bus=_ExplodingBus())
    sync.dispatch.after_commit(sync)
    await _drain()  # must not raise into the loop

    assert "Deferred event emit failed" in caplog.text
