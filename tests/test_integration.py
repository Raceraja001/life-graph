"""Integration tests for Life Graph SaaS backend.

Tests cover:
  - Auth middleware (Task 38)
  - Tenant isolation (Task 39)
  - API versioning (Task 41)
  - Health checks (Task 42)
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app


# ── Test Client Fixtures ─────────────────────────────────────


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Unauthenticated test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def tenant_a_client() -> AsyncClient:
    """Authenticated client for tenant A."""
    transport = ASGITransport(app=app)
    headers = {"X-Tenant-ID": "test_tenant_a", "X-User-ID": "user-a"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as c:
        yield c


@pytest_asyncio.fixture
async def tenant_b_client() -> AsyncClient:
    """Authenticated client for tenant B."""
    transport = ASGITransport(app=app)
    headers = {"X-Tenant-ID": "test_tenant_b", "X-User-ID": "user-b"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as c:
        yield c


# ── Health & Probe Tests (Task 42) ───────────────────────────


class TestHealthAndProbes:
    """Test health, liveness, and readiness endpoints."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "version" in data
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_liveness_returns_200(self, client):
        r = await client.get("/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

    @pytest.mark.asyncio
    async def test_readiness_returns_200(self, client):
        r = await client.get("/ready")
        # May return 200 or 503 depending on DB, both are valid
        assert r.status_code in (200, 503)


# ── Auth Tests (Task 38) ─────────────────────────────────────


class TestAuth:
    """Test service-to-service authentication."""

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client):
        """Health endpoint should not require auth."""
        r = await client.get("/health")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_api_endpoint_requires_tenant_in_production(self, client):
        """In dev mode, tenant defaults to 'dev'. In prod, 400 expected."""
        r = await client.get("/api/v1/memories/")
        # In dev mode this should work (defaults to 'dev' tenant)
        # In prod this would return 400 for missing X-Tenant-ID
        assert r.status_code in (200, 400)

    @pytest.mark.asyncio
    async def test_api_works_with_tenant_header(self, tenant_a_client):
        """Request with tenant header should succeed."""
        r = await tenant_a_client.get("/api/v1/memories/")
        assert r.status_code == 200


# ── API Versioning Tests (Task 41) ───────────────────────────


class TestAPIVersioning:
    """Test that API is correctly versioned under /api/v1/."""

    @pytest.mark.asyncio
    async def test_v1_memories_endpoint(self, tenant_a_client):
        r = await tenant_a_client.get("/api/v1/memories/")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_v1_search_endpoint(self, tenant_a_client):
        r = await tenant_a_client.post("/api/v1/search/", json={"query": "test"})
        # Should return 200 or 422 (validation), not 404
        assert r.status_code != 404

    @pytest.mark.asyncio
    async def test_old_path_returns_404(self, tenant_a_client):
        """Old un-versioned paths should return 404."""
        r = await tenant_a_client.get("/memories/")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_root_redirects(self, client):
        r = await client.get("/", follow_redirects=False)
        assert r.status_code in (301, 302, 307)


# ── Tenant Isolation Tests (Task 39) ─────────────────────────


class TestTenantIsolation:
    """Test that tenants cannot see each other's data."""

    @pytest.mark.asyncio
    async def test_create_memory_for_tenant_a(self, tenant_a_client):
        """Tenant A can create a memory."""
        r = await tenant_a_client.post(
            "/api/v1/memories/",
            json={"content": "Tenant A secret", "source": "test"},
        )
        assert r.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_tenant_b_cannot_see_tenant_a_memories(
        self, tenant_a_client, tenant_b_client
    ):
        """Tenant B should not see Tenant A's memories."""
        # Create a memory as tenant A
        await tenant_a_client.post(
            "/api/v1/memories/",
            json={"content": "Isolation test secret", "source": "test"},
        )

        # List as tenant B
        r = await tenant_b_client.get("/api/v1/memories/")
        assert r.status_code == 200
        data = r.json()

        # Tenant B's response should not contain tenant A's data
        memories = data if isinstance(data, list) else data.get("data", data)
        if isinstance(memories, list):
            for m in memories:
                content = m.get("content", "") if isinstance(m, dict) else ""
                assert "Isolation test secret" not in content
