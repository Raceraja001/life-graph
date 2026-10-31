"""Jarvis starts a personal answer with the owner's matching memories (services/memory_context.py)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from life_graph.services import memory_retrieval, profile_card
from life_graph.services.memory_context import (
    HEADER,
    NOTHING_ELSE,
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


def _wire(monkeypatch, found, card=()):
    import life_graph.api.dependencies as deps

    async def fake_retrieve(question, limit=6, **kw):
        if isinstance(found, Exception):
            raise found
        return found

    async def fake_card(tenant_id):
        return list(card)

    _Store.touched = None
    monkeypatch.setattr(deps, "get_store", lambda: _Store())
    monkeypatch.setattr(memory_retrieval, "retrieve", fake_retrieve)
    monkeypatch.setattr(profile_card, "card_items", fake_card)


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


def test_a_note_that_is_not_the_owners_word_says_where_it_came_from():
    when = datetime(2026, 10, 3, tzinfo=UTC)
    out = render(
        [
            ("Prefers local HTML files.", when, {"evidence": "said"}),
            ("Seems to like short answers.", when, {"evidence": "inferred"}),
            ("Car insurance renews in March.", None, {"evidence": "document"}),
        ]
    )
    assert out.splitlines()[-3:] == [
        "- (2026-10-03) Prefers local HTML files.",
        "- (2026-10-03 · your guess) Seems to like short answers.",
        "- (from a document) Car insurance renews in March.",
    ]
    assert "never as a fact" in HEADER


CARD = [{"id": "c1", "content": "My phone is a Realme X2 Pro.", "created_at": None}]


async def test_the_profile_card_comes_first_and_is_not_repeated(monkeypatch):
    on_card = SimpleNamespace(
        id="c1", content="My phone is a Realme X2 Pro.", created_at=None, properties={}
    )
    other = SimpleNamespace(
        id=uuid.uuid4(),
        content="Seems to like short answers.",
        created_at=None,
        source_type="distillation",
        trust_tier="verified",
        properties={},
    )
    _wire(monkeypatch, [on_card, other], card=CARD)
    used: list[dict] = []
    out = await memory_block("raja", "Which phone case should I buy?", used=used)
    assert out.startswith(profile_card.HEADER)
    assert out.count("Realme X2 Pro") == 1
    assert "(your guess) Seems to like short answers." in out
    # Always shown is not read: only the searched memory is touched.
    assert _Store.touched == [other.id]
    assert used == [
        {"id": "c1", "content": "My phone is a Realme X2 Pro.", "via": "profile"},
        {"id": str(other.id), "content": "Seems to like short answers."},
    ]


async def test_with_a_card_nothing_found_does_not_contradict_it(monkeypatch):
    _wire(monkeypatch, [], card=CARD)
    out = await memory_block("raja", "What is my blood group?")
    assert out.startswith(profile_card.HEADER) and out.endswith(NOTHING_ELSE)
    assert NOTHING_FOUND not in out


async def test_the_card_still_shows_when_search_cannot_run(monkeypatch):
    _wire(monkeypatch, None, card=CARD)
    assert await memory_block("raja", "anything at all here please") == profile_card.render(CARD)
    _wire(monkeypatch, RuntimeError("db down"), card=CARD)
    assert await memory_block("raja", "anything at all here please") == profile_card.render(CARD)
