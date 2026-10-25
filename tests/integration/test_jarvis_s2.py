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
