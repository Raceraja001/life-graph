"""What the two chat streams send, pinned before the chat-turn logic moves
out of the route handlers (audit M16, docs/audits/2026-11-19-code-quality-audit.html).

/kernel/chat/stream (the dashboard) and /jarvis/chat (the phone) run the same
turn: the same spawn, the same bus events. This test feeds both one canned
run and checks, frame by frame, what each sends back, and that both asked the
process manager for the same thing. Ids that change every run are replaced by
placeholders. Nothing here may change when the logic moves; a change in what a
client receives is a behaviour change, not a refactor.

No model runs: the process manager is a stub that records the spawn and
publishes the canned events, as in test_chat_history.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"parity_{uuid.uuid4().hex[:8]}"
HEADERS = {"X-Tenant-ID": TENANT}


def _run(task_id: str) -> list[dict]:
    """One turn: a route, tokens, a tool, two delegated children (one fails), done."""

    def ev(event: dict, *, depth: int = 0, child: str | None = None, name: str = "jarvis"):
        return {"task_id": child or task_id, "agent_name": name, "depth": depth, "event": event}

    return [
        ev({"type": "route", "kind": "local", "model": "stub-model"}),
        ev({"type": "token", "content": "Hel"}),
        ev({"type": "tool_call", "name": "clock", "arguments": {}}),
        ev({"type": "tool_result", "name": "clock", "result": "12:00"}),
        ev({"type": "tool_call", "name": "delegate_to_persona"}),
        ev({"type": "token", "content": "child says"}, depth=1, child="child-1", name="scout"),
        ev({"type": "done"}, depth=1, child="child-1", name="scout"),
        ev({"type": "done"}, depth=1, child="child-2", name="analyst"),
        ev({"type": "error", "error": "child broke"}, depth=1, child="child-3", name="coder"),
        ev({"type": "token", "content": "lo"}),
        ev({"type": "done"}),
    ]


class _Persona:
    async def get_by_name(self, tenant_id, name):
        if name == "nobody":
            return None
        return {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "name": name, "is_active": True}


class _PM:
    """Records each spawn and publishes the canned run for it."""

    def __init__(self):
        self.spawns: list[dict] = []

    async def spawn(self, **kw):
        from life_graph.services.chat_stream import get_chat_stream_bus

        self.spawns.append(kw)
        task_id = str(uuid.uuid4())
        bus = get_chat_stream_bus()

        async def publish():
            await asyncio.sleep(0)
            for event in _run(task_id):
                bus.publish(task_id, event)

        asyncio.create_task(publish())
        return {"task_id": task_id}


@pytest.fixture
def pm(monkeypatch):
    from life_graph.api import dependencies, jarvis
    from life_graph.main import app

    stub = _PM()

    async def capture(*a, **k):
        return None

    # /jarvis/chat reads these at call time; /kernel/chat/stream through Depends.
    originals = (dependencies.get_process_manager, dependencies.get_persona_service)
    monkeypatch.setattr(dependencies, "get_process_manager", lambda: stub)
    monkeypatch.setattr(dependencies, "get_persona_service", lambda: _Persona())
    monkeypatch.setattr(jarvis, "_capture", capture)
    app.dependency_overrides[originals[0]] = lambda: stub
    app.dependency_overrides[originals[1]] = lambda: _Persona()
    yield stub
    app.dependency_overrides.pop(originals[0], None)
    app.dependency_overrides.pop(originals[1], None)


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS
    ) as c:
        yield c


async def _frames(client, path: str, body: dict) -> tuple[int, list]:
    """Status and every frame, with this run's ids replaced by placeholders."""
    async with client.stream("POST", path, json=body) as resp:
        if resp.status_code != 200:
            await resp.aread()
            error = resp.json()["error"]
            return resp.status_code, [{"code": error["code"], "message": error["message"]}]
        raw = [line async for line in resp.aiter_lines() if line.startswith("data: ")]
    frames = [json.loads(line[6:]) for line in raw]
    ids: dict[str, str] = {}
    for f in frames:
        for key in ("task_id", "session_id", "conversation_id"):
            value = f.get(key)
            if isinstance(value, str) and value not in ("child-1", "child-2", "child-3"):
                ids.setdefault(value, f"<{key.replace('conversation_id', 'session_id')}>")
    text = json.dumps(frames)
    for value, placeholder in ids.items():
        text = text.replace(value, placeholder)
    return 200, json.loads(text)


def _spawn(kw: dict) -> dict:
    """A spawn with its conversation id replaced, to compare across routes."""
    out = dict(kw)
    assert isinstance(out.pop("session_id"), uuid.UUID)
    return out


