"""Apache AGE is optional — plain Postgres + pgvector must work.

AGE is a *compiled* Postgres extension needing ``shared_preload_libraries =
age``, so it cannot exist on managed Postgres (Supabase, Neon, RDS) or in the
stock ``pgvector/pgvector:pg16`` image. Three things had to become optional for
that to be true, and each is asserted here:

1. **Migration 002.** ``CREATE EXTENSION IF NOT EXISTS age`` raises
   ``FeatureNotSupported`` when the control file is missing — IF NOT EXISTS
   suppresses "already exists", not "not available". As the 2nd of 35
   revisions it blocked 003..035, so a plain-Postgres database got nothing past
   001.

2. **The runtime.** ``GraphStore`` must short-circuit to an empty result rather
   than attempt a connection, and must do so *once* per process: a failed
   ``asyncpg.create_pool`` leaves the pool unset, so an uncached probe retries
   the connection on every single call forever.

3. **Ranking.** ``tri_search`` applies the graph only as an additive boost, so
   vector+BM25 order must survive the graph leg being absent untouched. There
   was no test for that.
"""

from __future__ import annotations

import ast
import importlib.util
import pathlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.config import settings
from life_graph.storage.hybrid import HybridQueryEngine

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[2] / "alembic" / "versions" / "002_add_age_graph.py"
)


# ── 1. The migration guard ────────────────────────────────────


