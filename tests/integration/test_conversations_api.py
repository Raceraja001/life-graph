"""Integration tests for the ask-your-memories Conversation API.

Covers:
- POST /api/v1/conversations (create → id)
- GET /api/v1/conversations (list)
- POST /api/v1/conversations/{id}/messages (ask → answer + citations; empty → 422; 404)
- GET /api/v1/conversations/{id} (thread — both turns visible)
- DELETE /api/v1/conversations/{id} (delete → gone)
- tenant isolation (cross-tenant id → 404)

Every status is asserted exactly: ``skip_on_db_error`` skips when no
database is reachable, so a 500 is always a failure. See docs/specs
(ask-your-memories chat).
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import assert_ok, skip_on_db_error

TENANT = "test-chat"
OTHER_TENANT = "test-chat-other"
TENANT_HEADERS = {"X-Tenant-ID": TENANT}
OTHER_TENANT_HEADERS = {"X-Tenant-ID": OTHER_TENANT}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


@pytest_asyncio.fixture
async def other_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=OTHER_TENANT_HEADERS
    ) as c:
        yield c


async def _create_conversation(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/conversations")
    return assert_ok(resp, 200)["data"]["id"]


class TestCreateAndList:
    @skip_on_db_error
    async def test_create_returns_id(self, client: AsyncClient):
        resp = await client.post("/api/v1/conversations")
        body = assert_ok(resp, 200)
        assert "id" in body["data"]

    @skip_on_db_error
    async def test_list_returns_envelope(self, client: AsyncClient):
        resp = await client.get("/api/v1/conversations")
        assert isinstance(assert_ok(resp, 200)["data"], list)


class TestAsk:
    @skip_on_db_error
    async def test_ask_returns_answer_and_citations(self, client: AsyncClient):
        cid = await _create_conversation(client)

        resp = await client.post(
            f"/api/v1/conversations/{cid}/messages", json={"content": "hello?"}
        )
        body = assert_ok(resp, 200)["data"]
        assert "message" in body
        assert "citations" in body
        assert body["message"]["role"] == "assistant"

        thread = await client.get(f"/api/v1/conversations/{cid}")
        messages = assert_ok(thread, 200)["data"]["messages"]
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    @skip_on_db_error
    async def test_empty_content_422(self, client: AsyncClient):
        cid = await _create_conversation(client)
        resp = await client.post(f"/api/v1/conversations/{cid}/messages", json={"content": "   "})
        assert resp.status_code == 422, resp.text

    @skip_on_db_error
    async def test_ask_unknown_conversation_404(self, client: AsyncClient):
        import uuid

        resp = await client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/messages", json={"content": "hi"}
        )
        assert resp.status_code == 404, resp.text


class TestTenantIsolation:
    @skip_on_db_error
    async def test_cross_tenant_get_404(self, client: AsyncClient, other_client: AsyncClient):
        cid = await _create_conversation(client)
        resp = await other_client.get(f"/api/v1/conversations/{cid}")
        assert resp.status_code == 404, resp.text

    @skip_on_db_error
    async def test_cross_tenant_ask_404(self, client: AsyncClient, other_client: AsyncClient):
        cid = await _create_conversation(client)
        resp = await other_client.post(
            f"/api/v1/conversations/{cid}/messages", json={"content": "hi"}
        )
        assert resp.status_code == 404, resp.text


class TestDelete:
    @skip_on_db_error
    async def test_delete_then_gone(self, client: AsyncClient):
        cid = await _create_conversation(client)

        resp = await client.delete(f"/api/v1/conversations/{cid}")
        assert assert_ok(resp, 200)["data"]["deleted"] is True

        follow_up = await client.get(f"/api/v1/conversations/{cid}")
        assert follow_up.status_code == 404, follow_up.text
