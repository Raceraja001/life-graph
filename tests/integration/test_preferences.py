"""Integration tests for Preference CRUD + semantic search (Era 4 Personal AI).

Tests the Preference API layer:
- POST /api/v1/preferences/ (create)
- GET /api/v1/preferences/ (list with filters)
- POST /api/v1/preferences/search (semantic search)
- PATCH /api/v1/preferences/{id} (partial update)
- DELETE /api/v1/preferences/{id} (soft delete)
- Inferred confidence cap at 0.7

Follows existing test patterns: httpx AsyncClient + ASGITransport. Every
status is asserted exactly; ``skip_on_db_error`` skips when no database is
reachable, so a 500 is always a failure.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import assert_ok, skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test-preferences-tenant",
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for preference API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


class TestCreatePreference:
    """POST /api/v1/preferences/"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_preference_returns_201(self, client: AsyncClient):
        """Creating a preference with valid input returns 201."""
        response = await client.post(
            "/api/v1/preferences/",
            json={
                "topic": "ORM",
                "choice": "SQLAlchemy",
                "reason": "Type safety + async",
                "confidence": 0.9,
                "source": "explicit",
                "tags": ["backend"],
                "category": "infrastructure",
            },
        )
        data = assert_ok(response, 201)["data"]
        assert data["topic"] == "ORM"
        assert data["choice"] == "SQLAlchemy"
        assert data["confidence"] == 0.9
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_preference_missing_topic(self, client: AsyncClient):
        """Missing required field topic returns 422."""
        response = await client.post(
            "/api/v1/preferences/",
            json={"choice": "pytest"},
        )
        assert response.status_code == 422, response.text

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_inferred_confidence_cap(self, client: AsyncClient):
        """Inferred-source preferences have confidence capped at 0.7."""
        response = await client.post(
            "/api/v1/preferences/",
            json={
                "topic": "Inferred test",
                "choice": "Y",
                "confidence": 0.95,
                "source": "inferred",
            },
        )
        data = assert_ok(response, 201)["data"]
        assert data["confidence"] <= 0.7, (
            f"Inferred confidence should be capped at 0.7, got {data['confidence']}"
        )


class TestListPreferences:
    """GET /api/v1/preferences/"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_preferences_returns_200(self, client: AsyncClient):
        """Listing preferences returns 200 with data array."""
        response = await client.get("/api/v1/preferences/")
        body = assert_ok(response, 200)
        assert "data" in body
        assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_preferences_with_category_filter(
        self,
        client: AsyncClient,
    ):
        """Listing preferences with category filter returns filtered results."""
        response = await client.get(
            "/api/v1/preferences/",
            params={"category": "infrastructure"},
        )
        body = assert_ok(response, 200)
        assert all(p["category"] == "infrastructure" for p in body["data"])


class TestSearchPreferences:
    """POST /api/v1/preferences/search"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_preferences_returns_200(self, client: AsyncClient):
        """Semantic search returns 200."""
        response = await client.post(
            "/api/v1/preferences/search",
            json={
                "query": "database choice",
                "limit": 5,
            },
        )
        body = assert_ok(response, 200)
        assert "data" in body
        assert isinstance(body["data"], list)


class TestUpdatePreference:
    """PATCH /api/v1/preferences/{preference_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_update_preference(self, client: AsyncClient):
        """Create then update a preference."""
        # Create
        create_resp = await client.post(
            "/api/v1/preferences/",
            json={
                "topic": "Testing Framework",
                "choice": "pytest",
                "confidence": 0.8,
            },
        )
        pref_id = assert_ok(create_resp, 201)["data"]["id"]

        # Update
        resp = await client.patch(
            f"/api/v1/preferences/{pref_id}",
            json={
                "confidence": 0.6,
                "reason": "Considering alternatives",
            },
        )
        data = assert_ok(resp, 200)["data"]
        assert data["confidence"] == 0.6

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_update_nonexistent_returns_404(self, client: AsyncClient):
        """Updating a non-existent preference returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.patch(
            f"/api/v1/preferences/{fake_id}",
            json={"confidence": 0.5},
        )
        assert resp.status_code == 404, resp.text


class TestDeletePreference:
    """DELETE /api/v1/preferences/{preference_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_preference(self, client: AsyncClient):
        """Create then soft-delete a preference."""
        create_resp = await client.post(
            "/api/v1/preferences/",
            json={
                "topic": "To Delete",
                "choice": "X",
                "confidence": 0.5,
            },
        )
        pref_id = assert_ok(create_resp, 201)["data"]["id"]

        resp = await client.delete(f"/api/v1/preferences/{pref_id}")
        assert resp.status_code == 204, resp.text

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_nonexistent_returns_404(self, client: AsyncClient):
        """Deleting a non-existent preference returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.delete(f"/api/v1/preferences/{fake_id}")
        assert resp.status_code == 404, resp.text
