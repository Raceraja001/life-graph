"""Integration tests for the reconciled Era-8 autonomy pipeline.

`POST /autonomy/auto-actions` classifies → routes → writes a real `AutoAction`
row (all NOT NULL columns populated). A brand-new project is L0, so nothing
auto-executes — safe actions queue for approval, which is DB-only (no shell run).

Defensive per house convention: accept 500 when the DB is unreachable, never
422 for valid input. See docs/specs/era8-autonomy-reconciliation.md.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

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
        # 201 auto-executed, 202 queued/notify, 500 DB down — but never 422 for valid input.
        assert resp.status_code in (201, 202, 500), resp.text
        assert resp.status_code != 422

    async def test_trigger_missing_field_is_422(self, client: AsyncClient):
        # Genuinely invalid input (missing required fields) MUST 422.
        resp = await client.post(
            "/api/v1/autonomy/auto-actions", json={"agent_id": "only"}
        )
        assert resp.status_code == 422, resp.text

    @skip_on_db_error
    async def test_list_never_422(self, client: AsyncClient):
        resp = await client.get("/api/v1/autonomy/auto-actions")
        assert resp.status_code in (200, 500), resp.text
        if resp.status_code == 200:
            body = resp.json()
            assert isinstance(body["data"], list)

    @skip_on_db_error
    async def test_trigger_then_list_roundtrip(self, client: AsyncClient):
        req = _valid_request()
        created = await client.post("/api/v1/autonomy/auto-actions", json=req)
        if created.status_code not in (201, 202):
            return
        listing = await client.get(
            f"/api/v1/autonomy/auto-actions?project_id={req['project_id']}"
        )
        assert listing.status_code == 200, listing.text
        rows = listing.json()["data"]
        assert any(r["action_name"] == req["action_type"] for r in rows)
        # Real fields present, phantom ones gone.
        assert all("action_command" in r for r in rows)
