"""Detection of explicit confidence claims in captured text.

Pure functions: no DB, no LLM. The anchor date is fixed so relative
horizons ("by Friday") are deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from life_graph.services.prediction_detection import detect_predictions, parse_horizon

# Wednesday 16 September 2026, 10:00 UTC
NOW = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)


def _one(text: str):
    found = detect_predictions(text, NOW)
    assert len(found) == 1, found
    return found[0]


@pytest.mark.parametrize(
    ("text", "statement", "confidence"),
    [
        ("I'm 80% sure the migration lands by Friday.", "The migration lands by Friday", 0.8),
        ("The client will sign this month, 70% confident.", "The client will sign this month", 0.7),
        (
            "There's a 60% chance that the new release ships next week.",
            "The new release ships next week",
            0.6,
        ),
        (
            "Dashboard rewrite done in two weeks (75% likely)",
            "Dashboard rewrite done in two weeks",
            0.75,
        ),
        (
            "We're 85% certain that Priya accepts the offer by October 5th.",
            "Priya accepts the offer by October 5th",
            0.85,
        ),
        (
            "I am 30 percent confident the vendor delivers on time",
            "The vendor delivers on time",
            0.3,
        ),
    ],
)
def test_detects_stated_confidence(text, statement, confidence):
    found = _one(text)
    assert found.statement == statement
    assert found.confidence == pytest.approx(confidence)
    assert found.quote == text


@pytest.mark.parametrize(
    "text",
    [
        "Revenue grew 15% this quarter.",
        "Battery is at 80% now.",
        "95% of users never open settings.",
        "I think the client will sign.",  # no number: nothing to calibrate against
        "I'm 100% sure about this.",  # certainty is not a calibratable claim
        "I'm 0% sure it works.",
        "There's a 70% chance of rain tomorrow.",
    ],
)
def test_ignores_numbers_that_are_not_confidence_claims(text):
    assert detect_predictions(text, NOW) == []


def test_finds_each_claim_in_a_longer_capture_once():
    text = (
        "Bought milk. I'm 80% sure the migration lands by Friday. "
        "Maybe 65% chance I finish the book by next month.\n"
        "I'm 80% sure the migration lands by Friday."
    )
    found = detect_predictions(text, NOW)
    assert [p.statement for p in found] == [
        "The migration lands by Friday",
        "I finish the book by next month",
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("done by Friday", "2026-09-18"),
        ("done by next Friday", "2026-09-25"),
        ("done by Wednesday", "2026-09-23"),  # said on a Wednesday: a week out
        ("ships tomorrow", "2026-09-17"),
        ("lands today", "2026-09-16"),
        ("done this week", "2026-09-20"),
        ("done next week", "2026-09-27"),
        ("sign this month", "2026-09-30"),
        ("sign by end of the month", "2026-09-30"),
        ("finish next month", "2026-10-31"),
        ("hit it this year", "2026-12-31"),
        ("hit it next year", "2027-12-31"),
        ("done in two weeks", "2026-09-30"),
        ("done within 10 days", "2026-09-26"),
        ("accepts by October 5th", "2026-10-05"),
        ("accepts by the 5th of October", "2026-10-05"),
        ("renewed by March 1", "2027-03-01"),  # already past this year
        ("reach 1000 users by 2026-12-31", "2026-12-31"),
    ],
)
def test_parse_horizon(text, expected):
    got = parse_horizon(text, NOW)
    assert got is not None
    assert got.date().isoformat() == expected
    assert (got.hour, got.minute) == (23, 59)  # open for the whole deadline day


def test_parse_horizon_without_a_deadline():
    assert parse_horizon("the vendor delivers on time", NOW) is None
