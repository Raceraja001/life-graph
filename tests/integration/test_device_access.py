"""The device allowlist (docs/specs/device-access.md) with a real device token
through the real app: every allowed route answers it (whatever the answer,
never 401), a sample of others refuse it, and an approval decided on the
phone is recorded as such, for the device's tenant only.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.api.device_access import _PARAM, DEVICE_ALLOWLIST
from tests.integration.conftest import skip_on_db_error

TENANT = f"devacc_{uuid.uuid4().hex[:8]}"
OTHER = f"other_{TENANT}"
KEY = "svc-test-key"
OWNER = {"Authorization": f"Bearer {KEY}", "X-Tenant-ID": TENANT}
ID = str(uuid.uuid4())

REFUSED = [
    ("POST", "/api/v1/memories/", {"content": "x"}),
    ("DELETE", f"/api/v1/devices/{ID}", None),
    ("GET", "/api/v1/devices", None),
    ("POST", f"/api/v1/kernel/tasks/{ID}/cancel", None),
    ("POST", "/api/v1/kernel/drivers/tasks", {"instruction": "x"}),
    ("PUT", "/api/v1/money/budgets/food", {"monthly_limit": 1}),
    ("PUT", "/api/v1/connectors/google-client", {"client": {}}),
    ("PATCH", "/api/v1/watchers/configs/app_uptime", {"enabled": False}),
    ("GET", "/api/v1/admin/stats", None),
    ("POST", "/api/v1/admin/tenants/provision", {"tenant_id": "x"}),
    ("HEAD", "/api/v1/money/summary", None),
    ("GET", "/api/v1/money/summary/", None),
    # httpx keeps %2F; ASGITransport decodes it into scope["path"], as a server
    # does. (Bare ".." is tidied away by httpx itself: tests/unit covers it.)
    ("GET", "/api/v1/jarvis%2F..%2Fmemories/", None),
]


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


async def _phone(client) -> tuple[dict, str]:
    code = (await client.post("/api/v1/devices/codes", headers=OWNER)).json()["data"]["code"]
    resp = await client.post("/api/v1/devices/pair", json={"code": code, "name": "Pixel"})
    data = resp.json()["data"]
    return {"Authorization": f"Bearer {data['token']}"}, data["device_id"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_every_allowed_route_answers_a_device_token(client):
    phone, _ = await _phone(client)
    for entry in DEVICE_ALLOWLIST:
        path = _PARAM.sub(ID, entry.route)
        body = {"grade": "good"} if entry.route.endswith("/grade") else None
        resp = await client.request(entry.method, path, headers=phone, json=body)
        assert resp.status_code != 401, (entry.method, path, resp.status_code)
        assert resp.status_code < 500, (entry.method, path, resp.text[:200])


@pytest.mark.asyncio
@skip_on_db_error
async def test_other_routes_refuse_a_device_token(client):
    phone, _ = await _phone(client)
    for method, path, body in REFUSED:
        resp = await client.request(method, path, headers=phone, json=body)
        assert resp.status_code == 401, (method, path, resp.status_code)


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_approval_decided_on_the_phone_is_marked_and_tenant_bound(client):
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    phone, device_id = await _phone(client)
    async with async_session() as s:
        mine = Approval(tenant_id=TENANT, kind="phone_test", title="Mine", source="test")
        theirs = Approval(tenant_id=OTHER, kind="phone_test", title="Theirs", source="test")
        s.add_all([mine, theirs])
        await s.commit()
        mine_id, theirs_id = mine.id, theirs.id

    # A spoofed resolver and tenant in the request change nothing.
    spoof = {**phone, "X-Tenant-ID": OTHER}
    resp = await client.post(
        f"/api/v1/approvals/{mine_id}/reject", headers=spoof, json={"resolved_by": "raja"}
    )
    assert resp.status_code == 200 and resp.json()["data"]["status"] == "rejected"
    resp = await client.post(f"/api/v1/approvals/{theirs_id}/approve", headers=spoof)
    assert resp.status_code == 404

    listed = (await client.get("/api/v1/approvals?status=all", headers=spoof)).json()["data"]
    assert {a["id"] for a in listed} == {str(mine_id)}
    async with async_session() as s:
        row = await s.get(Approval, mine_id)
        other = await s.get(Approval, theirs_id)
    assert row.resolved_by == f"phone:{device_id}"
    assert other.status == "pending"
