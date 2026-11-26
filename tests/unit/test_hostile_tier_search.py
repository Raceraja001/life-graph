"""Memories other people wrote never come back from search or recall by default.

A memory with trust tier ``hostile_possible`` (core/trust.py: text from a
surface like WhatsApp, written by someone else) lands ``pending``, but the
owner's Keep makes it ``active``. Nothing in search or recall checked the
tier, so once kept it could reach ``retrieve()`` and the Jarvis memory block
like any of the owner's own notes. Only the context snapshot filtered them.

Now the store leaves them out in SQL (``hybrid_search``, ``search_similar``,
``list_recall_candidates``) unless a caller passes ``include_hostile=True``,
and ``retrieve()`` drops any that arrive another way (a link, an entity).
The Postgres side is covered in tests/integration/test_hostile_tier_search_pg.py.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.dialects import postgresql

from life_graph.core.tenant import tenant_scope
from life_graph.models.db import _EMBED_DIM
from life_graph.services.memory import retrieval
from life_graph.storage import postgres
from life_graph.storage.postgres import HOSTILE_TIER, PostgresMemoryStore


def _factory(session):
    @contextlib.asynccontextmanager
    async def factory():
        yield session

    return factory


class _Session:
    """Records every statement; returns no rows."""

    def __init__(self):
        self.calls: list[tuple] = []

    async def execute(self, stmt, params=None):
        self.calls.append((stmt, params))
        return SimpleNamespace(
            fetchall=lambda: [],
            scalars=lambda: SimpleNamespace(all=lambda: []),
        )


def _wire(monkeypatch) -> _Session:
    session = _Session()
    monkeypatch.setattr(postgres, "async_session", _factory(session))
    monkeypatch.setattr(postgres, "_apply_vector_scan_settings", AsyncMock())
    return session


def _orm_sql(session: _Session) -> tuple[str, dict]:
    stmt = session.calls[-1][0]
    compiled = stmt.compile(dialect=postgresql.dialect())
    return str(compiled), dict(compiled.params)


def test_the_tier_left_out_is_the_hostile_one():
    assert HOSTILE_TIER == "hostile_possible"


async def test_hybrid_search_leaves_hostile_rows_out_of_every_leg(monkeypatch):
    session = _wire(monkeypatch)
    with tenant_scope("t-hostile"):
        await PostgresMemoryStore().hybrid_search(
            embedding=[0.0] * _EMBED_DIM, query_text="where is it"
        )
    sql, params = str(session.calls[0][0]), session.calls[0][1]
    # The vector pool, the keyword matches and the IDF row count.
    assert sql.count("AND trust_tier <> :hostile_tier") == 3
    assert params["hostile_tier"] == "hostile_possible"


async def test_hybrid_search_can_be_asked_for_them(monkeypatch):
    session = _wire(monkeypatch)
    with tenant_scope("t-hostile"):
        await PostgresMemoryStore().hybrid_search(
            embedding=[0.0] * _EMBED_DIM, query_text="where is it", include_hostile=True
        )
    sql, params = str(session.calls[0][0]), session.calls[0][1]
    assert "trust_tier" not in sql
    assert "hostile_tier" not in params


async def test_search_similar_leaves_hostile_rows_out(monkeypatch):
    session = _wire(monkeypatch)
    with tenant_scope("t-hostile"):
        await PostgresMemoryStore().search_similar(embedding=[0.0] * _EMBED_DIM)
    sql, params = _orm_sql(session)
    assert "memories.trust_tier !=" in sql
    assert "hostile_possible" in params.values()


async def test_search_similar_can_be_asked_for_them(monkeypatch):
    session = _wire(monkeypatch)
    with tenant_scope("t-hostile"):
        await PostgresMemoryStore().search_similar(
            embedding=[0.0] * _EMBED_DIM, include_hostile=True
        )
    sql, params = _orm_sql(session)
    assert "trust_tier" not in sql.split("WHERE", 1)[1]
    assert "hostile_possible" not in params.values()


async def test_recall_candidates_leave_hostile_rows_out(monkeypatch):
    session = _wire(monkeypatch)
    with tenant_scope("t-hostile"):
        await PostgresMemoryStore().list_recall_candidates(filters={"status": "active"})
    sql, params = _orm_sql(session)
    assert "memories.trust_tier !=" in sql
    assert "hostile_possible" in params.values()


async def test_recall_candidates_can_be_asked_for_them(monkeypatch):
    session = _wire(monkeypatch)
    with tenant_scope("t-hostile"):
        await PostgresMemoryStore().list_recall_candidates(
            filters={"status": "active"}, include_hostile=True
        )
    _, params = _orm_sql(session)
    assert "hostile_possible" not in params.values()


def test_retrieve_drops_hostile_rows_that_arrive_another_way(monkeypatch):
    """A link or a named entity can bring a row search never returned."""
    seen: list = []

    def assess(question, items, now=None):
        seen.extend(items)
        return {"abstain": False, "abstention_reason": None, "per_memory": [{}] * len(items)}

    monkeypatch.setattr(retrieval, "assess_candidate_evidence", assess)
    own = SimpleNamespace(id=1, trust_tier="self")
    untagged = SimpleNamespace(id=2)  # no tier: fenced as external, still returned
    other = SimpleNamespace(id=3, trust_tier="hostile_possible")
    result = retrieval._result("q", [own, other, untagged])
    assert [m.id for m in result] == [1, 2]
    assert [m.id for m in seen] == [1, 2]


async def test_the_dashboard_search_alone_sees_them(monkeypatch):
    """api/search.py: the include_pending opt-in (the dashboard) is the only
    caller that gets them; the MCP ``search`` tool never sets it."""
    import ast
    import pathlib

    src = (pathlib.Path(retrieval.__file__).parents[2] / "api" / "search.py").read_text()
    tree = ast.parse(src)
    assigns = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "include_hostile" for t in n.targets)
    ]
    assert len(assigns) == 1
    assert ast.unparse(assigns[0].value) == "bool(body.include_pending)"
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in ("hybrid_search", "search_similar", "tri_search")
    ]
    assert calls
    for call in calls:
        kw = {k.arg: ast.unparse(k.value) for k in call.keywords}
        assert kw.get("include_hostile") == "include_hostile", ast.unparse(call)
