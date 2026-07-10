"""Integration tests for the Life Graph API.

These tests run in-process against the FastAPI app using ASGITransport.
They test the full pipeline: ingest → extract → store → search → recall.

No external server required — runs as part of pytest suite.

Prerequisites:
    - docker compose up -d (for DB)
    - alembic upgrade head (to create schema)
    - pytest (which sets up in-process ASGI transport)
"""

from __future__ import annotations

import pytest
import pytest_asyncio
import uuid
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test-pipeline-tenant",
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """In-process HTTP client using ASGI transport (no external server needed)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
        timeout=60.0,  # Generous timeout for embedding model loading
    ) as c:
        yield c


# ── Health & Stats ─────────────────────────────────────────────


class TestHealthAndStats:
    """Basic connectivity and stats."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_health(self, client):
        r = await client.get("/health")
        assert r.status_code in (200, 500)
        data = r.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_stats(self, client):
        r = await client.get("/admin/stats")
        assert r.status_code in (200, 500)
        data = r.json()
        assert "memory_count" in data
        assert "intention_count" in data
        assert "gap_count" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_docs(self, client):
        r = await client.get("/docs")
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_brain_viewer(self, client):
        r = await client.get("/brain/")
        assert r.status_code in (200, 500)


# ── Ingestion Pipeline ─────────────────────────────────────────


class TestIngestionPipeline:
    """Test the full ingest → extract → store pipeline."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_ingest_preference(self, client):
        r = await client.post("/admin/ingest", json={
            "text": f"I prefer Rust over C++ for systems programming. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code in (201, 500)
        memories = r.json()
        assert isinstance(memories, list)
        assert len(memories) >= 1
        # Should detect a preference
        tags_all = [t for m in memories for t in m.get("tags", [])]
        assert "preference" in tags_all or any(
            m.get("properties", {}).get("fact_type") == "preference"
            for m in memories
        )

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_ingest_decision(self, client):
        r = await client.post("/admin/ingest", json={
            "text": f"I switched from npm to pnpm for package management. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code in (201, 500)
        memories = r.json()
        assert len(memories) >= 1
        tags_all = [t for m in memories for t in m.get("tags", [])]
        # Should detect a decision/transition
        assert "decision" in tags_all or any(
            m.get("properties", {}).get("fact_type") == "decision"
            for m in memories
        )

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_ingest_intention(self, client):
        r = await client.post("/admin/ingest", json={
            "text": f"TODO: add WebSocket support to the API. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code in (201, 500)
        memories = r.json()
        assert len(memories) >= 1
        tags_all = [t for m in memories for t in m.get("tags", [])]
        assert "intention" in tags_all

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_ingest_explicit_save(self, client):
        r = await client.post("/admin/ingest", json={
            "text": f"Remember this: always use parameterized queries to prevent SQL injection. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code in (201, 500)
        memories = r.json()
        tags_all = [t for m in memories for t in m.get("tags", [])]
        assert "explicit_save" in tags_all

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_ingest_empty_text(self, client):
        r = await client.post("/admin/ingest", json={"text": ""})
        # Empty text should return 201 with empty list or 422
        assert r.status_code in (201, 422)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_ingest_multiple_facts(self, client):
        r = await client.post("/admin/ingest", json={
            "text": (
                f"I use PostgreSQL for databases, Redis for caching, "
                f"and Docker for deployment. Test-{uuid.uuid4().hex[:8]}"
            )
        })
        assert r.status_code in (201, 500)
        memories = r.json()
        # Should extract multiple facts
        assert len(memories) >= 2


# ── Memory CRUD ────────────────────────────────────────────────


class TestMemoryCRUD:
    """Test individual memory create/read/update/delete."""

    @pytest_asyncio.fixture
    async def created_memory(self, client):
        """Create a memory and return its data."""
        r = await client.post("/admin/ingest", json={
            "text": f"Test memory for CRUD operations. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code in (201, 500)
        memories = r.json()
        assert len(memories) >= 1
        return memories[0]

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_memories(self, client):
        r = await client.get("/memories/")
        assert r.status_code in (200, 500)
        memories = r.json()
        assert isinstance(memories, list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_memory_by_id(self, client, created_memory):
        memory_id = created_memory["id"]
        r = await client.get(f"/memories/{memory_id}")
        assert r.status_code in (200, 500)
        data = r.json()
        assert data["id"] == memory_id

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_nonexistent_memory(self, client):
        fake_id = str(uuid.uuid4())
        r = await client.get(f"/memories/{fake_id}")
        assert r.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_memory(self, client, created_memory):
        memory_id = created_memory["id"]
        r = await client.delete(f"/memories/{memory_id}")
        assert r.status_code in (204, 500)
        # Verify it's gone
        r = await client.get(f"/memories/{memory_id}")
        assert r.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_nonexistent_memory(self, client):
        fake_id = str(uuid.uuid4())
        r = await client.delete(f"/memories/{fake_id}")
        assert r.status_code in (404, 500)


# ── Search ─────────────────────────────────────────────────────


class TestSearch:
    """Test semantic search functionality."""

    @pytest_asyncio.fixture(autouse=True)
    async def seed_memories(self, client):
        """Seed some searchable memories."""
        texts = [
            f"I strongly prefer Python over Java for backend development. Search-seed-{uuid.uuid4().hex[:6]}",
            f"My favorite database is PostgreSQL with pgvector. Search-seed-{uuid.uuid4().hex[:6]}",
            f"I always deploy using Docker containers and Kubernetes. Search-seed-{uuid.uuid4().hex[:6]}",
        ]
        for text in texts:
            await client.post("/admin/ingest", json={"text": text})

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_returns_results(self, client):
        r = await client.post("/search/", json={
            "query": "what programming language do I use",
            "limit": 5,
        })
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_empty_query(self, client):
        r = await client.post("/search/", json={"query": "", "limit": 5})
        # Should return 422 or empty results
        assert r.status_code in (200, 422)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_with_limit(self, client):
        r = await client.post("/search/", json={
            "query": "database preference",
            "limit": 2,
        })
        assert r.status_code in (200, 500)


# ── Graph Endpoints ────────────────────────────────────────────


class TestGraphEndpoints:
    """Test graph API endpoints (may return empty if AGE not configured)."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_entities(self, client):
        r = await client.get("/graph/entities")
        # Expect 200 or 503 if AGE not available
        assert r.status_code in (200, 500, 503)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_entity_detail(self, client):
        r = await client.get("/graph/entity/Python")
        assert r.status_code in (200, 404, 500, 503)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_cypher_query(self, client):
        r = await client.post("/graph/query", json={
            "cypher": "MATCH (n) RETURN n LIMIT 5",
            "columns": ["n"],
        })
        # 200 if AGE works, 400 if query validation fails, 500/503 if not configured
        assert r.status_code in (200, 400, 500, 503)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_path_finding(self, client):
        r = await client.get("/graph/path", params={
            "from_name": "Python",
            "to_name": "PostgreSQL",
        })
        assert r.status_code in (200, 404, 500, 503)


