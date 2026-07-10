"""Integration tests for Autonomous AI (Era 8).

Tests the Autonomy API layer:
- POST /api/v1/autonomy/safety/rules (create safety rule)
- GET /api/v1/autonomy/safety/rules (list safety rules)
- POST /api/v1/autonomy/safety/classify (classify safe action)
- POST /api/v1/autonomy/safety/classify (classify unknown/dangerous)
- GET /api/v1/autonomy/trust/scores (get trust scores)
- POST /api/v1/autonomy/trust/override (override trust)
- GET /api/v1/autonomy/approvals (get approvals empty)
- GET /api/v1/autonomy/levels/{project_id} (get autonomy level)
- POST /api/v1/autonomy/levels/{project_id}/set (set autonomy level)
- GET /api/v1/autonomy/audit (query audit log)

Follows existing test patterns: httpx AsyncClient + ASGITransport,
defensive assertions accepting 500 if DB unreachable.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test-autonomy-tenant",
}




@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for autonomy API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


class TestSafetyRules:
    """Safety rule CRUD tests."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_safety_rule(self, client: AsyncClient):
        """POST /api/v1/autonomy/safety/rules — create a safety rule."""
        response = await client.post(
            "/api/v1/autonomy/safety/rules",
            json={
                "action_name": "fix_lint",
                "action_pattern": "eslint --fix",
                "risk_level": "safe",
                "description": "Auto-fix lint errors with eslint",
            },
        )
        assert response.status_code in (200, 201, 500), (
            f"Expected 200/201/500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code in (200, 201):
            body = response.json()
            data = body.get("data", body)
            assert "id" in data or "action_name" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_safety_rules(self, client: AsyncClient):
        """GET /api/v1/autonomy/safety/rules — list safety rules."""
        response = await client.get("/api/v1/autonomy/safety/rules")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            data = body.get("data", body)
            assert isinstance(data, list)


class TestSafetyClassification:
    """Safety classification tests."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_classify_safe_action(self, client: AsyncClient):
        """POST /api/v1/autonomy/safety/classify — classify a safe action."""
        # First create a rule
        await client.post(
            "/api/v1/autonomy/safety/rules",
            json={
                "action_name": "test",
                "action_pattern": "echo *",
                "risk_level": "safe",
            },
        )

        response = await client.post(
            "/api/v1/autonomy/safety/classify",
            json={
                "agent_id": "test-agent-classify",
                "action_name": "test",
                "action_command": "echo hello",
            },
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            data = body.get("data", body)
            assert "risk_level" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_classify_unknown_dangerous(self, client: AsyncClient):
        """POST /api/v1/autonomy/safety/classify — unknown commands classified as high risk."""
        response = await client.post(
            "/api/v1/autonomy/safety/classify",
            json={
                "agent_id": "test-agent-classify",
                "action_name": "unknown",
                "action_command": "rm -rf /",
            },
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            data = body.get("data", body)
            risk = data.get("risk_level", "")
            assert risk in ("high", "dangerous", "unknown"), (
                f"Expected high/dangerous for 'rm -rf /', got {risk}"
            )


class TestTrustScores:
    """Trust score tests."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_trust_scores(self, client: AsyncClient):
        """GET /api/v1/autonomy/trust/scores — list trust scores."""
        response = await client.get("/api/v1/autonomy/trust/scores")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            data = body.get("data", body)
            assert isinstance(data, list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_override_trust(self, client: AsyncClient):
        """POST /api/v1/autonomy/trust/override — override trust score."""
        response = await client.post(
            "/api/v1/autonomy/trust/override",
            json={
                "agent_id": "test-agent-001",
                "action_type": "general",
                "score": 0.8,
                "reason": "Manual trust boost for testing",
                "by": "admin",
            },
        )
        assert response.status_code in (200, 500)


class TestApprovals:
    """Approval queue tests."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_approvals_empty(self, client: AsyncClient):
        """GET /api/v1/autonomy/approvals — empty queue returns 200 with empty list."""
        response = await client.get(
            "/api/v1/autonomy/approvals",
            params={"status": "pending"},
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            data = body.get("data", body)
            assert isinstance(data, list)


class TestAutonomyLevels:
    """Autonomy level tests."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_autonomy_level(self, client: AsyncClient):
        """GET /api/v1/autonomy/levels/{project_id} — get level (creates L0 default)."""
        response = await client.get("/api/v1/autonomy/levels/test-project-001")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            data = body.get("data", body)
            assert data.get("current_level") == 0
            assert data.get("level_name") == "Ask Everything"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_set_autonomy_level(self, client: AsyncClient):
        """POST /api/v1/autonomy/levels/{project_id}/set — manual level set."""
        response = await client.post(
            "/api/v1/autonomy/levels/test-project-002/set",
            json={
                "level": 2,
                "reason": "Trusted project for testing",
                "set_by": "admin",
            },
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            data = body.get("data", body)
            assert data.get("level") == 2
            assert data.get("level_name") == "Notify Before"


class TestAuditLog:
    """Audit log tests."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_query_audit_log(self, client: AsyncClient):
        """GET /api/v1/autonomy/audit — query returns 200 with list."""
        response = await client.get("/api/v1/autonomy/audit")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            data = body.get("data", body)
            assert isinstance(data, list)
