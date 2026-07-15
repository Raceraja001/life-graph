"""Unit tests for the shadow-mode policy (life_graph.core.shadow).

Pure policy — locks the graduation bar: soak + samples + good-rate, all required.
"""

from __future__ import annotations

import pytest

from life_graph.core.shadow import ShadowGrade, good_rate, should_graduate

# Defaults: min_days=14, min_samples=5, good_rate_threshold=0.8


# ── good_rate ─────────────────────────────────────────────────────────

def test_good_rate_ungraded_is_zero():
    assert good_rate(0, 0) == 0.0


def test_good_rate_all_good():
    assert good_rate(5, 0) == 1.0


def test_good_rate_mixed():
    assert good_rate(3, 1) == 0.75


# ── should_graduate: the happy path ───────────────────────────────────

def test_graduates_when_all_criteria_met():
    assert should_graduate(days_enrolled=14, graded_good=5, graded_bad=0) is True


def test_graduates_with_slack_above_all_thresholds():
    assert should_graduate(days_enrolled=30, graded_good=20, graded_bad=2) is True


# ── each single unmet criterion blocks ────────────────────────────────

def test_blocked_when_soak_too_short():
    assert should_graduate(days_enrolled=13.9, graded_good=50, graded_bad=0) is False


def test_blocked_when_too_few_samples():
    assert should_graduate(days_enrolled=100, graded_good=4, graded_bad=0) is False


def test_blocked_when_good_rate_too_low():
    # 8 good / 2 bad = 0.8 exactly passes; 7/3 = 0.7 fails.
    assert should_graduate(days_enrolled=100, graded_good=7, graded_bad=3) is False


# ── boundaries ────────────────────────────────────────────────────────

def test_exactly_min_days_passes():
    assert should_graduate(days_enrolled=14, graded_good=5, graded_bad=0) is True


def test_exactly_min_samples_passes():
    assert should_graduate(days_enrolled=14, graded_good=5, graded_bad=0) is True


def test_exactly_good_rate_threshold_passes():
    # 8/(8+2) = 0.8 exactly.
    assert should_graduate(days_enrolled=14, graded_good=8, graded_bad=2) is True


def test_ungraded_never_graduates_even_after_soak():
    assert should_graduate(days_enrolled=365, graded_good=0, graded_bad=0) is False


# ── custom thresholds ─────────────────────────────────────────────────

def test_respects_custom_thresholds():
    assert should_graduate(
        days_enrolled=3, graded_good=2, graded_bad=0,
        min_days=2, min_samples=2, good_rate_threshold=0.9,
    ) is True


# ── enum sanity ───────────────────────────────────────────────────────

@pytest.mark.parametrize("grade,value", [(ShadowGrade.GOOD, "good"), (ShadowGrade.BAD, "bad")])
def test_grade_values(grade, value):
    assert grade.value == value
