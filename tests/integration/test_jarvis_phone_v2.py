"""The phone app's v2 endpoints, with a real device token through the real
middleware: review memories, undo what Jarvis saved, read an image's words
without storing it, notifications, and the "saved" chat event.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"phone2_{uuid.uuid4().hex[:8]}"
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


async def _phone(client) -> dict:
    code = (await client.post("/api/v1/devices/codes", headers=OWNER)).json()["data"]["code"]
    resp = await client.post("/api/v1/devices/pair", json={"code": code, "name": "Pixel"})
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


async def _seed(content, *, tenant=TENANT, status="pending", props=None, age_min=0):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{tenant}{content}{uuid.uuid4()}".encode()).hexdigest(),
            status=status,
            trust_tier="self",
            source_type="capture",
            properties=props or {},
        )
        m.created_at = datetime.now(UTC) - timedelta(minutes=age_min)
        s.add(m)
        await s.commit()
        return m.id


async def _status(mid):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return (await s.get(Memory, mid)).status


@pytest.mark.asyncio
@skip_on_db_error
async def test_reviewing_memories_from_the_phone(client):
    phone = await _phone(client)
    older = await _seed("I prefer tea.", props={"surface": "cli"}, age_min=60)
    newer = await _seed("I moved to Chennai.", props={"surface": "jarvis_app"})
    theirs = await _seed("Someone else's.", tenant="other_" + TENANT)

    data = (await client.get("/api/v1/jarvis/memories/pending", headers=phone)).json()["data"]
    assert data["total"] == 2
    assert [(m["content"], m["source"]) for m in data["memories"]] == [
        ("I moved to Chennai.", "Jarvis"),
        ("I prefer tea.", "Claude Code"),
    ]

    ok = await client.post(f"/api/v1/jarvis/memories/{newer}/approve", headers=phone)
    assert ok.json()["data"] == {"id": str(newer), "status": "active"}
    no = await client.post(f"/api/v1/jarvis/memories/{older}/reject", headers=phone)
    assert no.json()["data"] == {"id": str(older), "status": "rejected"}
    assert (await _status(newer), await _status(older)) == ("active", "rejected")

    gone = await client.post(f"/api/v1/jarvis/memories/{theirs}/approve", headers=phone)
    assert gone.status_code == 404 and await _status(theirs) == "pending"


@pytest.mark.asyncio
@skip_on_db_error
async def test_undo_takes_back_only_what_jarvis_saved(client):
    phone = await _phone(client)
    saved = await _seed("My locker is 82.", status="active", props={"saved_by": "jarvis"})
    learnt = await _seed("I like tea.", status="active")

    ok = await client.post(f"/api/v1/jarvis/memories/{saved}/undo", headers=phone)
    assert ok.json()["data"] == {"id": str(saved), "status": "archived"}
    assert await _status(saved) == "archived"  # archived, never deleted
    again = await client.post(f"/api/v1/jarvis/memories/{saved}/undo", headers=phone)
    assert again.status_code == 404
    other = await client.post(f"/api/v1/jarvis/memories/{learnt}/undo", headers=phone)
    assert other.status_code == 404 and await _status(learnt) == "active"


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_image_is_read_on_the_pc_and_not_stored(client, monkeypatch):
    from life_graph.services.multimodal import MultiModalService

    phone = await _phone(client)
    monkeypatch.setattr(
        MultiModalService, "_ocr_image", staticmethod(lambda data: " Fees due Friday \n")
    )
    png = {"image": ("shot.png", b"\x89PNG" + b"\x00" * 100, "image/png")}
    resp = await client.post("/api/v1/jarvis/read-image", headers=phone, files=png)
    assert resp.status_code == 200 and resp.json()["data"] == {"text": "Fees due Friday"}

    gif = {"image": ("a.gif", b"GIF89a", "image/gif")}
    wrong = await client.post("/api/v1/jarvis/read-image", headers=phone, files=gif)
    assert wrong.status_code == 415
    monkeypatch.setattr(MultiModalService, "_ocr_image", staticmethod(lambda data: "  "))
    blank = await client.post("/api/v1/jarvis/read-image", headers=phone, files=png)
    assert blank.status_code == 422 and "No words" in blank.text


@pytest.mark.asyncio
@skip_on_db_error
async def test_notifications_newer_than_the_last_seen(client):
    from life_graph.models.db import Notification
    from life_graph.storage.database import async_session

    phone = await _phone(client)
    now = datetime.now(UTC)
    async with async_session() as s:
        for title, prio, mins in (
            ("Old", "info", 30),
            ("Brief", "info", 10),
            ("Alert", "important", 5),
        ):
            n = Notification(tenant_id=TENANT, title=title, body=f"{title} body", priority=prio)
            n.created_at = now - timedelta(minutes=mins)
            s.add(n)
        s.add(Notification(tenant_id="other_" + TENANT, title="Not yours", priority="info"))
        await s.commit()

    after = (now - timedelta(minutes=20)).isoformat()
    resp = await client.get("/api/v1/jarvis/notifications", headers=phone, params={"after": after})
    assert [(n["title"], n["priority"]) for n in resp.json()["data"]] == [
        ("Brief", "info"),
        ("Alert", "important"),
    ]
    every = (await client.get("/api/v1/jarvis/notifications", headers=phone)).json()["data"]
    assert [n["title"] for n in every] == ["Old", "Brief", "Alert"]
    bad = await client.get("/api/v1/jarvis/notifications", headers=phone, params={"after": "soon"})
    assert bad.status_code == 400


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_voice_reply_lists_what_was_saved_in_that_run():
    from life_graph.api.jarvis import _saved_in

    run = uuid.uuid4()
    props = {"saved_by": "jarvis", "task_id": str(run)}
    await _seed("My locker is 82.", status="active", props=props)
    elsewhere = {"saved_by": "jarvis", "task_id": str(uuid.uuid4())}
    await _seed("Unrelated.", status="active", props=elsewhere)
    saved = await _saved_in(TENANT, run)
    assert [(s["content"], s["pending"]) for s in saved] == [("My locker is 82.", False)]
    assert await _saved_in("other_" + TENANT, run) == []


def test_a_save_reaches_the_app_as_a_saved_event():
    from life_graph.api.jarvis import _app_event

    def event(result):
        return _app_event({"type": "tool_result", "name": "memory_save", "result": result}, {})

    assert event('{"saved": true, "id": "m1", "content": "My locker is 82."}') == {
        "type": "saved",
        "id": "m1",
        "content": "My locker is 82.",
        "pending": False,
    }
    assert event('{"saved": true, "id": "m2", "content": "X", "status": "waiting"}')["pending"]
    for result in ('{"saved": false, "already_remembered": "X"}', '{"error": "no"}', "not json"):
        assert event(result) is None
    other = {"type": "tool_result", "name": "bills_due", "result": '{"saved": true, "id": "x"}'}
    assert _app_event(other, {}) is None
