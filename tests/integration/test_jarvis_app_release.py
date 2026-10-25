"""The in-app update with a real device token through the real middleware:
latest.json read from app_release_dir, the APK streamed to paired phones
(and the service key) only, and only under the name latest.json gives.
"""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"apprel_{uuid.uuid4().hex[:8]}"
KEY = "svc-test-key"
OWNER = {"Authorization": f"Bearer {KEY}", "X-Tenant-ID": TENANT}
APK = b"PK\x03\x04" + b"\x00" * 300_000


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch, tmp_path):
    from life_graph.config import settings
    from life_graph.services import devices

    monkeypatch.setattr(settings, "service_api_keys", KEY)
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(devices, "pairing_limiter", devices.PairingLimiter())
    devices._cache.clear()
    (tmp_path / "jarvis-2.0.0.apk").write_bytes(APK)
    meta = {"version_code": 20, "version_name": "2.0.0", "file": "jarvis-2.0.0.apk", "notes": "v4"}
    (tmp_path / "latest.json").write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr(settings, "app_release_dir", str(tmp_path))


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _phone(client) -> dict:
    code = (await client.post("/api/v1/devices/codes", headers=OWNER)).json()["data"]["code"]
    resp = await client.post("/api/v1/devices/pair", json={"code": code, "name": "Pixel"})
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_paired_phone_finds_and_downloads_the_update(client):
    phone = await _phone(client)
    latest = await client.get("/api/v1/jarvis/app/latest", headers=phone)
    assert latest.status_code == 200
    data = latest.json()["data"]
    assert data == {
        "version_code": 20,
        "version_name": "2.0.0",
        "url": "/api/v1/jarvis/app/download/jarvis-2.0.0.apk",
        "notes": "v4",
    }
    apk = await client.get(data["url"], headers=phone)
    assert apk.status_code == 200 and apk.content == APK
    assert apk.headers["content-type"] == "application/vnd.android.package-archive"

    owner = await client.get(data["url"], headers=OWNER)
    assert owner.status_code == 200


@pytest.mark.asyncio
@skip_on_db_error
async def test_without_a_token_or_by_another_name_nothing(client):
    phone = await _phone(client)
    assert (await client.get("/api/v1/jarvis/app/latest")).status_code == 401
    url = "/api/v1/jarvis/app/download/jarvis-2.0.0.apk"
    assert (await client.get(url)).status_code == 401
    assert (await client.get(url, headers={"Authorization": "Bearer nope"})).status_code == 401
    for name in ("latest.json", "other.apk", "..%2Flatest.json"):
        resp = await client.get(f"/api/v1/jarvis/app/download/{name}", headers=phone)
        assert resp.status_code in (401, 404), name
