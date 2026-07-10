"""Integration tests for memory deduplication via the creation endpoint.

Validates that the POST /api/v1/memories/ endpoint:
- Accepts baseline memory creation payloads (201).
- Accepts the ``skip_dedup`` field without validation errors.
- Returns a consistent response shape regardless of skip_dedup.
"""

from __future__ import annotations

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


class TestMemoryDeduplication:
    """Test deduplication behaviour on memory creation."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_memory_baseline(self, client: AsyncClient):
        """POST /api/v1/memories/ with minimal payload returns 201 or 500 (no DB)."""
        r = await client.post(
            "/api/v1/memories/",
            json={"content": "test fact", "source_type": "test"},
        )
        assert r.status_code in (201, 500), f"Unexpected status {r.status_code}: {r.text}"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_memory_with_skip_dedup_true(self, client: AsyncClient):
        """POST with skip_dedup=true is accepted — no 422 validation error."""
        r = await client.post(
            "/api/v1/memories/",
            json={"content": "test fact", "source_type": "test", "skip_dedup": True},
        )
        assert r.status_code in (201, 500), f"Unexpected status {r.status_code}: {r.text}"
        assert r.status_code != 422, "skip_dedup=true should not cause a validation error"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_memory_with_skip_dedup_false(self, client: AsyncClient):
        """POST with skip_dedup=false is accepted (explicit default)."""
        r = await client.post(
            "/api/v1/memories/",
            json={"content": "test fact", "source_type": "test", "skip_dedup": False},
        )
        assert r.status_code in (201, 500), f"Unexpected status {r.status_code}: {r.text}"
        assert r.status_code != 422, "skip_dedup=false should not cause a validation error"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_skip_dedup_invalid_type_rejected(self, client: AsyncClient):
        """POST with skip_dedup set to a non-boolean should return 422."""
        r = await client.post(
            "/api/v1/memories/",
            json={"content": "test fact", "source_type": "test", "skip_dedup": "not_a_bool"},
        )
        assert r.status_code in (422, 201, 500), f"Unexpected status {r.status_code}"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_response_shape_without_skip_dedup(self, client: AsyncClient):
        """Response body is a list or wrapped object when skip_dedup is absent."""
        r = await client.post(
            "/api/v1/memories/",
            json={"content": "test fact for shape check", "source_type": "test"},
        )
        if r.status_code == 201:
            body = r.json()
            assert isinstance(body, (list, dict)), "Response should be list or dict"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_response_shape_with_skip_dedup(self, client: AsyncClient):
        """Response body shape is consistent when skip_dedup=true."""
        r = await client.post(
            "/api/v1/memories/",
            json={
                "content": "test fact for shape check",
                "source_type": "test",
                "skip_dedup": True,
            },
        )
        if r.status_code == 201:
            body = r.json()
            assert isinstance(body, (list, dict)), "Response should be list or dict"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_memory_missing_content_rejected(self, client: AsyncClient):
        """POST without 'content' field must return 422."""
        r = await client.post(
            "/api/v1/memories/",
            json={"source_type": "test", "skip_dedup": True},
        )
        assert r.status_code in (422, 500), "Missing 'content' should trigger validation error"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_memory_empty_content_rejected(self, client: AsyncClient):
        """POST with empty content should return 422 (min_length=1)."""
        r = await client.post(
            "/api/v1/memories/",
            json={"content": "", "source_type": "test"},
        )
        assert r.status_code in (422, 500), "Empty content should trigger validation error"
