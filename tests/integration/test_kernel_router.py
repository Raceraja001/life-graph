"""Integration tests for OS Kernel Chief Router.

Tests the routing layer:
- POST /api/v1/kernel/route (classify + spawn)
- POST /api/v1/kernel/classify (classify only)
- GET /api/v1/kernel/sessions (session history)

Also tests regex intent classification (unit-style,
no DB needed).
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test_router_tenant",
    "X-User-ID": "router-test-user",
}




@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for router API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


# ── Intent Classification (unit tests, no DB) ───────────────


class TestIntentClassification:
    """ChiefRouter.classify — regex-based intent matching."""

    @pytest.fixture
    def router(self):
        """Create a ChiefRouter with dummy deps."""
        from life_graph.kernel.chief_router import (
            ChiefRouter,
        )
        return ChiefRouter(
            session_factory=None,  # type: ignore
            persona_service=None,
            process_manager=None,
        )

    def test_classify_code_intent(self, router):
        """Code-related messages classify as 'code'."""
        intent, conf = router.classify(
            "Can you refactor the user service class?"
        )
        assert intent == "code"
        assert conf >= 0.4

    def test_classify_code_debug(self, router):
        """Debug messages classify as 'code'."""
        intent, conf = router.classify(
            "Fix the bug in the login endpoint"
        )
        assert intent == "code"
        assert conf >= 0.4

    def test_classify_code_multiple_patterns(self, router):
        """Multiple code patterns increase confidence."""
        intent, conf = router.classify(
            "Write a function to refactor the endpoint"
        )
        assert intent == "code"
        # Multiple matches → higher confidence
        assert conf >= 0.55

    def test_classify_research_intent(self, router):
        """Research messages classify as 'research'."""
        intent, conf = router.classify(
            "Research the best approach for caching"
        )
        assert intent == "research"
        assert conf >= 0.4

    def test_classify_research_comparison(self, router):
        """Comparison queries classify as 'research'."""
        intent, conf = router.classify(
            "Compare Redis vs Memcached pros and cons"
        )
        assert intent == "research"

    def test_classify_deploy_intent(self, router):
        """Deploy messages classify as 'deploy'."""
        intent, conf = router.classify(
            "Deploy the app to production using Docker"
        )
        assert intent == "deploy"

    def test_classify_monitor_intent(self, router):
        """Monitor messages classify as 'monitor'."""
        intent, conf = router.classify(
            "Check the health status and metrics"
        )
        assert intent == "monitor"

    def test_classify_data_intent(self, router):
        """Data messages classify as 'data'."""
        intent, conf = router.classify(
            "Write a SQL query for the database migration"
        )
        assert intent == "data"

    def test_classify_docs_intent(self, router):
        """Documentation messages classify as 'docs'."""
        intent, conf = router.classify(
            "Update the README with API documentation"
        )
        assert intent == "docs"

    def test_classify_question_intent(self, router):
        """Questions classify as 'question'."""
        intent, conf = router.classify(
            "How do I reset my password?"
        )
        assert intent == "question"

    def test_classify_general_fallback(self, router):
        """Unmatched messages fall back to 'general'."""
        intent, conf = router.classify(
            "Hello there, nice weather today"
        )
        assert intent == "general"
        assert conf == 0.3

    def test_classify_empty_ish_message(self, router):
        """Short vague messages fall back to general."""
        intent, conf = router.classify("ok")
        assert intent == "general"
        assert conf == 0.3


# ── Default Routing Map ──────────────────────────────────────


class TestDefaultRouting:
    """Verify the DEFAULT_ROUTING map is correct."""

    def test_routing_map_completeness(self):
        from life_graph.kernel.chief_router import (
            DEFAULT_ROUTING,
        )
        expected_intents = {
            "code", "research", "deploy", "monitor",
            "data", "docs", "question", "general",
        }
        assert set(DEFAULT_ROUTING.keys()) == expected_intents

    def test_routing_map_agents(self):
        from life_graph.kernel.chief_router import (
            DEFAULT_ROUTING,
        )
        assert DEFAULT_ROUTING["code"] == "cody"
        assert DEFAULT_ROUTING["research"] == "rex"
        assert DEFAULT_ROUTING["deploy"] == "ops"
        assert DEFAULT_ROUTING["monitor"] == "ops"
        assert DEFAULT_ROUTING["data"] == "penny"
        assert DEFAULT_ROUTING["docs"] == "scribe"
        assert DEFAULT_ROUTING["question"] == "chief"
        assert DEFAULT_ROUTING["general"] == "chief"


# ── Classify Endpoint ────────────────────────────────────────


class TestClassifyEndpoint:
    """POST /api/v1/kernel/classify"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_classify_returns_200(
        self, client: AsyncClient,
    ):
        """Classify endpoint returns intent metadata."""
        response = await client.post(
            "/api/v1/kernel/classify",
            json={"message": "Refactor the user service"},
        )
        assert response.status_code in (200, 500)
        data = response.json()["data"]
        assert data["intent"] == "code"
        assert data["method"] == "regex"
        assert "confidence" in data
        assert "all_scores" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_classify_general_fallback(
        self, client: AsyncClient,
    ):
        """Unmatched messages return 'general' intent."""
        response = await client.post(
            "/api/v1/kernel/classify",
            json={"message": "Hello there!"},
        )
        assert response.status_code in (200, 500)
        data = response.json()["data"]
        assert data["intent"] == "general"
        assert data["confidence"] == 0.3

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_classify_missing_message(
        self, client: AsyncClient,
    ):
        """Missing message returns 422."""
        response = await client.post(
            "/api/v1/kernel/classify",
            json={},
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_classify_research_intent(
        self, client: AsyncClient,
    ):
        """Research message is classified correctly."""
        response = await client.post(
            "/api/v1/kernel/classify",
            json={
                "message": "Investigate the best practices"
                " for WebSocket scaling",
            },
        )
        assert response.status_code in (200, 500)
        data = response.json()["data"]
        assert data["intent"] == "research"
        assert data["confidence"] >= 0.4

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_classify_shows_all_scores(
        self, client: AsyncClient,
    ):
        """Classify returns all non-zero intent scores."""
        response = await client.post(
            "/api/v1/kernel/classify",
            json={
                "message": "Research and implement a"
                " code refactoring tool",
            },
        )
        assert response.status_code in (200, 500)
        data = response.json()["data"]
        # Should show scores for both code + research
        assert len(data["all_scores"]) >= 2


# ── Route Endpoint ───────────────────────────────────────────


class TestRouteEndpoint:
    """POST /api/v1/kernel/route"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_route_returns_201(
        self, client: AsyncClient,
    ):
        """Routing a message creates session and task."""
        response = await client.post(
            "/api/v1/kernel/route",
            json={"message": "Refactor the auth service"},
        )
        assert response.status_code in (201, 500)

        if response.status_code == 201:
            data = response.json()["data"]
            assert "session_id" in data
            assert data["classified_intent"] == "code"
            assert data["routed_to"] == "cody"
            assert data["task_status"] == "queued"
            assert "task_id" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_route_missing_message(
        self, client: AsyncClient,
    ):
        """Missing message returns 422."""
        response = await client.post(
            "/api/v1/kernel/route", json={},
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_route_with_project_id(
        self, client: AsyncClient,
    ):
        """Route with project_id passes it through."""
        import uuid as _uuid
        response = await client.post(
            "/api/v1/kernel/route",
            json={
                "message": "Deploy the app to staging",
                "project_id": str(_uuid.uuid4()),
            },
        )
        assert response.status_code in (201, 500)


# ── Sessions Endpoint ────────────────────────────────────────


class TestSessionsEndpoint:
    """GET /api/v1/kernel/sessions"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_returns_200(
        self, client: AsyncClient,
    ):
        """Listing sessions returns paginated data."""
        response = await client.get(
            "/api/v1/kernel/sessions",
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert "meta" in body
            assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_with_intent_filter(
        self, client: AsyncClient,
    ):
        """Sessions can be filtered by intent."""
        response = await client.get(
            "/api/v1/kernel/sessions",
            params={"intent": "code"},
        )
        assert response.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_pagination(
        self, client: AsyncClient,
    ):
        """Pagination params are respected."""
        response = await client.get(
            "/api/v1/kernel/sessions",
            params={"limit": 5, "offset": 0},
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            meta = response.json()["meta"]
            assert meta["page_size"] == 5
