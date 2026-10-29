"""Where a memory came from: said, read, observed or guessed (core/evidence.py)."""

from __future__ import annotations

import pytest

from life_graph.core import evidence as ev


@pytest.mark.parametrize(
    ("source", "tier", "props", "expected"),
    [
        ("capture", "self", {}, ev.SAID),
        ("explicit", "self", {}, ev.SAID),
        ("document", "external", {}, ev.DOCUMENT),
        ("episode", "verified", {"kind": "episode"}, ev.SUMMARY),
        ("capture", "verified", {"kind": "episode"}, ev.SUMMARY),
        ("distillation", "verified", {}, ev.INFERRED),
        ("belief_challenge", "self", {}, ev.INFERRED),
        ("capture", "self", {"inferred_from": ["a", "b"]}, ev.INFERRED),
        ("project_scan", "verified", {}, ev.OBSERVED),
        ("mcp", "external", {}, ev.OUTSIDE),
        ("unknown", "external", {}, ev.OUTSIDE),
        (None, None, None, ev.OUTSIDE),
    ],
)
def test_evidence_of(source, tier, props, expected):
    assert ev.evidence_of(source, tier, props) == expected


def test_the_old_inferred_default_is_a_guess_only_from_our_own_pipeline():
    # failure_mining stores source_type="inferred" on purpose (tier verified) ...
    assert ev.evidence_of("inferred", "verified", {}) == ev.INFERRED
    # ... while an API write without a source got the same label: 13 of 15 such
    # production memories were the owner's own notes and test strings (2026-10-29).
    assert ev.evidence_of("inferred", "external", {}) == ev.OUTSIDE


def test_a_stamped_kind_wins_and_an_unknown_one_is_ignored():
    assert ev.evidence_of("capture", "self", {"evidence": ev.INFERRED}) == ev.INFERRED
    assert ev.evidence_of("capture", "self", {"evidence": "certain"}) == ev.SAID


def test_guesses_are_the_inferred_and_the_unverified():
    assert {k for k in ev.KINDS if ev.is_guess(k)} == {ev.INFERRED, ev.OUTSIDE}
    assert set(ev.PROMPT_LABEL) == set(ev.KINDS)
