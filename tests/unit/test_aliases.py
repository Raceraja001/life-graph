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
