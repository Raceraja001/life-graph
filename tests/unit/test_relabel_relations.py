"""The people table's role wins over a relation the extractor guessed."""

import uuid

from life_graph.core import aliases
from life_graph.services import entities

SENTHIL, ARUN, LAKSHMI, KAVI = (uuid.uuid4() for _ in range(4))
ROWS = [
    ("senthil", SENTHIL, "Senthil", None, "spouse"),
    ("arun", ARUN, "Arun", None, "brother"),
    ("lakshmi", LAKSHMI, "Lakshmi", None, "friend"),
    ("kavitha", KAVI, "Kavitha", None, "owner"),
]


async def _relabel(monkeypatch, text_):
    async def known(_tenant):
        return ROWS

    monkeypatch.setattr(entities, "_known", known)
    return await entities.relabel("t", text_)


def test_role_of_word():
    assert aliases.role_of_word("husband") == "spouse"
    assert aliases.role_of_word("Mother-in-law") == "mother_in_law"
    assert aliases.role_of_word("college batch") is None


async def test_a_wrong_guess_is_corrected(monkeypatch):
    out = await _relabel(
        monkeypatch,
        "- Senthil (the owner's colleague) works on the airport project.\n"
        "- Arun (the owner's colleague) is using a OnePlus 13.",
    )
    assert "Senthil (the owner's spouse) works" in out
    assert "Arun (the owner's brother) is using" in out
    assert "colleague" not in out


async def test_a_right_or_unknown_label_is_left_alone(monkeypatch):
    text_ = (
        "- Senthil (the owner's husband) is at L&T.\n"
        "- Lakshmi (from the owner's college batch) works at Thenral.\n"
        "- Ravi (the owner's colleague) is learning Japanese."
    )
    assert await _relabel(monkeypatch, text_) == text_
