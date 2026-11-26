"""Raw Cypher needs an owner key; the graph never falls back to "default".

``POST /api/v1/graph/query`` reads every tenant's graph. It was allowed
whenever ``X-Tenant-ID`` was "default", and any service-key holder (an MCP
server, a watcher, an integration) can send that header. It now needs an owner
API key as well (api/auth.py ``require_owner_key``).

``GraphStore`` used to put a call with no tenant into the "default" tenant
when no tenant context was set; it now raises (storage/graph.py
``_resolve_tenant``).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from life_graph.api import auth
from life_graph.api import graph as graph_api
from life_graph.config import settings
from life_graph.core.tenant import tenant_scope
from life_graph.main import app
from life_graph.storage.graph import DEFAULT_GRAPH_TENANT, GraphStore
from tests.conftest import fake_request

OWNER_KEY = "owner-key-graph-0123456789"
SERVICE_KEY = "mcp-key-graph-9876543210"
QUERY = {"cypher": "MATCH (n) RETURN n LIMIT 5", "columns": ["n"]}


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)


@pytest.fixture
def store(monkeypatch):
    graph_store = AsyncMock()
    graph_store.execute_cypher = AsyncMock(return_value=[{"n": 1}])
    monkeypatch.setattr(graph_api, "graph_available", AsyncMock(return_value=True))
    monkeypatch.setattr(graph_api, "_get_graph_store", lambda: graph_store)
    return graph_store


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def _headers(key: str, tenant: str = DEFAULT_GRAPH_TENANT) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": tenant}


class TestRawCypherGate:
    async def test_a_service_key_with_the_admin_tenant_header_is_refused(self, keys, store, client):
        response = await client.post(
            "/api/v1/graph/query", json=QUERY, headers=_headers(SERVICE_KEY)
        )

        assert response.status_code == 403, response.text
        assert response.json()["detail"] == auth.OWNER_KEY_REQUIRED
        store.execute_cypher.assert_not_awaited()

    async def test_the_owner_key_with_the_admin_tenant_runs_the_query(self, keys, store, client):
        response = await client.post("/api/v1/graph/query", json=QUERY, headers=_headers(OWNER_KEY))

        assert response.status_code == 200, response.text
        assert response.json()["data"] == [{"n": 1}]
        store.execute_cypher.assert_awaited_once()

    async def test_the_owner_key_still_needs_the_admin_tenant(self, keys, store, client):
        response = await client.post(
            "/api/v1/graph/query", json=QUERY, headers=_headers(OWNER_KEY, "tenant-b")
        )

        assert response.status_code == 403, response.text
        assert "administrative tenant" in response.json()["detail"]
        store.execute_cypher.assert_not_awaited()

    async def test_no_key_is_still_401(self, keys, store, client):
        response = await client.post(
            "/api/v1/graph/query", json=QUERY, headers={"X-Tenant-ID": DEFAULT_GRAPH_TENANT}
        )

        assert response.status_code == 401, response.text
        store.execute_cypher.assert_not_awaited()


class TestRequireOwnerKey:
    def test_a_service_key_is_refused(self, keys):
        with pytest.raises(HTTPException) as exc:
            auth.require_owner_key(fake_request(api_key=SERVICE_KEY))
        assert exc.value.status_code == 403

    def test_a_paired_phone_is_refused(self, keys):
        """A phone is owner-verified but bound to one tenant: not a deployment owner."""
        with pytest.raises(HTTPException) as exc:
            auth.require_owner_key(fake_request(device_id="phone-1"))
        assert exc.value.status_code == 403

    def test_the_owner_key_passes(self, keys):
        auth.require_owner_key(fake_request(api_key=OWNER_KEY))

    def test_a_dev_stack_with_auth_off_passes(self, monkeypatch):
        monkeypatch.setattr(settings, "environment", "development")
        monkeypatch.setattr(settings, "api_key", None)
        monkeypatch.setattr(settings, "service_api_keys", "")
        monkeypatch.setattr(settings, "owner_api_keys", "")
        auth.require_owner_key(fake_request())


_CALLS = [
    ("create_vertex", ("Entity", {"name": "x"})),
    ("get_vertex", ("Entity", "x")),
    ("upsert_vertex", ("Entity", "x")),
    ("create_edge", ("Entity", "a", "Entity", "b", "rel")),
    ("create_edge_if_absent", ("Entity", "a", "Entity", "b", "rel")),
    ("get_neighbors", ("x",)),
    ("find_path", ("Entity", "a", "Entity", "b")),
    ("search_entities", ("x",)),
    ("get_all_entities", ()),
]


class TestGraphFailsClosed:
    @pytest.fixture
    def recording(self):
        graph_store = GraphStore()
        graph_store.execute_cypher = AsyncMock(return_value=[])
        return graph_store

    @pytest.mark.parametrize(("method", "args"), _CALLS, ids=[c[0] for c in _CALLS])
    async def test_no_tenant_and_no_context_raises(self, recording, method, args):
        with pytest.raises(RuntimeError, match="No tenant context"):
            await getattr(recording, method)(*args)

        recording.execute_cypher.assert_not_awaited()

    @pytest.mark.parametrize(("method", "args"), _CALLS, ids=[c[0] for c in _CALLS])
    async def test_the_context_tenant_is_used(self, recording, method, args):
        with tenant_scope("ctx-tenant"):
            await getattr(recording, method)(*args)

        sent = [
            (c.args[0], c.kwargs.get("params") or {})
            for c in recording.execute_cypher.await_args_list
        ]
        assert sent
        for cypher, params in sent:
            assert DEFAULT_GRAPH_TENANT not in cypher
            assert params.get("tid", "ctx-tenant") == "ctx-tenant"
