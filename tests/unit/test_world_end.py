"""When a fact stops being true, from its own words (ADR m8-ingestion §5.1, world end).

``extraction/world_time.py`` ``find_end`` / ``world_end_of`` / ``end_from_model``:
pure rules, no I/O and no model. The end is the first instant after the named
period, in the owner's time zone.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from life_graph.extraction import world_time as w

IST = ZoneInfo("Asia/Kolkata")
#: Saturday 28 Nov 2026, 15:00 in Chennai.
NOW = datetime(2026, 11, 28, 15, 0, tzinfo=IST)
#: Saturday 14 Nov 2026: "until 20 November" is still ahead.
MID_NOV = datetime(2026, 11, 14, 10, 0, tzinfo=IST)


def _end(text, anchor=NOW):
    found = w.find_end(text, anchor, IST)
    return None if found is None else (found.end.date(), found.precision)


@pytest.mark.parametrize(
    ("text", "anchor", "expected"),
    [
        ("The owner is on leave until 20 November.", MID_NOV, (date(2026, 11, 21), "day")),
        ("The owner is on leave till 5 December.", NOW, (date(2026, 12, 6), "day")),
        ("The owner is in Madurai till March.", NOW, (date(2027, 4, 1), "month")),
        ("Valid until June 2027.", NOW, (date(2027, 7, 1), "month")),
        ("The passport is valid until 2031.", NOW, (date(2032, 1, 1), "year")),
        ("The pass is valid until 2026-12-31.", NOW, (date(2027, 1, 1), "day")),
        ("Cover runs until 15/1/2027.", NOW, (date(2027, 1, 16), "day")),
        ("Staying till tomorrow.", NOW, (date(2026, 11, 30), "day")),
        ("Night shifts until next week.", NOW, (date(2026, 12, 7), "week")),
        ("On a diet until the end of this month.", NOW, (date(2026, 12, 1), "month")),
        ("Has the car until the end of the month.", NOW, (date(2026, 12, 1), "month")),
        ("Has the car until the end of March.", NOW, (date(2027, 4, 1), "month")),
        ("Visiting until the 20th of December.", NOW, (date(2026, 12, 21), "day")),
        ("Offer valid up to 31 January 2027.", NOW, (date(2027, 2, 1), "day")),
        # Past tense: a date or month with no year is the most recent one.
        ("The owner was on leave until 10 November.", NOW, (date(2026, 11, 11), "day")),
        ("The owner had a car loan till October.", NOW, (date(2026, 11, 1), "month")),
        # Tamil and Tanglish: the time comes before வரை / varaikum.
        ("நவம்பர் 20 வரை லீவு.", MID_NOV, (date(2026, 11, 21), "day")),
        ("அடுத்த மாசம் வரை மதுரையில் இருக்கேன்.", NOW, (date(2027, 1, 1), "month")),
        ("டிசம்பர் மாசம் வரைக்கும் நைட் ஷிஃப்ட்.", NOW, (date(2027, 1, 1), "month")),
        ("2027 வரை ஒப்பந்தம்.", NOW, (date(2028, 1, 1), "year")),
        ("நாளைக்கு வரை அம்மா இங்கே.", NOW, (date(2026, 11, 30), "day")),
        ("மார்ச் கடைசி வரை சென்னையில்.", NOW, (date(2027, 4, 1), "month")),
        ("March varaikum Coimbatore la.", NOW, (date(2027, 4, 1), "month")),
        ("December 15 varaikkum leave la iruken.", NOW, (date(2026, 12, 16), "day")),
        ("Adutha vaaram varaikum night shift.", NOW, (date(2026, 12, 7), "week")),
        ("Indha maasam end varaikum diet.", NOW, (date(2026, 12, 1), "month")),
        ("October varaikum Chennai la irundhen.", NOW, (date(2026, 11, 1), "month")),
    ],
)
def test_an_until_with_a_time_gives_the_end_of_that_period(text, anchor, expected):
    assert _end(text, anchor) == expected


@pytest.mark.parametrize(
    "text",
    [
        "The owner is staying at the hostel until the flat is ready.",  # a condition
        "The owner is in Bangalore until Friday.",  # seen, not placeable
        "The owner has used the old laptop until now.",
        "The owner is staying with his parents till then.",
        "The owner can spend up to ₹5,000 a month on fuel.",  # an amount
        "The owner might stay in Pune until March.",  # hedged
        "The owner will stay in Pune until March.",  # intention
        "The owner is not working from home until December.",  # negated
        "The owner cannot travel overnight until Amma's insulin routine is stable.",
        "The owner is in Delhi until 3 December and in Mumbai until 10 December.",  # two ends
        "The owner paid off the car loan in October.",  # a past event stays true
        "The owner's leave ended last month.",
        "The owner works at Zoho.",
        "டிசம்பர் வரை வேலைக்கு போக மாட்டேன்.",  # negated
        "மார்ச் வரை சென்னையில் இருக்கலாம்.",  # hedged
        "வீடு ரெடி ஆகும் வரை ஹாஸ்டலில் இருக்கேன்.",  # a condition
        "பொங்கல் வரை ஊரில் இருக்கேன்.",  # a festival
        "2000 ரூபாய் வரை செலவு.",  # an amount, not the year 2000
        "January varaikum leave illa.",
        "March varaikum Chennai la stay pannuven.",
        "Oruvelai December varaikum Bangalore la irupen.",
        "Velli varaikum Madurai la iruken.",
        "",
    ],
)
def test_no_end_when_unknown_not_firm_or_not_an_end(text):
    assert _end(text) is None


def test_an_end_in_the_future_is_kept():
    # Said on 14 November: the fact is current until the end of 20 November.
    found = w.find_end("The owner is on leave until 20 November.", MID_NOV, IST)
    assert found is not None and found.end > MID_NOV
    assert found.end == datetime(2026, 11, 21, tzinfo=IST)
    assert (found.rule, found.source) == ("until.date", w.CONTENT)


def test_until_still_blocks_a_start_and_not_firm_does_not_count_until():
    text = "The owner is on leave until 20 November."
    assert w.blocked(text) and not w.not_firm(text)
    assert w.blocked("நவம்பர் 20 வரை லீவு") and not w.not_firm("நவம்பர் 20 வரை லீவு")
    assert w.not_firm("maybe until March") and w.blocked("maybe until March")
    assert w.find(text, NOW, IST) is None  # an end is not a start


def test_the_owners_words_are_read_only_when_the_content_has_no_time():
    found = w.world_end_of("The owner is on leave.", "டிசம்பர் 5 வரை லீவு எடுத்திருக்கேன்.", NOW, IST)
    assert found is not None
    assert (found.end.date(), found.precision, found.source) == (
        date(2026, 12, 6),
        "day",
        w.SOURCE_TEXT,
    )
    # The content names a time of its own: the owner's words cannot settle it.
    assert (
        w.world_end_of("The owner joined Zoho last month.", "March varaikum leave", NOW, IST)
        is None
    )
    # The owner's words hold two "until"s: which fact is which is not known.
    assert (
        w.world_end_of("The owner is on leave.", "March varai leave, April varai Chennai", NOW, IST)
        is None
    )
    # A content that is not firm stops here.
    assert w.world_end_of("The owner might be on leave.", "March varaikum leave", NOW, IST) is None


@pytest.mark.parametrize(
    ("text", "value", "expected"),
    [
        ("The owner is in Bangalore until Friday.", "2026-12-04", date(2026, 12, 5)),
        ("The owner is in Bangalore until Friday.", "2026-12-03", None),  # a Thursday
        ("The owner is in Bangalore until Friday.", "2027-01-01", None),  # weeks away
        ("Pongal varaikum ooru la iruken.", "2027-01-15", date(2027, 1, 16)),
        ("Pongal varaikum ooru la iruken.", "2028-01-15", None),  # over a year away
        ("The owner is on leave.", "2026-12-10", None),  # no "until": a bare date
        ("The owner might be in Bangalore until Friday.", "2026-12-04", None),  # hedged
        ("The owner is in Madurai till March.", "2027-03-15", date(2027, 3, 16)),  # inside
        ("The owner is in Madurai till March.", "2027-05-15", None),  # outside March
        ("The owner is in Bangalore until Friday.", "next friday", None),  # not a date
        ("The owner is in Bangalore until Friday.", None, None),
    ],
)
def test_the_models_end_is_kept_only_when_a_rule_agrees(text, value, expected):
    found = w.end_from_model(value, text, NOW, IST)
    if expected is None:
        assert found is None
    else:
        assert found is not None
        assert (found.end.date(), found.precision, found.rule, found.source) == (
            expected,
            "day",
            "model",
            w.MODEL,
        )


def test_end_count_counts_until_with_or_without_a_time_but_not_an_amount():
    assert w.end_count("until 20 November", NOW, IST) == 1
    assert w.end_count("until the flat is ready", NOW, IST) == 1
    assert w.end_count("up to ₹5,000", NOW, IST) == 0
    assert w.end_count("March varai leave, April varai Chennai", NOW, IST) == 2
