"""One person, many names: what the owner's words teach (core/aliases.py) and how the
entity index uses it without a query (services/entities.py, migration 057)."""

from __future__ import annotations

import time
import uuid

import pytest

from life_graph.core import aliases
from life_graph.core.aliases import AliasClaim, RoleClaim
from life_graph.services import entities, profile_card


@pytest.mark.parametrize(
    ("text", "claims"),
    [
        (
            "My wife Priyadharshini — I call her Priya — teaches maths.",
            [AliasClaim("Priyadharshini", "Priya")],
        ),
        ("Our son Vikram (Vicky) is 3.", [AliasClaim("Vikram", "Vicky")]),
        ("Our daughter Anushka, we call her Anu, is 7.", [AliasClaim("Anushka", "Anu")]),
        ("Priyadharshini, called Priya, teaches.", [AliasClaim("Priyadharshini", "Priya")]),
        ("Vikram, also known as Vicky, is 3.", [AliasClaim("Vikram", "Vicky")]),
        ("Maha is short for Mahalakshmi.", [AliasClaim("Mahalakshmi", "Maha")]),
        ("Maha is my wife Mahalakshmi.", [AliasClaim("Mahalakshmi", "Maha")]),
        (
            "My name is Karthik Rajan, but everyone calls me Karthi.",
            [AliasClaim("Karthik Rajan", "Karthi")],
        ),
        ("Mahalakshmi's birthday is 4 March; I call her Ma.", [AliasClaim("Mahalakshmi", "Ma")]),
        # Not an alias: a description in brackets, a lone first name, two candidates for "her".
        ("Ravi (the owner's colleague) is learning Japanese.", []),
        ("Priya teaches maths at Sunrise School.", []),
        ("Priya and Divya came over; I call her Pri.", []),
        ("", []),
    ],
)
def test_alias_statements(text, claims):
    assert aliases.parse(text)[0] == claims


@pytest.mark.parametrize(
    ("text", "role"),
    [
        ("My wife Mahalakshmi works at a bank.", RoleClaim("Mahalakshmi", "spouse")),
        ("Lakshmi, the owner's mother, has diabetes.", RoleClaim("Lakshmi", "mother")),
        ("Ramasamy is my father.", RoleClaim("Ramasamy", "father")),
        ("Priya (the owner's wife) teaches.", RoleClaim("Priya", "spouse")),
        ("My name is Karthik Rajan.", RoleClaim("Karthik Rajan", "owner")),
        ("My colleague Priya Venkat joined Tessera.", RoleClaim("Priya Venkat", "colleague")),
    ],
)
def test_role_statements(text, role):
    assert role in aliases.parse(text)[1]


def test_someone_elses_relative_is_not_the_owners():
    # "my sister's friend" is not the owner's friend, and Divya is not the owner's sister here.
    assert aliases.parse("Divya is my sister's friend.")[1] == []


@pytest.mark.parametrize(
    ("a", "b", "ok"),
    [
        ("Ma", "Mahalakshmi", True),
        ("Maha", "Mahalakshmi", True),
        ("Priya", "Priyadharshini", True),
        ("Priya", "Divya", False),
        ("M", "Mahalakshmi", False),  # one letter is not a name
    ],
)
def test_names_that_can_be_one_person(a, b, ok):
    assert aliases.compatible(a, b) is ok


def test_one_person_roles_in_a_question():
    assert aliases.roles_in_question("When is my wife's birthday?") == {"spouse"}
    assert aliases.roles_in_question("What is Amma's health issue?") == {"mother"}
    assert aliases.roles_in_question("அப்பா எங்கே?") == {"father"}
    assert aliases.roles_in_question("When is Priya's birthday?") == set()
    # Son, friend… are many people: never resolved by role.
    assert aliases.roles_in_question("Where does my son study?") == set()


# ── The entity index, from its cache (no database) ─────────────────────────

T = "t_alias_unit"
MAHAL, MAHA, MA, PRIYA_V, LAKSHMI = (uuid.uuid4() for _ in range(5))


@pytest.fixture
def known():
    rows = [
        ("mahalakshmi", MAHAL, "Mahalakshmi", None, "spouse"),
        ("priya venkat", PRIYA_V, "Priya Venkat", None, "colleague"),
        ("lakshmi", LAKSHMI, "Lakshmi", None, "mother"),
        ("maha", MAHA, "Maha", MAHAL, None),
        ("ma", MA, "Ma", MAHA, None),  # a chain: Ma → Maha → Mahalakshmi
    ]
    entities._cache[T] = (time.monotonic(), sorted(rows, key=lambda r: -len(r[0])))
    yield
    entities._cache.pop(T, None)


@pytest.mark.asyncio
async def test_a_nickname_brings_the_whole_person(known):
    found = await entities.known_in_text(T, "When is Maha's birthday?")
    assert found[0] == (MAHA, "Maha")
    assert {eid for eid, _ in found} == {MAHA, MAHAL, MA}
    hint = entities.alias_hint(T, found)
    assert hint == "Names: Mahalakshmi = Maha = Ma (the owner's spouse)"


