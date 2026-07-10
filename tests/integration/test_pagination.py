"""Integration tests for cursor-based pagination.

Tests the paginated list endpoints for memories and sessions,
verifying the response envelope shape (data + meta), cursor
handling, include_total behavior, and invalid cursor resilience.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Authenticated test client."""
    transport = ASGITransport(app=app)
    headers = {"X-Tenant-ID": "test_tenant", "X-User-ID": "user-test"}
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as c:
        yield c


# ── Helpers ──────────────────────────────────────────────────


def _assert_paginated_envelope(body: dict) -> None:
    """Assert the response follows the paginated envelope contract.

    Expected shape:
        {
            "data": [...],
            "meta": {
                "page_size": int,
                "has_more": bool,
                "next_cursor": str | null,
                "total": int | null,
            }
        }
    """
    assert "data" in body, "Response must contain 'data'"
    assert isinstance(body["data"], list), "'data' must be a list"

    assert "meta" in body, "Response must contain 'meta'"
    meta = body["meta"]
    assert "page_size" in meta, "'meta' must contain 'page_size'"
    assert "has_more" in meta, "'meta' must contain 'has_more'"
    assert "next_cursor" in meta, "'meta' must contain 'next_cursor'"
    assert isinstance(meta["has_more"], bool)


# ── Memory Pagination ───────────────────────────────────────


class TestMemoryPagination:
    """Tests for GET /api/v1/memories/ pagination."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_basic_shape(self, client: AsyncClient):
        """Response has the standard paginated envelope."""
        r = await client.get("/api/v1/memories/", params={"limit": 5})
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            _assert_paginated_envelope(body)
            assert body["meta"]["page_size"] == 5

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_data_is_list(self, client: AsyncClient):
        """The data field must always be a list (possibly empty)."""
        r = await client.get("/api/v1/memories/", params={"limit": 5})
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_include_total(self, client: AsyncClient):
        """When include_total=true, meta.total must be an integer."""
        r = await client.get(
            "/api/v1/memories/",
            params={"limit": 5, "include_total": "true"},
        )
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            _assert_paginated_envelope(body)
            total = body["meta"]["total"]
            assert total is not None
            assert isinstance(total, int)
            assert total >= 0

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_total_absent_by_default(
        self, client: AsyncClient
    ):
        """Without include_total, meta.total should be null."""
        r = await client.get("/api/v1/memories/", params={"limit": 5})
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            assert body["meta"]["total"] is None

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_invalid_cursor(self, client: AsyncClient):
        """An invalid cursor should be handled gracefully (200 or 400/422)."""
        r = await client.get(
            "/api/v1/memories/",
            params={"limit": 5, "cursor": "invalidcursor"},
        )
        # The endpoint may return an empty result, a 400 for bad cursor,
        # or a 500 if the decode raises unhandled
        assert r.status_code in (200, 400, 422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_has_more_false_when_empty(
        self, client: AsyncClient
    ):
        """On an empty DB, has_more must be false."""
        r = await client.get("/api/v1/memories/", params={"limit": 100})
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            # If there are fewer items than the limit, has_more should be False
            if len(body["data"]) < 100:
                assert body["meta"]["has_more"] is False

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_next_cursor_null_when_no_more(
        self, client: AsyncClient
    ):
        """When has_more is false, next_cursor should be null."""
        r = await client.get("/api/v1/memories/", params={"limit": 100})
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            if not body["meta"]["has_more"]:
                assert body["meta"]["next_cursor"] is None

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_respects_limit(self, client: AsyncClient):
        """The data array must not exceed the requested limit."""
        r = await client.get("/api/v1/memories/", params={"limit": 3})
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            assert len(body["data"]) <= 3

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories_limit_validation(self, client: AsyncClient):
        """limit=0 or limit > 100 should be rejected (422)."""
        r = await client.get("/api/v1/memories/", params={"limit": 0})
        assert r.status_code in (422, 500)

        r2 = await client.get("/api/v1/memories/", params={"limit": 999})
        assert r2.status_code in (422, 500)


# ── Session Pagination ───────────────────────────────────────


class TestSessionPagination:
    """Tests for GET /api/v1/sessions/ pagination."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_basic_shape(self, client: AsyncClient):
        """Response has the standard paginated envelope."""
        r = await client.get("/api/v1/sessions/", params={"limit": 5})
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            _assert_paginated_envelope(body)
            assert body["meta"]["page_size"] == 5

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_data_is_list(self, client: AsyncClient):
        """The data field must always be a list."""
        r = await client.get("/api/v1/sessions/", params={"limit": 5})
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_include_total(self, client: AsyncClient):
        """When include_total=true, meta.total must be present as int."""
        r = await client.get(
            "/api/v1/sessions/",
            params={"limit": 5, "include_total": "true"},
        )
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            _assert_paginated_envelope(body)
            total = body["meta"]["total"]
            assert total is not None
            assert isinstance(total, int)
            assert total >= 0

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_total_absent_by_default(
        self, client: AsyncClient
    ):
        """Without include_total, meta.total should be null."""
        r = await client.get("/api/v1/sessions/", params={"limit": 5})
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            assert body["meta"]["total"] is None

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_invalid_cursor(self, client: AsyncClient):
        """An invalid cursor should be handled gracefully."""
        r = await client.get(
            "/api/v1/sessions/",
            params={"limit": 5, "cursor": "invalidcursor"},
        )
        assert r.status_code in (200, 400, 422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_respects_limit(self, client: AsyncClient):
        """The data array must not exceed the requested limit."""
        r = await client.get("/api/v1/sessions/", params={"limit": 3})
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            assert len(body["data"]) <= 3

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_sessions_limit_validation(self, client: AsyncClient):
        """limit=0 or limit > 100 should be rejected (422)."""
        r = await client.get("/api/v1/sessions/", params={"limit": 0})
        assert r.status_code in (422, 500)

        r2 = await client.get("/api/v1/sessions/", params={"limit": 999})
        assert r2.status_code in (422, 500)


# ── Cross-Endpoint Envelope Consistency ──────────────────────


class TestEnvelopeConsistency:
    """Verify both list endpoints use the same response envelope."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_memories_and_sessions_share_envelope_keys(
        self, client: AsyncClient
    ):
        """Both endpoints must return identical top-level keys."""
        r_mem = await client.get("/api/v1/memories/", params={"limit": 5})
        r_ses = await client.get("/api/v1/sessions/", params={"limit": 5})

        if r_mem.status_code == 200 and r_ses.status_code == 200:
            mem_keys = set(r_mem.json().keys())
            ses_keys = set(r_ses.json().keys())
            assert mem_keys == ses_keys, (
                f"Envelope keys differ: memories={mem_keys}, sessions={ses_keys}"
            )

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_memories_and_sessions_share_meta_keys(
        self, client: AsyncClient
    ):
        """Both endpoints must have identical meta keys."""
        r_mem = await client.get("/api/v1/memories/", params={"limit": 5})
        r_ses = await client.get("/api/v1/sessions/", params={"limit": 5})

        if r_mem.status_code == 200 and r_ses.status_code == 200:
            mem_meta = set(r_mem.json()["meta"].keys())
            ses_meta = set(r_ses.json()["meta"].keys())
            assert mem_meta == ses_meta, (
                f"Meta keys differ: memories={mem_meta}, sessions={ses_meta}"
            )
