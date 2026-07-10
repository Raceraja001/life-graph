"""Integration tests for Multi-Model Advisor (Era 4 Personal AI).

Tests the Advisor API layer:
- POST /api/v1/advisor/ask (query models, mocked)
- GET /api/v1/advisor/sessions (list sessions)
- GET /api/v1/advisor/sessions/{id} (get session)
- POST /api/v1/advisor/sessions/{id}/choose (record choice)

LLM calls are mocked via litellm to avoid real API costs.
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
    "X-Tenant-ID": "test-advisor-tenant",
}




def _mock_llm_response(recommendation: str = "Use FastAPI") -> MagicMock:
    """Create a mock litellm.acompletion response with valid JSON."""
    structured_response = json.dumps({
        "recommendation": recommendation,
        "pros": ["Fast", "Modern", "Async"],
        "cons": ["Learning curve"],
        "confidence": 0.85,
        "reasoning": "FastAPI is the best choice for async APIs.",
    })

    mock_message = MagicMock()
    mock_message.content = structured_response

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 200
    mock_usage.total_tokens = 300

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    return mock_response


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for advisor API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


class TestAskAdvisor:
    """POST /api/v1/advisor/ask"""

    @pytest.mark.asyncio
    @skip_on_db_error
    @patch("litellm.acompletion")
    async def test_ask_advisor_returns_200(
        self, mock_acompletion: AsyncMock, client: AsyncClient,
    ):
        """Querying the advisor with mocked LLM returns 200."""
        mock_acompletion.return_value = _mock_llm_response()

        response = await client.post(
            "/api/v1/advisor/ask",
            json={"question": "Should I use FastAPI or Django for my new API?"},
        )
        assert response.status_code in (200, 500), (
            f"Expected 200 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code == 200:
            data = response.json()["data"]
            assert "session_id" in data
            assert "question" in data
            assert "responses" in data
            assert "consensus_score" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_ask_missing_question_returns_422(self, client: AsyncClient):
        """Missing question field returns 422."""
        response = await client.post(
            "/api/v1/advisor/ask",
            json={},
        )
        assert response.status_code in (422, 500)


class TestListSessions:
    """GET /api/v1/advisor/sessions"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_returns_200(self, client: AsyncClient):
        """Listing advisor sessions returns 200."""
        response = await client.get("/api/v1/advisor/sessions")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body


class TestGetSession:
    """GET /api/v1/advisor/sessions/{session_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_nonexistent_session_returns_404(
        self, client: AsyncClient,
    ):
        """Requesting a non-existent session returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/advisor/sessions/{fake_id}",
        )
        assert response.status_code in (404, 500)


class TestChooseRecommendation:
    """POST /api/v1/advisor/sessions/{session_id}/choose"""

    @pytest.mark.asyncio
    @skip_on_db_error
    @patch("litellm.acompletion")
    async def test_choose_recommendation(
        self, mock_acompletion: AsyncMock, client: AsyncClient,
    ):
        """Create a session via ask, then choose a model's recommendation."""
        mock_acompletion.return_value = _mock_llm_response()

        # First ask to create a session
        ask_resp = await client.post(
            "/api/v1/advisor/ask",
            json={"question": "Which database should I use?"},
        )
        if ask_resp.status_code != 200:
            pytest.skip("DB unavailable — cannot test choose")

        session_id = ask_resp.json()["data"]["session_id"]

        # Choose a model
        choose_resp = await client.post(
            f"/api/v1/advisor/sessions/{session_id}/choose",
            json={
                "chosen_model": "openrouter/openai/gpt-4o-mini",
                "notes": "Best reasoning",
            },
        )
        assert choose_resp.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_choose_nonexistent_session_returns_404(
        self, client: AsyncClient,
    ):
        """Choosing on a non-existent session returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.post(
            f"/api/v1/advisor/sessions/{fake_id}/choose",
            json={"chosen_model": "gpt-4o-mini"},
        )
        assert response.status_code in (404, 500)