@pytest.mark.asyncio
async def test_a_role_in_the_question_brings_who_holds_it(known):
    found = await entities.known_in_text(T, "When is my wife's birthday?")
    assert {eid for eid, _ in found} == {MAHAL, MAHA, MA}
    assert {eid for eid, _ in await entities.known_in_text(T, "Is amma ok?")} == {LAKSHMI}


@pytest.mark.asyncio
async def test_another_person_with_a_similar_name_is_not_brought_in(known):
    found = await entities.known_in_text(T, "What does Priya Venkat do?")
    assert found == [(PRIYA_V, "Priya Venkat")]
    assert entities.alias_hint(T, found) == "Names: Priya Venkat (the owner's colleague)"


def test_no_hint_without_the_cache():
    assert entities.alias_hint("nobody", [(uuid.uuid4(), "X")]) == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("slot", "expected"),
    [
        ("family.maha.birthday", "family.mahalakshmi.birthday"),
        ("family.ma.birthday", "family.mahalakshmi.birthday"),
        ("family.spouse.birthday", "family.mahalakshmi.birthday"),
        ("family.mother.health", "family.lakshmi.health"),
        ("family.mahalakshmi.birthday", "family.mahalakshmi.birthday"),
        ("family.spouse", "family.spouse"),  # the spouse's name itself
        ("family.priya.school", "family.priya.school"),  # unknown name: as given
        ("hobbies.cricket.day", "hobbies.cricket.day"),
    ],
)
async def test_family_slots_are_filed_under_the_known_name(known, slot, expected):
    assert await entities.canonical_slot(T, slot) == expected


@pytest.mark.asyncio
async def test_the_card_shows_the_other_names(known):
    assert sorted(await entities.other_names(T, "mahalakshmi")) == ["Ma", "Maha"]
    items = [
        {"content": "Mahalakshmi's birthday is 4 March.", "slot": "family.mahalakshmi.birthday"}
    ]
    await profile_card._add_other_names(T, items)
    assert profile_card.render(items).splitlines()[-1] == (
        "- [family · mahalakshmi (Maha, Ma) · birthday] Mahalakshmi's birthday is 4 March."
    )


# ── Review of PR #205 (2026-10-31) ─────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "Meenakshi is my mother-in-law.",
        "Kamala, my mother in law, visited.",
        "My mother-in-law Kamala visited.",
        "My mother in law, Kamala, visited.",
        "Kamala, my MIL, visited.",
        "Kamala is my motherinlaw.",
        "Kamala is my Mother-In-Law.",
    ],
)
def test_a_mother_in_law_is_never_the_mother(text):
    roles = aliases.parse(text)[1]
    assert all(r.role != "mother" for r in roles), roles
    assert any(r.role == "mother_in_law" for r in roles), roles


@pytest.mark.parametrize(
    "text",
    [
        "Raman is my father-in-law.",
        "Raman, my father in law, retired.",
        "My FIL Raman retired.",
    ],
)
def test_a_father_in_law_is_never_the_father(text):
    roles = aliases.parse(text)[1]
    assert all(r.role != "father" for r in roles), roles
    assert any(r.role == "father_in_law" for r in roles), roles


def test_in_laws_are_not_auto_linked_to_a_parent():
    assert "mother_in_law" != "mother"
    assert aliases.roles_in_question("When is my mother-in-law's birthday?") == {"mother_in_law"}
    assert aliases.roles_in_question("When is my mother's birthday?") == {"mother"}


@pytest.mark.parametrize(
    "text",
    [
        "Remember I call her Ammu.",
        "Nobody calls her Lakshmi.",
        "No one calls him Vicky any more.",
        "Never call me Karthi.",
        "Please don't call her Maha.",
        "Lakshmi doesn't like it when people call her Lachu.",
        "Okay so we call him Kutty.",
    ],
)
def test_sentence_words_and_negations_name_nobody(text):
    assert aliases.parse(text)[0] == [], text


def test_a_negated_explicit_alias_teaches_nothing():
    assert aliases.parse("Mahalakshmi — nobody calls her Maha.")[0] == []
    assert aliases.parse("My name is Karthik, but don't call me Karthi.")[0] == []


# ── Bake-off leftovers (2026-10-31) ────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        # test_life m84: "Priyavukku eppavum malli poo pudikkum — Priya always loves
        # jasmine flowers." The extracted fact kept the Tamil word in brackets.
        "Priya (Priyavukku) always loves jasmine flowers.",
        "Priyavukku (Priya) always loves jasmine flowers.",
        "Priya, called Priyavukku, loves jasmine.",
        "Anu (Anuvoda) school is DAV.",
        "Maha (Mahakitta) said yes.",
        "Kumar (Kumarukku) is my brother.",
    ],
)
def test_a_tamil_case_form_is_not_a_nickname(text):
    assert aliases.parse(text)[0] == [], text


