"""The phone's S2 endpoints (docs/PLAN-v4.md in life-graph-android) with a real
device token through the real middleware: Plan, Memory, an entity, contacts
and mail waiting answer for the device's tenant whatever headers the phone
sends, and another tenant's rows never show.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"s2_{uuid.uuid4().hex[:8]}"
OTHER = f"other_{TENANT}"
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


def _spoofed(phone: dict) -> dict:
    """The phone naming another tenant in its headers: ignored."""
    return {**phone, "X-Tenant-ID": OTHER, "X-User-ID": "x"}


async def _reminder(text: str, tenant: str, at: datetime) -> uuid.UUID:
    from life_graph.models.db import Intention
    from life_graph.storage.database import async_session

    async with async_session() as s:
        it = Intention(
            tenant_id=tenant, content=text, trigger_type="time", trigger_time=at, status="pending"
        )
        s.add(it)
        await s.commit()
        return it.id


# ── Plan ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_plan_is_the_devices_days_and_reminders_only(client):
    phone = await _phone(client)
    at = datetime.now(UTC) + timedelta(days=1)
    mine = await _reminder("Call the plumber", TENANT, at)
    await _reminder("Someone else's reminder", OTHER, at)

    resp = await client.get("/api/v1/jarvis/plan?days=7", headers=_spoofed(phone))
    assert resp.status_code == 200
    days = resp.json()["data"]["days"]
    assert len(days) == 7
    for d in days:
        assert set(d) == {"date", "events", "due", "reminders", "tasks"}
    reminders = [r for d in days for r in d["reminders"]]
    assert [r["id"] for r in reminders] == [str(mine)]
    assert set(reminders[0]) == {"id", "text", "at"}
    # Nothing connected for this tenant: empty, not an error.
    assert all(d["events"] == [] and d["due"] == [] and d["tasks"] == [] for d in days)


@pytest.mark.asyncio
@skip_on_db_error
async def test_plan_days_out_of_range_is_refused(client):
    phone = await _phone(client)
    assert (await client.get("/api/v1/jarvis/plan?days=0", headers=phone)).status_code == 422
    assert (await client.get("/api/v1/jarvis/plan?days=32", headers=phone)).status_code == 422
    resp = await client.get("/api/v1/jarvis/plan", headers=phone)
    assert resp.status_code == 200 and len(resp.json()["data"]["days"]) == 7


@pytest.mark.asyncio
@skip_on_db_error
async def test_s2_endpoints_need_a_device_token(client):
    for path in (
        "/api/v1/jarvis/plan",
        "/api/v1/jarvis/memory/overview",
        "/api/v1/jarvis/memory/search?q=x",
        f"/api/v1/jarvis/entities/{uuid.uuid4()}",
        "/api/v1/jarvis/contacts?q=x",
        "/api/v1/jarvis/mail/waiting",
    ):
        assert (await client.get(path)).status_code == 401, path
        bad = {"Authorization": "Bearer not-a-device-token"}
        assert (await client.get(path, headers=bad)).status_code == 401, path


async def _memory(content: str, tenant: str, **fields) -> uuid.UUID:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{tenant}{content}{uuid.uuid4()}".encode()).hexdigest(),
            status=fields.pop("status", "active"),
            trust_tier="self",
            source_type=fields.pop("source_type", "capture"),
            properties=fields.pop("properties", {"surface": "jarvis_app"}),
            **fields,
        )
        s.add(m)
        await s.commit()
        return m.id


async def _entity(name: str, tenant: str, memory_ids: list[uuid.UUID]) -> uuid.UUID:
    from life_graph.models.assistant import Entity, MemoryEntity
    from life_graph.services.entities import normalize
    from life_graph.storage.database import async_session

    async with async_session() as s:
        e = Entity(tenant_id=tenant, key=normalize(name), name=name, mentions=len(memory_ids))
        s.add(e)
        await s.flush()
        for mid in memory_ids:
            s.add(MemoryEntity(memory_id=mid, entity_id=e.id, tenant_id=tenant))
        await s.commit()
        return e.id


# ── Memory ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_memory_overview_is_the_devices_tenant_only(client):
    phone = await _phone(client)
    fact = await _memory("I moved to Chennai.", TENANT)
    rule = await _memory(
        "Always write local HTML files.",
        TENANT,
        source_type="explicit",
        tags=["explicit_save"],
        properties={"saved_by": "jarvis"},
    )
    day = await _memory(
        "Conversations with Jarvis on Saturday 24 October 2026: Planned the school app.",
        TENANT,
        source_type="episode",
        properties={"kind": "episode", "source": "jarvis", "date": "2026-10-24"},
    )
    await _memory("Waiting for review.", TENANT, status="pending")
    await _memory("Someone else's fact.", OTHER)
    await _memory("Never share this.", OTHER, source_type="explicit", tags=["explicit_save"])
    await _entity("Murugan", TENANT, [fact])

    resp = await client.get("/api/v1/jarvis/memory/overview", headers=_spoofed(phone))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert {"counts", "people", "projects", "rules", "recent", "days"} <= set(data)
    assert data["counts"]["total"] == 3 and data["counts"]["to_review"] == 1
    assert data["counts"]["rules"] == 1 and data["counts"]["facts"] == 1
    assert [r["id"] for r in data["rules"]] == [str(rule)]
    assert {r["id"]: r["kind"] for r in data["recent"]} == {str(fact): "fact", str(rule): "rule"}
    assert data["days"] == [
        {
            "id": str(day),
            "date": "2026-10-24",
            "source": "Jarvis",
            "summary": "Planned the school app.",
        }
    ]
    # No contact or project names Murugan for this tenant: a thing, not a person.
    assert data["people"] == [] and [t["name"] for t in data["things"]] == ["Murugan"]
    assert "Someone else" not in resp.text and "Never share" not in resp.text


@pytest.mark.asyncio
@skip_on_db_error
async def test_entity_is_the_devices_own(client):
    phone = await _phone(client)
    mine = await _memory("Murugan fixed the pump.", TENANT)
    other_memory = await _memory("Murugan is someone else's.", OTHER)
    ent = await _entity("Murugan", TENANT, [mine])
    theirs = await _entity("Murugan", OTHER, [other_memory])

    resp = await client.get(f"/api/v1/jarvis/entities/{ent}", headers=_spoofed(phone))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert set(data) == {"id", "name", "also_called", "mentions", "memories", "related", "days"}
    assert data["name"] == "Murugan" and [m["id"] for m in data["memories"]] == [str(mine)]
    # Another tenant's entity id is not found, nor is a malformed one.
    assert (await client.get(f"/api/v1/jarvis/entities/{theirs}", headers=phone)).status_code == 404
    assert (await client.get("/api/v1/jarvis/entities/nope", headers=phone)).status_code == 404


@pytest.mark.asyncio
@skip_on_db_error
async def test_memory_search_blank_is_empty_and_limit_is_bounded(client):
    phone = await _phone(client)
    resp = await client.get("/api/v1/jarvis/memory/search?q=", headers=phone)
    assert resp.status_code == 200 and resp.json()["data"] == []
    resp = await client.get("/api/v1/jarvis/memory/search?q=x&limit=500", headers=phone)
    assert resp.status_code == 422


@pytest.mark.asyncio
@skip_on_db_error
async def test_memory_search_finds_only_the_devices_active_memories(client):
    phone = await _phone(client)
    word = f"zebrafish{uuid.uuid4().hex[:6]}"
    mine = await _memory(f"My {word} is called Nemo.", TENANT)
    await _memory(f"My {word} waits for review.", TENANT, status="pending")
    await _memory(f"Their {word} is called Dory.", OTHER)
    resp = await client.get(f"/api/v1/jarvis/memory/search?q={word}", headers=_spoofed(phone))
    if resp.status_code == 503:
        pytest.skip("no embedding service")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert [r["id"] for r in rows] == [str(mine)]
    assert set(rows[0]) == {"id", "content", "kind", "source", "created_at", "score"}
