"""Unit tests for the pure verification math in scripts/verify_embeddings.py."""

from __future__ import annotations

import math

from scripts.verify_embeddings import cosine, ranking_ok, separation_ok

# ── cosine ────────────────────────────────────────────────────────────

def test_cosine_identical_is_one():
    assert math.isclose(cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0, rel_tol=1e-9)


def test_cosine_orthogonal_is_zero():
    assert math.isclose(cosine([1.0, 0.0], [0.0, 1.0]), 0.0, abs_tol=1e-9)


def test_cosine_empty_or_mismatched_is_zero():
    assert cosine([], [1.0]) == 0.0
    assert cosine([1.0, 2.0], [1.0]) == 0.0
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


# ── ranking_ok ────────────────────────────────────────────────────────

def test_ranking_ok_when_related_beats_unrelated():
    assert ranking_ok(related_scores=[0.8, 0.75], unrelated_scores=[0.3, 0.4]) is True


def test_ranking_fails_on_overlap():
    # Weakest related (0.5) does not beat strongest unrelated (0.6).
    assert ranking_ok(related_scores=[0.5, 0.9], unrelated_scores=[0.6, 0.2]) is False


def test_ranking_fails_on_empty():
    assert ranking_ok([], [0.1]) is False
    assert ranking_ok([0.9], []) is False


# ── separation_ok ─────────────────────────────────────────────────────

def test_separation_ok():
    # dup clears 0.92, distinct below it.
    assert separation_ok(dup_score=0.95, distinct_score=0.40) is True


def test_separation_fails_when_dup_below_threshold():
    assert separation_ok(dup_score=0.90, distinct_score=0.40) is False


def test_separation_fails_when_distinct_above_threshold():
    assert separation_ok(dup_score=0.95, distinct_score=0.93) is False
