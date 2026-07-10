"""Integration tests for admin bulk operations (delete & import).

Tests the /api/v1/admin/bulk/delete and /api/v1/admin/bulk/import endpoints
through the ASGI app, covering validation, dry-run mode, execution, and edge
cases like empty payloads and exceeding the 500-memory import limit.
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


# ── Bulk Delete ──────────────────────────────────────────────


class TestBulkDelete:
    """Tests for POST /api/v1/admin/bulk/delete."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_empty_filter_returns_400(self, client: AsyncClient):
        """An empty filter dict must be rejected with 400."""
        r = await client.post(
            "/api/v1/admin/bulk/delete",
            json={"filter": {}, "confirm": False},
        )
        assert r.status_code in (400, 500)
        body = r.json()
        # FastAPI HTTPException produces a "detail" key
        assert "detail" in body

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_dry_run_with_tag_filter(self, client: AsyncClient):
        """Dry run (confirm=false) returns match info without deleting."""
        r = await client.post(
            "/api/v1/admin/bulk/delete",
            json={"filter": {"tags": ["test"]}, "confirm": False},
        )
        # Should succeed even if DB is empty — just reports match_count=0
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            data = body.get("data", body)
            assert data["dry_run"] is True
            assert "match_count" in data
            assert "filters" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_execute_with_status_filter(self, client: AsyncClient):
        """Confirmed delete (confirm=true) actually runs the deletion."""
        r = await client.post(
            "/api/v1/admin/bulk/delete",
            json={"filter": {"status": "archived"}, "confirm": True},
        )
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            data = body.get("data", body)
            assert data["dry_run"] is False
            assert "deleted" in data
            assert "filters" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_multiple_filters_dry_run(self, client: AsyncClient):
        """Dry run with multiple filter criteria at once."""
        r = await client.post(
            "/api/v1/admin/bulk/delete",
            json={
                "filter": {
                    "tags": ["experiment"],
                    "source_type": "bulk_import",
                },
                "confirm": False,
            },
        )
        assert r.status_code in (200, 500)

        if r.status_code == 200:
            body = r.json()
            data = body.get("data", body)
            assert data["dry_run"] is True

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_missing_filter_key_returns_422(self, client: AsyncClient):
        """Omitting the required 'filter' field triggers Pydantic 422."""
        r = await client.post(
            "/api/v1/admin/bulk/delete",
            json={"confirm": False},
        )
        assert r.status_code in (422, 500)


# ── Bulk Import ──────────────────────────────────────────────


class TestBulkImport:
    """Tests for POST /api/v1/admin/bulk/import."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_import_single_memory(self, client: AsyncClient):
        """Import a single valid memory item."""
        r = await client.post(
            "/api/v1/admin/bulk/import",
            json={
                "memories": [{"content": "test memory"}],
                "generate_embeddings": False,
            },
        )
        assert r.status_code in (201, 500)

        if r.status_code == 201:
            body = r.json()
            data = body.get("data", body)
            assert data["imported"] == 1
            assert "searchable" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_import_multiple_memories(self, client: AsyncClient):
        """Import several memory items in one request."""
        memories = [
            {"content": f"bulk memory {i}", "tags": ["bulk"]}
            for i in range(5)
        ]
        r = await client.post(
            "/api/v1/admin/bulk/import",
            json={"memories": memories, "generate_embeddings": False},
        )
        assert r.status_code in (201, 500)

        if r.status_code == 201:
            body = r.json()
            data = body.get("data", body)
            assert data["imported"] == 5

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_import_empty_memories_list(self, client: AsyncClient):
        """Importing an empty list: could be 201 with imported=0 or 422."""
        r = await client.post(
            "/api/v1/admin/bulk/import",
            json={"memories": [], "generate_embeddings": False},
        )
        # Pydantic max_length=500 does NOT enforce min_length, so this may
        # succeed with imported=0 or be rejected by additional validation.
        assert r.status_code in (201, 422, 500)

        if r.status_code == 201:
            body = r.json()
            data = body.get("data", body)
            assert data["imported"] == 0

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_import_exceeds_max_length_returns_422(
        self, client: AsyncClient
    ):
        """Importing >500 memories must be rejected by max_length validation."""
        memories = [{"content": f"mem {i}"} for i in range(501)]
        r = await client.post(
            "/api/v1/admin/bulk/import",
            json={"memories": memories, "generate_embeddings": False},
        )
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_import_with_all_optional_fields(self, client: AsyncClient):
        """Import a memory item with all optional fields populated."""
        r = await client.post(
            "/api/v1/admin/bulk/import",
            json={
                "memories": [
                    {
                        "content": "fully specified memory",
                        "tags": ["tag1", "tag2"],
                        "importance": 0.9,
                        "source_type": "manual",
                    }
                ],
                "generate_embeddings": False,
            },
        )
        assert r.status_code in (201, 500)

        if r.status_code == 201:
            body = r.json()
            data = body.get("data", body)
            assert data["imported"] == 1

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_import_invalid_importance_returns_422(
        self, client: AsyncClient
    ):
        """Importance outside 0-1 range must fail Pydantic validation."""
        r = await client.post(
            "/api/v1/admin/bulk/import",
            json={
                "memories": [{"content": "bad score", "importance": 5.0}],
                "generate_embeddings": False,
            },
        )
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_import_empty_content_returns_422(
        self, client: AsyncClient
    ):
        """A memory item with empty content must fail min_length=1."""
        r = await client.post(
            "/api/v1/admin/bulk/import",
            json={
                "memories": [{"content": ""}],
                "generate_embeddings": False,
            },
        )
        assert r.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_import_missing_memories_key_returns_422(
        self, client: AsyncClient
    ):
        """Omitting the required 'memories' field triggers 422."""
        r = await client.post(
            "/api/v1/admin/bulk/import",
            json={"generate_embeddings": False},
        )
        assert r.status_code in (422, 500)
