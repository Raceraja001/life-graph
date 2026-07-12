"""Unit tests for the big-decision detection heuristic (Judgment Engine)."""

from __future__ import annotations

from life_graph.services.judgment import BIG_DECISION_TAG, detect_big_decision


def test_money_signal():
    big, signals = detect_big_decision("Invest $20k in new servers")
    assert big is True
    assert "money" in signals


def test_long_commitment_signal():
    big, signals = detect_big_decision("Sign a 12 month lease for the office")
    assert big is True
    assert "commitment" in signals


def test_irreversibility_signal():
    big, signals = detect_big_decision("Quit my job to go full-time on this")
    assert big is True
    assert "irreversible" in signals


def test_reasoning_text_is_considered():
    big, signals = detect_big_decision(
        "Go with option A", reasoning="This is basically irreversible once shipped"
    )
    assert big is True


def test_small_decision_is_not_big():
    big, signals = detect_big_decision("Use tabs instead of spaces")
    assert big is False
    assert signals == []


def test_empty_is_not_big():
    assert detect_big_decision("") == (False, [])
    assert detect_big_decision(None) == (False, [])


def test_tag_constant_exported():
    assert BIG_DECISION_TAG == "big_decision"
