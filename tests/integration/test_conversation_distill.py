"""Integration tests for the manual chat distillation endpoint.

Covers:
- POST /api/v1/conversations/{id}/distill on an unknown/foreign id → 404
- POST /api/v1/conversations/{id}/distill on an owned conversation → 200,
  the standard envelope with {"status": "distilling"}

Every status is asserted exactly: ``skip_on_db_error`` skips when no
database is reachable, so a 500 is always a failure (CI runs Redis too).
Reuses the `client` fixture and `_create_conversation` helper pattern from
test_conversations_api.py.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import assert_ok, skip_on_db_error

TENANT = "test-chat-distill"
TENANT_HEADERS = {"X-Tenant-ID": TENANT}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


async def _create_conversation(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/conversations")
    return assert_ok(resp, 200)["data"]["id"]


class TestDistill:
    @skip_on_db_error
    async def test_distill_unknown_conversation_returns_404(self, client: AsyncClient):
        resp = await client.post(f"/api/v1/conversations/{uuid.uuid4()}/distill")
        assert resp.status_code == 404, resp.text

    @skip_on_db_error
    async def test_distill_own_conversation_acks(self, client: AsyncClient):
        cid = await _create_conversation(client)

        resp = await client.post(f"/api/v1/conversations/{cid}/distill")
        assert assert_ok(resp, 200)["data"]["status"] == "distilling"
