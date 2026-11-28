"""Phase 3b part 2 routes: continue (owner), resume a parked task (owner), list parked.

In-process (httpx ASGITransport); the service functions are stand-ins.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from life_graph.api import drivers as drivers_api
from life_graph.api.middleware import TenantMiddleware
from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.dev.continuation import ContinueError

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "svc-key-9876543210"
TASK = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)


@pytest_asyncio.fixture
async def client():
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(drivers_api.router, prefix="/api/v1")
    app.dependency_overrides[get_current_tenant_id] = lambda: "raja"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _as(key):
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": "raja"}


@pytest.fixture
def calls(monkeypatch):
    seen: list = []

    async def _continue(sf, tenant_id, task_id, feedback, reason):
        seen.append((tenant_id, task_id, feedback, reason))
        if feedback == "busy":
            raise ContinueError("busy", "Dev task is running; continue it once it has finished")
        return {"id": task_id, "status": "queued"}

    async def _resume(sf, tenant_id, task_id):
        seen.append(("resume", tenant_id, task_id))
        return (
            {"id": task_id, "status": "completed", "resumed": False}
            if task_id != TASK
            else {"id": task_id, "status": "queued", "resumed": True}
        )

    async def _parked(session, tenant_id):
        return [{"id": TASK, "status": "parked", "park": {"resume_at": "2026-11-27T12:01:00Z"}}]

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_e):
            return False

    monkeypatch.setattr(drivers_api, "continue_task", _continue)
    monkeypatch.setattr(drivers_api._dev_tasks, "resume_parked", _resume)
    monkeypatch.setattr(drivers_api._dev_tasks, "list_parked", _parked)
    monkeypatch.setattr(drivers_api, "async_session", lambda: _Session())
    return seen


async def test_continue_is_owner_only(client, calls):
    url = f"/api/v1/kernel/drivers/tasks/{TASK}/continue"
    r = await client.post(url, json={"feedback": "also None"}, headers=_as(SERVICE_KEY))
    assert r.status_code == 403 and calls == []
    r = await client.post(
        url, json={"feedback": "also None", "reason": "pr_feedback"}, headers=_as(OWNER_KEY)
    )
    assert r.status_code == 200 and r.json()["data"]["status"] == "queued"
    assert calls == [("raja", TASK, "also None", "pr_feedback")]


async def test_continue_refusals_and_validation(client, calls):
    url = f"/api/v1/kernel/drivers/tasks/{TASK}/continue"
    r = await client.post(url, json={"feedback": "busy"}, headers=_as(OWNER_KEY))
    assert r.status_code == 409 and r.json()["detail"].startswith("busy:")
    r = await client.post(url, json={"feedback": ""}, headers=_as(OWNER_KEY))
    assert r.status_code == 422
    r = await client.post(url, json={"feedback": "x", "key": "sk"}, headers=_as(OWNER_KEY))
    assert r.status_code == 422
    r = await client.post(
        "/api/v1/kernel/drivers/tasks/not-a-uuid/continue",
        json={"feedback": "x"},
        headers=_as(OWNER_KEY),
    )
    assert r.status_code == 404


async def test_resume_parked_is_owner_only_and_409_when_not_parked(client, calls):
    r = await client.post(f"/api/v1/kernel/drivers/tasks/{TASK}/resume", headers=_as(SERVICE_KEY))
    assert r.status_code == 403
    r = await client.post(f"/api/v1/kernel/drivers/tasks/{TASK}/resume", headers=_as(OWNER_KEY))
    assert r.status_code == 200 and r.json()["data"]["resumed"] is True
    other = str(uuid.uuid4())
    r = await client.post(f"/api/v1/kernel/drivers/tasks/{other}/resume", headers=_as(OWNER_KEY))
    assert r.status_code == 409


async def test_list_parked(client, calls):
    r = await client.get("/api/v1/kernel/drivers/tasks/parked", headers=_as(SERVICE_KEY))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["count"] == 1 and data["tasks"][0]["park"]["resume_at"] == "2026-11-27T12:01:00Z"
