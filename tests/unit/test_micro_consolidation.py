"""Post-session micro-consolidation (audit H8, 2026-11-19).

Three faults in the job that runs after every session end:

* it closed the process-wide AGE pool when it finished, breaking every graph
  query running at the same moment;
* its dedup called ``search_by_embedding``, which exists nowhere, so the
  AttributeError was swallowed and ``duplicates_removed`` was always 0;
* its edges matched both ends as ``Entity`` while the vertices were written
  with ``infer_label``'s label, so edges to a Person/Project/Technology never
  landed — and were counted anyway — and a re-run duplicated the ones that did.

No database: fakes stand in for the session, the memory store and the graph.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from life_graph.core.tenant import tenant_scope
from life_graph.services.memory.micro_consolidation import MicroConsolidator
from life_graph.storage import graph as graph_module
from life_graph.storage.graph import GraphStore

NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)


def _mem(content="I use PostgreSQL", embedding=(1.0, 0.0, 0.0), created_at=NOW, **kw):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="acme",
        content=content,
        status="active",
        embedding=list(embedding) if embedding is not None else None,
        created_at=created_at,
        importance=0.5,
        tags=kw.pop("tags", []),
        properties=kw.pop("properties", {}),
        **kw,
    )


class _Session:
    def __init__(self) -> None:
        self.statements: list = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    async def execute(self, stmt):
        self.statements.append(stmt)
        return SimpleNamespace(rowcount=1)

    async def commit(self) -> None:
        self.commits += 1


def _consolidator(store_rows):
    session = _Session()
    consolidator = MicroConsolidator(lambda: session, embedding_service=None)
    consolidator._store = SimpleNamespace(search_similar=AsyncMock(return_value=store_rows))
    return consolidator, session


# ── Dedup ─────────────────────────────────────────────────────


class TestDedup:
    @pytest.mark.asyncio
    async def test_a_near_identical_older_memory_supersedes_the_new_one(self):
        old = _mem(embedding=(1.0, 0.01, 0.0), created_at=NOW - timedelta(days=3))
        new = _mem(embedding=(1.0, 0.0, 0.0))
        consolidator, session = _consolidator([new, old])

        with tenant_scope("acme"):
            removed = await consolidator._dedup_against_existing([new])

        assert removed == 1
        (stmt,) = session.statements
        params = stmt.compile(dialect=postgresql.dialect()).params
        assert params["status"] == "superseded"
        assert params["superseded_by"] == old.id
        # Scoped to the tenant, and to the new memory only.
        assert "tenant_id" in str(stmt.whereclause)
        assert new.id in params.values()

    @pytest.mark.asyncio
    async def test_search_is_the_real_store_method_limited_to_active_rows(self):
        new = _mem()
        consolidator, _session = _consolidator([new])

        with tenant_scope("acme"):
            await consolidator._dedup_against_existing([new])

        call = consolidator._store.search_similar.await_args
        assert call.kwargs["filters"] == {"status": "active"}
        assert call.kwargs["embedding"] == [1.0, 0.0, 0.0]

    @pytest.mark.asyncio
    async def test_only_itself_found_removes_nothing(self):
        new = _mem()
        consolidator, session = _consolidator([new])

        with tenant_scope("acme"):
            assert await consolidator._dedup_against_existing([new]) == 0
        assert session.statements == []

    @pytest.mark.asyncio
    async def test_a_merely_similar_memory_is_kept(self):
        """Below the conservative 0.95 cosine nothing is superseded."""
        other = _mem(embedding=(1.0, 1.0, 0.0), created_at=NOW - timedelta(days=3))  # cos 0.707
        new = _mem(embedding=(1.0, 0.0, 0.0))
        consolidator, session = _consolidator([other, new])

        with tenant_scope("acme"):
            assert await consolidator._dedup_against_existing([new]) == 0
        assert session.statements == []

    @pytest.mark.asyncio
    async def test_a_newer_duplicate_does_not_supersede_the_older_session_memory(self):
        older_in_session = _mem(created_at=NOW - timedelta(days=3))
        newer = _mem(embedding=(1.0, 0.01, 0.0))
        consolidator, session = _consolidator([older_in_session, newer])

        with tenant_scope("acme"):
            assert await consolidator._dedup_against_existing([older_in_session]) == 0
        assert session.statements == []


# ── Graph ─────────────────────────────────────────────────────


class _FakeGraph:
    """Records calls; ``existing`` holds edges already in the graph."""

    instances: list[_FakeGraph] = []

    def __init__(self) -> None:
        self.vertices: list[tuple[str, str]] = []
        self.edges: list[tuple[str, str, str, str]] = []
        self.existing: set[frozenset[str]] = set()
        self.closed = False
        _FakeGraph.instances.append(self)

    async def upsert_vertex(self, label, name, properties=None, tenant_id=None):
        self.vertices.append((label, name))
        return "1"

    async def create_edge_if_absent(self, from_label, from_name, to_label, to_name, **_kw):
        self.edges.append((from_label, from_name, to_label, to_name))
        key = frozenset((from_name, to_name))
        if key in self.existing:
            return ""
        self.existing.add(key)
        return "42"

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_graph(monkeypatch):
    _FakeGraph.instances = []
    monkeypatch.setattr("life_graph.storage.graph.GraphStore", _FakeGraph)
    monkeypatch.setattr(
        "life_graph.jobs.graph_migration.infer_label",
        lambda name, context="": "Technology" if name == "postgresql" else "Project",
    )
    return _FakeGraph


class TestGraph:
    @pytest.mark.asyncio
    async def test_edges_match_the_labels_the_vertices_were_written_with(self, fake_graph):
        consolidator, _ = _consolidator([])
        mem = _mem(tags=["postgresql", "life-graph"])

        entities, edges = await consolidator._update_graph([mem])

        graph = fake_graph.instances[0]
        assert sorted(graph.vertices) == [("Project", "life-graph"), ("Technology", "postgresql")]
        ((from_label, from_name, to_label, to_name),) = graph.edges
        labels = {from_name: from_label, to_name: to_label}
        assert labels == {"postgresql": "Technology", "life-graph": "Project"}
        assert (entities, edges) == (2, 1)

    @pytest.mark.asyncio
    async def test_an_edge_that_already_exists_is_not_counted(self, fake_graph):
        consolidator, _ = _consolidator([])
        first = _mem(tags=["postgresql", "life-graph"])
        again = _mem(tags=["life-graph", "postgresql"])

        _entities, edges = await consolidator._update_graph([first, again])

        assert edges == 1

    @pytest.mark.asyncio
    async def test_an_edge_that_did_not_land_is_not_counted(self, fake_graph, monkeypatch):
        monkeypatch.setattr(_FakeGraph, "create_edge_if_absent", AsyncMock(return_value=""))
        consolidator, _ = _consolidator([])

        _entities, edges = await consolidator._update_graph([_mem(tags=["postgresql", "x-y"])])

        assert edges == 0

    @pytest.mark.asyncio
    async def test_the_shared_pool_is_still_open_afterwards(self, monkeypatch):
        """The real GraphStore: its pool is process-wide, so a job must not close it."""
        sentinel = SimpleNamespace(close=AsyncMock())
        monkeypatch.setattr(graph_module, "_pool", sentinel)
        monkeypatch.setattr(GraphStore, "upsert_vertex", AsyncMock(return_value="1"))
        monkeypatch.setattr(GraphStore, "create_edge_if_absent", AsyncMock(return_value="9"))
        consolidator, _ = _consolidator([])

        await consolidator._update_graph([_mem(tags=["postgresql", "life-graph"])])

        assert graph_module._pool is sentinel
        sentinel.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_graph_store_close_leaves_the_shared_pool_alone(self, monkeypatch):
        sentinel = SimpleNamespace(close=AsyncMock())
        monkeypatch.setattr(graph_module, "_pool", sentinel)

        await GraphStore().close()

        assert graph_module._pool is sentinel
        sentinel.close.assert_not_awaited()


# ── create_edge_if_absent ─────────────────────────────────────


class TestCreateEdgeIfAbsent:
    @pytest.mark.asyncio
    async def test_an_existing_edge_is_not_created_again(self):
        store = GraphStore()
        store.execute_cypher = AsyncMock(return_value=[{"v": 5}])
        store.create_edge = AsyncMock()

        assert await store.create_edge_if_absent("Person", "a", "Project", "b", "rel") == ""

        store.create_edge.assert_not_awaited()
        cypher = store.execute_cypher.await_args.args[0]
        assert "(a:Person)-[e:rel]-(b:Project)" in cypher
        assert "a.tenant_id = $tid" in cypher and "b.tenant_id = $tid" in cypher

    @pytest.mark.asyncio
    async def test_a_missing_edge_is_created_in_the_same_tenant(self):
        store = GraphStore()
        store.execute_cypher = AsyncMock(return_value=[])
        store.create_edge = AsyncMock(return_value="7")

        assert (
            await store.create_edge_if_absent("Person", "a", "Project", "b", "rel", tenant_id="T")
            == "7"
        )

        assert store.create_edge.await_args.kwargs["tenant_id"] == "T"
        assert store.execute_cypher.await_args.kwargs["params"]["tid"] == "T"

    @pytest.mark.asyncio
    async def test_labels_are_still_validated(self):
        store = GraphStore()
        store.execute_cypher = AsyncMock(return_value=[])

        with pytest.raises(ValueError):
            await store.create_edge_if_absent("Person) //", "a", "Project", "b", "rel")
