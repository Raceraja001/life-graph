"""The owner's form: slot keys (core/slots.py) and how the card shows them (services/profile_card.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from life_graph.core import slots
from life_graph.extraction.llm import _meaning
from life_graph.services import profile_card as pc

NOW = datetime(2026, 10, 31, 9, tzinfo=UTC)


@pytest.mark.parametrize(
    ("raw", "subject", "expected"),
    [
        ("work.employer", "owner", "work.employer"),
        ("Work.Company", "owner", "work.employer"),
        ("job.role", "owner", "work.title"),
        ("career.boss", "owner", "work.manager"),
        ("residence.current_city", "owner", "home.city"),
        ("family.wife", "owner", "family.spouse"),
        ("tech.mobile phone", "owner", "devices.phone"),
        ("finance.monthly_budget", "owner", "money.budget"),
        ("health.blood type", "owner", "health.blood_group"),
        ("family.anu.school", "Anu", "family.anu.school"),
        ("devices.phone", "Senthil", None),  # a colleague's phone is never the owner's
        ("phone", "owner", None),  # not topic.field
        ("weather.today", "owner", None),  # not a topic
        ("a.b.c.d.e", "owner", None),
        ("", "owner", None),
        (None, "owner", None),
    ],
)
def test_normalise(raw, subject, expected):
    assert slots.normalise(raw, subject=subject) == expected


def test_only_a_firm_affirmed_value_fills_the_form():
    assert _meaning({"slot": "devices.phone"})["slot"] == "devices.phone"
    assert _meaning({"slot": "devices.phone", "certainty": "hedged"})["slot"] is None
    assert _meaning({"slot": "devices.phone", "polarity": "negate"})["slot"] is None
    assert _meaning({"slot": "devices.phone", "subject": "Senthil"})["slot"] is None


def _m(content, slot=None, **props):
    return SimpleNamespace(
        content=content,
        source_type="capture",
        trust_tier="self",
        properties={"fact_type": "fact", **({"slot": slot} if slot else {}), **props},
        valid_until=None,
    )


def test_the_form_comes_first_one_memory_per_slot():
    rows = [
        _m("The owner prefers local HTML files."),
        _m("The owner works at Tessera Labs.", "work.employer"),
        _m("The owner lives in Adyar, Chennai.", "home.city"),
        _m("The owner works at Nimbus Soft.", "work.employer"),  # an older duplicate slot
    ]
    picked = pc.pick(rows, 25, NOW)
    assert [m.content for m in picked] == [
        "The owner lives in Adyar, Chennai.",  # home before work (TOPICS order)
        "The owner works at Tessera Labs.",
        "The owner prefers local HTML files.",
    ]


def test_render_marks_form_fields_and_history():
    when = datetime(2025, 12, 1, tzinfo=UTC)
    out = pc.render(
        [
            {
                "content": "The owner works at Tessera Labs.",
                "created_at": when,
                "slot": "work.employer",
            },
            {"content": "The owner prefers dark mode.", "created_at": when},
        ]
    )
    assert out.splitlines()[-2:] == [
        "- [work · employer] (since 2025-12-01) The owner works at Tessera Labs.",
        "- The owner prefers dark mode.",
    ]
    hist = pc.render_history(
        [{"content": "The owner works at Nimbus Soft.", "slot": "work.employer", "until": when}]
    )
    assert hist.startswith(pc.HISTORY_HEADER)
    assert (
        hist.splitlines()[-1]
        == "- (until 2025-12-01 · work · employer) The owner works at Nimbus Soft."
    )
    assert pc.render_history([]) == ""


@pytest.mark.parametrize(
    ("question", "past"),
    [
        ("Where did I work before Tessera?", True),
        ("What phone did I use previously?", True),
        ("Which school did Anu go to first?", True),
        ("நான் முன்பு எங்கே வேலை செய்தேன்?", True),
        ("Where do I work?", False),
        ("Which phone do I use?", False),
    ],
)
def test_past_questions(question, past):
    assert bool(pc.PAST.search(question)) is past


def test_someone_elses_fact_carries_their_name():
    # Measured 2026-10-31: "Divya is married to Naveen" came back as family.spouse.
    assert slots.normalise("family.spouse", subject="Divya") == "family.divya.spouse"
    assert slots.normalise("family.divya.spouse", subject="Divya") == "family.divya.spouse"
    assert slots.normalise("work.employer", subject="Divya") is None


def test_home_is_only_where_the_owner_lives():
    # "My parents live in Madurai" came back as home.city: it would have replaced the owner's city.
    assert slots.normalise("home.city", content="The owner's parents live in Madurai.") is None
    assert slots.normalise("home.city", content="The owner lives in Adyar, Chennai.") == "home.city"
    assert slots.normalise("home.city", content="The owner moved to Chennai.") == "home.city"


def test_a_slot_must_fit_its_sentence():
    # Measured 2026-10-31: a sentence about a self-hosted app got work.employer.
    assert (
        slots.normalise("work.employer", content="mediagrab is accessible only through tailscale")
        is None
    )
    assert (
        slots.normalise("work.employer", content="The owner works at Tessera Labs.")
        == "work.employer"
    )
    assert slots.normalise("devices.phone", content="The owner prefers dark mode.") is None
    assert (
        slots.normalise("devices.phone", content="The owner's phone is a Pixel 9.")
        == "devices.phone"
    )
    assert slots.normalise("family.spouse", content="Priya teaches maths.") is None
    assert (
        slots.normalise("hobbies.cricket.day", content="The owner plays on Saturdays.")
        == "hobbies.cricket.day"
    )


CRICKET = "The owner plays cricket on Saturday mornings with the Adyar Cricket Club."


@pytest.mark.parametrize(
    ("raw", "content", "expected"),
    [
        # 2026-10-31: a changed hobby day or club landed in a new slot beside the old one.
        ("hobbies.cricket_day", CRICKET, "hobbies.cricket.day"),
        ("hobbies.cricket.day", CRICKET, "hobbies.cricket.day"),
        ("hobbies.day_cricket", CRICKET, "hobbies.cricket.day"),
        ("hobbies.cricket.playing_day", CRICKET, "hobbies.cricket.day"),
        ("hobbies.cricket.practice.day", CRICKET, "hobbies.cricket.practice_day"),
        ("hobbies.playing_cricket.day", CRICKET, "hobbies.cricket.day"),
        ("sports.cricket_days", CRICKET, "hobbies.cricket.day"),
        ("hobbies.cricket.team", CRICKET, "hobbies.cricket.club"),
        ("hobbies.cricket_club.name", CRICKET, "hobbies.cricket.club"),
        ("hobbies.cricket.timing", CRICKET, "hobbies.cricket.time"),
        (
            "hobbies.badminton_club",
            "The owner plays badminton at Smash Club.",
            "hobbies.badminton.club",
        ),
        (
            "hobbies.club",
            "The owner switched to Shuttle Hub for badminton.",
            "hobbies.badminton.club",
        ),
        ("hobbies.soccer.coach", "The owner's football coach is Ravi.", "hobbies.football.coach"),
        (
            "hobbies.table_tennis.day",
            "The owner plays table tennis every Friday.",
            "hobbies.table_tennis.day",
        ),
        # A field with no activity, and the sentence names none or several: no slot.
        ("hobbies.club", "The owner joined a new club.", None),
        ("hobbies.day", "The owner plays cricket and tennis on Sundays.", None),
        # A day that the sentence does not give is not filled.
        ("hobbies.cricket.day", "The owner likes cricket.", None),
    ],
)
def test_hobby_slots_have_one_spelling(raw, content, expected):
    assert slots.normalise(raw, content=content) == expected


@pytest.mark.parametrize(
    ("raw", "subject", "expected"),
    [
        ("family.anu_school", "owner", "family.anu.school"),
        ("family.anu_school", "Anu", "family.anu.school"),
        ("family.amma.health", "owner", "family.mother.health"),
        ("family.priya.dob", "owner", "family.priya.birthday"),
    ],
)
def test_family_fields_have_one_spelling(raw, subject, expected):
    assert slots.normalise(raw, subject=subject) == expected


@pytest.mark.parametrize(
    ("raw", "subject", "expected"),
    [
        # Bake-off 2026-10-31: the model wrote family.anu.age for a fact about Anushka,
        # and family.anushka.anu.age stayed current next to family.anushka.age.
        ("family.anu.age", "Anushka", "family.anushka.age"),
        ("family.anushka.anu.age", "owner", "family.anushka.age"),
        ("family.anushka.anushka.age", "owner", "family.anushka.age"),
        ("family.anushka.anu.age", "Anushka", "family.anushka.age"),
        # A middle segment that is not the person stays.
        ("family.anushka.school.bus", "owner", "family.anushka.school.bus"),
        ("family.anu.school", "Anu", "family.anu.school"),
    ],
)
def test_a_name_in_the_path_is_the_person(raw, subject, expected):
    assert slots.normalise(raw, subject=subject) == expected


def test_old_rows_with_the_nickname_segment_count_once_on_the_card():
    rows = [
        _m("Anu is 9 years old.", "family.anushka.age"),
        _m("Anushka, called Anu, is 7 years old.", "family.anushka.anu.age"),
    ]
    assert [m.content for m in pc.pick(rows, 25, NOW)] == ["Anu is 9 years old."]


def test_old_spellings_count_once_on_the_card():
    rows = [
        _m("The owner plays cricket on Saturdays.", "hobbies.cricket.day"),
        _m("The owner plays cricket on Sundays.", "hobbies.cricket_day"),  # older spelling
    ]
    assert [m.content for m in pc.pick(rows, 25, NOW)] == ["The owner plays cricket on Saturdays."]


PRACTICE = "The owner's cricket practice is on Tuesdays."
MATCHES = "The owner's cricket matches are on Sundays."
CHESS = "The owner's chess club meets on Thursdays."
TT = "The owner plays table tennis every Friday."


@pytest.mark.parametrize(
    ("raw", "content", "expected"),
    [
        # Review of PR #205: different hobby fields must not share one slot.
        ("hobbies.cricket.practice_day", PRACTICE, "hobbies.cricket.practice_day"),
        ("hobbies.cricket.practice.day", PRACTICE, "hobbies.cricket.practice_day"),
        ("hobbies.cricket_practice_day", PRACTICE, "hobbies.cricket.practice_day"),
        ("hobbies.cricket.training_day", PRACTICE, "hobbies.cricket.practice_day"),
        ("hobbies.practice_day", PRACTICE, "hobbies.cricket.practice_day"),
        ("hobbies.cricket.match_day", MATCHES, "hobbies.cricket.match_day"),
        ("hobbies.cricket.match_days", MATCHES, "hobbies.cricket.match_day"),
        ("hobbies.cricket.match.day", MATCHES, "hobbies.cricket.match_day"),
        ("hobbies.cricket.game_day", MATCHES, "hobbies.cricket.match_day"),
        ("hobbies.chess.club.day", CHESS, "hobbies.chess.club_day"),
        ("hobbies.chess_club_day", CHESS, "hobbies.chess.club_day"),
        ("hobbies.chess.team.day", CHESS, "hobbies.chess.club_day"),
        ("hobbies.chess.club.name", CHESS, "hobbies.chess.club"),
        (
            "hobbies.cricket.practice_time",
            "Cricket practice is at 6 am.",
            "hobbies.cricket.practice_time",
        ),
        # An unknown qualifier is kept, never dropped.
        ("hobbies.chess.tournament.day", CHESS, "hobbies.chess.tournament_day"),
        ("hobbies.chess.blitz.day", CHESS, "hobbies.chess.blitz_day"),
        # Genuine spellings of one field still collapse.
        ("hobbies.cricket_day", CRICKET, "hobbies.cricket.day"),
        ("hobbies.day_cricket", CRICKET, "hobbies.cricket.day"),
        ("hobbies.cricket.days", CRICKET, "hobbies.cricket.day"),
        ("hobbies.table_tennis_day", TT, "hobbies.table_tennis.day"),
        # A practice day must still name a day.
        ("hobbies.cricket.practice_day", "The owner likes cricket practice.", None),
    ],
)
def test_distinct_hobby_fields_stay_distinct(raw, content, expected):
    assert slots.normalise(raw, content=content) == expected


def test_practice_and_match_days_are_never_one_slot():
    practice = slots.normalise("hobbies.cricket.practice_day", content=PRACTICE)
    match = slots.normalise("hobbies.cricket.match_day", content=MATCHES)
    day = slots.normalise("hobbies.cricket.day", content=CRICKET)
    assert len({practice, match, day}) == 3
