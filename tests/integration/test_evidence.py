"""Integration tests for Evidence CRUD + semantic search (Era 4 Personal AI).

Tests the Evidence API layer:
- POST /api/v1/evidence/ (create with dedup)
- GET /api/v1/evidence/for-preference/{id} (list grouped by stance)
- GET /api/v1/evidence/{id} (get single)
- POST /api/v1/evidence/search (semantic search)
- DELETE /api/v1/evidence/{id} (soft delete)
- 409 on duplicate source_url

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
    "X-Tenant-ID": "test-evidence-tenant",
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for evidence API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


async def _create_preference(client: AsyncClient) -> str:
    """Helper: create a preference and return its ID."""
    resp = await client.post(
        "/api/v1/preferences/",
        json={
            "topic": "Evidence Test Pref",
            "choice": "TestChoice",
            "confidence": 0.8,
        },
    )
    return assert_ok(resp, 201)["data"]["id"]


class TestCreateEvidence:
    """POST /api/v1/evidence/"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_evidence_returns_201(self, client: AsyncClient):
        """Creating evidence linked to a preference returns 201."""
        pref_id = await _create_preference(client)

        response = await client.post(
            "/api/v1/evidence/",
            json={
                "preference_id": pref_id,
                "source_type": "benchmark",
                "source_url": "https://example.com/bench1",
                "source_title": "Performance Benchmark 2024",
                "stance": "supports",
                "summary": "Shows 2x throughput improvement",
            },
        )
        data = assert_ok(response, 201)["data"]
        assert data["stance"] == "supports"
        assert data["source_type"] == "benchmark"
        assert "id" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_duplicate_source_url_returns_409(self, client: AsyncClient):
        """Duplicate source_url for same preference returns 409."""
        pref_id = await _create_preference(client)

        evidence_data = {
            "preference_id": pref_id,
            "source_type": "article",
            "source_url": "https://example.com/unique-dedup-test",
            "summary": "First submission",
        }

        # First create should succeed
        resp1 = await client.post("/api/v1/evidence/", json=evidence_data)
        assert_ok(resp1, 201)

        # Second create with same source_url should return 409
        resp2 = await client.post("/api/v1/evidence/", json=evidence_data)
        assert resp2.status_code == 409, resp2.text


class TestListEvidence:
    """GET /api/v1/evidence/for-preference/{preference_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_evidence_grouped_by_stance(
        self,
        client: AsyncClient,
    ):
        """Evidence for a preference is returned grouped by stance."""
        pref_id = await _create_preference(client)

        # Create supporting evidence
        supporting = await client.post(
            "/api/v1/evidence/",
            json={
                "preference_id": pref_id,
                "source_type": "paper",
                "summary": "Supports the choice",
                "stance": "supports",
            },
        )
        assert_ok(supporting, 201)

        # Create contradicting evidence
        contradicting = await client.post(
            "/api/v1/evidence/",
            json={
                "preference_id": pref_id,
                "source_type": "blog",
                "summary": "Alternative is better",
                "stance": "contradicts",
            },
        )
        assert_ok(contradicting, 201)

        response = await client.get(
            f"/api/v1/evidence/for-preference/{pref_id}",
        )
        data = assert_ok(response, 200)["data"]
        assert "supports" in data
        assert "contradicts" in data
        assert "neutral" in data
        assert "net_score" in data
        assert "total_count" in data
        assert data["total_count"] == 2


class TestSearchEvidence:
    """POST /api/v1/evidence/search"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_evidence_returns_200(self, client: AsyncClient):
        """Semantic search returns 200 with data array."""
        response = await client.post(
            "/api/v1/evidence/search",
            json={"query": "performance benchmarks", "limit": 5},
        )
        body = assert_ok(response, 200)
        assert "data" in body
        assert isinstance(body["data"], list)


class TestDeleteEvidence:
    """DELETE /api/v1/evidence/{evidence_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_evidence_soft_delete(self, client: AsyncClient):
        """Soft-deleting evidence returns 204."""
        pref_id = await _create_preference(client)

        create_resp = await client.post(
            "/api/v1/evidence/",
            json={
                "preference_id": pref_id,
                "source_type": "reddit",
                "summary": "To be deleted",
            },
        )
        evidence_id = assert_ok(create_resp, 201)["data"]["id"]
        resp = await client.delete(f"/api/v1/evidence/{evidence_id}")
        assert resp.status_code == 204, resp.text

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_nonexistent_returns_404(self, client: AsyncClient):
        """Deleting non-existent evidence returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.delete(f"/api/v1/evidence/{fake_id}")
        assert resp.status_code == 404, resp.text