@pytest.mark.parametrize(
    ("word", "base"),
    [
        ("Priyavukku", "Priya"),
        ("priyavukku", "priya"),
        ("Anuvoda", "Anu"),
        ("Ravikku", "Ravi"),
        ("Kumarukku", "Kumar"),
        ("Mahakitta", "Maha"),
        ("பிரியாவுக்கு", "பிரியா"),
        ("Priyadharshini", None),
        ("Anushka", None),
        ("Priya", None),
    ],
)
def test_case_forms(word, base):
    known = ["Priya", "priya", "Anu", "Ravi", "Kumar", "Maha", "பிரியா"]
    assert aliases.base_name(word, known) == base


def test_a_case_form_is_never_compatible():
    assert aliases.compatible("Priya", "Priyavukku") is False
    assert aliases.compatible("Priya", "Priyadharshini") is True


@pytest.mark.parametrize(
    ("text", "claims"),
    [
        (
            "Priyadharshini (the owner's wife, called Priya) teaches maths at Sunrise.",
            [AliasClaim("Priyadharshini", "Priya")],
        ),
        (
            "Priyadharshini (the owner's wife, also known as Priya) teaches.",
            [AliasClaim("Priyadharshini", "Priya")],
        ),
        ("Priyadharshini (called Priya) teaches.", [AliasClaim("Priyadharshini", "Priya")]),
        ("Priyadharshini, called Priya, teaches.", [AliasClaim("Priyadharshini", "Priya")]),
        # Guards kept: negated, a Tamil case form, a description without a name.
        ("Priyadharshini (the owner's wife, never called Priya) teaches.", []),
        ("Priya (the owner's wife, called Priyavukku) teaches.", []),
        ("Ravi (the owner's colleague) is learning Japanese.", []),
    ],
)
def test_a_name_given_inside_brackets(text, claims):
    assert aliases.parse(text)[0] == claims


@pytest.fixture
def priya_known():
    pd, p, pv, an, anu, lk, ammu = (uuid.uuid4() for _ in range(7))
    rows = [
        ("priyadharshini", pd, "Priyadharshini", None, "spouse"),
        ("priya", p, "Priya", pd, None),
        ("priyavukku", pv, "Priyavukku", None, None),
        ("anushka", an, "Anushka", None, "daughter"),
        ("anu", anu, "Anu", an, None),
        ("lakshmi", lk, "Lakshmi", None, "mother"),
        ("ammu", ammu, "Ammu", lk, None),
    ]
    entities._cache[T] = (time.monotonic(), sorted(rows, key=lambda r: -len(r[0])))
    yield
    entities._cache.pop(T, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("slot", "expected"),
    [
        ("family.priya.birthday", "family.priyadharshini.birthday"),
        ("family.priyadharshini.occupation", "family.priyadharshini.occupation"),
        # A case form of a known name files under that person.
        ("family.priyavukku.likes", "family.priyadharshini.likes"),
        # A nickname left as a path segment is dropped.
        ("family.anushka.anu.age", "family.anushka.age"),
        ("family.anu.anushka.age", "family.anushka.age"),
        ("family.lakshmi.ammu.health", "family.lakshmi.health"),
        ("family.anushka.school.bus", "family.anushka.school.bus"),
    ],
)
async def test_one_person_one_name_in_the_form(priya_known, slot, expected):
    assert await entities.canonical_slot(T, slot) == expected


@pytest.mark.asyncio
async def test_a_case_form_in_the_question_finds_the_person(priya_known):
    rows = entities._cache[T][1]
    # Without an entity of its own, the case form still matches the person.
    entities._cache[T] = (time.monotonic(), [r for r in rows if r[0] != "priyavukku"])
    found = await entities.known_in_text(T, "Priyavukku enna pidikkum?")
    assert "Priyadharshini" in {n for _, n in found}


@pytest.mark.asyncio
async def test_the_card_shows_one_person_once_linked(priya_known):
    from datetime import UTC, datetime
    from types import SimpleNamespace

    def m(content, slot):
        return SimpleNamespace(
            content=content,
            source_type="capture",
            trust_tier="self",
            properties={"fact_type": "fact", "slot": slot},
            valid_until=None,
            created_at=datetime(2025, 1, 7, tzinfo=UTC),
        )

    rows = [
        m("Priya's birthday is on 14 February.", "family.priya.birthday"),
        m("Priyadharshini teaches maths.", "family.priyadharshini.occupation"),
    ]
    filed = await profile_card.filed_slots(T, rows)
    picked = profile_card.pick(rows, 25, filed=filed)
    assert [profile_card.card_slot(r, filed) for r in picked] == [
        "family.priyadharshini.birthday",
        "family.priyadharshini.occupation",
    ]
