"""Autonomy trust boundaries over real HTTP and Postgres (quality phase 2, batch 2a).

The unit tests (tests/unit/test_autonomy_trust_boundaries.py) pin each rule;
these check the same rules end to end, through the auth middleware, with the
migrated schema (migration 061 adds ``approval_queue.requested_by``):

* a service key's host command is queued, never run, under the caller's own
  identity, with the command pinned — whatever ``agent_id`` the body names;
* that caller cannot approve its own entry; the owner can;
* a batch with no filter is refused;
* trust overrides, autonomy levels and resuming autonomy are owner only.

Only harmless commands are used, and none runs: the queued path writes rows.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from life_graph.config import settings
from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = "test_autonomy_trust_tenant"
OWNER_KEY = "it-owner-key-0123456789"
SERVICE_KEY = "it-mcp-key-9876543210"
SERVICE_LABEL = f"service-key:{hashlib.sha256(SERVICE_KEY.encode()).hexdigest()[:8]}"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "approvals_require_owner", False)


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Tenant-ID": TENANT}
    ) as c:
        yield c


def _as(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


async def _queue_as_service_key(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/autonomy/auto-actions",
        json={
            "agent_id": "cody",  # someone else's name; it must not count
            "project_id": f"proj-{uuid.uuid4().hex[:8]}",
            "action_type": "fix_lint",
            "command": "true",
        },
        headers=_as(SERVICE_KEY),
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["data"]


@skip_on_db_error
async def test_a_service_key_command_is_queued_as_the_caller_and_pinned(client):
    from life_graph.autonomy.models import ApprovalQueueEntry, AutoAction
    from life_graph.storage.database import async_session

    data = await _queue_as_service_key(client)
    assert data["routing"] == "queued_for_approval"
    action = data["action"]
    assert action["agent_id"] == SERVICE_LABEL
    assert action["status"] == "pending"
    assert action["exit_code"] is None  # nothing ran

    async with async_session() as session:
        row = await session.get(AutoAction, action["id"])
        entry = (
            await session.execute(
                select(ApprovalQueueEntry).where(ApprovalQueueEntry.id == action["approval_id"])
            )
        ).scalar_one()
    assert row.before_state["command_approval"]["sha256"] == hashlib.sha256(b"true").hexdigest()
    assert row.before_state["request"]["claimed_agent_id"] == "cody"
    assert entry.requested_by == SERVICE_LABEL
    assert entry.expires_at is None  # no notify-then-auto-approve


@skip_on_db_error
async def test_the_caller_cannot_approve_its_own_entry_but_the_owner_can(client):
    approval_id = (await _queue_as_service_key(client))["action"]["approval_id"]
    url = f"/api/v1/autonomy/approvals/{approval_id}/resolve"

    own = await client.post(url, json={"decision": "approve"}, headers=_as(SERVICE_KEY))
    assert own.status_code == 403, own.text

    owner = await client.post(url, json={"decision": "approve"}, headers=_as(OWNER_KEY))
    assert owner.status_code == 200, owner.text
    assert owner.json()["data"]["status"] == "approved"


@skip_on_db_error
async def test_a_batch_including_the_callers_own_entry_is_refused(client):
    action = (await _queue_as_service_key(client))["action"]
    resp = await client.post(
        "/api/v1/autonomy/approvals/batch",
        json={"decision": "approve", "approval_ids": [action["approval_id"]]},
        headers=_as(SERVICE_KEY),
    )
    assert resp.status_code == 403, resp.text


async def test_a_batch_with_no_filter_is_refused(client):
    resp = await client.post(
        "/api/v1/autonomy/approvals/batch", json={"decision": "approve"}, headers=_as(OWNER_KEY)
    )
    assert resp.status_code == 422, resp.text


@skip_on_db_error
async def test_trust_override_is_owner_only_and_by_is_the_servers(client):
    body = {
        "agent_id": f"agent-{uuid.uuid4().hex[:8]}",
        "action_type": "fix_lint",
        "score": 0.9,
        "reason": "integration test",
        "by": "owner",
    }
    refused = await client.post(
        "/api/v1/autonomy/trust/override", json=body, headers=_as(SERVICE_KEY)
    )
    assert refused.status_code == 403, refused.text

    ok = await client.post("/api/v1/autonomy/trust/override", json=body, headers=_as(OWNER_KEY))
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["override_by"] == "owner"


@skip_on_db_error
async def test_setting_a_level_is_owner_only(client):
    url = f"/api/v1/autonomy/levels/proj-{uuid.uuid4().hex[:8]}/set"
    body = {"level": 3, "reason": "integration test", "set_by": "owner"}

    refused = await client.post(url, json=body, headers=_as(SERVICE_KEY))
    assert refused.status_code == 403, refused.text

    ok = await client.post(url, json=body, headers=_as(OWNER_KEY))
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["level"] == 3


async def test_resuming_autonomy_is_owner_only(client):
    resp = await client.post(
        "/api/v1/autonomy/safety/kill-switch/resume", json={}, headers=_as(SERVICE_KEY)
    )
    assert resp.status_code == 403, resp.text
