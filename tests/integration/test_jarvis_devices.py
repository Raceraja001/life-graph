"""The phone app's API against the database and the real middleware:
pairing, device tokens (scoped to Jarvis, tenant from the device, revocable),
the conversation endpoints, and voice transcribed locally only.

A service key is configured for these tests so authentication runs as in
production (the integration suite otherwise runs with auth off).
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"phone_{uuid.uuid4().hex[:8]}"
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


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _pair(client) -> tuple[str, str]:
    code = (await client.post("/api/v1/devices/codes", headers=OWNER)).json()["data"]["code"]
    assert len(code) == 6 and code.isdigit()
    resp = await client.post("/api/v1/devices/pair", json={"code": code, "name": "Pixel"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    return data["device_id"], data["token"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_pairing_and_what_a_device_token_opens(client):
    device_id, token = await _pair(client)
    phone = {"Authorization": f"Bearer {token}"}

    # The tenant comes from the device, not from headers: none sent, a wrong one ignored.
    assert (await client.get("/api/v1/jarvis/conversations", headers=phone)).status_code == 200
    other = {**phone, "X-Tenant-ID": "someone-else"}
    assert (await client.get("/api/v1/jarvis/conversations", headers=other)).json()["data"] == []

    # Nothing outside /jarvis/ accepts it.
    for path in ("/api/v1/devices", "/api/v1/admin/stats", "/api/v1/memories"):
        assert (await client.get(path, headers=phone)).status_code == 401, path

    # Only the hash is stored.
    from life_graph.models.assistant import Device
    from life_graph.services.devices import hash_token
    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = await s.get(Device, uuid.UUID(device_id))
    assert row.token_hash == hash_token(token) and token not in row.token_hash

    listed = (await client.get("/api/v1/devices", headers=OWNER)).json()["data"]
    assert [d["name"] for d in listed] == ["Pixel"] and "token" not in listed[0]

    assert (await client.delete(f"/api/v1/devices/{device_id}", headers=OWNER)).status_code == 200
    assert (await client.get("/api/v1/jarvis/conversations", headers=phone)).status_code == 401


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_code_works_once_and_guessing_is_capped(client):
    code = (await client.post("/api/v1/devices/codes", headers=OWNER)).json()["data"]["code"]
    assert (await client.post("/api/v1/devices/pair", json={"code": code})).status_code == 200
    again = await client.post("/api/v1/devices/pair", json={"code": code})
    assert again.status_code == 400 and "not valid" in again.json()["detail"]

    statuses = [
        (await client.post("/api/v1/devices/pair", json={"code": f"{n:06d}"})).status_code
        for n in range(7)
    ]
    # One failure above, four more allowed, then refused before any lookup.
    assert statuses[:4] == [400] * 4 and statuses[4:] == [429] * 3


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_token_unused_for_too_long_stops_working(client):
    """Review 2026-10-24 (M5): device_token_idle_days since last_seen_at."""
    from datetime import UTC, datetime, timedelta

    from life_graph.models.assistant import Device
    from life_graph.services import devices
    from life_graph.storage.database import async_session

    device_id, token = await _pair(client)
    phone = {"Authorization": f"Bearer {token}"}
    async with async_session() as s:
        row = await s.get(Device, uuid.UUID(device_id))
        row.last_seen_at = datetime.now(UTC) - timedelta(days=61)
        await s.commit()
    devices._cache.clear()
    assert (await client.get("/api/v1/jarvis/conversations", headers=phone)).status_code == 401


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_new_code_retires_the_earlier_unused_one(client):
    """Review 2026-10-24 (M1): only the code on screen pairs."""
    first = (await client.post("/api/v1/devices/codes", headers=OWNER)).json()["data"]["code"]
    second = (await client.post("/api/v1/devices/codes", headers=OWNER)).json()["data"]["code"]
    if first == second:  # one in a million: the new code reused the number
        pytest.skip("the two codes collided")
    old = await client.post("/api/v1/devices/pair", json={"code": first})
    assert old.status_code == 400
    assert (await client.post("/api/v1/devices/pair", json={"code": second})).status_code == 200


@pytest.mark.asyncio
@skip_on_db_error
async def test_conversations_and_messages_are_the_devices_own(client):
    from life_graph.models.db import AgentSession, AgentTask
    from life_graph.storage.database import async_session

    _, token = await _pair(client)
    phone = {"Authorization": f"Bearer {token}"}
    async with async_session() as s:
        mine = AgentSession(
            tenant_id=TENANT, user_message="When is my  dentist?", routed_to="jarvis"
        )
        theirs = AgentSession(tenant_id="other", user_message="x", routed_to="jarvis")
        s.add_all([mine, theirs])
        await s.flush()
        s.add(
            AgentTask(
                tenant_id=TENANT,
                agent_name="jarvis",
                task_name="chat:jarvis",
                session_id=mine.id,
                status="completed",
                input={"message": "When is my dentist?"},
                result={"response": "Thursday at 10."},
            )
        )
        await s.commit()
        mine_id, theirs_id = str(mine.id), str(theirs.id)

    convs = (await client.get("/api/v1/jarvis/conversations", headers=phone)).json()["data"]
    assert [(c["id"], c["title"]) for c in convs] == [(mine_id, "When is my dentist?")]
    msgs = (
        await client.get(f"/api/v1/jarvis/conversations/{mine_id}/messages", headers=phone)
    ).json()["data"]
    assert [(m["role"], m["content"]) for m in msgs] == [
        ("user", "When is my dentist?"),
        ("assistant", "Thursday at 10."),
    ]
    foreign = await client.get(f"/api/v1/jarvis/conversations/{theirs_id}/messages", headers=phone)
    assert foreign.status_code == 404
    chat = await client.post(
        "/api/v1/jarvis/chat", headers=phone, json={"message": "hi", "conversation_id": theirs_id}
    )
    assert chat.status_code == 404


@pytest.mark.asyncio
@skip_on_db_error
async def test_voice_is_transcribed_locally_and_spoken_back(client, monkeypatch):
    from life_graph.api import jarvis, multimodal
    from life_graph.services import assistant_chat

    _, token = await _pair(client)
    seen = {}

    class FakeStt:
        async def transcribe_only(self, data, filename, *, local_only=False):
            seen.update(local_only=local_only, size=len(data), filename=filename)
            return {"transcript": "what bills are due"}

    async def fake_answer(tenant_id, question, conversation_id, **kw):
        seen.update(tenant=tenant_id, question=question)
        return {"reply": "None this week.", "conversation_id": "c1", "route": "personal"}

    async def fake_speak(text, client=None):
        return b"ID3mp3"

    monkeypatch.setattr(multimodal, "_get_multimodal_service", lambda: FakeStt())
    monkeypatch.setattr(jarvis, "_answer", fake_answer)
    monkeypatch.setattr(assistant_chat, "speak", fake_speak)

    resp = await client.post(
        "/api/v1/jarvis/voice",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio": ("clip.m4a", b"\x00" * 1000, "audio/mp4")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert seen["local_only"] is True  # never a cloud speech service
    assert seen["tenant"] == TENANT and seen["question"] == "what bills are due"
    assert data["heard"] == "what bills are due" and data["reply"] == "None this week."
    assert data["route"] == "personal" and data["audio_base64"] == "SUQzbXAz"


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_app_can_warm_the_local_model(client, monkeypatch):
    from life_graph.services import local_runtime

    _, token = await _pair(client)
    warmed = []

    async def fake_warm(chat_model, embedding_model):
        warmed.append((chat_model, embedding_model))

    monkeypatch.setattr(local_runtime, "warm", fake_warm)
    resp = await client.post("/api/v1/jarvis/warm", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 202 and resp.json()["data"] == {"warming": True}
    import asyncio

    await asyncio.sleep(0)  # let the background task run
    assert len(warmed) == 1


def test_chat_events_in_the_apps_shape():
    from life_graph.api.jarvis import _app_event

    state: dict = {}
    assert _app_event({"type": "start", "session_id": "s1"}, state) is None
    assert _app_event({"type": "route", "kind": "personal"}, state) is None
    assert _app_event({"type": "assistant_delta", "text": "Hi"}, state) == {
        "type": "token",
        "content": "Hi",
    }
    assert _app_event({"type": "tool_call", "name": "bills_due"}, state) is None
    assert _app_event({"type": "done"}, state) == {
        "type": "done",
        "conversation_id": "s1",
        "route": "personal",
    }
    assert _app_event({"type": "error", "message": "boom"}, {}) == {
        "type": "error",
        "message": "boom",
    }