@pytest.fixture
def migration():
    """Load 002 as a module without going through alembic's script directory."""
    spec = importlib.util.spec_from_file_location("_migration_002", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stub_alembic(mod, monkeypatch, *, age_available: bool, age_installed: bool = False):
    op = MagicMock()
    context = MagicMock()
    context.is_offline_mode.return_value = False
    monkeypatch.setattr(mod, "op", op)
    monkeypatch.setattr(mod, "context", context)
    monkeypatch.setattr(mod, "_age_available", lambda: age_available)
    monkeypatch.setattr(mod, "_age_installed", lambda: age_installed)
    return op


class TestMigration002Guard:
    def test_upgrade_emits_no_age_ddl_when_age_is_missing(self, migration, monkeypatch):
        """No CREATE EXTENSION, no LOAD, no create_graph — those are what raised."""
        op = _stub_alembic(migration, monkeypatch, age_available=False)

        migration.upgrade()

        sql = " ".join(str(c.args[0]) for c in op.execute.call_args_list)
        for forbidden in ("CREATE EXTENSION", "LOAD 'age'", "create_graph", "ag_catalog"):
            assert forbidden not in sql, (
                f"002 emitted {forbidden!r} on a server without AGE; that raises "
                "FeatureNotSupported and blocks revisions 003..035."
            )

    def test_upgrade_still_creates_the_schema_when_age_is_missing(self, migration, monkeypatch):
        """AGE's create_graph() makes the `life_graph` schema as a side effect.

        Migrations 019 and 021 put nine ordinary tables in it, so skipping 002
        outright just moves the failure to 019.
        """
        op = _stub_alembic(migration, monkeypatch, age_available=False)

        migration.upgrade()

        sql = " ".join(str(c.args[0]) for c in op.execute.call_args_list)
        assert "CREATE SCHEMA IF NOT EXISTS life_graph" in sql

    def test_upgrade_pins_search_path_when_age_is_missing(self, migration, monkeypatch):
        """The DB role is also named life_graph, so `"$user"` would resolve to
        the schema just created and divert every unqualified CREATE TABLE in
        003..035 into it. The AGE branch pins search_path too."""
        op = _stub_alembic(migration, monkeypatch, age_available=False)

        migration.upgrade()

        sql = [str(c.args[0]) for c in op.execute.call_args_list]
        assert "SET search_path = public" in sql
        assert sql.index("SET search_path = public") > sql.index(
            "CREATE SCHEMA IF NOT EXISTS life_graph"
        )

    def test_downgrade_drops_only_the_schema_when_age_is_not_installed(
        self, migration, monkeypatch
    ):
        op = _stub_alembic(migration, monkeypatch, age_available=False, age_installed=False)

        migration.downgrade()

        sql = " ".join(str(c.args[0]) for c in op.execute.call_args_list)
        assert "DROP SCHEMA IF EXISTS life_graph CASCADE" in sql
        assert "drop_graph" not in sql
        assert "DROP EXTENSION" not in sql

    def test_upgrade_still_builds_the_graph_when_age_is_present(self, migration, monkeypatch):
        """The guard must not have turned 002 into a permanent no-op."""
        op = _stub_alembic(migration, monkeypatch, age_available=True)

        migration.upgrade()

        sql = " ".join(str(c.args[0]) for c in op.execute.call_args_list)
        assert "CREATE EXTENSION IF NOT EXISTS age" in sql
        assert "create_graph('life_graph')" in sql
        for label in migration.VERTEX_LABELS:
            assert f"create_vlabel('life_graph', '{label}')" in sql
        for label in migration.EDGE_LABELS:
            assert f"create_elabel('life_graph', '{label}')" in sql

    def test_graph_and_label_creation_are_re_run_safe(self, migration, monkeypatch):
        """AGE has no CREATE GRAPH IF NOT EXISTS — the catalog guard supplies it."""
        op = _stub_alembic(migration, monkeypatch, age_available=True)

        migration.upgrade()

        for call in op.execute.call_args_list:
            sql = str(call.args[0])
            if "create_graph(" in sql or "create_vlabel(" in sql or "create_elabel(" in sql:
                assert "NOT EXISTS" in sql, f"not re-run safe: {sql}"

    def test_the_probe_runs_on_its_own_connection(self):
        """A query on the *migration* connection silently voids the whole run.

        An implicit transaction there makes alembic's begin_transaction() a
        no-op, so every migration rolls back while `upgrade head` exits 0.
        alembic/env.py guards against this for the AGE label list; the same
        rule applies to the availability probe.
        """
        tree = ast.parse(_MIGRATION.read_text(encoding="utf-8"))
        probe = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_probe")
        sources = {
            ast.unparse(n.func)
            for n in ast.walk(probe)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        assert "engine.connect" in sources, "_probe must open its own connection"
        assert not any(
            s.startswith("op.get_bind().exec") or s == "op.get_bind().execute" for s in sources
        ), "_probe must not query the migration connection"


# ── 2. The runtime short-circuit ──────────────────────────────


@pytest.fixture
def fresh_graph_module(monkeypatch):
    """life_graph.storage.graph with its process-wide caches reset."""
    from life_graph.storage import graph as graph_module

    monkeypatch.setattr(graph_module, "_pool", None)
    monkeypatch.setattr(graph_module, "_available", None)
    return graph_module


class TestGraphStoreShortCircuit:
    @pytest.mark.asyncio
    async def test_disabled_never_attempts_a_connection(self, fresh_graph_module, monkeypatch):
        def explode(*args, **kwargs):
            raise AssertionError("create_pool called with the graph disabled")

        monkeypatch.setattr(fresh_graph_module.asyncpg, "create_pool", explode)
        monkeypatch.setattr(settings, "graph_enabled", False)

        store = fresh_graph_module.GraphStore()

        assert await store.execute_cypher("MATCH (n) RETURN n") == []
        assert await store.get_vertex("Entity", "FastAPI") is None
        assert await store.get_neighbors("FastAPI") == []
        assert await store.find_path("Entity", "a", "Entity", "b") == []
        assert await store.search_entities("fastapi") == []
        assert await store.get_all_entities() == []
        assert await store.create_vertex("Entity", {"name": "x"}) == ""
        assert await store.get_preference_graph("acme", "p1") == {
            "preference": None,
            "connections": [],
        }
        assert await fresh_graph_module.graph_available() is False
        assert await fresh_graph_module.graph_status() == "disabled"

    @pytest.mark.asyncio
    async def test_one_failed_probe_disables_the_graph_for_the_process(
        self, fresh_graph_module, monkeypatch
    ):
        """LOAD 'age' fails in the pool init; retrying it per call is the bug."""
        attempts = []

        async def failing_create_pool(*args, **kwargs):
            attempts.append(1)
            raise RuntimeError('extension "age" is not available')

        monkeypatch.setattr(fresh_graph_module.asyncpg, "create_pool", failing_create_pool)
        monkeypatch.setattr(settings, "graph_enabled", True)

        store = fresh_graph_module.GraphStore()
        for _ in range(5):
            assert await store.execute_cypher("MATCH (n) RETURN n") == []

        assert len(attempts) == 1, f"probed the database {len(attempts)} times, expected 1"
        assert await fresh_graph_module.graph_status() == "unavailable"

    @pytest.mark.asyncio
    async def test_every_store_shares_one_pool(self, fresh_graph_module, monkeypatch):
        """_pool was a class attribute assigned as an instance attribute, so
        every GraphStore() built its own — and memory_links.py makes one per
        link and never closes it."""
        created = []

        class _FakeConn:
            async def fetchrow(self, *args, **kwargs):
                return (1,)

        class _Acquire:
            async def __aenter__(self):
                return _FakeConn()

            async def __aexit__(self, *exc):
                return False

        class _FakePool:
            def acquire(self):
                return _Acquire()

            async def close(self):
                return None

        async def create_pool(*args, **kwargs):
            created.append(1)
            return _FakePool()

        monkeypatch.setattr(fresh_graph_module.asyncpg, "create_pool", create_pool)
        monkeypatch.setattr(settings, "graph_enabled", True)

        pools = [await fresh_graph_module.GraphStore()._get_pool() for _ in range(4)]

        assert len(created) == 1
        assert len({id(p) for p in pools}) == 1


# ── 3. Ranking without the graph ──────────────────────────────


def _memory(mem_id: str, content: str, tags: list[str] | None = None):
    return SimpleNamespace(
        id=mem_id,
        content=content,
        tags=tags or [],
        importance=0.5,
        confidence=0.5,
        source_type="stated",
        created_at=None,
        access_count=0,
        extraction_tier="rules",
    )


# (memory, base_score) pairs, deliberately NOT in descending order so the sort
# is actually exercised. "fastapi" is a graph entity name, so under a working
# AGE install the lowest-scoring row would be boosted past the others.
_RESULTS = [
    (_memory("a", "Chose Postgres for storage"), 0.40),
    (_memory("b", "Deployed on a VPS"), 0.70),
    (_memory("c", "FastAPI handles the API", ["fastapi"]), 0.10),
]


@pytest.fixture
def engine(monkeypatch):
    """A tri_search engine whose vector+BM25 leg returns _RESULTS."""
    eng = HybridQueryEngine()

    memory_store = MagicMock()
    memory_store.hybrid_search = AsyncMock(return_value=list(_RESULTS))
    eng._memory_store = memory_store

    embedder = MagicMock()
    embedder.embed_async = AsyncMock(return_value=[0.1] * 8)
    monkeypatch.setattr("life_graph.api.dependencies.get_embedding_service", lambda: embedder)
    return eng


def _assert_pure_vector_bm25(result):
    memories = result["memories"]
    assert [m["id"] for m in memories] == ["b", "a", "c"], (
        "ranking changed without the graph — tri_search must fall back to the "
        "vector+BM25 order exactly"
    )
    assert all(m["graph_boost"] == 0.0 for m in memories)
    assert all(m["final_score"] == m["base_score"] for m in memories)
    assert result["entities"] == []
    assert result["search_mode"] == "hybrid", "reported three signals when only two ran"
    # graph_weight is excluded from the base normalisation, so nothing needs
    # reweighting — the signals block still reports the configured weights.
    assert result["signals"]["graph_weight"] == 0.20


class TestTriSearchWithoutGraph:
    @pytest.mark.asyncio
    async def test_graph_leg_raising_leaves_ranking_untouched(self, engine, monkeypatch):
        graph_store = MagicMock()
        graph_store.search_entities = AsyncMock(
            side_effect=RuntimeError('relation "ag_catalog.ag_graph" does not exist')
        )
        engine._graph_store = graph_store
        monkeypatch.setattr(
            "life_graph.storage.graph.graph_available", AsyncMock(return_value=True)
        )

        _assert_pure_vector_bm25(await engine.tri_search("fastapi"))
        graph_store.search_entities.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_graph_unavailable_skips_the_leg_entirely(self, engine, monkeypatch):
        graph_store = MagicMock()
        graph_store.search_entities = AsyncMock(return_value=[])
        engine._graph_store = graph_store
        monkeypatch.setattr(
            "life_graph.storage.graph.graph_available", AsyncMock(return_value=False)
        )

        _assert_pure_vector_bm25(await engine.tri_search("fastapi"))
        graph_store.search_entities.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_working_graph_still_boosts(self, engine, monkeypatch):
        """The guard must not have disabled the boost on a real AGE install."""
        graph_store = MagicMock()
        graph_store.search_entities = AsyncMock(return_value=[{"properties": {"name": "FastAPI"}}])
        graph_store.get_neighbors = AsyncMock(return_value=[])
        engine._graph_store = graph_store
        monkeypatch.setattr(
            "life_graph.storage.graph.graph_available", AsyncMock(return_value=True)
        )

        result = await engine.tri_search("fastapi")

        assert result["search_mode"] == "tri_hybrid"
        boosted = next(m for m in result["memories"] if m["id"] == "c")
        assert boosted["graph_boost"] == 0.20
        assert boosted["final_score"] == pytest.approx(0.30)
