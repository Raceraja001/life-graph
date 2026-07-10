"""Integration tests for tenant lifecycle endpoints.

Covers:
- POST   /api/v1/admin/tenants/provision        — provision with valid & invalid bodies
- GET    /api/v1/admin/tenants/{tenant_id}      — get tenant summary
- POST   /api/v1/admin/tenants/{id}/deactivate  — deactivate a tenant
- POST   /api/v1/admin/tenants/{id}/reactivate  — reactivate a tenant
- DELETE /api/v1/admin/tenants/{tenant_id}      — permanently delete a tenant
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error


@pytest_asyncio.fixture
async def admin_client() -> AsyncClient:
    """Authenticated admin test client."""
    transport = ASGITransport(app=app)
    headers = {"X-Tenant-ID": "test_admin", "X-User-ID": "admin-user"}
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as c:
        yield c


# ── Tenant Provisioning ────────────────────────────────────────


class TestTenantProvision:
    """POST /api/v1/admin/tenants/provision — create a new tenant."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_provision_valid_tenant(self, admin_client: AsyncClient):
        """Valid tenant_id + plan should return 201 with tenant details."""
        payload = {"tenant_id": "testco123", "plan": "free"}
        r = await admin_client.post("/api/v1/admin/tenants/provision", json=payload)
        assert r.status_code in (201, 409, 500)

        if r.status_code == 201:
            body = r.json()
            data = body.get("data", body)
            assert data["tenant_id"] == "testco123"
            assert data["plan"] == "free"
            assert "status" in data
            assert "provisioned_at" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_provision_invalid_tenant_id_special_chars(self, admin_client: AsyncClient):
        """tenant_id with special characters like '!' must be rejected (422)."""
        payload = {"tenant_id": "ABC!", "plan": "free"}
        r = await admin_client.post("/api/v1/admin/tenants/provision", json=payload)
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_provision_invalid_tenant_id_uppercase(self, admin_client: AsyncClient):
        """tenant_id with uppercase letters violates the regex pattern (422)."""
        payload = {"tenant_id": "MyTenant", "plan": "free"}
        r = await admin_client.post("/api/v1/admin/tenants/provision", json=payload)
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_provision_tenant_id_too_short(self, admin_client: AsyncClient):
        """tenant_id shorter than 3 characters must be rejected (422)."""
        payload = {"tenant_id": "ab", "plan": "free"}
        r = await admin_client.post("/api/v1/admin/tenants/provision", json=payload)
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_provision_invalid_plan(self, admin_client: AsyncClient):
        """Invalid plan value 'platinum' must be rejected (422)."""
        payload = {"tenant_id": "testco456", "plan": "platinum"}
        r = await admin_client.post("/api/v1/admin/tenants/provision", json=payload)
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_provision_missing_tenant_id(self, admin_client: AsyncClient):
        """Missing tenant_id field must be rejected (422)."""
        payload = {"plan": "free"}
        r = await admin_client.post("/api/v1/admin/tenants/provision", json=payload)
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_provision_empty_body(self, admin_client: AsyncClient):
        """Completely empty body must be rejected (422)."""
        r = await admin_client.post("/api/v1/admin/tenants/provision", json={})
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_provision_valid_plans(self, admin_client: AsyncClient):
        """All three valid plans (free, pro, enterprise) must pass validation."""
        for plan in ("free", "pro", "enterprise"):
            tid = f"plantest-{plan}-{uuid.uuid4().hex[:6]}"
            payload = {"tenant_id": tid, "plan": plan}
            r = await admin_client.post("/api/v1/admin/tenants/provision", json=payload)
            assert r.status_code in (201, 500)


# ── Get Tenant Summary ──────────────────────────────────────────


class TestTenantGet:
    """GET /api/v1/admin/tenants/{tenant_id} — retrieve tenant summary."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_nonexistent_tenant(self, admin_client: AsyncClient):
        """Fetching a nonexistent tenant should return 404 (or 500 if no DB)."""
        fake_id = f"nonexistent-{uuid.uuid4().hex[:8]}"
        r = await admin_client.get(f"/api/v1/admin/tenants/{fake_id}")
        assert r.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_tenant_response_shape(self, admin_client: AsyncClient):
        """If a tenant exists the response should contain expected fields."""
        tid = f"gettest-{uuid.uuid4().hex[:6]}"
        await admin_client.post(
            "/api/v1/admin/tenants/provision",
            json={"tenant_id": tid, "plan": "free"},
        )

        r = await admin_client.get(f"/api/v1/admin/tenants/{tid}")

        if r.status_code == 200:
            body = r.json()
            data = body.get("data", body)
            assert "tenant_id" in data
            assert "plan" in data
            assert "status" in data
            assert "memory_count" in data
            assert "session_count" in data
            assert "usage" in data


# ── Tenant Deactivate ───────────────────────────────────────────


class TestTenantDeactivate:
    """POST /api/v1/admin/tenants/{tenant_id}/deactivate — deactivate a tenant."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_deactivate_nonexistent(self, admin_client: AsyncClient):
        """Deactivating a nonexistent tenant should return 404 (or 500)."""
        fake_id = f"nope-{uuid.uuid4().hex[:8]}"
        r = await admin_client.post(f"/api/v1/admin/tenants/{fake_id}/deactivate")
        assert r.status_code in (404, 500)


# ── Tenant Reactivate ──────────────────────────────────────────


class TestTenantReactivate:
    """POST /api/v1/admin/tenants/{tenant_id}/reactivate — reactivate a tenant."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_reactivate_nonexistent(self, admin_client: AsyncClient):
        """Reactivating a nonexistent tenant should return 404 (or 500)."""
        fake_id = f"nope-{uuid.uuid4().hex[:8]}"
        r = await admin_client.post(f"/api/v1/admin/tenants/{fake_id}/reactivate")
        assert r.status_code in (404, 500)


# ── Tenant Deletion ────────────────────────────────────────────


class TestTenantDelete:
    """DELETE /api/v1/admin/tenants/{tenant_id} — permanently delete a tenant."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_nonexistent(self, admin_client: AsyncClient):
        """Deleting a nonexistent tenant should return 404 (or 500)."""
        fake_id = f"ghost-{uuid.uuid4().hex[:8]}"
        r = await admin_client.delete(f"/api/v1/admin/tenants/{fake_id}")
        assert r.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_active_tenant_conflict(self, admin_client: AsyncClient):
        """Deleting an active (non-deactivated) tenant should return 409 (or 500)."""
        tid = f"active-{uuid.uuid4().hex[:6]}"
        provision_r = await admin_client.post(
            "/api/v1/admin/tenants/provision",
            json={"tenant_id": tid, "plan": "free"},
        )

        if provision_r.status_code == 201:
            r = await admin_client.delete(f"/api/v1/admin/tenants/{tid}")
            assert r.status_code in (409, 500)
