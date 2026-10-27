"""The owner's promises with a time (services/commitments.py, web-chat-wave1 F2)."""

from datetime import UTC, datetime

import pytest

from life_graph.services.commitments import find_commitment

# Tuesday 27 October 2026, 09:00 UTC.
NOW = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)


def _at(day, hour, minute=0):
    return datetime(2026, 10 if day > 20 else 11, day, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "when", "due_from", "due_by"),
    [
        ("I'll call the insurer this week", "this week", _at(29, 10), _at(1, 23, 59)),
        ("I need to pay the school fees by Friday", "by Friday", _at(29, 10), _at(30, 23, 59)),
        ("I'll send Murugan the photos tomorrow", "tomorrow", _at(28, 10), _at(28, 23, 59)),
        ("I will book the gas cylinder today", "today", _at(27, 17), _at(27, 23, 59)),
        ("I have to renew the passport next week", "next week", _at(4, 10), _at(8, 23, 59)),
        ("I'm going to see the doctor on Monday", "on Monday", _at(2, 10), _at(2, 23, 59)),
        ("I should file the claim this month", "this month", _at(27, 10), _at(31, 23, 59)),
        ("I'll clean the garage this weekend", "this weekend", _at(31, 10), _at(1, 23, 59)),
    ],
)
def test_promises_with_a_time(text, when, due_from, due_by):
    found = find_commitment(text, NOW, "UTC")
    assert found is not None
    assert (found["when"].lower(), found["due_from"], found["due_by"]) == (when.lower(), due_from, due_by)
    assert found["what"] == text


@pytest.mark.parametrize(
    "text",
    [
        "remind me to call mom tomorrow",  # a reminder: reminder_set's
        "Will I need to call tomorrow?",  # a question
        "I'll summarise the news every Monday",  # a repeat: ask_schedule's
        "I called him yesterday",  # done, not promised
        "I'll do it later",  # no time
        "",
    ],
)
def test_not_promises(text):
    assert find_commitment(text, NOW, "UTC") is None


def test_only_the_promise_sentence_is_kept():
    found = find_commitment("Thanks for that. I'll pay the electricity bill by Friday. Hi to Amma", NOW, "UTC")
    assert found["what"] == "I'll pay the electricity bill by Friday"


def test_times_are_the_owners_day():
    # 14:30 in India: tomorrow mid-morning there is 04:30 UTC.
    found = find_commitment("I'll call the bank tomorrow", NOW, "Asia/Kolkata")
    assert found["due_from"] == datetime(2026, 10, 28, 4, 30, tzinfo=UTC)
    assert found["due_by"] == datetime(2026, 10, 28, 18, 29, tzinfo=UTC)


def test_today_late_in_the_day_still_gets_an_hour():
    late = datetime(2026, 10, 27, 20, 0, tzinfo=UTC)
    found = find_commitment("I'll reply to the landlord tonight", late, "UTC")
    assert found["due_from"] == datetime(2026, 10, 27, 21, 0, tzinfo=UTC)
