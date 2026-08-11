# tests/unit/test_list_memories_defer_embedding.py
"""Unit test for PostgresMemoryStore.list_memories()'s include_embedding
option: a plain list view was fetching and discarding every row's pgvector
embedding column. include_embedding=False should defer that column."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.orm import defer

from life_graph.core.tenant import set_tenant_context
from life_graph.models.db import Memory
from life_graph.storage.postgres import PostgresMemoryStore


class _FakeScalars:
    def all(self):
        return []


class _FakeResult:
    def scalars(self):
        return _FakeScalars()


class _FakeSession:
    def __init__(self, captured):
        self._captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, stmt):
        self._captured.append(stmt)
        return _FakeResult()


def _deferred_columns(stmt) -> set[str]:
    """Extract the set of deferred column keys from a Select's loader options.

    A defer()'d Select has one Load in _with_options, whose .context holds
    one _AttributeStrategyLoad per deferred attribute; each carries
    strategy=(('deferred', True), ...) and a path ending in the target
    ColumnProperty (whose .key is the column name).
    """
    deferred = set()
    for opt in stmt._with_options:
        for entry in getattr(opt, "context", ()):
            strategy = dict(getattr(entry, "strategy", ()) or ())
            if strategy.get("deferred"):
                prop = entry.path.path[-1]
                deferred.add(prop.key)
    return deferred


@pytest.mark.asyncio
async def test_include_embedding_false_defers_the_column():
    set_tenant_context("t1")
    store = PostgresMemoryStore()
    captured: list = []

    with patch(
        "life_graph.storage.postgres.async_session",
        lambda: _FakeSession(captured),
    ):
        await store.list_memories(include_embedding=False)

    assert len(captured) == 1
    assert "embedding" in _deferred_columns(captured[0])


@pytest.mark.asyncio
async def test_include_embedding_true_does_not_defer():
    set_tenant_context("t1")
    store = PostgresMemoryStore()
    captured: list = []

    with patch(
        "life_graph.storage.postgres.async_session",
        lambda: _FakeSession(captured),
    ):
        await store.list_memories(include_embedding=True)

    assert len(captured) == 1
    assert "embedding" not in _deferred_columns(captured[0])


@pytest.mark.asyncio
async def test_include_embedding_defaults_to_true():
    """Default must preserve prior behavior for every other caller
    (hybrid.py, recall.py, merge_suggestions.py, cleanup.py, admin.py) that
    doesn't pass this new kwarg at all."""
    set_tenant_context("t1")
    store = PostgresMemoryStore()
    captured: list = []

    with patch(
        "life_graph.storage.postgres.async_session",
        lambda: _FakeSession(captured),
    ):
        await store.list_memories()

    assert "embedding" not in _deferred_columns(captured[0])
