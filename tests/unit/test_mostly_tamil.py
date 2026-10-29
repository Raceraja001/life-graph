"""Tamil questions skip hybrid search's keyword leg: it matched only the English
names left in them (2026-10-29: first result right 67.5% with it, 75.0% without)."""

from __future__ import annotations

import pytest

from life_graph.storage.postgres import mostly_tamil


@pytest.mark.parametrize(
    ("text", "tamil"),
    [
        ("இந்த திட்டத்தின் எந்த பகுதிகளை நான் தொட்டு விடக்கூடாது?", True),
        ("Claude-க்கு ஒரு கோடு சாண்ட்பாக்ஸ் அமைப்பை எப்படி திட்டமிடலாம்?", True),
        ("எனது life-graph project எங்கே இருக்கிறது?", True),
        ("Where is the life-graph project?", False),
        ("What is my phone? Realme X2 Pro", False),
        ("Is the பொங்கல் holiday on the calendar this year?", False),  # mostly English
        ("", False),
        ("12345 ?!", False),
    ],
)
def test_mostly_tamil(text, tamil):
    assert mostly_tamil(text) is tamil
