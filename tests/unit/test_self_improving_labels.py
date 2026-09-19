"""Labels for the self-improvement loop come from the user's memory reviews.

A wrong label teaches the wrong thing, silently, forever — so these pin the
conservative rules in suite_builder.derive_expected.
"""

from __future__ import annotations

import json
import uuid

from life_graph.self_improving.suite_builder import LabelledTrace, derive_expected, split_for

MIN = 0.45


def _fact(content: str, confidence: float = 0.9, fact_type: str = "fact") -> dict:
    return {"content": content, "fact_type": fact_type, "confidence": confidence}


def _memory(status: str, content: str, fact_type: str = "fact") -> dict:
    return {"status": status, "content": content, "fact_type": fact_type, "entities": []}


def test_approved_fact_is_expected():
    expected = derive_expected([_fact("Uses uv")], {0: _memory("active", "Uses uv")}, MIN)
    assert [f["content"] for f in expected] == ["Uses uv"]


def test_edit_before_approval_becomes_the_target():
    """The user's corrected wording is what the model should have produced."""
    expected = derive_expected(
        [_fact("Uses uv instead of pip")],
        {0: _memory("active", "Uses uv instead of pip and conda")},
        MIN,
    )
    assert expected[0]["content"] == "Uses uv instead of pip and conda"


def test_rejected_fact_is_not_expected():
    expected = derive_expected(
        [_fact("Keep"), _fact("Wrong")],
        {0: _memory("active", "Keep"), 1: _memory("rejected", "Wrong")},
        MIN,
    )
    assert [f["content"] for f in expected] == ["Keep"]


def test_everything_rejected_means_extract_nothing():
    """A confirmed empty target is a real label, not a missing one."""
    assert derive_expected([_fact("Noise")], {0: _memory("rejected", "Noise")}, MIN) == []


def test_pending_review_makes_the_trace_unusable():
    assert derive_expected([_fact("A")], {0: _memory("pending", "A")}, MIN) is None


def test_unlinked_fact_makes_the_trace_unusable():
    """Deduplicated or deleted facts can't be told apart from rejections."""
    assert derive_expected([_fact("A"), _fact("B")], {0: _memory("active", "A")}, MIN) is None


def test_below_floor_facts_are_ignored_like_production_ignores_them():
    expected = derive_expected(
        [_fact("Solid"), _fact("Shaky", confidence=0.2)],
        {0: _memory("active", "Solid")},  # the shaky one was never stored
        MIN,
    )
    assert [f["content"] for f in expected] == ["Solid"]


def test_trace_without_facts_is_not_used():
    """Nothing tells us what the model missed, so there is no label."""
    assert derive_expected([], {}, MIN) is None


def test_expected_facts_satisfy_the_extraction_schema():
    """Few-shot outputs are replayed as assistant turns under constrained decoding."""
    expected = derive_expected(
        [_fact("Uses uv", fact_type="preference")],
        {0: _memory("active", "Uses uv", fact_type="preference")},
        MIN,
    )
    assert set(expected[0]) == {"content", "fact_type", "confidence", "entities"}
    trace = LabelledTrace("t", "I use uv", expected)
    assert json.loads(trace.expected_output()) == {"facts": expected}
    assert trace.as_few_shot() == {"input": "I use uv", "output": {"facts": expected}}


def test_split_is_stable_and_roughly_one_in_five():
    ids = [str(uuid.UUID(int=i)) for i in range(2000)]
    first = [split_for(i) for i in ids]
    assert first == [split_for(i) for i in ids]  # never moves
    holdout = first.count("holdout") / len(ids)
    assert 0.15 < holdout < 0.25
