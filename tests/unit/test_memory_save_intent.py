"""Which owner messages count as asking Jarvis to remember (memory_save)."""

from __future__ import annotations

import pytest

from life_graph.services.lead import PERSONAL_TOOLS
from life_graph.tools.memory_search import SAVE_INTENT


@pytest.mark.parametrize(
    "message",
    [
        "Remember that my car insurance renews on 5 March",
        "please save this: I'm allergic to peanuts",
        "note that the school fees are due Friday",
        "Don't forget I moved to Chennai",
        "keep in mind I prefer morning meetings",
        "make a note: Murugan's number changed",
    ],
)
def test_asking_to_remember(message):
    assert SAVE_INTENT.search(message)


@pytest.mark.parametrize(
    "message",
    [
        "Summarise my latest email from the bank",
        "what's on my calendar tomorrow?",
        "read this page and tell me what it says",
    ],
)
def test_not_asking_to_remember(message):
    assert not SAVE_INTENT.search(message)


def test_saving_is_a_personal_tool():
    # Never offered to a model that leaves the machine.
    assert "memory_save" in PERSONAL_TOOLS
