"""The owner introducing themselves is told to the extractor as the owner.

"Hi Jarvis! I'm Priya Raman. My friends call me Pri." was stored as "Priya
Raman (called Pri) is the owner's friend" (live path, 2026-11-02).
"""

from __future__ import annotations

import pytest

from life_graph.extraction.llm import self_introduction


@pytest.mark.parametrize(
    ("text", "hint"),
    [
        ("Hi Jarvis! I'm Priya Raman. My friends call me Pri.", "Priya Raman (the owner)"),
        ("Myself Deepak, from Trichy.", "Deepak (the owner)"),
        ("This is Anitha here, I just installed you.", "Anitha (the owner)"),
        ("I am Karthikeyan, but everyone calls me Karthi.", "Karthikeyan (the owner)"),
        ("my name is Sudha", "Sudha (the owner)"),
        ("I’m Meera", "Meera (the owner)"),
    ],
)
def test_a_self_introduction_names_the_owner(text, hint):
    assert self_introduction(text) == hint


@pytest.mark.parametrize(
    "text",
    [
        "I'm Fine, thanks.",
        "I'm Going to Pune tomorrow.",
        "This is Google's model, not ours.",
        "My friend Kavya and I started a bakery.",
        "i'm tired today",
        "",
    ],
)
def test_other_sentences_name_no_one(text):
    assert self_introduction(text) == ""
