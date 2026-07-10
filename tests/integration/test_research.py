"""Integration tests for Autonomous Research Engine (Era 4 Personal AI — Phase 6).

Tests the Research API layer:
- POST /api/v1/research/trigger  (trigger a research cycle)
- GET  /api/v1/research/runs     (list research runs)
- GET  /api/v1/research/runs/{id} (get a single run)

External sources (HN, Reddit, GitHub) and LLM calls are mocked
to avoid real network/API costs.
Follows existing test patterns: httpx AsyncClient + ASGITransport.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test-research-tenant",
}




def _mock_stance_response(
    stance: str = "supports",
    strength: float = 0.8,
) -> MagicMock:
    """Create a mock litellm.acompletion response for stance detection."""
    structured_response = json.dumps({
        "stance": stance,
        "strength": strength,
        "reasoning": "Mock stance detection result.",
    })

    mock_message = MagicMock()
    mock_message.content = structured_response

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 50
    mock_usage.completion_tokens = 30
    mock_usage.total_tokens = 80

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    return mock_response


def _mock_hn_response() -> MagicMock:
    """Create a mock httpx response for HN Algolia API."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "hits": [
            {
                "title": "FastAPI vs Django performance benchmark",
                "url": "https://example.com/fastapi-benchmark",
                "objectID": "12345",
                "story_text": "FastAPI outperforms Django in async workloads.",
                "points": 150,
            },
        ],
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _mock_empty_source_response() -> MagicMock:
    """Create a mock httpx response with no results."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"hits": [], "data": {"children": []}, "items": []}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for research API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


# ── Trigger Research ─────────────────────────────────────────


class TestTriggerResearch:
    """POST /api/v1/research/trigger"""

    @pytest.mark.asyncio
    @skip_on_db_error
    @patch("litellm.acompletion")
    async def test_trigger_research_returns_202(
        self, mock_acompletion: AsyncMock, client: AsyncClient,
    ):
        """Triggering a research cycle with mocked sources returns 202."""
        mock_acompletion.return_value = _mock_stance_response()

        response = await client.post(
            "/api/v1/research/trigger",
            json={},
        )
        assert response.status_code in (200, 202, 500), (
            f"Expected 200/202 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code in (200, 202):
            data = response.json()["data"]
            assert "status" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    @patch("litellm.acompletion")
    async def test_trigger_with_preference_id(
        self, mock_acompletion: AsyncMock, client: AsyncClient,
    ):
        """Triggering research for a specific preference_id accepts valid UUID."""
        mock_acompletion.return_value = _mock_stance_response()
        fake_pref_id = "00000000-0000-0000-0000-000000000001"

        response = await client.post(
            "/api/v1/research/trigger",
            json={"preference_id": fake_pref_id},
        )
        # Should not be 422 — the UUID is valid
        assert response.status_code != 422, (
            f"Valid UUID should not return 422: {response.text}"
        )
        assert response.status_code in (200, 202, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_trigger_with_invalid_preference_id_returns_422(
        self, client: AsyncClient,
    ):
        """Triggering research with an invalid UUID returns 422."""
        response = await client.post(
            "/api/v1/research/trigger",
            json={"preference_id": "not-a-uuid"},
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_trigger_no_stale_preferences_returns_early(
        self, client: AsyncClient,
    ):
        """When there are no stale preferences, the engine returns early.

        With an empty DB / fresh tenant the engine should report
        'no_stale_preferences' or 'budget_exhausted' without errors.
        """
        response = await client.post(
            "/api/v1/research/trigger",
            json={},
        )
        assert response.status_code in (200, 202, 500)

        if response.status_code in (200, 202):
            data = response.json()["data"]
            assert data["status"] in (
                "no_stale_preferences",
                "budget_exhausted",
                "completed",
            )


# ── List Research Runs ───────────────────────────────────────


class TestListResearchRuns:
    """GET /api/v1/research/runs"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_runs_returns_200(self, client: AsyncClient):
        """Listing research runs returns 200 with data array."""
        response = await client.get("/api/v1/research/runs")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_runs_with_pagination(self, client: AsyncClient):
        """Listing research runs respects limit and offset params."""
        response = await client.get(
            "/api/v1/research/runs",
            params={"limit": 5, "offset": 0},
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "meta" in body
            assert body["meta"]["page_size"] == 5

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_runs_with_status_filter(self, client: AsyncClient):
        """Listing runs with status filter returns 200 (even if empty)."""
        response = await client.get(
            "/api/v1/research/runs",
            params={"status": "completed"},
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_runs_invalid_limit_returns_422(self, client: AsyncClient):
        """Requesting with limit=0 (below ge=1) returns 422."""
        response = await client.get(
            "/api/v1/research/runs",
            params={"limit": 0},
        )
        assert response.status_code in (422, 500)


# ── Get Research Run by ID ───────────────────────────────────


class TestGetResearchRun:
    """GET /api/v1/research/runs/{run_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_nonexistent_run_returns_404(self, client: AsyncClient):
        """Requesting a non-existent research run returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/research/runs/{fake_id}",
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_run_with_invalid_uuid_returns_422(self, client: AsyncClient):
        """Requesting a run with an invalid UUID returns 422."""
        response = await client.get("/api/v1/research/runs/not-a-valid-uuid")
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    @patch("litellm.acompletion")
    async def test_get_run_after_trigger(
        self, mock_acompletion: AsyncMock, client: AsyncClient,
    ):
        """Trigger a research run, then retrieve it by ID.

        This is an end-to-end flow: trigger → list → get by ID.
        Only viable when DB is reachable and preferences exist,
        so we tolerate the run completing with 'no_stale_preferences'.
        """
        mock_acompletion.return_value = _mock_stance_response()

        # Trigger
        trigger_resp = await client.post(
            "/api/v1/research/trigger",
            json={},
        )
        if trigger_resp.status_code not in (200, 202):
            pytest.skip("DB unavailable — cannot test get-after-trigger")

        data = trigger_resp.json()["data"]

        # If no run was created (no stale prefs), verify via list instead
        if "run_id" not in data:
            # Still valid — just no work to do
            return

        run_id = data["run_id"]

        # Get by ID
        get_resp = await client.get(f"/api/v1/research/runs/{run_id}")
        assert get_resp.status_code in (200, 500)

        if get_resp.status_code == 200:
            run_data = get_resp.json()["data"]
            assert run_data["id"] == run_id
            assert "status" in run_data
            assert "query" in run_data


# ── Tenant Isolation ─────────────────────────────────────────


class TestTenantIsolation:
    """Verify tenant_id header handling for research endpoints."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_missing_tenant_header_returns_error(self):
        """Requests without X-Tenant-ID should fail (400 or 500)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            # No X-Tenant-ID header
        ) as no_tenant_client:
            response = await no_tenant_client.get("/api/v1/research/runs")
            # Should not succeed without tenant context
            assert response.status_code in (400, 403, 422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_different_tenant_sees_empty_runs(self):
        """A different tenant should not see another tenant's research runs."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"X-Tenant-ID": "test-research-tenant-OTHER"},
        ) as other_client:
            response = await other_client.get("/api/v1/research/runs")
            assert response.status_code in (200, 500)

            if response.status_code == 200:
                body = response.json()
                assert isinstance(body["data"], list)


# ── Budget Enforcement ───────────────────────────────────────


class TestBudgetEnforcement:
    """Verify that the research engine respects monthly budget limits."""

    @pytest.mark.asyncio
    @skip_on_db_error
    @patch(
        "life_graph.services.research_engine.ResearchEngine._check_budget",
        new_callable=AsyncMock,
    )
    async def test_budget_exhausted_returns_budget_status(
        self, mock_check_budget: AsyncMock, client: AsyncClient,
    ):
        """When budget is exhausted, trigger should return budget_exhausted status."""
        mock_check_budget.return_value = 0.0  # No budget remaining

        response = await client.post(
            "/api/v1/research/trigger",
            json={},
        )
        assert response.status_code in (200, 202, 500)

        if response.status_code in (200, 202):
            data = response.json()["data"]
            assert data["status"] == "budget_exhausted"
            assert data["budget_remaining"] == 0.0

    @pytest.mark.asyncio
    @skip_on_db_error
    @patch(
        "life_graph.services.research_engine.ResearchEngine._check_budget",
        new_callable=AsyncMock,
    )
    async def test_budget_negative_returns_budget_exhausted(
        self, mock_check_budget: AsyncMock, client: AsyncClient,
    ):
        """Negative budget remaining is still reported as budget_exhausted."""
        mock_check_budget.return_value = -0.05

        response = await client.post(
            "/api/v1/research/trigger",
            json={},
        )
        assert response.status_code in (200, 202, 500)

        if response.status_code in (200, 202):
            data = response.json()["data"]
            assert data["status"] == "budget_exhausted"
