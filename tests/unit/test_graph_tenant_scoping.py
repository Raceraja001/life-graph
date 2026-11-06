"""Every graph read and write stays inside one tenant.

AGE is not installed where these run, so ``_FakeAGE`` stands in for it: a small
in-memory graph that evaluates the Cypher ``GraphStore`` really emits, and
honours only the tenant predicates present in that text. A query that forgets
one vertex's filter therefore walks straight through the other tenant's data
and the test fails, which asserting on a mocked return value could not show.

The bridge fixture is the shape that matters. Vertices written before scoping
were shared by name, so old edges can join two tenants through a third vertex:
``a1 - bridge - a2``. Filtering only the endpoints would pass ``a1 -> a2``.
"""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from life_graph.api import graph as graph_api
from life_graph.core.tenant import tenant_scope
from life_graph.main import app
from life_graph.storage import graph as graph_module
from life_graph.storage.graph import DEFAULT_GRAPH_TENANT, GraphStore


def _vertex(vid: int, name: str, tenant: str, label: str = "Entity") -> dict[str, Any]:
    return {"id": vid, "label": label, "properties": {"name": name, "tenant_id": tenant}}


class _FakeAGE:
    """Evaluates the MATCH shapes ``GraphStore`` emits against an in-memory graph."""

    def __init__(self, vertices: list[dict[str, Any]], edges: list[tuple[str, str]]):
        self.vertices = {v["properties"]["name"]: v for v in vertices}
        self.edges = edges
        self.queries: list[tuple[str, dict[str, Any]]] = []

    def _adjacent(self, name: str) -> list[dict[str, Any]]:
        out = [b for a, b in self.edges if a == name] + [a for a, b in self.edges if b == name]
        return [self.vertices[n] for n in out]

    def _walks(self, start: dict[str, Any], hops: int) -> list[list[dict[str, Any]]]:
        walks = [[start]]
        for _ in range(hops):
            walks = [
                [*w, nxt]
                for w in walks
                for nxt in self._adjacent(w[-1]["properties"]["name"])
                if nxt not in w
            ]
        return walks

    async def execute_cypher(self, cypher, params=None, columns=None):
        params = params or {}
        self.queries.append((cypher, params))

        scoped = set(re.findall(r"(\w+)\.tenant_id = \$tid", cypher))
        tid = params.get("tid")

        def allowed(var: str, vertex: dict[str, Any]) -> bool:
            return var not in scoped or vertex["properties"]["tenant_id"] == tid

        if "MATCH p = " in cypher or re.search(r"\(a:\w+\)-\[", cypher):
            return self._traverse(cypher, params, allowed)

        pattern = params.get("pattern")
        rows = []
        for vertex in self.vertices.values():
            name = vertex["properties"]["name"]
            if "name" in params and name != params["name"]:
                continue
            if pattern and not re.fullmatch(pattern, name):
                continue
            if allowed("n", vertex):
                rows.append({"v": vertex})
        return rows

    def _traverse(self, cypher, params, allowed):
        variables = re.findall(r"\((\w+)(?::\w+)?\)", cypher.split(" WHERE ")[0])
        start_name = params.get("name") or params["from_name"]
        start = self.vertices.get(start_name)
        if start is None:
            return []

        rows = []
        for walk in self._walks(start, len(variables) - 1):
            if not all(allowed(var, v) for var, v in zip(variables, walk, strict=True)):
                continue
            if "to_name" in params and walk[-1]["properties"]["name"] != params["to_name"]:
                continue
            rows.append({"p": walk} if "RETURN p" in cypher else {"v": walk[-1]})
        return rows


@pytest.fixture
def age():
    """Tenant A owns a1, a2, a3; tenant B owns b1 and the bridge."""
    return _FakeAGE(
        vertices=[
            _vertex(1, "a1", "A"),
            _vertex(2, "a2", "A"),
            _vertex(3, "a3", "A"),
            _vertex(4, "b1", "B"),
            _vertex(5, "bridge", "B"),
        ],
        edges=[("a1", "bridge"), ("bridge", "a2"), ("a1", "a3"), ("bridge", "b1")],
    )


@pytest.fixture
def store(age):
    graph_store = GraphStore()
    graph_store.execute_cypher = age.execute_cypher
    return graph_store


@pytest.fixture
def recording_store():
    """A store whose Cypher is captured and answers with one row."""
    graph_store = GraphStore()
    graph_store.execute_cypher = AsyncMock(return_value=[{"v": 7}])
    return graph_store


