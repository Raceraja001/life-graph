"""GET /jarvis/today and POST /jarvis/bills/{id}/paid with a real device token
through the real middleware (docs/PLAN-v4.md S1 in life-graph-android): the
screen answers for the device's tenant whatever headers the phone sends, and
another tenant's rows never show.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"today_{uuid.uuid4().hex[:8]}"
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


async def _memory(content: str, tenant: str) -> uuid.UUID:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{tenant}{content}{uuid.uuid4()}".encode()).hexdigest(),
            status="pending",
            trust_tier="self",
            source_type="capture",
            properties={"surface": "jarvis_app"},
        )
        s.add(m)
        await s.commit()
        return m.id


async def _approval(tenant: str) -> None:
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as s:
        s.add(Approval(tenant_id=tenant, kind="merge", title="Merge two", source="test"))
        await s.commit()


@pytest.mark.asyncio
@skip_on_db_error
async def test_today_is_the_devices_tenant_only(client):
    phone = await _phone(client)
    mine = await _memory("I moved to Chennai.", TENANT)
    await _memory("Someone else's fact.", OTHER)
    await _approval(TENANT)
    await _approval(OTHER)
    await _approval(OTHER)

    # The phone names another tenant in its headers: ignored, the device's tenant answers.
    resp = await client.get(
        "/api/v1/jarvis/today", headers={**phone, "X-Tenant-ID": OTHER, "X-User-ID": "x"}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert set(data) == {
        "counts",
        "insights",
        "next_event",
        "brief",
        "schedule",
        "due",
        "money",
        "mail_waiting",
        "work",
        "study_due",
        "learnt",
    }
    assert data["counts"]["to_review"] == 1
    assert data["counts"]["approvals"] == 1 and data["work"]["approvals"] == 1
    assert [m["id"] for m in data["learnt"]] == [str(mine)]
    assert data["learnt"][0]["source"] == "Jarvis" and data["learnt"][0]["status"] == "pending"
    # Nothing connected for this tenant: empty, not an error.
    assert data["schedule"] == [] and data["due"] == [] and data["insights"] == []
    assert data["brief"] is None and data["mail_waiting"] == 0 and data["study_due"] == 0


@pytest.mark.asyncio
@skip_on_db_error
async def test_today_without_a_token_is_refused(client):
    assert (await client.get("/api/v1/jarvis/today")).status_code == 401
    bad = {"Authorization": "Bearer not-a-device-token"}
    assert (await client.get("/api/v1/jarvis/today", headers=bad)).status_code == 401


@pytest.mark.asyncio
@skip_on_db_error
async def test_mark_paid_only_finds_the_devices_own_bills(client):
    phone = await _phone(client)
    resp = await client.post(f"/api/v1/jarvis/bills/{uuid.uuid4()}/paid", headers=phone)
    assert resp.status_code == 404
    resp = await client.post("/api/v1/jarvis/bills/not-a-uuid/paid", headers=phone)
    assert resp.status_code == 404
