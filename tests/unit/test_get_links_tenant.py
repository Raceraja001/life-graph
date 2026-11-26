"""get_links never lists every tenant's links (services/memory/links.py).

``tenant_id=None`` used to mean "no tenant filter": any caller that forgot to
pass one got the links of every tenant touching that memory id. It now
defaults to the tenant context and raises without one, like get_link_graph.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.core.tenant import tenant_scope
from life_graph.services.memory import links


def _session_factory():
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    @contextlib.asynccontextmanager
    async def factory():
        yield session

    return session, factory


def _params(session) -> dict:
    stmt = session.execute.await_args.args[0]
    return stmt.compile().params


async def test_no_tenant_given_uses_the_tenant_context(monkeypatch):
    session, factory = _session_factory()
    monkeypatch.setattr(links, "async_session", factory)

    with tenant_scope("links-ctx-tenant"):
        await links.get_links(uuid.uuid4())

    assert "links-ctx-tenant" in _params(session).values()


async def test_a_given_tenant_is_used(monkeypatch):
    session, factory = _session_factory()
    monkeypatch.setattr(links, "async_session", factory)

    with tenant_scope("someone-else"):
        await links.get_links(uuid.uuid4(), tenant_id="links-named")

    values = _params(session).values()
    assert "links-named" in values
    assert "someone-else" not in values


async def test_no_tenant_and_no_context_raises(monkeypatch):
    session, factory = _session_factory()
    monkeypatch.setattr(links, "async_session", factory)

    task = asyncio.get_running_loop().create_task(
        links.get_links(uuid.uuid4()), context=contextvars.Context()
    )
    with pytest.raises(RuntimeError):
        await task
    session.execute.assert_not_awaited()
