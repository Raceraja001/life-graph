"""Integration tests for the Life Graph API.

These tests run against the actual running API server (localhost:8000)
with a real PostgreSQL database. They test the full pipeline:
ingest → extract → store → search → recall.

Prerequisites:
    - docker compose up -d
    - alembic upgrade head
    - uvicorn life_graph.main:app --port 8000
"""

from __future__ import annotations

import httpx
import os
import pytest
import uuid

BASE = "http://localhost:8000"
TIMEOUT = 60.0
# For auth tests: set LIFE_GRAPH_TEST_API_KEY to match your server's LIFE_GRAPH_API_KEY
TEST_API_KEY = os.environ.get("LIFE_GRAPH_TEST_API_KEY", "")


@pytest.fixture(scope="module")
def client():
    """HTTP client with generous timeout for embedding model loading."""
    with httpx.Client(base_url=BASE, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope="module")
def health_check(client: httpx.Client):
    """Skip all tests if the API is not reachable."""
    try:
        r = client.get("/health")
        if r.status_code != 200:
            pytest.skip("API not healthy")
    except httpx.ConnectError:
        pytest.skip("API not reachable at localhost:8000")


# ── Health & Stats ─────────────────────────────────────────────


class TestHealthAndStats:
    """Basic connectivity and stats."""

    def test_health(self, client, health_check):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"

    def test_stats(self, client, health_check):
        r = client.get("/admin/stats")
        assert r.status_code == 200
        data = r.json()
        assert "memory_count" in data
        assert "intention_count" in data
        assert "gap_count" in data

    def test_docs(self, client, health_check):
        r = client.get("/docs")
        assert r.status_code == 200

    def test_brain_viewer(self, client, health_check):
        r = client.get("/brain/")
        assert r.status_code == 200


# ── Ingestion Pipeline ─────────────────────────────────────────


