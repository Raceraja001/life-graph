"""Tenant filters as defence in depth (links and hybrid_search).

- ``PostgresMemoryStore.hybrid_search`` fetched its final rows by id alone,
  trusting the ranking SQL's own tenant filters. The fetch is scoped too now.
- ``create_link`` and ``auto_link_memories`` defaulted to the tenant
  "legacy", so a caller that forgot the tenant wrote links nobody owns. They
  take the current tenant context now, and raise without one.
- ``get_link_graph`` with no tenant walked every tenant's links; it takes the
  context's tenant now. Its memory filter is covered against Postgres in
  tests/integration/test_link_graph_tenant_pg.py.
"""

from __future__ import annotations

import contextlib
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.core.tenant import tenant_scope
from life_graph.models.db import _EMBED_DIM
from life_graph.services.memory import links
from life_graph.storage import postgres
from life_graph.storage.postgres import PostgresMemoryStore


def _factory(session):
    @contextlib.asynccontextmanager
    async def factory():
        yield session

    return factory


class _RankingSession:
    """First execute: the ranking SQL returns another tenant's id. Then the fetch."""

    def __init__(self, scored_id):
        self.scored_id = scored_id
        self.statements: list = []

    async def execute(self, stmt, params=None):
        self.statements.append(stmt)
        if len(self.statements) == 1:
            return SimpleNamespace(fetchall=lambda: [(self.scored_id, 0.9)])
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))


async def test_hybrid_search_fetches_rows_of_the_current_tenant_only(monkeypatch):
    session = _RankingSession(uuid.uuid4())
    monkeypatch.setattr(postgres, "async_session", _factory(session))
    monkeypatch.setattr(postgres, "_apply_vector_scan_settings", AsyncMock())

    with tenant_scope("tenant-a"):
        hits = await PostgresMemoryStore().hybrid_search(
            embedding=[0.0] * _EMBED_DIM, query_text="where is it"
        )

    assert hits == []
    fetch = session.statements[-1].compile()
    assert "memories.tenant_id" in str(fetch)
    assert "tenant-a" in fetch.params.values()


def _recording_session():
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


async def test_create_link_without_a_tenant_or_context_raises(monkeypatch):
    session = _recording_session()
    monkeypatch.setattr(links, "async_session", _factory(session))
    monkeypatch.setattr(links, "_both_in_tenant", AsyncMock(return_value=True))

    with pytest.raises(RuntimeError, match="No tenant context"):
        await links.create_link(uuid.uuid4(), uuid.uuid4(), "RELATED_TO")

    session.add.assert_not_called()


async def test_create_link_takes_the_tenant_from_context(monkeypatch):
    session = _recording_session()
    check = AsyncMock(return_value=True)
    monkeypatch.setattr(links, "async_session", _factory(session))
    monkeypatch.setattr(links, "_both_in_tenant", check)
    monkeypatch.setattr(links, "_sync_link_to_graph", AsyncMock())

    with tenant_scope("ctx-tenant"):
        link = await links.create_link(uuid.uuid4(), uuid.uuid4(), "RELATED_TO")

    assert link.tenant_id == "ctx-tenant"
    assert check.await_args.args[3] == "ctx-tenant"


def _embedded(vector):
    return SimpleNamespace(id=uuid.uuid4(), embedding=vector)


async def test_auto_link_without_a_tenant_or_context_raises(monkeypatch):
    create = AsyncMock()
    monkeypatch.setattr(links, "create_link", create)

    with pytest.raises(RuntimeError, match="No tenant context"):
        await links.auto_link_memories([_embedded([1.0, 0.0]), _embedded([1.0, 0.0])])

    create.assert_not_awaited()


async def test_auto_link_takes_the_tenant_from_context(monkeypatch):
    create = AsyncMock()
    monkeypatch.setattr(links, "create_link", create)

    with tenant_scope("ctx-tenant"):
        made = await links.auto_link_memories([_embedded([1.0, 0.0]), _embedded([1.0, 0.0])])

    assert made == 1
    assert create.await_args.kwargs["tenant_id"] == "ctx-tenant"


async def test_link_graph_without_a_tenant_or_context_raises(monkeypatch):
    session = MagicMock(execute=AsyncMock())
    monkeypatch.setattr(links, "async_session", _factory(session))

    with pytest.raises(RuntimeError, match="No tenant context"):
        await links.get_link_graph(uuid.uuid4())

    session.execute.assert_not_awaited()
