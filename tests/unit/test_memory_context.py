"""Jarvis starts a personal answer with the owner's matching memories (services/memory_context.py)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from life_graph.services import memory_retrieval
from life_graph.services.memory_context import (
    HEADER,
    NOTHING_FOUND,
    memory_block,
    render,
    search_text,
)


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
    touched = None

    async def touch_many(self, ids):
        _Store.touched = ids


def _wire(monkeypatch, found):
    import life_graph.api.dependencies as deps

    async def fake_retrieve(question, limit=6):
        if isinstance(found, Exception):
            raise found
        return found

    _Store.touched = None
    monkeypatch.setattr(deps, "get_store", lambda: _Store())
    monkeypatch.setattr(memory_retrieval, "retrieve", fake_retrieve)


async def test_matching_memories_are_shown_and_counted_as_read(monkeypatch):
    mem = SimpleNamespace(
        id=uuid.uuid4(), content="My car insurance renews in March.", created_at=None
    )
    _wire(monkeypatch, [mem])
    out = await memory_block("raja", "When does my car insurance renew?")
    assert "My car insurance renews in March." in out
    assert _Store.touched == [mem.id]


async def test_nothing_relevant_is_said_not_left_out(monkeypatch):
    _wire(monkeypatch, [])
    assert await memory_block("raja", "What is my blood group?") == NOTHING_FOUND
    assert _Store.touched is None


async def test_memory_that_could_not_be_searched_says_nothing(monkeypatch):
    _wire(monkeypatch, None)  # no embedding
    assert await memory_block("raja", "anything at all here please") == ""


async def test_a_failure_is_never_a_failed_answer(monkeypatch):
    _wire(monkeypatch, RuntimeError("db down"))
    assert await memory_block("raja", "When does my car insurance renew?") == ""
