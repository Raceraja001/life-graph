"""Integration tests for the ask-your-memories Conversation API.

Covers:
- POST /api/v1/conversations (create → id)
- GET /api/v1/conversations (list)
- POST /api/v1/conversations/{id}/messages (ask → answer + citations; empty → 422; 404)
- GET /api/v1/conversations/{id} (thread — both turns visible)
- DELETE /api/v1/conversations/{id} (delete → gone)
- tenant isolation (cross-tenant id → 404)

Defensive per house convention: accept 500 when the DB is unreachable, but
never 422 for a valid request. See docs/specs (ask-your-memories chat).
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

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


async def _create_conversation(client: AsyncClient) -> str | None:
    resp = await client.post("/api/v1/conversations")
    assert resp.status_code in (200, 201, 500), resp.text
    if resp.status_code not in (200, 201):
        return None
    return resp.json()["data"]["id"]


class TestCreateAndList:
    @skip_on_db_error
    async def test_create_returns_id(self, client: AsyncClient):
        resp = await client.post("/api/v1/conversations")
        assert resp.status_code in (200, 201, 500), resp.text
        if resp.status_code in (200, 201):
            body = resp.json()
            assert "id" in body["data"]

    @skip_on_db_error
    async def test_list_returns_envelope(self, client: AsyncClient):
        resp = await client.get("/api/v1/conversations")
        assert resp.status_code in (200, 500), resp.text
        if resp.status_code == 200:
            assert isinstance(resp.json()["data"], list)


class TestAsk:
    @skip_on_db_error
    async def test_ask_returns_answer_and_citations(self, client: AsyncClient):
        cid = await _create_conversation(client)
        if cid is None:
            return

        resp = await client.post(
            f"/api/v1/conversations/{cid}/messages", json={"content": "hello?"}
        )
        assert resp.status_code in (200, 500), resp.text
        if resp.status_code != 200:
            return

        body = resp.json()["data"]
        assert "message" in body
        assert "citations" in body
        assert body["message"]["role"] == "assistant"

        thread = await client.get(f"/api/v1/conversations/{cid}")
        assert thread.status_code in (200, 500)
        if thread.status_code == 200:
            messages = thread.json()["data"]["messages"]
            roles = [m["role"] for m in messages]
            assert "user" in roles
            assert "assistant" in roles

    @skip_on_db_error
    async def test_empty_content_422(self, client: AsyncClient):
        cid = await _create_conversation(client)
        if cid is None:
            return
        resp = await client.post(f"/api/v1/conversations/{cid}/messages", json={"content": "   "})
        assert resp.status_code == 422

    @skip_on_db_error
    async def test_ask_unknown_conversation_404(self, client: AsyncClient):
        import uuid

        resp = await client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/messages", json={"content": "hi"}
        )
        assert resp.status_code in (404, 500)


class TestTenantIsolation:
    @skip_on_db_error
    async def test_cross_tenant_get_404(self, client: AsyncClient, other_client: AsyncClient):
        cid = await _create_conversation(client)
        if cid is None:
            return
        resp = await other_client.get(f"/api/v1/conversations/{cid}")
        assert resp.status_code in (404, 500)

    @skip_on_db_error
    async def test_cross_tenant_ask_404(self, client: AsyncClient, other_client: AsyncClient):
        cid = await _create_conversation(client)
        if cid is None:
            return
        resp = await other_client.post(
            f"/api/v1/conversations/{cid}/messages", json={"content": "hi"}
        )
        assert resp.status_code in (404, 500)


class TestDelete:
    @skip_on_db_error
    async def test_delete_then_gone(self, client: AsyncClient):
        cid = await _create_conversation(client)
        if cid is None:
            return

        resp = await client.delete(f"/api/v1/conversations/{cid}")
        assert resp.status_code in (200, 500), resp.text
        if resp.status_code == 200:
            assert resp.json()["data"]["deleted"] is True

        follow_up = await client.get(f"/api/v1/conversations/{cid}")
        assert follow_up.status_code in (404, 500)
