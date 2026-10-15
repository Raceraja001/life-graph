"""Tests for the read-only memory_search agent tool.

Every persona's allowed_tools lists "memory_search", so the two things
that matter most here are the ones a persona cannot control: which
tenant the search runs under (never an argument — the contextvar or the
kernel task), and that reading memory writes nothing. The fake store
below makes the write paths tripwires rather than no-ops, so a future
"just touch the rows we surfaced" is a test failure.

Tenant/task context is established with `with` blocks inside the test
bodies rather than from a fixture: pytest-asyncio runs each test
coroutine in its own `contextvars.Context`, so a token taken in the test
cannot be reset from fixture teardown.

No DB: the recall/search layer is faked at life_graph.api.dependencies.
"""

from __future__ import annotations

import inspect
import json
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from life_graph.core.tenant import has_tenant_context, tenant_scope
from life_graph.scoring.ranking import INDEX_CONTENT_CHARS
from life_graph.tools.memory_search import memory_search
from life_graph.tools.registry import registry

# Store methods that write — mutation or access bookkeeping. A read-only
# tool must touch none of them. The create/update/delete trio is named
# store/update/delete on PostgresMemoryStore; the names below are the real
# ones so the hasattr guard in test_never_calls_a_write_path has teeth.
WRITE_PATHS = ("touch", "touch_many", "store", "update", "delete")


def _memory(content: str = "The developer self-hosts everything.", **kw) -> SimpleNamespace:
    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        content=content,
        source_type=kw.get("source_type", "capture"),
        importance=kw.get("importance", 0.8),
        created_at=kw.get("created_at", datetime(2026, 10, 13, 9, 30, tzinfo=UTC)),
    )


class FakeStore:
    """Records each hybrid_search call; every write path is a tripwire."""

    def __init__(
        self,
        hits: list[SimpleNamespace] | None = None,
        raises: Exception | None = None,
    ):
        self.hits = hits if hits is not None else [_memory()]
        self.raises = raises
        self.calls: list[dict] = []

    async def hybrid_search(self, *, embedding, query_text, limit, statuses=("active",)):
        from life_graph.core.tenant import get_current_tenant_id

        self.calls.append(
            {
                "tenant": get_current_tenant_id(),
                "query_text": query_text,
                "limit": limit,
                "statuses": statuses,
            }
        )
        if self.raises is not None:
            raise self.raises
        return [(mem, 0.9) for mem in self.hits]


def _tripwire(name: str):
    async def _boom(*args, **kwargs):
        raise AssertionError(f"memory_search called the write path {name}()")

    return _boom


for _name in WRITE_PATHS:
    setattr(FakeStore, _name, _tripwire(_name))


_DEFAULT_EMBEDDING = [0.1, 0.2, 0.3]
_UNSET = object()


class FakeManager:
    """Stands in for MemoryManager — only the embedding call is used.

    ``embedding=None`` is a meaningful value (backend down), so the
    default is a sentinel rather than None.
    """

    def __init__(self, embedding: list[float] | None = _UNSET):  # type: ignore[assignment]
        self.embedding = list(_DEFAULT_EMBEDDING) if embedding is _UNSET else embedding
        self.queries: list[str] = []

    async def generate_embedding(self, text: str):
        self.queries.append(text)
        return self.embedding


@pytest.fixture
def wire(monkeypatch):
    """Point the tool's lazy dependency lookups at fakes."""
    from life_graph.api import dependencies

    def _wire(store=None, manager=None):
        store = FakeStore() if store is None else store
        manager = FakeManager() if manager is None else manager
        monkeypatch.setattr(dependencies, "get_store", lambda: store)
        monkeypatch.setattr(dependencies, "get_memory_manager", lambda: manager)
        return store, manager

    return _wire


@contextmanager
def as_task(tenant_id: str):
    """Run as if inside a kernel AgentTask for *tenant_id*.

    set_task_context() is fire-and-forget, so the var is set and reset
    through its token here — both inside the calling context.
    """
    from life_graph.core import task_context as task_mod

    ctx = task_mod.TaskContext(task_id=uuid.uuid4(), tenant_id=tenant_id)
    token = task_mod._task_context_var.set(ctx)
    try:
        yield ctx
    finally:
        task_mod._task_context_var.reset(token)


# ── Tenant scoping ────────────────────────────────────────────


async def test_searches_under_the_current_tenant(wire):
    mine = [_memory(content="I prefer Gemini Flash."), _memory(content="Dual-boots Linux.")]
    store, manager = wire(store=FakeStore(hits=mine))

    with tenant_scope("acme"):
        out = json.loads(await memory_search("which model do I like?"))

    # The tenant is never an argument — nothing the LLM says can widen it.
    assert set(inspect.signature(memory_search).parameters) == {"query", "limit"}
    assert len(store.calls) == 1
    assert store.calls[0]["tenant"] == "acme"
    assert store.calls[0]["query_text"] == "which model do I like?"
    assert store.calls[0]["statuses"] == ("active",)
    assert manager.queries == ["which model do I like?"]
    assert [row["id"] for row in out["results"]] == [str(m.id) for m in mine]
    assert out["count"] == 2


