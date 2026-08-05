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
    top-level done. The child's error must reach the client as an `error`
    chat event but must NOT terminate the SSE stream.
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

    def _install(task_id: str, events: list[dict]) -> None:
        installed["persona"] = get_persona_service
        installed["pm"] = get_process_manager
        app.dependency_overrides[get_persona_service] = lambda: _StubPersonaService()
        app.dependency_overrides[get_process_manager] = lambda: _StubProcessManager(task_id, events)

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
    """A depth>=1 child error must surface as an `error` event but must NOT
    end the stream -- the client keeps receiving events (here, Jarvis's own
    tokens) up to the real top-level `done`. Regression test for a bug where
    the endpoint broke the SSE loop on ANY mapped `error`, including a
    delegated child's, cutting the stream off before Jarvis's continuation
    ever reached the client.
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
    # parent tool_call dropped; child error surfaces but does not truncate the
    # stream; Jarvis's own deltas and final done still arrive after it.
    assert types == ["start", "error", "assistant_delta", "assistant_delta", "done"]
    text = "".join(e["text"] for e in events if e["type"] == "assistant_delta")
    assert text == "Despite the failure"


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
