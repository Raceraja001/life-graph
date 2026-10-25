"""Idempotent phone sends, with a real device token through the real middleware:
a message resent under the same client_id is answered from the turn it already
started, never spawned or captured again (api/jarvis.py, client_id).

No model runs here: every turn is seeded as an agent_tasks row.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from tests.integration.conftest import skip_on_db_error

TENANT = f"idem_{uuid.uuid4().hex[:8]}"
KEY = "svc-test-key"
OWNER = {"Authorization": f"Bearer {KEY}", "X-Tenant-ID": TENANT}


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    from life_graph.config import settings
    from life_graph.services import devices

    monkeypatch.setattr(settings, "service_api_keys", KEY)
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(devices, "pairing_limiter", devices.PairingLimiter())
    devices._cache.clear()


@pytest.fixture(autouse=True)
def _nothing_new_starts(monkeypatch):
    """A replay must not capture, transcribe or start a turn: each one fails the test."""
    from life_graph.api import jarvis

    async def refuse(*_a, **_k):
        raise AssertionError("a resent message started something new")

    monkeypatch.setattr(jarvis, "_capture", refuse)
    monkeypatch.setattr(jarvis, "_start_chat", refuse)
    monkeypatch.setattr(jarvis, "_transcribe", refuse)
    monkeypatch.setattr(jarvis, "_answer", refuse)


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _phone(client) -> dict:
    code = (await client.post("/api/v1/devices/codes", headers=OWNER)).json()["data"]["code"]
    resp = await client.post("/api/v1/devices/pair", json={"code": code, "name": "Pixel"})
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


def _cid() -> str:
    return f"msg_{uuid.uuid4().hex[:16]}"


async def _turn(client_id, *, tenant=TENANT, status="completed", age=timedelta(0), parent=None):
    """One Jarvis turn sent under *client_id*, in a conversation of its own."""
    from life_graph.models.db import AgentSession, AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        conv = AgentSession(tenant_id=tenant, user_message="how hot is it?", routed_to="jarvis")
        s.add(conv)
        await s.flush()
        task = AgentTask(
            tenant_id=tenant,
            agent_name="jarvis",
            task_name="chat:jarvis",
            session_id=conv.id,
            parent_task_id=parent,
            status=status,
            input={"message": "how hot is it?", "history": [], "client_id": client_id},
            result=(
                {"response": "It is 31 degrees.", "route": {"kind": "personal"}}
                if status == "completed"
                else {}
            ),
        )
        task.created_at = datetime.now(UTC) - age
        s.add(task)
        await s.commit()
        return task.id, conv.id


async def _count_turns(client_id) -> int:
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.scalar(
            select(func.count())
            .select_from(AgentTask)
            .where(AgentTask.tenant_id == TENANT, AgentTask.input["client_id"].astext == client_id)
        )


def _events(body: str) -> list:
    return [json.loads(f[6:]) for f in body.split("\n\n") if f.startswith("data: ")]


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_resent_chat_message_is_replayed_with_what_it_saved_and_set(client):
    from life_graph.models.db import Memory
    from life_graph.services import reminders
    from life_graph.storage.database import async_session

    phone = await _phone(client)
    cid = _cid()
    task_id, conv_id = await _turn(cid)
    when = datetime.now(UTC) + timedelta(days=1)
    async with async_session() as s:
        s.add(
            Memory(
                content="I like filter coffee.",
                tenant_id=TENANT,
                content_hash=hashlib.sha256(f"{TENANT}{uuid.uuid4()}".encode()).hexdigest(),
                status="active",
                trust_tier="self",
                source_type="capture",
                properties={"saved_by": "jarvis", "task_id": str(task_id)},
            )
        )
        reminder = await reminders.create(s, TENANT, "Pay TNEB", when, task_id=str(task_id))
        await s.commit()

    resp = await client.post(
        "/api/v1/jarvis/chat", headers=phone, json={"message": "how hot is it?", "client_id": cid}
    )
    assert resp.status_code == 200
    events = _events(resp.text)
    assert [e["type"] for e in events] == ["saved", "reminded", "token", "done"]
    assert events[0]["content"] == "I like filter coffee." and events[0]["pending"] is False
    assert events[1]["id"] == str(reminder.id) and events[1]["text"] == "Pay TNEB"
    assert events[2] == {"type": "token", "content": "It is 31 degrees."}
    assert events[3] == {"type": "done", "conversation_id": str(conv_id), "route": "personal"}
    assert await _count_turns(cid) == 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_resent_running_chat_message_is_waited_for(client, monkeypatch):
    from life_graph.api import dependencies, jarvis
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    phone = await _phone(client)
    cid = _cid()
    task_id, conv_id = await _turn(cid, status="running")

    async def get_task(tenant_id, tid):
        async with async_session() as s:
            row = await s.get(AgentTask, uuid.UUID(tid))
        return row if row is not None and row.tenant_id == tenant_id else None

    monkeypatch.setattr(
        dependencies, "get_process_manager", lambda: SimpleNamespace(get_task=get_task)
    )
    monkeypatch.setattr(jarvis, "_POLL_SECONDS", 0.05)

    async def finish():
        await asyncio.sleep(0.3)
        async with async_session() as s:
            row = await s.get(AgentTask, task_id)
            row.status = "completed"
            row.result = {"response": "Done now.", "route": {"kind": "general"}}
            await s.commit()

    finisher = asyncio.create_task(finish())
    resp = await client.post(
        "/api/v1/jarvis/chat", headers=phone, json={"message": "how hot is it?", "client_id": cid}
    )
    await finisher
    events = _events(resp.text)
    assert events[-2:] == [
        {"type": "token", "content": "Done now."},
        {"type": "done", "conversation_id": str(conv_id), "route": "general"},
    ]
    assert await _count_turns(cid) == 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_resent_voice_message_returns_the_stored_reply(client, monkeypatch):
    from life_graph.services import assistant_chat

    monkeypatch.setattr(assistant_chat, "speak", _fake_speak)
    phone = await _phone(client)
    cid = _cid()
    _, conv_id = await _turn(cid)
    resp = await client.post(
        "/api/v1/jarvis/voice",
        headers=phone,
        files={"audio": ("voice.m4a", b"not really audio", "audio/mp4")},
        data={"client_id": cid},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["heard"] == "how hot is it?" and data["reply"] == "It is 31 degrees."
    assert data["conversation_id"] == str(conv_id) and data["route"] == "personal"
    assert data["audio_base64"] == "bXAz"
    assert await _count_turns(cid) == 1


async def _fake_speak(text):
    return b"mp3"


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_bad_client_id_is_a_422(client):
    phone = await _phone(client)
    for bad in ("short", "x" * 65, "has space!"):
        chat = await client.post(
            "/api/v1/jarvis/chat", headers=phone, json={"message": "hi", "client_id": bad}
        )
        assert chat.status_code == 422, bad
        voice = await client.post(
            "/api/v1/jarvis/voice",
            headers=phone,
            files={"audio": ("voice.m4a", b"x", "audio/mp4")},
            data={"client_id": bad},
        )
        assert voice.status_code == 422, bad


@pytest.mark.asyncio
@skip_on_db_error
async def test_only_this_tenants_recent_top_level_turn_matches():
    from life_graph.api.jarvis import _turn_for

    cid = _cid()
    await _turn(cid, tenant="other_" + TENANT)
    await _turn(cid, age=timedelta(hours=25))
    assert await _turn_for(TENANT, cid) is None
    parent, _ = await _turn(_cid())
    await _turn(cid, parent=parent)  # a retry child is not the phone's turn
    assert await _turn_for(TENANT, cid) is None
    mine, _ = await _turn(cid, status="failed")
    newer, _ = await _turn(cid, status="running")
    found = await _turn_for(TENANT, cid)
    assert found is not None and found.id == newer and found.id != mine