async def test_falls_back_to_task_context_tenant(wire):
    store, _ = wire()

    with as_task("task-tenant"):
        out = json.loads(await memory_search("anything"))

        assert store.calls[0]["tenant"] == "task-tenant"
        assert out["count"] == 1
        # tenant_scope, not set_tenant_context: the borrowed tenant does not
        # outlive the call and leak into whatever the agent does next.
        assert not has_tenant_context()


async def test_returns_error_json_without_tenant_context(monkeypatch):
    """No request tenant, no task — say so rather than guess a tenant."""
    from life_graph.api import dependencies

    def _never(*args, **kwargs):
        raise AssertionError("memory_search touched the store with no tenant context")

    monkeypatch.setattr(dependencies, "get_store", _never)
    monkeypatch.setattr(dependencies, "get_memory_manager", _never)

    out = json.loads(await memory_search("secrets of another tenant"))

    assert "tenant context" in out["error"]
    assert "results" not in out


# ── Limit clamping ────────────────────────────────────────────


async def test_limit_defaults_to_five_and_caps_at_twenty(wire):
    store, _ = wire()

    with tenant_scope("acme"):
        await memory_search("q")
        await memory_search("q", limit=50)
        await memory_search("q", limit=0)

    assert [call["limit"] for call in store.calls] == [5, 20, 1]


# ── Read-only contract ────────────────────────────────────────


async def test_never_calls_a_write_path(wire, monkeypatch):
    from life_graph.services.recall import RecallEngine
    from life_graph.storage.postgres import PostgresMemoryStore

    # The tripwire names must be the real store's, or this proves nothing.
    for name in WRITE_PATHS:
        assert hasattr(PostgresMemoryStore, name), f"{name}() is no longer a store write path"

    async def _no_disclosure(*args, **kwargs):
        raise AssertionError("memory_search recorded a disclosure")

    monkeypatch.setattr(RecallEngine, "record_disclosure", _no_disclosure)

    wire(store=FakeStore(hits=[_memory(), _memory()]))

    with tenant_scope("acme"):
        out = json.loads(await memory_search("what do you know about me?"))

    # A tripwire raise comes back as the tool's error JSON (it catches
    # everything), so assert on that first — it carries which path was hit.
    assert "error" not in out, out["error"]
    assert out["count"] == 2


# ── Failure modes return JSON, never raise ────────────────────


async def test_returns_error_json_when_search_fails(wire):
    # Embedding backend down — nothing to search with.
    wire(manager=FakeManager(embedding=None))
    with tenant_scope("acme"):
        out = json.loads(await memory_search("q"))
    assert "error" in out
    assert "Embedding" in out["error"]

    # The search itself blew up.
    wire(store=FakeStore(raises=RuntimeError("pgvector exploded")))
    with tenant_scope("acme"):
        out = json.loads(await memory_search("q"))
    assert "pgvector exploded" in out["error"]


# ── Result shape ──────────────────────────────────────────────


async def test_result_rows_are_compact_and_truncated(wire):
    created = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    long_one = _memory(content="x" * 500, source_type="manual", importance=0.42, created_at=created)
    wire(store=FakeStore(hits=[long_one]))

    with tenant_scope("acme"):
        row = json.loads(await memory_search("q"))["results"][0]

    assert set(row) == {"id", "content", "type", "importance", "created_at"}
    assert row["id"] == str(long_one.id)
    assert len(row["content"]) == INDEX_CONTENT_CHARS + 1  # + the ellipsis
    assert row["content"].endswith("…")
    assert row["type"] == "manual"
    assert row["importance"] == 0.42
    assert row["created_at"] == created.isoformat()


# ── Registration ──────────────────────────────────────────────


def test_registered_in_registry_as_memory_search():
    assert "memory_search" in registry.tool_names

    spec = next(t for t in registry.get_tools() if t["function"]["name"] == "memory_search")
    params = spec["function"]["parameters"]
    assert params["required"] == ["query"]
    assert set(params["properties"]) == {"query", "limit"}
    assert params["properties"]["limit"]["default"] == 5


def test_registered_by_main_startup():
    """The @tool decorator only fires on import, so boot must import us.

    Asserted against the "agent_tools" startup step specifically — an
    import anywhere else in the module would not survive a reshuffle of
    the lifespan steps.
    """
    import ast
    import textwrap

    from life_graph import main

    tree = ast.parse(textwrap.dedent(inspect.getsource(main.lifespan)))

    step = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.With)
        and any(
            isinstance(item.context_expr, ast.Call)
            and getattr(item.context_expr.func, "id", None) == "startup_step"
            and item.context_expr.args[1].value == "agent_tools"
            for item in node.items
        )
    )
    imported = {
        alias.name
        for node in ast.walk(step)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "life_graph.tools.memory_search" in imported
