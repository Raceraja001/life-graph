"""create_link refuses a memory of another tenant, the same way as a missing one.

The foreign keys on ``memory_links`` only prove that both memories exist, in
any tenant, so a caller could link its memory to another tenant's (and then
walk to it through ``/memories/{id}/linked``). ``create_link`` now checks both
ends against the caller's tenant first (services/memory/links.py
``_both_in_tenant``). The real query is covered against Postgres in
tests/integration/test_memory_link_tenant_pg.py.
"""

from __future__ import annotations

import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from life_graph.core.errors import NotFoundError
from life_graph.models.schemas import MemoryLinkCreate
from life_graph.services.memory import links


def _recording_session():
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    @contextlib.asynccontextmanager
    async def factory():
        yield session

    return session, factory


async def test_another_tenants_memory_is_not_linked(monkeypatch):
    session, factory = _recording_session()
    sync = AsyncMock()
    monkeypatch.setattr(links, "async_session", factory)
    monkeypatch.setattr(links, "_both_in_tenant", AsyncMock(return_value=False))
    monkeypatch.setattr(links, "_sync_link_to_graph", sync)

    with pytest.raises(NotFoundError) as exc:
        await links.create_link(uuid.uuid4(), uuid.uuid4(), "RELATED_TO", tenant_id="A")

    # The same words as a memory that does not exist (the FK branch).
    assert str(exc.value) == links.MEMORY_NOT_FOUND
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    sync.assert_not_awaited()


async def test_the_check_is_asked_about_both_ends_and_the_callers_tenant(monkeypatch):
    session, factory = _recording_session()
    check = AsyncMock(return_value=True)
    monkeypatch.setattr(links, "async_session", factory)
    monkeypatch.setattr(links, "_both_in_tenant", check)
    monkeypatch.setattr(links, "_sync_link_to_graph", AsyncMock())
    source, target = uuid.uuid4(), uuid.uuid4()

    await links.create_link(source, target, "RELATED_TO", tenant_id="A")

    check.assert_awaited_once_with(session, source, target, "A")
    session.add.assert_called_once()


async def test_both_in_tenant_needs_both_ids_back():
    source, target = uuid.uuid4(), uuid.uuid4()

    def session_returning(ids):
        result = MagicMock()
        result.all.return_value = ids
        return MagicMock(scalars=AsyncMock(return_value=result))

    assert await links._both_in_tenant(session_returning([source, target]), source, target, "A")
    assert not await links._both_in_tenant(session_returning([source]), source, target, "A")
    assert not await links._both_in_tenant(session_returning([]), source, target, "A")


def test_the_api_does_not_accept_associated_links():
    """ASSOCIATED links are learned (services/memory/associations.py), not made by hand."""
    with pytest.raises(ValidationError):
        MemoryLinkCreate(source_memory_id="s", target_memory_id="t", link_type="ASSOCIATED")
    MemoryLinkCreate(source_memory_id="s", target_memory_id="t", link_type="RELATED_TO")
