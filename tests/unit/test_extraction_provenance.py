"""Extraction provenance must be recorded, not just modelled.

``memories.extraction_tier``, ``extraction_confidence`` and
``capture_event_id`` have existed since the early migrations, and recall reads
all three back — but nothing ever wrote them, so every memory claimed unknown
provenance and "which tier produced this, from which capture?" could not be
answered. These tests pin the two halves: the pipeline stamps each fact with
the tier that produced it, and the store persists what it is given.
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.extraction.pipeline import _deduplicate, _stamp_tier
from life_graph.extraction.rules import ExtractedFact
from life_graph.storage.postgres import _as_uuid


def _fact(content: str, confidence: float = 0.8, tier: str = "") -> ExtractedFact:
    return ExtractedFact(content=content, fact_type="fact", confidence=confidence, tier=tier)


def test_stamp_tier_marks_unstamped_facts():
    facts = [_fact("a"), _fact("b")]
    _stamp_tier(facts, "regex")
    assert [f.tier for f in facts] == ["regex", "regex"]


def test_stamp_tier_keeps_existing_provenance():
    """A fact that survived an earlier merge keeps the tier that produced it."""
    facts = [_fact("a", tier="regex"), _fact("b")]
    _stamp_tier(facts, "llm")
    assert [f.tier for f in facts] == ["regex", "llm"]


def test_dedup_keeps_the_winning_tier():
    """Dedup keeps the higher-confidence fact, so its tier must travel with it."""
    kept = _deduplicate([_fact("Same fact", 0.5, "regex"), _fact("same FACT", 0.9, "llm")])
    assert len(kept) == 1
    assert kept[0].tier == "llm"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("not-a-uuid", None),
        ("", None),
        (17, None),
    ],
)
def test_as_uuid_tolerates_junk(value, expected):
    """capture_event_id arrives from JSONB properties; junk must not break ingest."""
    assert _as_uuid(value) is expected


def test_as_uuid_accepts_uuid_and_string():
    real = uuid.uuid4()
    assert _as_uuid(real) == real
    assert _as_uuid(str(real)) == real
