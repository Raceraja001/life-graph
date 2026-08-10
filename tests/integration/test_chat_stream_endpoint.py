"""End-to-end: POST /kernel/chat/stream returns a mapped SSE token stream.

Persona lookup and task spawning go through real ProcessManager/PersonaService
in production, both of which need a live Postgres connection. To keep this
test deterministic without a DB, we override their FastAPI dependencies with
stubs: the stub persona service returns a plain persona dict for any name,
and the stub process manager returns a fixed task_id and schedules a
coroutine that publishes raw bus events (the same shape ProcessManager._run_agent
publishes) for that task_id, then closes the bus. This exercises the real
endpoint code path -- subscribe -> map_bus_event -> SSE framing -- end to end.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.api.dependencies import get_persona_service, get_process_manager
from life_graph.main import app
from life_graph.services.chat_stream import get_chat_stream_bus

HEADERS = {"X-Tenant-ID": "test-chat"}


class _StubPersonaService:
    """get_by_name returns a plain persona dict for any known-looking name."""

    async def get_by_name(self, tenant_id: str, name: str) -> dict | None:
        if name == "missing-persona":
            return None
        return {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "name": name, "is_active": True}


class _StubProcessManager:
    """spawn() returns a fixed task_id and publishes canned bus events for it."""

    def __init__(self, task_id: str, bus_events: list[dict]) -> None:
        self._task_id = task_id
        self._bus_events = bus_events

    async def spawn(self, **kwargs) -> dict:
        bus = get_chat_stream_bus()

        async def _publish() -> None:
            for event in self._bus_events:
                bus.publish(self._task_id, event)
            bus.close(self._task_id)

        asyncio.create_task(_publish())
        return {"task_id": self._task_id}


class _StubProcessManagerSpawnFails:
    """spawn() raises -- reproduces a DB failure (or any other exception)
    happening AFTER the SSE response has already started (spawn() now runs
    inside the endpoint's generator, not before the response object is
    returned). Regression coverage for the previously-unhandled path: before
    this, an exception here would propagate out of the generator as an
    unhandled error; now it must surface as a clean `error` SSE frame.
    """

    def __init__(self, message: str = "db unavailable") -> None:
        self._message = message

    async def spawn(self, **kwargs) -> dict:
        raise RuntimeError(self._message)


class _StubProcessManagerNoClose:
    """Like _StubProcessManager, but never calls bus.close().

    Production `ProcessManager._execute_task` never closes the bus either --
    only the SSE endpoint does, from its own `finally`, and only AFTER its
    `async for` loop has already broken out on a terminal event. This stub
    reproduces that: it publishes canned events and stops, so the test can
    verify the endpoint terminates on the terminal event's content alone,
    not because the producer happened to close the stream for it.
    """

    def __init__(self, task_id: str, bus_events: list[dict]) -> None:
        self._task_id = task_id
        self._bus_events = bus_events

    async def spawn(self, **kwargs) -> dict:
        bus = get_chat_stream_bus()

        async def _publish() -> None:
            for event in self._bus_events:
                bus.publish(self._task_id, event)
            # Deliberately no bus.close() here -- see class docstring.

        asyncio.create_task(_publish())
        return {"task_id": self._task_id}


class _StubProcessManagerIdleGap:
    """Publishes one delta, idles LONGER than the (patched-tiny) heartbeat
    interval, then publishes more deltas + a top-level done and closes.

    Reproduces the real-world case that Regression A broke: a delegated child
    on a slow free model leaves the bus idle past the heartbeat interval. The
    endpoint must keep the subscription alive across the gap (emitting only
    keep-alive heartbeats) and still deliver the LATER deltas + done -- rather
    than cancelling its own __anext__() wait, unregistering the subscriber, and
    silently ending the stream at the first idle gap.
    """

    def __init__(self, task_id: str, idle_seconds: float) -> None:
        self._task_id = task_id
        self._idle_seconds = idle_seconds

    async def spawn(self, **kwargs) -> dict:
        bus = get_chat_stream_bus()
        task_id = self._task_id
        idle = self._idle_seconds

        def _delta(text: str) -> dict:
            return {
                "task_id": task_id,
                "agent_name": "jarvis",
                "depth": 0,
                "event": {"type": "token", "content": text},
            }

        async def _publish() -> None:
            bus.publish(task_id, _delta("before"))
            await asyncio.sleep(idle)  # idle gap > heartbeat interval
            bus.publish(task_id, _delta(" after"))
            bus.publish(
                task_id,
                {"task_id": task_id, "agent_name": "jarvis", "depth": 0, "event": {"type": "done"}},
            )
            bus.close(task_id)

        asyncio.create_task(_publish())
        return {"task_id": task_id}


def _token_done_events(task_id: str) -> list[dict]:
    """A depth-0 'Hello' response streamed as two tokens then done."""
    return [
        {
            "task_id": task_id,
            "agent_name": "jarvis",
            "depth": 0,
            "event": {"type": "token", "content": "Hel"},
        },
        {
            "task_id": task_id,
            "agent_name": "jarvis",
            "depth": 0,
            "event": {"type": "token", "content": "lo"},
        },
        {"task_id": task_id, "agent_name": "jarvis", "depth": 0, "event": {"type": "done"}},
    ]


def _child_error_then_continues_events(task_id: str) -> list[dict]:
    """A delegated child errors out, but the delegation architecture continues:

    Jarvis (depth 0) keeps running and still produces a real answer + a
    top-level done. The child's error must reach the client as a non-fatal
    `child_error` chat event but must NOT terminate the SSE stream.
    """
    return [
        {
            "task_id": task_id,
            "agent_name": "jarvis",
            "depth": 0,
            "event": {"type": "tool_call", "name": "delegate_to_persona"},
        },
        {
            "task_id": "child-err-1",
            "agent_name": "scout",
            "depth": 1,
            "event": {"type": "error", "error": "litellm.AuthenticationError"},
        },
        {
            "task_id": task_id,
            "agent_name": "jarvis",
            "depth": 0,
            "event": {"type": "token", "content": "Despite"},
        },
        {
            "task_id": task_id,
            "agent_name": "jarvis",
            "depth": 0,
            "event": {"type": "token", "content": " the failure"},
        },
        {"task_id": task_id, "agent_name": "jarvis", "depth": 0, "event": {"type": "done"}},
    ]


def _tokens_then_no_top_level_done_events(task_id: str) -> list[dict]:
    """Some tokens, then the task ends abnormally (timeout/cancel/crash)
    WITHOUT the orchestrator ever emitting a depth-0 `done`.

    This is the exact shape production `ProcessManager._execute_task` now
    publishes on its failure paths (see `_publish_terminal_bus_event`): a
    depth-0 `partial_error`, which `map_bus_event` turns into a fatal
    `error` -- the only thing that stops the SSE endpoint's `async for`
    loop from blocking forever, since the producer side never calls
    `bus.close()` (only `bus.discard()`, which is a no-op while this
    request's subscriber is still attached).
    """
    return [
        {
            "task_id": task_id,
            "agent_name": "jarvis",
            "depth": 0,
            "event": {"type": "token", "content": "Working"},
        },
        {
            "task_id": task_id,
            "agent_name": "jarvis",
            "depth": 0,
            "event": {"type": "token", "content": " on it"},
        },
        {
            "task_id": task_id,
            "agent_name": "jarvis",
            "depth": 0,
            "event": {"type": "partial_error", "error": "RuntimeError: boom"},
        },
    ]


def _delegation_events(task_id: str) -> list[dict]:
    """Parent tool_call/usage (dropped) + a child that only ever emits done."""
    return [
        {
            "task_id": task_id,
            "agent_name": "jarvis",
            "depth": 0,
            "event": {"type": "tool_call", "name": "delegate_to_persona"},
        },
        {"task_id": "child-1", "agent_name": "scout", "depth": 1, "event": {"type": "done"}},
        {"task_id": task_id, "agent_name": "jarvis", "depth": 0, "event": {"type": "done"}},
    ]


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


@pytest_asyncio.fixture
def stub_overrides():
    """Install dependency overrides for a test, tearing them down after."""
    installed: dict = {}

    def _install(task_id: str, events: list[dict], pm_cls: type = _StubProcessManager) -> None:
        installed["persona"] = get_persona_service
        installed["pm"] = get_process_manager
        app.dependency_overrides[get_persona_service] = lambda: _StubPersonaService()
        app.dependency_overrides[get_process_manager] = lambda: pm_cls(task_id, events)

    yield _install

    app.dependency_overrides.pop(get_persona_service, None)
    app.dependency_overrides.pop(get_process_manager, None)


@pytest.mark.asyncio
async def test_chat_stream_emits_start_deltas_done(client, stub_overrides):
    task_id = f"stub-{uuid.uuid4()}"
    stub_overrides(task_id, _token_done_events(task_id))

    async with client.stream(
        "POST",
        "/api/v1/kernel/chat/stream",
        headers=HEADERS,
        json={"message": "hi", "target_agent": "jarvis"},
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] == "done":
                    break

    types = [e["type"] for e in events]
    assert types == ["start", "assistant_delta", "assistant_delta", "done"]
    assert events[0]["task_id"] == task_id
    assert events[0]["persona"] == "jarvis"
    text = "".join(e["text"] for e in events if e["type"] == "assistant_delta")
    assert text == "Hello"


@pytest.mark.asyncio
async def test_chat_stream_expands_delegation_start_done_for_tokenless_child(
    client, stub_overrides
):
    task_id = f"stub-{uuid.uuid4()}"
    stub_overrides(task_id, _delegation_events(task_id))

    async with client.stream(
        "POST",
        "/api/v1/kernel/chat/stream",
        headers=HEADERS,
        json={"message": "delegate this", "target_agent": "jarvis"},
    ) as resp:
        assert resp.status_code == 200
        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] == "done":
                    break

    types = [e["type"] for e in events]
    # parent tool_call is dropped; the childless-token 'done' expands to two frames
    assert types == ["start", "delegation_start", "child_done", "done"]
    assert events[1]["child_id"] == "child-1"
    assert events[1]["persona"] == "scout"
    assert events[2]["child_id"] == "child-1"


@pytest.mark.asyncio
async def test_chat_stream_continues_past_child_error_to_top_level_done(client, stub_overrides):
    """A depth>=1 child error must surface as a non-fatal `child_error` event
    but must NOT end the stream -- the client keeps receiving events (here,
    Jarvis's own tokens) up to the real top-level `done`. Regression test for
    a bug where the endpoint broke the SSE loop on ANY mapped `error`,
    including a delegated child's, cutting the stream off before Jarvis's
    continuation ever reached the client. Also a regression test for the
    mapper itself once mapping errors as `error` regardless of depth, which
    would have painted a successful, recovered turn as fatally failed on the
    frontend.
    """
    task_id = f"stub-{uuid.uuid4()}"
    stub_overrides(task_id, _child_error_then_continues_events(task_id))

    async with client.stream(
        "POST",
        "/api/v1/kernel/chat/stream",
        headers=HEADERS,
        json={"message": "delegate and recover", "target_agent": "jarvis"},
    ) as resp:
        assert resp.status_code == 200
        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] == "done":
                    break

    types = [e["type"] for e in events]
    # parent tool_call dropped; child error surfaces as non-fatal `child_error`
    # but does not truncate the stream; Jarvis's own deltas and final done
    # still arrive after it.
    assert types == ["start", "child_error", "assistant_delta", "assistant_delta", "done"]
    child_error = events[1]
    assert child_error["child_id"] == "child-err-1"
    assert child_error["persona"] == "scout"
    assert child_error["message"] == "litellm.AuthenticationError"
    text = "".join(e["text"] for e in events if e["type"] == "assistant_delta")
    assert text == "Despite the failure"


@pytest.mark.asyncio
async def test_chat_stream_terminates_when_execution_ends_without_top_level_done(
    client, stub_overrides
):
    """Regression test for a silent hang: if the top-level task ends
    (timeout/cancel/crash) WITHOUT the orchestrator ever emitting a depth-0
    `done`, the SSE endpoint must still terminate instead of blocking
    forever on `async for raw in bus.subscribe(...)`.

    Production `ProcessManager._execute_task` now guarantees this by
    publishing a depth-0 `partial_error` terminal event on every failure
    path (timeout, cancellation, generic exception) -- see
    `_publish_terminal_bus_event`. `_StubProcessManagerNoClose` reproduces
    that exact event shape (and, crucially, never calls `bus.close()`
    either, matching production) so this test exercises the real
    consumer-side contract: the endpoint must break out of its loop on the
    terminal event's content alone.

    Consumption is wrapped in `asyncio.wait_for` with a short timeout so
    that if this regresses, the test FAILS on a timeout instead of hanging
    the whole suite.
    """
    task_id = f"stub-{uuid.uuid4()}"
    stub_overrides(
        task_id,
        _tokens_then_no_top_level_done_events(task_id),
        pm_cls=_StubProcessManagerNoClose,
    )

    async def _consume() -> list[dict]:
        events: list[dict] = []
        async with client.stream(
            "POST",
            "/api/v1/kernel/chat/stream",
            headers=HEADERS,
            json={"message": "hi", "target_agent": "jarvis"},
        ) as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
        return events

    events = await asyncio.wait_for(_consume(), timeout=10)

    types = [e["type"] for e in events]
    assert types == ["start", "assistant_delta", "assistant_delta", "error"]
    assert events[-1]["message"] == "RuntimeError: boom"


@pytest.mark.asyncio
async def test_chat_stream_survives_idle_gap_and_emits_heartbeat(client, monkeypatch):
    """Regression test for Regression A: an idle gap longer than the heartbeat
    interval must NOT kill the stream.

    We monkeypatch the heartbeat interval down to 0.05s so the producer's 0.25s
    idle gap spans several heartbeats without a slow test. The stream must (a)
    emit at least one `: heartbeat` comment frame during the gap and (b) still
    deliver the deltas published AFTER the gap plus the top-level done.

    The buggy implementation (asyncio.wait_for, which cancels the __anext__()
    wait on timeout) would unregister the subscriber at the first heartbeat and
    end the stream after only the pre-gap "before" delta -- so this test fails
    before / passes after the fix.
    """
    import life_graph.api.kernel as kernel_mod

    monkeypatch.setattr(kernel_mod, "CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)

    task_id = f"stub-{uuid.uuid4()}"
    app.dependency_overrides[get_persona_service] = lambda: _StubPersonaService()
    app.dependency_overrides[get_process_manager] = lambda: _StubProcessManagerIdleGap(
        task_id, idle_seconds=0.25
    )

    data_events: list[dict] = []
    saw_heartbeat = False

    async def _consume() -> None:
        nonlocal saw_heartbeat
        async with client.stream(
            "POST",
            "/api/v1/kernel/chat/stream",
            headers=HEADERS,
            json={"message": "hi", "target_agent": "jarvis"},
        ) as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_events.append(json.loads(line[6:]))
                    if data_events[-1]["type"] == "done":
                        break
                elif line.startswith(":"):
                    saw_heartbeat = True

    try:
        await asyncio.wait_for(_consume(), timeout=10)
    finally:
        app.dependency_overrides.pop(get_persona_service, None)
        app.dependency_overrides.pop(get_process_manager, None)

    types = [e["type"] for e in data_events]
    assert types == ["start", "assistant_delta", "assistant_delta", "done"]
    text = "".join(e["text"] for e in data_events if e["type"] == "assistant_delta")
    assert text == "before after"  # the post-gap delta survived the idle gap
    assert saw_heartbeat, "expected at least one ': heartbeat' frame during the idle gap"


@pytest.mark.asyncio
async def test_chat_stream_yields_error_frame_when_spawn_fails(client):
    """Persona lookup succeeds (so the response already opened as a 200
    text/event-stream), but pm.spawn() itself then raises. Must surface as a
    clean `error` SSE frame -- not an unhandled exception / broken stream."""
    app.dependency_overrides[get_persona_service] = lambda: _StubPersonaService()
    app.dependency_overrides[get_process_manager] = lambda: _StubProcessManagerSpawnFails(
        "db unavailable"
    )

    try:
        async with client.stream(
            "POST",
            "/api/v1/kernel/chat/stream",
            headers=HEADERS,
            json={"message": "hi", "target_agent": "jarvis"},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            events = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
    finally:
        app.dependency_overrides.pop(get_persona_service, None)
        app.dependency_overrides.pop(get_process_manager, None)

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["message"] == "db unavailable"


@pytest.mark.asyncio
async def test_chat_stream_404_for_unknown_persona(client, stub_overrides):
    task_id = f"stub-{uuid.uuid4()}"
    stub_overrides(task_id, [])

    resp = await client.post(
        "/api/v1/kernel/chat/stream",
        headers=HEADERS,
        json={"message": "hi", "target_agent": "missing-persona"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_stream_422_for_empty_message(client, stub_overrides):
    task_id = f"stub-{uuid.uuid4()}"
    stub_overrides(task_id, [])

    resp = await client.post(
        "/api/v1/kernel/chat/stream",
        headers=HEADERS,
        json={"message": "", "target_agent": "jarvis"},
    )
    assert resp.status_code == 422