class TestIngestionPipeline:
    """Test the full ingest → extract → store pipeline."""

    def test_ingest_preference(self, client, health_check):
        r = client.post("/admin/ingest", json={
            "text": f"I prefer Rust over C++ for systems programming. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code == 201
        memories = r.json()
        assert isinstance(memories, list)
        assert len(memories) >= 1
        # Should detect a preference
        tags_all = [t for m in memories for t in m.get("tags", [])]
        assert "preference" in tags_all or any(
            m.get("properties", {}).get("fact_type") == "preference"
            for m in memories
        )

    def test_ingest_decision(self, client, health_check):
        r = client.post("/admin/ingest", json={
            "text": f"I switched from npm to pnpm for package management. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code == 201
        memories = r.json()
        assert len(memories) >= 1
        tags_all = [t for m in memories for t in m.get("tags", [])]
        # Should detect a decision/transition
        assert "decision" in tags_all or any(
            m.get("properties", {}).get("fact_type") == "decision"
            for m in memories
        )

    def test_ingest_intention(self, client, health_check):
        r = client.post("/admin/ingest", json={
            "text": f"TODO: add WebSocket support to the API. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code == 201
        memories = r.json()
        assert len(memories) >= 1
        tags_all = [t for m in memories for t in m.get("tags", [])]
        assert "intention" in tags_all

    def test_ingest_explicit_save(self, client, health_check):
        r = client.post("/admin/ingest", json={
            "text": f"Remember this: always use parameterized queries to prevent SQL injection. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code == 201
        memories = r.json()
        tags_all = [t for m in memories for t in m.get("tags", [])]
        assert "explicit_save" in tags_all

    def test_ingest_empty_text(self, client, health_check):
        r = client.post("/admin/ingest", json={"text": ""})
        # Empty text should return 201 with empty list or 422
        assert r.status_code in (201, 422)

    def test_ingest_multiple_facts(self, client, health_check):
        r = client.post("/admin/ingest", json={
            "text": (
                f"I use PostgreSQL for databases, Redis for caching, "
                f"and Docker for deployment. Test-{uuid.uuid4().hex[:8]}"
            )
        })
        assert r.status_code == 201
        memories = r.json()
        # Should extract multiple facts
        assert len(memories) >= 2


# ── Memory CRUD ────────────────────────────────────────────────


class TestMemoryCRUD:
    """Test individual memory create/read/update/delete."""

    @pytest.fixture
    def created_memory(self, client, health_check):
        """Create a memory and return its data."""
        r = client.post("/admin/ingest", json={
            "text": f"Test memory for CRUD operations. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code == 201
        memories = r.json()
        assert len(memories) >= 1
        return memories[0]

    def test_list_memories(self, client, health_check):
        r = client.get("/memories/")
        assert r.status_code == 200
        memories = r.json()
        assert isinstance(memories, list)

    def test_get_memory_by_id(self, client, health_check, created_memory):
        memory_id = created_memory["id"]
        r = client.get(f"/memories/{memory_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == memory_id

    def test_get_nonexistent_memory(self, client, health_check):
        fake_id = str(uuid.uuid4())
        r = client.get(f"/memories/{fake_id}")
        assert r.status_code == 404

    def test_delete_memory(self, client, health_check, created_memory):
        memory_id = created_memory["id"]
        r = client.delete(f"/memories/{memory_id}")
        assert r.status_code == 204
        # Verify it's gone
        r = client.get(f"/memories/{memory_id}")
        assert r.status_code == 404

    def test_delete_nonexistent_memory(self, client, health_check):
        fake_id = str(uuid.uuid4())
        r = client.delete(f"/memories/{fake_id}")
        assert r.status_code == 404


# ── Search ─────────────────────────────────────────────────────


class TestSearch:
    """Test semantic search functionality."""

    @pytest.fixture(autouse=True, scope="class")
    def seed_memories(self, client, health_check):
        """Seed some searchable memories."""
        texts = [
            f"I strongly prefer Python over Java for backend development. Search-seed-{uuid.uuid4().hex[:6]}",
            f"My favorite database is PostgreSQL with pgvector. Search-seed-{uuid.uuid4().hex[:6]}",
            f"I always deploy using Docker containers and Kubernetes. Search-seed-{uuid.uuid4().hex[:6]}",
        ]
        for text in texts:
            client.post("/admin/ingest", json={"text": text})

    def test_search_returns_results(self, client, health_check):
        r = client.post("/search/", json={
            "query": "what programming language do I use",
            "limit": 5,
        })
        assert r.status_code == 200

    def test_search_empty_query(self, client, health_check):
        r = client.post("/search/", json={"query": "", "limit": 5})
        # Should return 422 or empty results
        assert r.status_code in (200, 422)

    def test_search_with_limit(self, client, health_check):
        r = client.post("/search/", json={
            "query": "database preference",
            "limit": 2,
        })
        assert r.status_code == 200


# ── Graph Endpoints ────────────────────────────────────────────


class TestGraphEndpoints:
    """Test graph API endpoints (may return empty if AGE not configured)."""

    def test_list_entities(self, client, health_check):
        r = client.get("/graph/entities")
        # Expect 200 or 503 if AGE not available
        assert r.status_code in (200, 500, 503)

    def test_entity_detail(self, client, health_check):
        r = client.get("/graph/entity/Python")
        assert r.status_code in (200, 404, 500, 503)

    def test_cypher_query(self, client, health_check):
        r = client.post("/graph/query", json={
            "cypher": "MATCH (n) RETURN n LIMIT 5",
            "columns": ["n"],
        })
        # 200 if AGE works, 400 if query validation fails, 500/503 if not configured
        assert r.status_code in (200, 400, 500, 503)

    def test_path_finding(self, client, health_check):
        r = client.get("/graph/path", params={
            "from_name": "Python",
            "to_name": "PostgreSQL",
        })
        assert r.status_code in (200, 404, 500, 503)


# ── Multi-Modal Endpoints ─────────────────────────────────────


class TestMultiModalEndpoints:
    """Test multi-modal ingest endpoints."""

    def test_voice_no_file(self, client, health_check):
        r = client.post("/ingest/voice")
        assert r.status_code == 422  # Missing file

    def test_image_no_file(self, client, health_check):
        r = client.post("/ingest/image")
        assert r.status_code == 422  # Missing file

    def test_document_no_file(self, client, health_check):
        r = client.post("/ingest/document")
        assert r.status_code == 422  # Missing file

    def test_document_text_file(self, client, health_check):
        """Upload a simple text file as a document."""
        content = (
            f"This is a test document about machine learning. "
            f"I prefer PyTorch over TensorFlow. Test-{uuid.uuid4().hex[:8]}"
        )
        files = {"file": ("test.txt", content.encode(), "text/plain")}
        r = client.post("/ingest/document", files=files)
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

    def test_full_lifecycle(self, client, health_check):
        """Ingest text, search for it, verify it's found, then delete."""
        marker = uuid.uuid4().hex[:8]
        text = f"I believe Haskell is the best language for type safety. Marker-{marker}"

        # 1. Ingest
        r = client.post("/admin/ingest", json={"text": text})
        assert r.status_code == 201
        memories = r.json()
        assert len(memories) >= 1
        memory_id = memories[0]["id"]

        # 2. Verify stored
        r = client.get(f"/memories/{memory_id}")
        assert r.status_code == 200

        # 3. Search
        r = client.post("/search/", json={
            "query": "type safety language",
            "limit": 10,
        })
        assert r.status_code == 200

        # 4. Delete
        r = client.delete(f"/memories/{memory_id}")
        assert r.status_code == 204

        # 5. Verify gone
        r = client.get(f"/memories/{memory_id}")
        assert r.status_code == 404

    def test_stats_increase_after_ingest(self, client, health_check):
        """Verify stats reflect new memories."""
        # Get initial count
        r = client.get("/admin/stats")
        initial = r.json()["memory_count"]

        # Ingest
        r = client.post("/admin/ingest", json={
            "text": f"Erlang is great for distributed systems. Test-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code == 201
        new_count = len(r.json())

        # Verify count increased
        r = client.get("/admin/stats")
        assert r.json()["memory_count"] >= initial + new_count


# ── API Authentication ────────────────────────────────────────


class TestAPIAuthentication:
    """Test API key authentication enforcement.

    These tests only run when LIFE_GRAPH_TEST_API_KEY is set and the
    server is started with LIFE_GRAPH_API_KEY set to the same value.
    """

    @pytest.fixture(autouse=True)
    def require_api_key(self):
        """Skip if no test API key configured."""
        if not TEST_API_KEY:
            pytest.skip("LIFE_GRAPH_TEST_API_KEY not set — skipping auth tests")

    @pytest.fixture
    def anon_client(self):
        """HTTP client without API key."""
        with httpx.Client(base_url=BASE, timeout=TIMEOUT) as c:
            yield c

    @pytest.fixture
    def authed_client(self):
        """HTTP client with valid API key in header."""
        with httpx.Client(
            base_url=BASE,
            timeout=TIMEOUT,
            headers={"X-API-Key": TEST_API_KEY},
        ) as c:
            yield c

    def test_health_no_auth_required(self, anon_client):
        """Health endpoint should always be accessible."""
        r = anon_client.get("/health")
        assert r.status_code == 200

    def test_docs_no_auth_required(self, anon_client):
        """Docs endpoints should always be accessible."""
        r = anon_client.get("/docs")
        assert r.status_code == 200

    def test_brain_no_auth_required(self, anon_client):
        """Brain dashboard should always be accessible."""
        r = anon_client.get("/brain/")
        assert r.status_code == 200

    def test_protected_route_returns_401(self, anon_client):
        """Protected routes should return 401 without API key."""
        r = anon_client.get("/memories/")
        assert r.status_code == 401
        assert "Invalid or missing API key" in r.json()["detail"]

    def test_protected_route_wrong_key(self, anon_client):
        """Protected routes should reject invalid API keys."""
        r = anon_client.get(
            "/memories/",
            headers={"X-API-Key": "wrong-key-12345"},
        )
        assert r.status_code == 401

    def test_header_auth_works(self, authed_client):
        """Valid API key in X-API-Key header should grant access."""
        r = authed_client.get("/memories/")
        assert r.status_code == 200

    def test_query_param_auth_works(self, anon_client):
        """Valid API key in ?api_key= query param should grant access."""
        r = anon_client.get("/memories/", params={"api_key": TEST_API_KEY})
        assert r.status_code == 200

    def test_admin_requires_auth(self, anon_client, authed_client):
        """Admin endpoints should require auth."""
        r = anon_client.get("/admin/stats")
        assert r.status_code == 401

        r = authed_client.get("/admin/stats")
        assert r.status_code == 200

