"""/kernel/automation routes: tenant reads, owner-only writes, error mapping.

In-process (httpx ASGITransport) over the real service with in-memory ports.
"""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from life_graph.api import dev_automation as api
from life_graph.api.middleware import TenantMiddleware
from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.dev.automation.breaker import BreakerState
from life_graph.services.dev.automation.service import AutomationService
from tests.unit.automation_fakes import (
    PROJECT_ID,
    FakeExec,
    FakeGate,
    FakeNotifier,
    FakeTasks,
    MemStore,
    T,
    at,
)

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "svc-key-9876543210"
BASE = "/api/v1/kernel/automation"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)


@pytest.fixture
def svc(monkeypatch):
    async def report_fn(tenant_id, since):
        return {"since": "", "merged": [], "waiting": [], "failed": [], "queued": 2}

    service = AutomationService(
        store=MemStore(),
        tasks=FakeTasks(),
        gate=FakeGate(),
        notifier=FakeNotifier(),
        exec_=FakeExec().on("git", "grep", stdout="main:a.py:1:# TODO(race): do x"),
        intentions=None,
        report_fn=report_fn,
        clock=lambda: at("2026-11-27T10:00"),
    )
    monkeypatch.setattr(api._service, "get_service", lambda: service)
    return service


@pytest_asyncio.fixture
async def client():
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(api.router, prefix="/api/v1")
    app.dependency_overrides[get_current_tenant_id] = lambda: T
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _as(key):
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": T}


OWNER, SERVICE = _as(OWNER_KEY), _as(SERVICE_KEY)

DOC = {
    "intake": {
        "maxConcurrent": 1,
        "maxPerDay": 3,
        "sources": [
            {"id": "draft", "kind": "todo_comments", "projectId": PROJECT_ID, "enabled": True}
        ],
    },
    "schedules": [
        {
            "id": "a",
            "name": "deps",
            "projectId": PROJECT_ID,
            "instruction": "Update dependencies.",
            "days": [1],
            "time": "02:00",
        },
        {
            "id": "b",
            "name": "after deps",
            "projectId": PROJECT_ID,
            "instruction": "Run the audit.",
            "after": "a",
        },
    ],
    "digest": {"enabled": True, "time": "07:30"},
    "breaker": {"enabled": True, "threshold": 4},
    "timezone": "Asia/Kolkata",
}


async def test_settings_defaults_then_owner_put(client, svc):
    r = await client.get(f"{BASE}/settings", headers=SERVICE)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["intake"] == {"sources": [], "maxConcurrent": 1, "maxPerDay": 5}
    assert data["digest"]["enabled"] is False and data["breaker"]["enabled"] is True
    assert (await client.put(f"{BASE}/settings", json=DOC, headers=SERVICE)).status_code == 403
    r = await client.put(f"{BASE}/settings", json=DOC, headers=OWNER)
    assert r.status_code == 200, r.text
    saved = r.json()["data"]
    first, second = saved["schedules"]
    assert second["after"] == first["id"] != "a"  # draft ids replaced and translated
    assert saved["intake"]["sources"][0]["id"] != "draft"
    assert saved["timezone"] == "Asia/Kolkata" and saved["breaker"]["threshold"] == 4


async def test_put_rejects_cycles_unknown_projects_and_invalid_bodies(client, svc):
    loop = {**DOC, "schedules": [{**DOC["schedules"][0], "after": "b"}, DOC["schedules"][1]]}
    r = await client.put(f"{BASE}/settings", json=loop, headers=OWNER)
    assert r.status_code == 400 and "loop" in r.json()["detail"]
    bad = {
        **DOC,
        "intake": {**DOC["intake"], "sources": [{"kind": "todo_comments", "projectId": "x"}]},
    }
    assert (await client.put(f"{BASE}/settings", json=bad, headers=OWNER)).status_code == 400
    invalid = {**DOC, "breaker": {"threshold": 99}}
    assert (await client.put(f"{BASE}/settings", json=invalid, headers=OWNER)).status_code == 422


async def test_poll_backlog_start_skip(client, svc):
    await client.put(
        f"{BASE}/settings",
        json={**DOC, "intake": {**DOC["intake"], "maxConcurrent": 0}},
        headers=OWNER,
    )
    assert (await client.post(f"{BASE}/intake/poll", headers=SERVICE)).status_code == 403
    r = await client.post(f"{BASE}/intake/poll", headers=OWNER)
    assert r.status_code == 200 and r.json()["data"]["added"] == 1
    r = await client.get(f"{BASE}/backlog", params={"status": "new"}, headers=SERVICE)
    items = r.json()["data"]["items"]
    assert len(items) == 1 and items[0]["externalKey"].startswith("todo:a.py:1:")
    item_id = items[0]["id"]
    assert (
        await client.get(f"{BASE}/backlog", params={"status": "bogus"}, headers=SERVICE)
    ).status_code == 422
    assert (
        await client.post(f"{BASE}/backlog/{item_id}/start", headers=SERVICE)
    ).status_code == 403
    r = await client.post(f"{BASE}/backlog/{item_id}/start", headers=OWNER)
    assert r.status_code == 200 and r.json()["data"]["item"]["status"] == "queued"
    assert svc.tasks.created[0]["start_now"] is True
    r = await client.post(f"{BASE}/backlog/{item_id}/skip", headers=OWNER)
    assert r.status_code == 409
    assert (await client.post(f"{BASE}/backlog/nope/start", headers=OWNER)).status_code == 404


async def test_run_now_and_runs(client, svc):
    saved = (await client.put(f"{BASE}/settings", json=DOC, headers=OWNER)).json()["data"]
    job_id = saved["schedules"][0]["id"]
    assert (await client.post(f"{BASE}/schedules/{job_id}/run", headers=SERVICE)).status_code == 403
    r = await client.post(f"{BASE}/schedules/{job_id}/run", headers=OWNER)
    assert r.status_code == 200 and r.json()["data"]["taskId"] == svc.tasks.created[0]["id"]
    r = await client.post(f"{BASE}/schedules/{job_id}/run", headers=OWNER)
    assert r.status_code == 409  # the first run's task is still queued
    runs = (await client.get(f"{BASE}/schedules/{job_id}/runs", headers=SERVICE)).json()["data"]
    assert [x["outcome"] for x in runs["items"]] == ["skipped_overlap", "started"]
    assert (await client.post(f"{BASE}/schedules/nope/run", headers=OWNER)).status_code == 404
    assert (await client.get(f"{BASE}/schedules/nope/runs", headers=SERVICE)).status_code == 404


async def test_breakers_list_and_reset(client, svc):
    key = "intake:abc"
    svc.store.breakers[(T, key)] = BreakerState(
        key=key, label="TODO comments", tripped=True, consecutive_failures=3, last_reason="boom"
    )
    items = (await client.get(f"{BASE}/breakers", headers=SERVICE)).json()["data"]["items"]
    assert items[0]["key"] == key and items[0]["tripped"] is True
    assert (await client.post(f"{BASE}/breakers/{key}/reset", headers=SERVICE)).status_code == 403
    r = await client.post(f"{BASE}/breakers/{key}/reset", headers=OWNER)
    assert r.status_code == 200 and r.json()["data"]["item"]["tripped"] is False
    assert (
        await client.post(f"{BASE}/breakers/intake:none/reset", headers=OWNER)
    ).status_code == 404


async def test_digest_preview(client, svc):
    r = await client.get(f"{BASE}/digest/preview", headers=SERVICE)
    data = r.json()["data"]
    assert r.status_code == 200 and data["queued"] == 2 and data["summary"].startswith("0 merged")