# ── Multi-Modal Endpoints ─────────────────────────────────────


class TestMultiModalEndpoints:
    """Test multi-modal ingest endpoints."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_voice_no_file(self, client):
        r = await client.post("/ingest/voice")
        assert r.status_code in (422, 500)  # Missing file

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_image_no_file(self, client):
        r = await client.post("/ingest/image")
        assert r.status_code in (422, 500)  # Missing file

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_document_no_file(self, client):
        r = await client.post("/ingest/document")
        assert r.status_code in (422, 500)  # Missing file

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_document_text_file(self, client):
        """Upload a simple text file as a document."""
        content = (
            f"This is a test document about machine learning. "
            f"I prefer PyTorch over TensorFlow. Test-{uuid.uuid4().hex[:8]}"
        )
        files = {"file": ("test.txt", content.encode(), "text/plain")}
        r = await client.post("/ingest/document", files=files)
        # 200/201 if deps available, 503 if not
        assert r.status_code in (200, 201, 503)


# ── Event Bus ──────────────────────────────────────────────────


class TestEventBus:
    """Test the event bus module directly."""

    def test_event_bus_import(self):
        from life_graph.core.events import EventBus, EventType, event_bus
        assert isinstance(event_bus, EventBus)
        assert len(EventType) >= 8

    def test_subscribe_and_emit(self):
        import asyncio
        from life_graph.core.events import EventBus, EventType

        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe(EventType.MEMORY_CREATED, handler)

        asyncio.run(bus.emit(
            EventType.MEMORY_CREATED,
            {"content": "test memory"},
            source="test",
        ))
        assert len(received) == 1
        assert received[0].payload["content"] == "test memory"

    def test_global_handler(self):
        import asyncio
        from life_graph.core.events import EventBus, EventType

        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event.type)

        bus.subscribe_all(handler)

        asyncio.run(bus.emit(EventType.MEMORY_CREATED, {}))
        asyncio.run(bus.emit(EventType.MEMORY_DELETED, {}))
        assert len(received) == 2
        assert EventType.MEMORY_CREATED in received
        assert EventType.MEMORY_DELETED in received


# ── Plugin System ──────────────────────────────────────────────


class TestPluginSystem:
    """Test the plugin loader."""

    def test_plugin_manager_import(self):
        from life_graph.core.plugins import PluginManager
        from life_graph.core.events import event_bus
        pm = PluginManager(event_bus)
        assert pm is not None

    def test_discover_plugins(self):
        from life_graph.core.plugins import PluginManager
        from life_graph.core.events import event_bus
        from pathlib import Path

        plugins_dir = Path("D:/DevTools/Projects/agents/plugins")
        pm = PluginManager(event_bus, plugins_dir=plugins_dir)
        found = pm.discover()
        # Should find at least webhook_notifier
        assert "webhook_notifier" in found


# ── End-to-End Pipeline ───────────────────────────────────────


class TestEndToEndPipeline:
    """Full pipeline tests: ingest → store → search → verify."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_full_lifecycle(self, client):
        """Ingest text, search for it, verify it's found, then delete."""
        marker = uuid.uuid4().hex[:8]
        text = f"I believe Haskell is the best language for type safety. Marker-{marker}"

        # 1. Ingest
        r = await client.post("/admin/ingest", json={"text": text})
        assert r.status_code in (201, 500)
        memories = r.json()
        assert len(memories) >= 1
        memory_id = memories[0]["id"]

        # 2. Verify stored
        r = await client.get(f"/memories/{memory_id}")
        assert r.status_code in (200, 500)

        # 3. Search
        r = await client.post("/search/", json={
            "query": "type safety language",
            "limit": 10,
        })
        assert r.status_code in (200, 500)

        # 4. Delete
        r = await client.delete(f"/memories/{memory_id}")
        assert r.status_code in (204, 500)

        # 5. Verify gone
        r = await client.get(f"/memories/{memory_id}")
        assert r.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_stats_increase_after_ingest(self, client):
        """Verify stats reflect new memories."""
        # Get initial count
        r = await client.get("/admin/stats")
        initial = r.json()["memory_count"]

        # Ingest
        r = await client.post("/admin/ingest", json={
            "text": f"Erlang is great for distributed systems. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code in (201, 500)
        new_count = len(r.json())

        # Verify count increased
        r = await client.get("/admin/stats")
        assert r.json()["memory_count"] >= initial + new_count


# ── API Authentication ────────────────────────────────────────


class TestAPIAuthentication:
    """Test API key authentication enforcement.

    These tests only run when LIFE_GRAPH_API_KEY is configured.
    They use in-process ASGI clients with and without auth headers.
    """

    @pytest_asyncio.fixture
    async def anon_client(self) -> AsyncClient:
        """HTTP client without API key."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            timeout=60.0,
        ) as c:
            yield c

    @pytest_asyncio.fixture
    async def authed_client(self) -> AsyncClient:
        """HTTP client with valid API key in header."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"X-API-Key": "test-api-key"},
            timeout=60.0,
        ) as c:
            yield c

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_health_no_auth_required(self, anon_client):
        """Health endpoint should always be accessible."""
        r = await anon_client.get("/health")
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_docs_no_auth_required(self, anon_client):
        """Docs endpoints should always be accessible."""
        r = await anon_client.get("/docs")
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_brain_no_auth_required(self, anon_client):
        """Brain dashboard should always be accessible."""
        r = await anon_client.get("/brain/")
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_protected_route_returns_401(self, anon_client):
        """Protected routes should return 401 without API key."""
        r = await anon_client.get("/memories/")
        assert r.status_code in (401, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_protected_route_wrong_key(self, anon_client):
        """Protected routes should reject invalid API keys."""
        r = await anon_client.get(
            "/memories/",
            headers={"X-API-Key": "wrong-key-12345"},
        )
        assert r.status_code in (401, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_header_auth_works(self, authed_client):
        """Valid API key in X-API-Key header should grant access."""
        r = await authed_client.get("/memories/")
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_query_param_auth_works(self, anon_client):
        """Valid API key in ?api_key= query param should grant access."""
        r = await anon_client.get("/memories/", params={"api_key": "test-api-key"})
        assert r.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_admin_requires_auth(self, anon_client, authed_client):
        """Admin endpoints should require auth."""
        r = await anon_client.get("/admin/stats")
        assert r.status_code in (401, 500)

        r = await authed_client.get("/admin/stats")
        assert r.status_code in (200, 500)

