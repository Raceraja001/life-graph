# tests/unit/test_contradiction_value_change.py
"""Unit tests for the value-change contradiction rule (2026-11-25).

"Priya lives in Chennai" → "Priya lives in Bangalore" is the same statement
with one value replaced, and the detector now suggests a supersede for it.
Every suggestion becomes an owner approval, so the hard negatives below (two
values that can both be true, or a different subject) matter as much as the
positives.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.services.contradiction import (
    ContradictionDetector,
    _check_value_change,
    _determine_resolution,
)

_EMB = [0.1, 0.2, 0.3]

VALUE_CHANGES = [
    ("Priya lives in Chennai.", "Priya lives in Bangalore.", "Chennai", "Bangalore"),
    ("Priya's birthday is 3 May.", "Priya's birthday is 4 May.", "3", "4"),
    ("My rent is 18000 rupees.", "My rent is 21000 rupees.", "18000", "21000"),
    ("My rent is 18,000 rupees a month.", "My rent is 21,000 rupees a month.", "18,000", "21,000"),
    ("I live in Chennai.", "I live in Coimbatore now.", "Chennai", "Coimbatore"),
    ("My manager is Anand.", "My manager is Deepa.", "Anand", "Deepa"),
    ("The meeting is on Tuesday.", "The meeting is on Thursday.", "Tuesday", "Thursday"),
    ("Our flight leaves at 7:30.", "Our flight leaves at 9:15.", "7:30", "9:15"),
    ("I work at Zoho.", "I work at Freshworks.", "Zoho", "Freshworks"),
    ("Our car is a white hatchback.", "Our car is a grey hatchback.", "white", "grey"),
    ("My son is in class four.", "My son is in class five.", "four", "five"),
    ("The rent is due on the 5th.", "The rent is due on the 10th.", "5th", "10th"),
    ("I weigh 72 kg.", "I weigh 68 kg.", "72", "68"),
]

# Both can be true, or the subject changed: never a value change.
HARD_NEGATIVES = [
    ("I have a dog.", "I have a cat."),  # no value words at all
    ("Priya lives in Chennai.", "Priya's office is in Bangalore."),  # different predicate
    ("Priya lives in Chennai.", "Arun lives in Bangalore."),  # different subject too
    ("My sister lives in Chennai.", "My brother lives in Bangalore."),
    ("Priya's birthday is 3 May.", "Maha's birthday is 3 May."),  # subject swapped
    ("Arun works at Zoho.", "Deepa works at Zoho."),
    ("I speak Tamil.", "I speak English."),  # many-valued verb
    ("Priya is friends with Anand.", "Priya is friends with Deepa."),  # list relation
    ("Priya is interested in Rust.", "Priya is interested in Go."),
    ("I visited Delhi in March.", "I visited Delhi in June."),  # no single-value cue
    ("I have a meeting on Tuesday.", "I have a meeting on Thursday."),
    ("I lived in Pune.", "I lived in Delhi."),  # past: both can be true
    ("I work at Zoho.", "I also work at Freshworks on weekends."),  # "also"
    ("My manager is Anand.", "Another manager is Deepa."),
    ("My manager is Anand.", "My manager is also Deepa."),  # a second value
    ("Priya is in Chennai on Monday.", "Priya is in Bangalore on Friday."),  # two changes
    ("Raja is working on Uzhavu.", "Raja is working on Life Graph."),  # activity
    ("My manager is Anand.", "My manager is a nice guy."),  # no value on one side
    ("I live in Chennai.", "I live in Chennai now."),  # same value
    ("Our car is a grey hatchback.", "Our car is a gray hatchback."),  # same value, spelled
    ("I live in Chennai.", "I don't live in Chennai, I live in Pune."),  # negation rules
    ("I live in Chennai.", "I live in Chennai, near Adyar."),  # a detail added, none replaced
]


def _memory(content: str, embedding=_EMB, properties=None):
    return SimpleNamespace(
        id="existing-1",
        content=content,
        status="active",
        properties=properties or {},
        embedding=embedding,
    )


@pytest.mark.parametrize(("existing", "new", "old_value", "new_value"), VALUE_CHANGES)
def test_value_change_is_detected(existing, new, old_value, new_value):
    reason = _check_value_change(new, existing)
    assert reason == f"Value change: '{old_value}' → '{new_value}'"


@pytest.mark.parametrize(("existing", "new"), HARD_NEGATIVES)
def test_compatible_or_other_subject_is_not_a_value_change(existing, new):
    assert _check_value_change(new, existing) is None
    assert _check_value_change(existing, new) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(("existing", "new"), HARD_NEGATIVES[:16])
async def test_hard_negatives_raise_no_supersede_through_the_detector(existing, new):
    detector = ContradictionDetector(store=None)  # type: ignore[arg-type]
    found = await detector.check_candidates(new, [_memory(existing)], _EMB)
    assert [c for c in found if c.resolution == "supersede"] == []


@pytest.mark.asyncio
async def test_detector_reports_value_change_as_a_supersede():
    detector = ContradictionDetector(store=None)  # type: ignore[arg-type]
    found = await detector.check_candidates(
        "Priya lives in Bangalore.", [_memory("Priya lives in Chennai.")], _EMB
    )
    assert len(found) == 1
    c = found[0]
    assert c.conflict_type == "value_change"
    assert c.resolution == "supersede"
    assert c.reason == "Value change: 'Chennai' → 'Bangalore'"
    assert c.existing_memory_id == "existing-1"


@pytest.mark.asyncio
async def test_value_change_in_a_different_project_keeps_both():
    detector = ContradictionDetector(store=None)  # type: ignore[arg-type]
    found = await detector.check_candidates(
        "The deadline is in June.",
        [_memory("The deadline is in March.", properties={"project": "alpha"})],
        _EMB,
        {"project": "beta"},
    )
    assert len(found) == 1
    assert found[0].conflict_type == "scope"
    assert found[0].resolution == "scope"


@pytest.mark.asyncio
async def test_value_change_below_the_similarity_floor_is_not_checked():
    detector = ContradictionDetector(store=None)  # type: ignore[arg-type]
    # Orthogonal vectors: cosine 0, below contradiction_similarity_threshold.
    found = await detector.check_candidates(
        "Priya lives in Bangalore.",
        [_memory("Priya lives in Chennai.", embedding=[1.0, 0.0])],
        [0.0, 1.0],
    )
    assert found == []


def test_value_change_resolves_to_supersede():
    assert _determine_resolution("value_change", _memory("x")) == "supersede"