class TestWrites:
    async def test_create_vertex_attaches_the_tenant(self, recording_store):
        await recording_store.create_vertex("Entity", {"name": "x"}, tenant_id="A")

        assert "tenant_id: 'A'" in recording_store.execute_cypher.call_args.args[0]

    async def test_create_vertex_takes_the_tenant_from_context(self, recording_store):
        with tenant_scope("ctx"):
            await recording_store.create_vertex("Entity", {"name": "x"})

        assert "tenant_id: 'ctx'" in recording_store.execute_cypher.call_args.args[0]

    async def test_create_vertex_falls_back_without_context(self, recording_store):
        await recording_store.create_vertex("Entity", {"name": "x"})

        cypher = recording_store.execute_cypher.call_args.args[0]
        assert f"tenant_id: '{DEFAULT_GRAPH_TENANT}'" in cypher

    async def test_properties_cannot_claim_another_tenant(self, recording_store):
        await recording_store.create_vertex(
            "Entity", {"name": "x", "tenant_id": "victim"}, tenant_id="A"
        )

        cypher = recording_store.execute_cypher.call_args.args[0]
        assert "tenant_id: 'A'" in cypher
        assert "victim" not in cypher

    async def test_upsert_looks_only_in_its_own_tenant(self, store, age):
        """B's ``a1`` lookup misses A's vertex, so B gets a vertex of its own."""
        store.create_vertex = AsyncMock(return_value="99")

        assert await store.upsert_vertex("Entity", "a1", tenant_id="B") == "99"

        store.create_vertex.assert_awaited_once_with("Entity", {"name": "a1"}, tenant_id="B")

    async def test_upsert_reuses_the_tenants_vertex(self, store):
        store.create_vertex = AsyncMock()

        assert await store.upsert_vertex("Entity", "a1", tenant_id="A") == "1"

        store.create_vertex.assert_not_awaited()

    async def test_create_edge_scopes_both_endpoints(self, recording_store):
        await recording_store.create_edge("Entity", "a", "Entity", "b", "rel", tenant_id="A")

        call = recording_store.execute_cypher.call_args
        assert "a.tenant_id = $tid" in call.args[0]
        assert "b.tenant_id = $tid" in call.args[0]
        assert call.kwargs["params"]["tid"] == "A"


class TestReads:
    async def test_get_vertex_hides_another_tenants_vertex(self, store):
        assert await store.get_vertex("Entity", "b1", tenant_id="A") is None
        assert (await store.get_vertex("Entity", "b1", tenant_id="B"))["id"] == 4

    async def test_get_all_entities_filters_by_tenant(self, store):
        names = {v["properties"]["name"] for v in await store.get_all_entities(tenant_id="A")}

        assert names == {"a1", "a2", "a3"}

    async def test_get_all_entities_uses_the_context_tenant(self, store):
        with tenant_scope("B"):
            names = {v["properties"]["name"] for v in await store.get_all_entities()}

        assert names == {"b1", "bridge"}

    async def test_search_entities_filters_by_tenant(self, store):
        found = await store.search_entities("1", tenant_id="A")

        assert [v["properties"]["name"] for v in found] == ["a1"]

    async def test_vertices_without_a_tenant_are_not_visible(self, age, store):
        """Pre-scoping vertices belong to nobody until they are backfilled."""
        age.vertices["old"] = _vertex(9, "old", None)

        names = {v["properties"]["name"] for v in await store.get_all_entities(tenant_id="A")}

        assert "old" not in names


class TestTraversal:
    async def test_get_neighbors_stops_at_the_tenant_boundary(self, store):
        found = await store.get_neighbors("a1", depth=3, tenant_id="A")

        assert [v["properties"]["name"] for v in found] == ["a3"]

    async def test_get_neighbors_does_not_start_from_another_tenants_vertex(self, store):
        assert await store.get_neighbors("b1", depth=3, tenant_id="A") == []

    async def test_get_neighbors_filters_every_vertex_on_the_walk(self, store, age):
        await store.get_neighbors("a1", depth=3, tenant_id="A")

        deepest = age.queries[-1][0]
        for var in ("a", "n1", "n2", "b"):
            assert f"{var}.tenant_id = $tid" in deepest

    async def test_find_path_will_not_cross_a_foreign_vertex(self, store):
        assert await store.find_path("Entity", "a1", "Entity", "a2", tenant_id="A") == []

    async def test_find_path_walks_inside_the_tenant(self, store):
        path = await store.find_path("Entity", "a1", "Entity", "a3", tenant_id="A")

        assert [v["properties"]["name"] for v in path] == ["a1", "a3"]

    async def test_find_path_cannot_reach_into_another_tenant(self, store):
        assert await store.find_path("Entity", "a1", "Entity", "b1", tenant_id="A") == []


