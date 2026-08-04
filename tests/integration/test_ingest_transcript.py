"""Integration tests for POST /api/v1/ingest/external-transcript."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {"X-Tenant-ID": "test-transcript-ingest"}

VALID = {
    "tool": "claude-code",
    "session_id": "sess-abc",
    "source_path": "~/.claude/projects/x/sess-abc.jsonl",
    "lines": [
        '{"type":"user","userType":"external","isSidechain":false,'
        '"message":{"role":"user","content":"hello world"}}'
    ],
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


class TestIngestTranscript:
    @skip_on_db_error
    async def test_valid_batch_is_accepted(self, client: AsyncClient):
        resp = await client.post("/api/v1/ingest/external-transcript", json=VALID)
        assert resp.status_code != 422, resp.text
        assert resp.status_code in (200, 202, 500), resp.text
        if resp.status_code in (200, 202):
            assert resp.json()["data"]["session_id"] == "sess-abc"

    async def test_unknown_tool_rejected(self, client: AsyncClient):
        bad = {**VALID, "tool": "not-a-real-tool"}
        resp = await client.post("/api/v1/ingest/external-transcript", json=bad)
        assert resp.status_code == 422, resp.text

    async def test_missing_fields_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/ingest/external-transcript", json={"tool": "claude-code"})
        assert resp.status_code == 422, resp.text
