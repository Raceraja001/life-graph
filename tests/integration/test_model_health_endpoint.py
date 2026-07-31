"""Integration tests for the free-LLM backend health status endpoint.

Covers:
- GET /api/v1/health/models (list of per-model health records; fail-open, so
  it may return 200 with an empty list even without Redis/DB configured).

Defensive per house convention: accept 500 when the DB is unreachable, but
never 422 for a valid request. See docs/specs (free-model resilience).
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test-model-health-tenant",
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


class TestModelHealth:
    @skip_on_db_error
    async def test_model_health_returns_list(self, client: AsyncClient):
        resp = await client.get("/api/v1/health/models")
        assert resp.status_code != 422, resp.text
        if resp.status_code == 200:
            assert isinstance(resp.json()["data"], list)
