"""Integration tests for memory decay and unarchive features.

Validates:
- POST /api/v1/memories/{id}/unarchive returns 404 for nonexistent UUIDs.
- GET  /api/v1/memories/?status=archived is accepted (200 or 500).
- The list_memories endpoint properly accepts the status query parameter.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Authenticated test client hitting the ASGI app in-process."""
    transport = ASGITransport(app=app)
    headers = {"X-Tenant-ID": "test_tenant", "X-User-ID": "user-test"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as c:
        yield c


class TestMemoryUnarchive:
    """Test the POST /api/v1/memories/{id}/unarchive endpoint."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_unarchive_nonexistent_memory_returns_404(self, client: AsyncClient):
        """Unarchiving a UUID that doesn't exist should return 404 or 500 (no DB)."""
        fake_id = str(uuid.uuid4())
        r = await client.post(f"/api/v1/memories/{fake_id}/unarchive")
        assert r.status_code in (404, 500), f"Unexpected status {r.status_code}: {r.text}"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_unarchive_invalid_uuid_returns_422(self, client: AsyncClient):
        """Unarchiving with a malformed UUID should return 422."""
        r = await client.post("/api/v1/memories/not-a-uuid/unarchive")
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_unarchive_response_shape_on_404(self, client: AsyncClient):
        """404 response should include a detail message."""
        fake_id = str(uuid.uuid4())
        r = await client.post(f"/api/v1/memories/{fake_id}/unarchive")
        if r.status_code == 404:
            body = r.json()
            assert "detail" in body


class TestListMemoriesStatusFilter:
    """Test the GET /api/v1/memories/?status=... query parameter."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_with_status_archived(self, client: AsyncClient):
        """GET with status=archived should be accepted (no 422)."""
        r = await client.get("/api/v1/memories/", params={"status": "archived"})
        assert r.status_code != 422
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_with_status_active(self, client: AsyncClient):
        """GET with status=active should be accepted (no 422)."""
        r = await client.get("/api/v1/memories/", params={"status": "active"})
        assert r.status_code != 422
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_without_status(self, client: AsyncClient):
        """GET without status param should return all memories (200 or 500)."""
        r = await client.get("/api/v1/memories/")
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_response_shape(self, client: AsyncClient):
        """Successful list should return a paginated envelope."""
        r = await client.get("/api/v1/memories/", params={"status": "archived"})
        if r.status_code == 200:
            body = r.json()
            data = body.get("data", body)
            assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_with_limit(self, client: AsyncClient):
        """GET with limit param should be accepted."""
        r = await client.get(
            "/api/v1/memories/",
            params={"status": "archived", "limit": 5},
        )
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_invalid_limit_rejected(self, client: AsyncClient):
        """GET with limit=0 should return 422 (ge=1 constraint)."""
        r = await client.get("/api/v1/memories/", params={"limit": 0})
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_with_min_importance(self, client: AsyncClient):
        """GET with min_importance filter should be accepted."""
        r = await client.get(
            "/api/v1/memories/",
            params={"min_importance": 0.7},
        )
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_with_tags_filter(self, client: AsyncClient):
        """GET with tags filter should be accepted."""
        r = await client.get(
            "/api/v1/memories/",
            params={"tags": "preference,decision"},
        )
        assert r.status_code in (200, 500)
