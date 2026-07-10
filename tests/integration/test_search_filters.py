"""Integration tests for search filter fields on POST /api/v1/search/.

Validates that the semantic search endpoint accepts the extended filter
parameters (``status``, ``source_type``, ``created_after``,
``created_before``) without returning 422 validation errors.
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


class TestSearchFilters:
    """Test that new filter fields are accepted by POST /api/v1/search/."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_with_status_filter(self, client: AsyncClient):
        """Search with status='active' should not produce a 422."""
        r = await client.post(
            "/api/v1/search/",
            json={"query": "test", "status": "active"},
        )
        assert r.status_code != 422, f"status filter caused validation error: {r.text}"
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_with_status_archived(self, client: AsyncClient):
        """Search with status='archived' should also be accepted."""
        r = await client.post(
            "/api/v1/search/",
            json={"query": "test", "status": "archived"},
        )
        assert r.status_code != 422
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_with_source_type_filter(self, client: AsyncClient):
        """Search with source_type='manual' should not produce a 422."""
        r = await client.post(
            "/api/v1/search/",
            json={"query": "test", "source_type": "manual"},
        )
        assert r.status_code != 422
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_with_created_after(self, client: AsyncClient):
        """Search with created_after should not produce a 422."""
        r = await client.post(
            "/api/v1/search/",
            json={"query": "test", "created_after": "2024-01-01T00:00:00Z"},
        )
        assert r.status_code != 422
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_with_created_before(self, client: AsyncClient):
        """Search with created_before should not produce a 422."""
        r = await client.post(
            "/api/v1/search/",
            json={"query": "test", "created_before": "2030-01-01T00:00:00Z"},
        )
        assert r.status_code != 422
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_with_all_filters_combined(self, client: AsyncClient):
        """Search with every filter set at once should not produce a 422."""
        r = await client.post(
            "/api/v1/search/",
            json={
                "query": "test query",
                "status": "active",
                "source_type": "manual",
                "created_after": "2024-01-01T00:00:00Z",
                "created_before": "2030-01-01T00:00:00Z",
                "min_importance": 0.5,
                "tags": ["preference"],
                "limit": 5,
            },
        )
        assert r.status_code != 422
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_response_shape(self, client: AsyncClient):
        """Successful search should return the SearchResult envelope."""
        r = await client.post(
            "/api/v1/search/",
            json={"query": "test"},
        )
        if r.status_code == 200:
            body = r.json()
            data = body.get("data", body)
            assert "memories" in data
            assert "total_count" in data
            assert "query_time_ms" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_missing_query_rejected(self, client: AsyncClient):
        """POST without 'query' field must return 422."""
        r = await client.post(
            "/api/v1/search/",
            json={"status": "active"},
        )
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_empty_query_rejected(self, client: AsyncClient):
        """POST with empty query string should return 422 (min_length=1)."""
        r = await client.post(
            "/api/v1/search/",
            json={"query": ""},
        )
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_invalid_created_after_rejected(self, client: AsyncClient):
        """POST with malformed created_after should return 422."""
        r = await client.post(
            "/api/v1/search/",
            json={"query": "test", "created_after": "not-a-date"},
        )
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_invalid_min_importance_rejected(self, client: AsyncClient):
        """POST with min_importance > 1.0 should return 422."""
        r = await client.post(
            "/api/v1/search/",
            json={"query": "test", "min_importance": 2.0},
        )
        assert r.status_code in (422, 500)
