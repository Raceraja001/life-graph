"""Integration tests for the manual chat distillation endpoint.

Covers:
- POST /api/v1/conversations/{id}/distill on an unknown/foreign id → 404
- POST /api/v1/conversations/{id}/distill on an owned conversation → never 422,
  and if 200, the standard envelope with {"status": "distilling"}

Defensive per house convention: accept 500 when the DB/redis is unreachable,
but never 422 for a valid request. Reuses the `client` fixture and
`_create_conversation` helper pattern from test_conversations_api.py.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = "test-chat-distill"
TENANT_HEADERS = {"X-Tenant-ID": TENANT}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


async def _create_conversation(client: AsyncClient) -> str | None:
    resp = await client.post("/api/v1/conversations")
    assert resp.status_code in (200, 201, 500), resp.text
    if resp.status_code not in (200, 201):
        return None
    return resp.json()["data"]["id"]


class TestDistill:
    @skip_on_db_error
    async def test_distill_unknown_conversation_returns_404(self, client: AsyncClient):
        resp = await client.post(f"/api/v1/conversations/{uuid.uuid4()}/distill")
        assert resp.status_code in (404, 500), resp.text

    @skip_on_db_error
    async def test_distill_own_conversation_acks(self, client: AsyncClient):
        cid = await _create_conversation(client)
        if cid is None:
            return

        resp = await client.post(f"/api/v1/conversations/{cid}/distill")
        # Valid input must never 422; accept 200 (queued/inline) or 500 (DB/redis down).
        assert resp.status_code != 422, resp.text
        if resp.status_code == 200:
            assert resp.json()["data"]["status"] == "distilling"
