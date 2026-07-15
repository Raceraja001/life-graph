"""Unit tests for the budget policy (life_graph.core.budget).

Pure policy — locks the Governor's throttle-autonomous / never-block-interactive
posture.
"""

from __future__ import annotations

import pytest

from life_graph.core.budget import (
    BudgetCategory,
    BudgetPriority,
    decide,
    priority_for,
)

CAP = 10.0


def _decide(spent, priority=BudgetPriority.LOW, interactive=False, cap=CAP, soft=0.8):
    return decide(spent, cap, priority, interactive=interactive, soft_threshold=soft)


# ── Category priority map ─────────────────────────────────────────────

def test_high_priority_categories():
    assert priority_for(BudgetCategory.DRIVER) is BudgetPriority.HIGH
    assert priority_for(BudgetCategory.ADVISOR) is BudgetPriority.HIGH


def test_low_priority_categories():
    for c in (BudgetCategory.RESEARCH, BudgetCategory.FAILURE_MINING, BudgetCategory.WATCHER):
        assert priority_for(c) is BudgetPriority.LOW


# ── Below soft threshold: everything allowed ──────────────────────────

@pytest.mark.parametrize("priority", [BudgetPriority.HIGH, BudgetPriority.LOW])
def test_below_soft_allows_all(priority):
    d = _decide(spent=5.0, priority=priority)  # 50%
    assert d.allowed and not d.throttled
    assert d.remaining_usd == 5.0


# ── Soft band (80%–100%): high allowed, low throttled ─────────────────

def test_soft_band_allows_high_priority():
    d = _decide(spent=8.5, priority=BudgetPriority.HIGH)  # 85%
    assert d.allowed and not d.throttled


def test_soft_band_throttles_low_priority():
    d = _decide(spent=8.5, priority=BudgetPriority.LOW)  # 85%
    assert not d.allowed and d.throttled
    assert "throttled" in d.reason


# ── At/over cap: autonomous denied ────────────────────────────────────

@pytest.mark.parametrize("priority", [BudgetPriority.HIGH, BudgetPriority.LOW])
def test_over_cap_denies_autonomous(priority):
    d = _decide(spent=10.5, priority=priority)  # 105%
    assert not d.allowed and d.throttled
    assert d.remaining_usd == 0.0


# ── Interactive is never blocked ──────────────────────────────────────

def test_interactive_allowed_within_budget():
    d = _decide(spent=5.0, interactive=True)
    assert d.allowed and not d.throttled


def test_interactive_allowed_in_soft_band_even_low_priority():
    d = _decide(spent=9.0, priority=BudgetPriority.LOW, interactive=True)
    assert d.allowed


def test_interactive_allowed_over_cap_but_flagged():
    d = _decide(spent=99.0, interactive=True)  # way over
    assert d.allowed          # never blocked
    assert d.throttled        # but pressure is signalled
    assert "over cap" in d.reason


# ── Non-positive cap disables gating ──────────────────────────────────

@pytest.mark.parametrize("cap", [0.0, -1.0])
def test_non_positive_cap_disables_gating(cap):
    d = _decide(spent=1000.0, priority=BudgetPriority.LOW, cap=cap)
    assert d.allowed and not d.throttled


# ── Boundaries ────────────────────────────────────────────────────────

def test_exactly_soft_threshold_throttles_low():
    # spent == soft*cap is "over_soft" (>=), so low-priority is throttled.
    d = _decide(spent=8.0, priority=BudgetPriority.LOW)  # exactly 80%
    assert not d.allowed


def test_just_below_soft_allows_low():
    d = _decide(spent=7.99, priority=BudgetPriority.LOW)
    assert d.allowed


def test_exactly_cap_denies_autonomous():
    d = _decide(spent=10.0, priority=BudgetPriority.HIGH)  # exactly 100%
    assert not d.allowed
