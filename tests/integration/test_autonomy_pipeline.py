"""Integration tests for the reconciled Era-8 autonomy pipeline.

`POST /autonomy/auto-actions` classifies → routes → writes a real `AutoAction`
row (all NOT NULL columns populated). A brand-new project is L0, so nothing
auto-executes — safe actions queue for approval, which is DB-only (no shell run).

Every status is asserted exactly: ``skip_on_db_error`` skips when no
database is reachable, so a 500 is always a failure. See
docs/specs/era8-autonomy-reconciliation.md. The 202 for a new (L0) project is
today's master behaviour; the autonomy trust-boundary work (server-derived
agent identity) may change who is recorded, not this routing.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import assert_ok, skip_on_db_error

TENANT = "test_autonomy_pipeline_tenant"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "autonomy-pipe-user"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


def _valid_request() -> dict:
    uniq = uuid.uuid4().hex[:8]
    return {
        "agent_id": "agent-x",
        "project_id": f"proj-{uniq}",
        "action_type": "fix_lint",
        "command": "echo noop",
        "description": "tidy imports",
        "timeout_seconds": 30,
    }


class TestPipeline:
    @skip_on_db_error
    async def test_trigger_valid_never_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/autonomy/auto-actions", json=_valid_request())
        # A brand-new project is L0: nothing auto-executes, so it queues (202).
        assert resp.status_code == 202, resp.text

    async def test_trigger_missing_field_is_422(self, client: AsyncClient):
        # Genuinely invalid input (missing required fields) MUST 422.
        resp = await client.post("/api/v1/autonomy/auto-actions", json={"agent_id": "only"})
        assert resp.status_code == 422, resp.text

    @skip_on_db_error
    async def test_list_never_422(self, client: AsyncClient):
        resp = await client.get("/api/v1/autonomy/auto-actions")
        body = assert_ok(resp, 200)
        assert isinstance(body["data"], list)

    @skip_on_db_error
    async def test_trigger_then_list_roundtrip(self, client: AsyncClient):
        req = _valid_request()
        created = await client.post("/api/v1/autonomy/auto-actions", json=req)
        assert_ok(created, 202)
        listing = await client.get(f"/api/v1/autonomy/auto-actions?project_id={req['project_id']}")
        rows = assert_ok(listing, 200)["data"]
        assert any(r["action_name"] == req["action_type"] for r in rows)
        # Real fields present, phantom ones gone.
        assert all("action_command" in r for r in rows)
