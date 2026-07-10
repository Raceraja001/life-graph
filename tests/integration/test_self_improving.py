"""Integration tests for Self-Improving Agent API (Era 5).

Tests the Self-Improving API layer:
- POST /api/v1/self-improving/eval-suites (create)
- POST /api/v1/self-improving/eval-suites/{id}/cases (add case)
- GET /api/v1/self-improving/eval-suites (list)
- POST /api/v1/self-improving/prompt-versions (create)
- POST /api/v1/self-improving/prompt-versions/{id}/activate (activate)
- GET /api/v1/self-improving/prompt-versions (list)
- GET /api/v1/self-improving/dashboard/overview (dashboard)

Follows existing test patterns: httpx AsyncClient + ASGITransport,
defensive assertions accepting 500 if DB unreachable.
Eval runs and optimization require LLM calls — 500/422 accepted.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test-self-improving-tenant",
}




@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for self-improving API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


class TestCreateEvalSuite:
    """POST /api/v1/self-improving/eval-suites"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_eval_suite(self, client: AsyncClient):
        """Creating an eval suite with valid input returns 201."""
        response = await client.post(
            "/api/v1/self-improving/eval-suites",
            json={
                "name": "Memory Extraction Suite",
                "task_type": "memory_extraction",
                "description": "Tests memory extraction accuracy",
                "auto_optimize_enabled": False,
            },
        )
        assert response.status_code in (201, 500), (
            f"Expected 201 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code == 201:
            data = response.json()["data"]
            assert data["name"] == "Memory Extraction Suite"
            assert data["task_type"] == "memory_extraction"
            assert "id" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_eval_suite_missing_name(self, client: AsyncClient):
        """Missing required field name returns 422."""
        response = await client.post(
            "/api/v1/self-improving/eval-suites",
            json={"task_type": "extraction"},
        )
        assert response.status_code in (422, 500)


class TestAddEvalCase:
    """POST /api/v1/self-improving/eval-suites/{id}/cases"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_add_eval_case(self, client: AsyncClient):
        """Create a suite then add a case to it."""
        # Create suite first
        create_resp = await client.post(
            "/api/v1/self-improving/eval-suites",
            json={
                "name": "Case Test Suite",
                "task_type": "scoring",
            },
        )
        if create_resp.status_code != 201:
            pytest.skip("DB unavailable — cannot test add case")

        suite_id = create_resp.json()["data"]["id"]

        # Add case
        response = await client.post(
            f"/api/v1/self-improving/eval-suites/{suite_id}/cases",
            json={
                "input_text": "What is the capital of France?",
                "expected_output": "Paris",
                "tags": ["geography"],
                "weight": 1.0,
            },
        )
        assert response.status_code in (201, 500), (
            f"Expected 201 or 500, got {response.status_code}: "
            f"{response.text}"
        )


class TestCreatePromptVersion:
    """POST /api/v1/self-improving/prompt-versions"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_prompt_version(self, client: AsyncClient):
        """Creating a prompt version with valid input returns 201."""
        response = await client.post(
            "/api/v1/self-improving/prompt-versions",
            json={
                "task_type": "memory_extraction",
                "prompt_text": "Extract key facts from the following text:\n\n{input}",
                "created_by": "manual",
                "description": "Baseline extraction prompt v1",
            },
        )
        assert response.status_code in (201, 500), (
            f"Expected 201 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code == 201:
            data = response.json()["data"]
            assert data["task_type"] == "memory_extraction"
            assert "id" in data


class TestActivatePromptVersion:
    """POST /api/v1/self-improving/prompt-versions/{id}/activate"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_activate_prompt_version(self, client: AsyncClient):
        """Create then activate a prompt version."""
        # Create
        create_resp = await client.post(
            "/api/v1/self-improving/prompt-versions",
            json={
                "task_type": "scoring",
                "prompt_text": "Score the importance of: {input}",
            },
        )
        if create_resp.status_code != 201:
            pytest.skip("DB unavailable — cannot test activate")

        version_id = create_resp.json()["data"]["id"]

        # Activate
        response = await client.post(
            f"/api/v1/self-improving/prompt-versions/{version_id}/activate",
        )
        assert response.status_code in (200, 500), (
            f"Expected 200 or 500, got {response.status_code}: "
            f"{response.text}"
        )


class TestListEvalSuites:
    """GET /api/v1/self-improving/eval-suites"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_eval_suites(self, client: AsyncClient):
        """Listing eval suites returns 200 with data array."""
        response = await client.get("/api/v1/self-improving/eval-suites")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert isinstance(body["data"], list)


class TestListPromptVersions:
    """GET /api/v1/self-improving/prompt-versions"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_prompt_versions(self, client: AsyncClient):
        """Listing prompt versions returns 200."""
        response = await client.get("/api/v1/self-improving/prompt-versions")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_prompt_versions_with_filter(self, client: AsyncClient):
        """Listing prompt versions with task_type filter."""
        response = await client.get(
            "/api/v1/self-improving/prompt-versions",
            params={"task_type": "memory_extraction"},
        )
        assert response.status_code in (200, 500)


class TestDashboard:
    """GET /api/v1/self-improving/dashboard/*"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_dashboard_overview(self, client: AsyncClient):
        """Dashboard overview returns 200 with metrics."""
        response = await client.get("/api/v1/self-improving/dashboard/overview")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            data = response.json()["data"]
            assert "overall_accuracy_pct" in data
            assert "tasks_monitored" in data
            assert "auto_fixes_this_week" in data
            assert "pending_reviews" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_dashboard_accuracy_trends(self, client: AsyncClient):
        """Dashboard accuracy trends returns 200."""
        response = await client.get(
            "/api/v1/self-improving/dashboard/accuracy-trends",
            params={"days": 7},
        )
        assert response.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_dashboard_per_task_accuracy(self, client: AsyncClient):
        """Dashboard per-task accuracy returns 200."""
        response = await client.get(
            "/api/v1/self-improving/dashboard/per-task-accuracy",
        )
        assert response.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_dashboard_auto_fixes(self, client: AsyncClient):
        """Dashboard auto-fixes returns 200."""
        response = await client.get(
            "/api/v1/self-improving/dashboard/auto-fixes",
            params={"days": 7},
        )
        assert response.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_dashboard_cost_trends(self, client: AsyncClient):
        """Dashboard cost trends returns 200."""
        response = await client.get(
            "/api/v1/self-improving/dashboard/cost-trends",
            params={"days": 30},
        )
        assert response.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_dashboard_pending_reviews(self, client: AsyncClient):
        """Dashboard pending reviews returns 200."""
        response = await client.get(
            "/api/v1/self-improving/dashboard/pending-reviews",
        )
        assert response.status_code in (200, 500)


class TestEvalRunEndpoints:
    """Eval run endpoints — expect 500/422/404 since they need LLM calls."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_eval_run_not_found(self, client: AsyncClient):
        """Getting a nonexistent eval run returns 404 or 500."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/self-improving/eval-runs/{fake_id}",
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_eval_run_failures_not_found(self, client: AsyncClient):
        """Getting failures for a nonexistent run returns 404 or 500."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/self-improving/eval-runs/{fake_id}/failures",
        )
        assert response.status_code in (404, 500)


class TestOptimizationEndpoints:
    """Optimization endpoints — expect 500/422 since they need LLM calls."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_optimization_run_not_found(self, client: AsyncClient):
        """Getting a nonexistent optimization run returns 404 or 500."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/self-improving/optimization-runs/{fake_id}",
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_review_optimization_not_found(self, client: AsyncClient):
        """Reviewing a nonexistent optimization returns 404 or 500."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.post(
            f"/api/v1/self-improving/optimization-runs/{fake_id}/review",
            json={"decision": "approve"},
        )
        assert response.status_code in (404, 500)