class TestInjection:
    """A filter in the query text only holds if input cannot rewrite that text."""

    @pytest.mark.parametrize("label", ["Entity) RETURN n //", "a b", "1x", "x\n", ""])
    async def test_labels_that_could_alter_the_query_are_refused(self, recording_store, label):
        with pytest.raises(ValueError, match="Invalid graph label"):
            await recording_store.get_vertex(label, "x", tenant_id="A")

    async def test_edge_label_is_validated_on_traversal(self, recording_store):
        with pytest.raises(ValueError, match="Invalid graph label"):
            await recording_store.get_neighbors("x", edge_label="r]-(b) //", tenant_id="A")

    @staticmethod
    def _capturing_pool(monkeypatch) -> MagicMock:
        conn = MagicMock(execute=AsyncMock(), fetch=AsyncMock(return_value=[]))
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(graph_module, "_get_pool", AsyncMock(return_value=pool))
        return conn

    async def test_a_value_is_not_expanded_by_a_later_parameter(self, monkeypatch):
        """``$tid`` as a name must stay a name, not become the tenant literal."""
        conn = self._capturing_pool(monkeypatch)

        await GraphStore().get_vertex("Entity", "$tid", tenant_id="A")

        assert "n.name = '$tid' AND n.tenant_id = 'A'" in conn.fetch.call_args.args[0]

    async def test_a_value_cannot_close_the_dollar_quote(self, monkeypatch):
        conn = self._capturing_pool(monkeypatch)

        await GraphStore().get_vertex("Entity", "x$$) --", tenant_id="A")

        sql = conn.fetch.call_args.args[0]
        assert "cypher('life_graph', $cypher$ " in sql
        assert sql.count("$cypher$") == 2

    async def test_a_value_containing_the_tag_gets_a_longer_one(self, monkeypatch):
        conn = self._capturing_pool(monkeypatch)

        await GraphStore().get_vertex("Entity", "x$cypher$) --", tenant_id="A")

        assert "cypher('life_graph', $cypherq$ " in conn.fetch.call_args.args[0]

    async def test_edge_properties_are_not_read_as_placeholders(self, monkeypatch):
        conn = self._capturing_pool(monkeypatch)

        await GraphStore().create_edge(
            "Entity", "a", "Entity", "b", "rel", {"note": "$tid"}, tenant_id="A"
        )

        assert "note: '$tid'" in conn.fetch.call_args.args[0]


class TestCallers:
    async def test_preference_node_keeps_its_own_tenant_under_another_context(self):
        graph_store = GraphStore()
        graph_store.execute_cypher = AsyncMock(return_value=[])

        with tenant_scope("other"):
            await graph_store.create_preference_node("acme", "p1", "editor", "vim", 0.9)

        assert "tenant_id: 'acme'" in graph_store.execute_cypher.call_args.args[0]

    async def test_link_sync_uses_the_links_tenant_not_the_context(self, monkeypatch):
        from life_graph.services import memory_links

        graph_store = MagicMock(upsert_vertex=AsyncMock(), create_edge=AsyncMock())
        monkeypatch.setattr(graph_module, "GraphStore", lambda: graph_store)

        await memory_links._sync_link_to_graph("s", "t", "related_to", 0.5, "acme")

        for call in (
            *graph_store.upsert_vertex.await_args_list,
            graph_store.create_edge.await_args,
        ):
            assert call.kwargs["tenant_id"] == "acme"


class TestApi:
    """The routes run behind the real middleware, so the tenant is the header's."""

    @pytest.fixture
    async def client(self, store, monkeypatch):
        monkeypatch.setattr(graph_api, "graph_available", AsyncMock(return_value=True))
        monkeypatch.setattr(graph_api, "_get_graph_store", lambda: store)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http

    async def test_entities_answers_for_the_header_tenant(self, client):
        response = await client.get("/api/v1/graph/entities", headers={"X-Tenant-ID": "B"})

        assert response.status_code == 200
        assert {e["name"] for e in response.json()["data"]} == {"b1", "bridge"}

    async def test_path_answers_for_the_header_tenant(self, client):
        params = {"from_name": "a1", "to_name": "a2"}

        response = await client.get(
            "/api/v1/graph/path", params=params, headers={"X-Tenant-ID": "A"}
        )

        assert response.status_code == 200
        assert response.json()["data"]["found"] is False

    @pytest.mark.parametrize(
        ("method", "url", "kwargs"),
        [
            ("GET", "/api/v1/graph/entities", {"params": {"label": "Entity) RETURN n //"}}),
            (
                "GET",
                "/api/v1/graph/path",
                {"params": {"from_name": "a", "to_name": "b", "to_label": "x) //"}},
            ),
            ("POST", "/api/v1/graph/search", {"json": {"query": "a", "label": "x) //"}}),
        ],
    )
    async def test_a_hostile_label_is_a_client_error(self, client, method, url, kwargs):
        response = await client.request(method, url, headers={"X-Tenant-ID": "A"}, **kwargs)

        assert response.status_code == 422
