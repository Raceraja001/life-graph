"""The owner putting right something remembered (tools/memory_search.py asks_to_correct)."""

from __future__ import annotations

import pytest

from life_graph.services.turn_trace import build_trace
from life_graph.tools.memory_search import asks_to_correct


@pytest.mark.parametrize(
    "message",
    [
        "No, it's a Pixel 8 now",
        "nope, Coimbatore",
        "That's wrong, my dentist is Dr. Mehta",
        "Actually the meeting is on Friday",
        "I moved to Chennai last month",
        "I switched to a Pixel 8",
        "My phone is not a Realme, it's a Pixel",
        "I don't use VS Code anymore",
        "இல்லை, என் போன் Pixel 8",
        "அது தவறு",
    ],
)
def test_corrections(message):
    assert asks_to_correct(message)


@pytest.mark.parametrize(
    "message",
    [
        "Which phone do I use?",
        "Do you remember my phone?",
        "I bought a Pixel 8 for my daughter",
        "Tell me about my week",
        "",
    ],
)
def test_not_corrections(message):
    assert not asks_to_correct(message)


def test_the_trace_marks_profile_card_memories():
    trace = build_trace(
        None,
        [],
        [
            {"id": "a", "content": "My phone is a Pixel 8.", "via": "profile"},
            {"id": "b", "content": "Electricity is due on the 5th."},
        ],
        [],
    )
    assert trace["memories"] == [
        {"id": "a", "snippet": "My phone is a Pixel 8.", "via": "profile"},
        {"id": "b", "snippet": "Electricity is due on the 5th."},
    ]
