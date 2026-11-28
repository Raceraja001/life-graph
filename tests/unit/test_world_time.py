"""Deterministic world-time rules (extraction/world_time.py, ADR m8-ingestion §5.1)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from life_graph.extraction import world_time as wt

IST = ZoneInfo("Asia/Kolkata")
#: A Saturday afternoon in Chennai.
SAID = datetime(2026, 11, 28, 15, 0, tzinfo=IST)


def _start(text: str, anchor: datetime = SAID) -> tuple[date, str] | None:
    found = wt.find(text, anchor, IST)
    return None if found is None else (found.start.date(), found.precision)


@pytest.mark.parametrize(
    ("text", "day", "precision"),
    [
        ("started yesterday", date(2026, 11, 27), wt.DAY),
        ("the day before yesterday", date(2026, 11, 26), wt.DAY),
        ("had a fever last night", date(2026, 11, 27), wt.DAY),
        ("joined today", date(2026, 11, 28), wt.DAY),
        ("moved 3 days ago", date(2026, 11, 25), wt.DAY),
        ("bought it a week ago", date(2026, 11, 16), wt.WEEK),
        ("started a month ago", date(2026, 10, 1), wt.MONTH),
        ("quit 2 years ago", date(2024, 1, 1), wt.YEAR),
        ("changed jobs last week", date(2026, 11, 16), wt.WEEK),
        ("moved last month", date(2026, 10, 1), wt.MONTH),
        ("married last year", date(2025, 1, 1), wt.YEAR),
        ("this week", date(2026, 11, 23), wt.WEEK),
        ("this month", date(2026, 11, 1), wt.MONTH),
        ("this year", date(2026, 1, 1), wt.YEAR),
    ],
)
def test_english_relative_phrases(text, day, precision):
    assert _start(text) == (day, precision)


@pytest.mark.parametrize(
    ("text", "day", "precision"),
    [
        ("born on 3 May 2019", date(2019, 5, 3), wt.DAY),
        ("joined on May 3, 2022", date(2022, 5, 3), wt.DAY),
        ("opened on the 3rd of March 2021", date(2021, 3, 3), wt.DAY),
        ("renewed on 2024-05-03.", date(2024, 5, 3), wt.DAY),
        ("started on 15/08/2024.", date(2024, 8, 15), wt.DAY),
        ("opened on 3/5/2025", date(2025, 5, 3), wt.DAY),  # day first
        ("signed on 5/23/2024", date(2024, 5, 23), wt.DAY),  # clearly month first
        ("since March 2024", date(2024, 3, 1), wt.MONTH),
        ("began March 2024", date(2024, 3, 1), wt.MONTH),
        ("in 2019", date(2019, 1, 1), wt.YEAR),
        ("since 2023", date(2023, 1, 1), wt.YEAR),
        ("back in early 2020", date(2020, 1, 1), wt.YEAR),
    ],
)
def test_dates_months_and_years(text, day, precision):
    assert _start(text) == (day, precision)


def test_a_month_without_a_year_is_the_most_recent_past_one():
    assert _start("moved in March") == (date(2026, 3, 1), wt.MONTH)
    assert _start("moved in November") == (date(2026, 11, 1), wt.MONTH)  # the month it is
    assert _start("adopted a dog in December") == (date(2025, 12, 1), wt.MONTH)
    assert _start("from January") == (date(2026, 1, 1), wt.MONTH)


def test_a_day_without_a_year_is_the_most_recent_past_one():
    assert _start("replaced on 12 October") == (date(2026, 10, 12), wt.DAY)
    assert _start("bought on 30 December") == (date(2025, 12, 30), wt.DAY)


@pytest.mark.parametrize(
    ("text", "day", "precision"),
    [
        ("நேற்று வேலையில் சேர்ந்தேன்", date(2026, 11, 27), wt.DAY),
        ("நேத்து வந்தேன்", date(2026, 11, 27), wt.DAY),
        ("முந்தாநாள் பண்ணேன்", date(2026, 11, 26), wt.DAY),
        ("முந்தா நாள் பண்ணேன்", date(2026, 11, 26), wt.DAY),
        ("இன்னைக்கு சேர்ந்தேன்", date(2026, 11, 28), wt.DAY),
        ("போன வாரம் வாங்கினேன்", date(2026, 11, 16), wt.WEEK),
        ("கடந்த வாரம் வாங்கினேன்", date(2026, 11, 16), wt.WEEK),
        ("போன மாதம் குடிபெயர்ந்தேன்", date(2026, 10, 1), wt.MONTH),
        ("கடந்த மாதம் குடிபெயர்ந்தேன்", date(2026, 10, 1), wt.MONTH),
        ("போன மாசத்துல வந்தேன்", date(2026, 10, 1), wt.MONTH),
        ("போன வருஷம் கல்யாணம் ஆச்சு", date(2025, 1, 1), wt.YEAR),
        ("கடந்த ஆண்டு வாங்கினோம்", date(2025, 1, 1), wt.YEAR),
        ("இந்த மாசம் சேர்ந்தேன்", date(2026, 11, 1), wt.MONTH),
        ("3 நாள் முன் வந்தோம்", date(2026, 11, 25), wt.DAY),
        ("மூணு நாளைக்கு முன்னாடி வந்தோம்", date(2026, 11, 25), wt.DAY),
        ("ரெண்டு வருஷம் முன்னாடி வாங்கினேன்", date(2024, 1, 1), wt.YEAR),
        ("2019 முதல் இருக்கிறேன்", date(2019, 1, 1), wt.YEAR),
        ("2021ல் திறந்தேன்", date(2021, 1, 1), wt.YEAR),
        ("2018-ஆம் ஆண்டு முதல் இருக்கிறேன்", date(2018, 1, 1), wt.YEAR),
        ("மார்ச் மாதம் முதல் செய்கிறேன்", date(2026, 3, 1), wt.MONTH),
    ],
)
def test_tamil_phrases(text, day, precision):
    assert _start(text) == (day, precision)


@pytest.mark.parametrize(
    ("text", "day", "precision"),
    [
        ("nethu join panninen", date(2026, 11, 27), wt.DAY),
        ("munthanethu panninen", date(2026, 11, 26), wt.DAY),
        ("innaiku join aanen", date(2026, 11, 28), wt.DAY),
        ("pona vaaram vaanginen", date(2026, 11, 16), wt.WEEK),
        ("pona maasam shift aanom", date(2026, 10, 1), wt.MONTH),
        ("pona varusham kalyanam aachu", date(2025, 1, 1), wt.YEAR),
        ("indha varusham join panninen", date(2026, 1, 1), wt.YEAR),
        ("3 naal munnadi vandhom", date(2026, 11, 25), wt.DAY),
        ("oru maasam munnadi vandhom", date(2026, 10, 1), wt.MONTH),
        ("2019 la irundhu irukken", date(2019, 1, 1), wt.YEAR),
        ("March la irundhu pannren", date(2026, 3, 1), wt.MONTH),
    ],
)
def test_tanglish_phrases(text, day, precision):
    assert _start(text) == (day, precision)


@pytest.mark.parametrize(
    "text",
    [
        "starts tomorrow",
        "the day after tomorrow",
        "moves next week",
        "ends next month",
        "due by Friday",
        "flies in 3 days",
        "in the coming month",
        "retires in 2030",
        "interview on 2027-01-15",
        "நாளைக்கு சேர்வது",
        "அடுத்த மாதம் பெங்களூர்",
        "வரும் வாரம் பெங்களூர்",
        "naalaiku join",
        "adutha maasam Bangalore",
    ],
)
def test_future_phrases_never_give_a_start(text):
    assert _start(text) is None


def test_a_future_phrase_beside_a_past_one_gives_no_start():
    assert _start("moved last month and leaves next month") is None


@pytest.mark.parametrize(
    "text",
    [
        # intentions
        "I will join a gym from January",
        "I'll move in March",
        "The owner is going to start yoga this week",
        "plans to sell the car this month",
        "wants to learn Tamil this year",
        "இந்த மாசம் கார் விக்கணும்",
        "அடுத்த வாரம் போறேன் பெங்களூர்",
        "nethu decide panni, pona maasam join pannuven",
        # hedges
        "maybe moved in March",
        "I think he got married last year",
        "probably started last week",
        "might have changed banks in 2022",
        "போன மாசம் மாறியிருக்கலாம்",
        "pona maasam maathinen nu ninaikiren",
        # negations
        "has not smoked since 2023",
        "didn't renew it last month",
        "no longer works there since last month",
        "போன வருஷம் லீவு எடுக்கவில்லை",
        "pona varusham leave edukala illa",
        # an end, not a start
        "lived in Trichy until last year",
        "used the old phone till March",
        "போன வருஷம் வரை இருந்தேன்",
        "pona varusham varaikum irundhen",
    ],
)
def test_intentions_hedges_negations_and_ends_give_no_start(text):
    assert wt.blocked(text)
    assert _start(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "lives in Coimbatore",
        "currently works at Infosys",
        "now drives an electric scooter",
        "met the doctor on Monday",
        "paid the fees last Friday",
        "moved last March",
        "recently switched to Airtel",
        "worked in sales for 3 years",
        "bought gold last Diwali",
        "the past few months",
        "may visit Ooty",
        "scored 3/5 on the quiz",
        "is 34 years old",
        "drives a 2019 Honda City",
        "on 31/02/2024",
    ],
)
def test_no_placeable_phrase_is_unknown(text):
    assert _start(text) is None


def test_two_different_starts_are_unknown_and_the_same_one_twice_is_kept():
    assert _start("moved in 2019 and joined Zoho last month") is None
    assert _start("moved in 2019 and has lived there since 2019") == (date(2019, 1, 1), wt.YEAR)


def test_ellam_is_not_read_as_a_hedge():
    assert not wt.blocked("போன மாசம் எல்லாம் வேலை அதிகம்")
    assert _start("போன மாசம் எல்லாம் வேலை அதிகம்") == (date(2026, 10, 1), wt.MONTH)


def test_tokens_keep_tamil_vowel_signs_and_split_digits_from_letters():
    assert wt.tokens("பள்ளி கட்டணம்") == ["பள்ளி", "கட்டணம்"]
    assert wt.tokens("2019ல், Nethu!") == ["2019", "ல்", "nethu"]


def test_the_start_is_local_midnight_in_the_owners_time_zone():
    found = wt.find("moved yesterday", SAID, IST)
    assert found is not None
    assert found.start == datetime(2026, 11, 27, 0, 0, tzinfo=IST)
    assert found.rule == "en.yesterday" and found.source == wt.CONTENT


def test_the_anchor_is_the_said_day_in_the_owners_time_zone():
    # 20:00 UTC on the 27th is already the 28th in Chennai.
    late_utc = datetime(2026, 11, 27, 20, 0, tzinfo=UTC)
    assert _start("joined yesterday", late_utc) == (date(2026, 11, 27), wt.DAY)
    # A late capture: anchored when it was said, not when it arrived.
    said = datetime(2026, 10, 5, 10, 0, tzinfo=IST)
    assert _start("pona maasam shift aanom", said) == (date(2026, 9, 1), wt.MONTH)


def test_world_time_of_reads_the_content_first():
    found = wt.world_time_of(
        "The owner has lived in Madurai since 2015.",
        "I moved to Madurai in 2015, then got married last year.",
        SAID,
        IST,
    )
    assert found is not None and found.source == wt.CONTENT
    assert found.start.date() == date(2015, 1, 1)


def test_world_time_of_reads_the_owners_words_with_exactly_one_phrase():
    found = wt.world_time_of(
        "The owner moved to Coimbatore.", "நேத்து கோயம்புத்தூருக்கு shift ஆனேன்.", SAID, IST
    )
    assert found is not None and found.source == wt.SOURCE_TEXT
    assert found.start.date() == date(2026, 11, 27)
    # Two time phrases: which fact each belongs to is not known.
    assert (
        wt.world_time_of(
            "The owner joined Zoho.",
            "2019 la Chennai vandhen, pona maasam Zoho la join panninen.",
            SAID,
            IST,
        )
        is None
    )
    # One placeable phrase beside an unplaceable one is still two phrases.
    assert (
        wt.world_time_of(
            "The owner joined Zoho.",
            "Pona maasam Chennai ku shift aanen, last Pongal Zoho la join panninen.",
            SAID,
            IST,
        )
        is None
    )
    # One unplaceable phrase is still the one phrase: nothing to read.
    assert wt.world_time_of("The owner moved.", "last Pongal shift aanen", SAID, IST) is None


def test_world_time_of_does_not_let_the_owners_words_overrule_a_blocked_content():
    assert (
        wt.world_time_of(
            "The owner plans to move to Chennai.", "Pona maasam decide panninen.", SAID, IST
        )
        is None
    )
    assert (
        wt.world_time_of("The owner moves next week.", "Pona maasam decide panninen.", SAID, IST)
        is None
    )


def test_phrase_count_includes_future_and_unplaceable_phrases():
    assert wt.phrase_count("nethu vandhen, adutha maasam poren", SAID, IST) == 2
    assert wt.phrase_count("last Pongal", SAID, IST) == 1
    assert wt.phrase_count("lives in Coimbatore", SAID, IST) == 0


def test_a_model_date_needs_a_phrase_in_the_text():
    found = wt.from_model("2026-01-14", "shifted last Pongal", SAID, IST)
    assert found is not None
    assert (found.start.date(), found.precision, found.source) == (
        date(2026, 1, 14),
        wt.DAY,
        wt.MODEL,
    )
    assert wt.from_model("2026-01-14", "shifted to Chennai", SAID, IST) is None  # bare date
    assert wt.from_model("2027-01-14", "shifted last Pongal", SAID, IST) is None  # future
    assert wt.from_model("14 Jan", "shifted last Pongal", SAID, IST) is None  # not ISO
    assert wt.from_model(None, "shifted last Pongal", SAID, IST) is None
    assert wt.from_model("2026-01-14", "maybe shifted last Pongal", SAID, IST) is None
    assert wt.from_model("2026-01-14", "shifted last Pongal, moving next week", SAID, IST) is None
