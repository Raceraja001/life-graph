"""Jarvis starts a personal answer with the owner's matching memories (services/memory_context.py)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from life_graph.services.memory_context import HEADER, memory_block, render, search_text


def test_a_short_follow_up_is_searched_with_the_previous_question():
    history = [
        {"role": "user", "content": "When does my car insurance renew?"},
        {"role": "assistant", "content": "In March."},
    ]
    assert search_text("and the house?", history) == (
        "When does my car insurance renew?\nand the house?"
    )
    long = "Which school did I say my daughter will join next year?"
    assert search_text(long, history) == long
    assert search_text("hi", []) == "hi"


def test_render_dates_and_trims():
    when = datetime(2026, 10, 3, tzinfo=UTC)
    out = render([("x" * 400, when), ("My car insurance renews in March.", None)])
    lines = out.splitlines()
    assert out.startswith(HEADER)
    assert lines[-2].startswith("- (2026-10-03) ") and lines[-2].endswith("…")
    assert lines[-1] == "- My car insurance renews in March."
    assert render([]) == ""


class _Store:
    def __init__(self, hits):
        self.hits, self.touched, self.kwargs = hits, None, None

    async def hybrid_search(self, **kw):
        self.kwargs = kw
        return self.hits

    async def touch_many(self, ids):
        self.touched = ids


def _wire(monkeypatch, store, embedding=(0.1,)):
    class _Manager:
        async def generate_embedding(self, text):
            return list(embedding) if embedding else None

    import life_graph.api.dependencies as deps

    monkeypatch.setattr(deps, "get_store", lambda: store)
    monkeypatch.setattr(deps, "get_memory_manager", lambda: _Manager())


async def test_memory_block_searches_active_memories_and_counts_the_read(monkeypatch):
    mem = SimpleNamespace(
        id=uuid.uuid4(), content="My car insurance renews in March.", created_at=None
    )
    store = _Store([(mem, 0.8)])
    _wire(monkeypatch, store)
    out = await memory_block("raja", "When does my car insurance renew?")
    assert "My car insurance renews in March." in out
    assert store.kwargs["statuses"] == ("active",)
    assert store.touched == [mem.id]


async def test_no_embedding_means_no_block(monkeypatch):
    store = _Store([])
    _wire(monkeypatch, store, embedding=None)
    assert await memory_block("raja", "anything at all here please") == ""
    assert store.kwargs is None


async def test_a_failure_is_never_a_failed_answer(monkeypatch):
    class _Broken(_Store):
        async def hybrid_search(self, **kw):
            raise RuntimeError("db down")

    _wire(monkeypatch, _Broken([]))
    assert await memory_block("raja", "When does my car insurance renew?") == ""
