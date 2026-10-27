"""Temporary chat (docs/specs/web-chat-wave1.md F5) against the database: nothing
captured, the flag kept by the conversation, never listed or summarised, refused
mid-conversation, and purged a day after its last message.

No model runs: the process manager is a stub that records what it was asked to
run and ends the stream, as in test_chat_stream_endpoint.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"temp_{uuid.uuid4().hex[:8]}"
HEADERS = {"X-Tenant-ID": TENANT}


class _Persona:
    async def get_by_name(self, tenant_id, name):
        return {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "name": name, "is_active": True}


class _PM:
    """Records each spawn's input and ends its stream at once."""

    def __init__(self):
        self.inputs: list[dict] = []

    async def spawn(self, **kw):
        from life_graph.services.chat_stream import get_chat_stream_bus

        self.inputs.append(kw["input_data"])
        task_id = str(uuid.uuid4())
        bus = get_chat_stream_bus()

        async def publish():
            await asyncio.sleep(0)
            bus.publish(
                task_id,
                {"task_id": task_id, "agent_name": "jarvis", "depth": 0, "event": {"type": "done"}},
            )

        asyncio.create_task(publish())
        return {"task_id": task_id}


@pytest.fixture
def pm(monkeypatch):
    from life_graph.api import dependencies, jarvis

    stub = _PM()
    captured: list[str] = []

    async def capture(tenant_id, text, *a, **k):
        captured.append(text)

    monkeypatch.setattr(dependencies, "get_process_manager", lambda: stub)
    monkeypatch.setattr(dependencies, "get_persona_service", lambda: _Persona())
    monkeypatch.setattr(jarvis, "_capture", capture)
    stub.captured = captured
    return stub


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS
    ) as c:
        yield c


def _start_id(body: str) -> str | None:
    for frame in body.split("\n\n"):
        if frame.startswith("data: "):
            event = json.loads(frame[6:])
            for key in ("conversation_id", "session_id"):
                if event.get(key):
                    return event[key]
    return None


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_temporary_chat_captures_nothing_and_keeps_its_flag(pm, client):
    r = await client.post(
        "/api/v1/jarvis/chat", json={"message": "what is my locker code?", "temporary": True}
    )
    assert r.status_code == 200
    conv = _start_id(r.text)
    assert conv and pm.captured == []
    assert pm.inputs[-1]["temporary"] is True

    # The next turn need not say so again; it still captures nothing.
    r = await client.post(
        "/api/v1/jarvis/chat", json={"message": "and the bike's?", "conversation_id": conv}
    )
    assert r.status_code == 200 and pm.inputs[-1]["temporary"] is True and pm.captured == []

    listed = (await client.get("/api/v1/jarvis/conversations")).json()["data"]
    assert conv not in [c["id"] for c in listed]

    # A normal chat is captured and listed as before.
    r = await client.post("/api/v1/jarvis/chat", json={"message": "hello"})
    normal = _start_id(r.text)
    assert pm.captured == ["hello"] and "temporary" not in pm.inputs[-1]
    assert normal in [
        c["id"] for c in (await client.get("/api/v1/jarvis/conversations")).json()["data"]
    ]

    # Temporary cannot start halfway through a kept chat.
    before = len(pm.captured)
    r = await client.post(
        "/api/v1/jarvis/chat",
        json={"message": "secret", "conversation_id": normal, "temporary": True},
    )
    assert r.status_code == 409 and len(pm.captured) == before


@pytest.mark.asyncio
@skip_on_db_error
async def test_temporary_turns_are_never_summarised_and_are_purged_after_a_day():
    from sqlalchemy import select

    from life_graph.models.db import AgentSession, AgentTask
    from life_graph.services import episodes, temporary_chats
    from life_graph.storage.database import async_session

    tenant = f"{TENANT}_purge"
    now = datetime.now(UTC)
    yesterday = now - timedelta(hours=25)

    async def chat(temporary: bool, at: datetime, text: str) -> uuid.UUID:
        async with async_session() as s:
            conv = AgentSession(
                tenant_id=tenant,
                user_message=text,
                routed_to="jarvis",
                context={"temporary": True} if temporary else {},
            )
            s.add(conv)
            await s.flush()
            turn = AgentTask(
                tenant_id=tenant,
                agent_name="jarvis",
                task_name="chat:jarvis",
                session_id=conv.id,
                status="completed",
                input={
                    "message": text,
                    "history": [],
                    **({"temporary": True} if temporary else {}),
                },
                result={"response": "ok"},
            )
            turn.created_at = at
            s.add(turn)
            await s.commit()
            return conv.id

    old_temp = await chat(True, yesterday, "old secret")
    new_temp = await chat(True, now, "new secret")
    old_kept = await chat(False, yesterday, "old kept")

    asked, _ = await episodes._jarvis_turns(tenant, yesterday.astimezone(episodes._tz()).date())
    assert any("old kept" in a for a in asked) and not any("secret" in a for a in asked)

    out = await temporary_chats.purge(async_session, now=now)
    assert out["chats"] >= 1
    async with async_session() as s:
        left = set(
            (
                await s.execute(select(AgentSession.id).where(AgentSession.tenant_id == tenant))
            ).scalars()
        )
        turns = (
            (await s.execute(select(AgentTask.input).where(AgentTask.tenant_id == tenant)))
            .scalars()
            .all()
        )
    assert old_temp not in left and {new_temp, old_kept} <= left
    assert not any(t.get("message") == "old secret" for t in turns)