# What the dashboard receives for the canned run.
KERNEL_FRAMES = [
    {"type": "start", "task_id": "<task_id>", "persona": "jarvis", "session_id": "<session_id>"},
    {"type": "route", "kind": "local", "model": "stub-model"},
    {"type": "assistant_delta", "text": "Hel"},
    # Arguments go out as JSON text, null included.
    {"type": "tool_call", "name": "clock", "arguments": "{}"},
    {"type": "tool_result", "name": "clock", "result": "12:00"},
    {"type": "tool_call", "name": "delegate_to_persona", "arguments": "null"},
    # A child's first token only opens it: its text is not sent (pinned as it
    # is today; services/chat_stream.py map_bus_event).
    {"type": "delegation_start", "child_id": "child-1", "persona": "scout"},
    {"type": "child_done", "child_id": "child-1", "persona": "scout"},
    {"type": "delegation_start", "child_id": "child-2", "persona": "analyst"},
    {"type": "child_done", "child_id": "child-2", "persona": "analyst"},
    {"type": "child_error", "child_id": "child-3", "persona": "coder", "message": "child broke"},
    {"type": "assistant_delta", "text": "lo"},
    {"type": "done"},
]

# What the phone receives for the same run.
JARVIS_FRAMES = [
    {"type": "token", "content": "Hel"},
    {"type": "token", "content": "lo"},
    {"type": "done", "conversation_id": "<session_id>", "route": "local", "task_id": "<task_id>"},
]


@pytest.mark.asyncio
@skip_on_db_error
async def test_both_streams_send_what_they_sent_before_the_move(pm, client):
    status, kernel = await _frames(
        client,
        "/api/v1/kernel/chat/stream",
        {"message": "hi", "target_agent": "jarvis", "shared": "from a friend"},
    )
    assert status == 200
    assert kernel == KERNEL_FRAMES

    status, phone = await _frames(
        client, "/api/v1/jarvis/chat", {"message": "hi", "shared": "from a friend"}
    )
    assert status == 200
    assert phone == JARVIS_FRAMES

    # The same turn asked for, down to the taint flag on the shared text.
    dashboard, app = (_spawn(s) for s in pm.spawns)
    assert dashboard == app
    assert dashboard["agent_name"] == "jarvis" and dashboard["task_name"] == "chat:jarvis"
    sent = dashboard["input_data"]
    assert sent["owner_message"] == "hi" and sent["shared"] == "from a friend"
    assert sent["history"] == [] and "from a friend" in sent["message"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_later_turn_sends_the_same_history_from_both_routes(pm, client):
    status, _ = await _frames(client, "/api/v1/jarvis/chat", {"message": "one"})
    assert status == 200
    conv = pm.spawns[-1]["session_id"]
    await _finish(pm.spawns[-1], "1")

    await _frames(client, "/api/v1/jarvis/chat", {"message": "two", "conversation_id": str(conv)})
    await _frames(
        client,
        "/api/v1/kernel/chat/stream",
        {"message": "two", "target_agent": "jarvis", "session_id": str(conv)},
    )
    app, dashboard = (_spawn(s) for s in pm.spawns[-2:])
    assert app == dashboard
    assert app["input_data"]["history"] == [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "1"},
    ]


async def _finish(spawn: dict, reply: str) -> None:
    """Write the stubbed turn as the process manager would have: completed, with a reply."""
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        s.add(
            AgentTask(
                tenant_id=spawn["tenant_id"],
                agent_name=spawn["agent_name"],
                task_name=spawn["task_name"],
                session_id=spawn["session_id"],
                status="completed",
                input=spawn["input_data"],
                result={"response": reply},
            )
        )
        await s.commit()


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_refusals_keep_their_codes_and_words(pm, client):
    k = "/api/v1/kernel/chat/stream"
    assert await _frames(client, k, {"message": "hi", "target_agent": "nobody"}) == (
        404,
        [{"code": "NOT_FOUND", "message": "Unknown persona: 'nobody'"}],
    )
    assert await _frames(
        client, k, {"message": "hi", "target_agent": "scout", "temporary": True}
    ) == (400, [{"code": "BAD_REQUEST", "message": "A temporary chat is with Jarvis only."}])

    await _frames(client, "/api/v1/jarvis/chat", {"message": "kept"})
    conv = str(pm.spawns[-1]["session_id"])
    assert await _frames(
        client,
        k,
        {"message": "hi", "target_agent": "jarvis", "session_id": conv, "temporary": True},
    ) == (
        409,
        [
            {
                "code": "CONFLICT",
                "message": "A chat becomes temporary only when it starts: open a new one.",
            }
        ],
    )
    assert pm.spawns[-1]["input_data"]["message"] == "kept"  # the refusals spawned nothing
