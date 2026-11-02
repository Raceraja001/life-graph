"""The extractor is told who the people a message names already are.

Each message is extracted on its own, so "Senthil plays cricket with his office
team" made Senthil the owner's colleague although the owner had called him her
husband before (test life 2, 2026-11-01). The people table already knows; these
pin that the extraction request carries it, and that nothing breaks without it.
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.config import settings
from life_graph.extraction.llm import build_extraction_messages, known_people
from life_graph.services import entities

SENTHIL = uuid.uuid4()


def test_the_request_names_who_the_people_already_are():
    messages = build_extraction_messages(
        "SYS", [], "Senthil plays cricket", structured=True, known="Senthil (the owner's husband)"
    )

    assert "Senthil (the owner's husband)" in messages[-1]["content"]
    assert "instead of guessing one" in messages[-1]["content"]
    assert "still keep every fact" in messages[-1]["content"]


def test_no_one_known_leaves_the_request_as_it_was():
    plain = build_extraction_messages("SYS", [], "I use uv", structured=True)
    empty = build_extraction_messages("SYS", [], "I use uv", structured=True, known="")

    assert plain == empty
    assert "Who these people are" not in plain[-1]["content"]


@pytest.fixture
def senthil(monkeypatch):
    async def fake_known(tenant_id, text_):
        entities._cache[tenant_id] = (
            1e18,
            [("senthil", SENTHIL, "Senthil", None, "husband")],
        )
        return [(SENTHIL, "Senthil")] if "Senthil" in text_ else []

    monkeypatch.setattr(entities, "known_in_text", fake_known)
    monkeypatch.setattr(settings, "extraction_known_people", True)
    yield
    entities._cache.pop("t1", None)


@pytest.mark.asyncio
async def test_known_people_reads_the_people_table(senthil):
    assert await known_people("t1", "Senthil plays cricket") == "Senthil (the owner's husband)"
    assert await known_people("t1", "I use uv") == ""


@pytest.mark.asyncio
async def test_off_or_outside_a_tenant_asks_nothing(senthil, monkeypatch):
    assert await known_people(None, "Senthil plays cricket") == ""
    monkeypatch.setattr(settings, "extraction_known_people", False)
    assert await known_people("t1", "Senthil plays cricket") == ""


@pytest.mark.asyncio
async def test_a_failed_lookup_still_extracts(monkeypatch):
    async def boom(*_):
        raise RuntimeError("db down")

    monkeypatch.setattr(entities, "known_in_text", boom)
    monkeypatch.setattr(settings, "extraction_known_people", True)
    assert await known_people("t1", "Senthil plays cricket") == ""


NILA = uuid.uuid4()


@pytest.fixture
def nila():
    entities._cache["t2"] = (1e18, [("nila", NILA, "Nila", None, "daughter")])
    yield
    entities._cache.pop("t2", None)


def test_a_name_inside_a_longer_name_is_not_that_person(nila):
    # "Nila Pickles" is the owner's company, not Nila her daughter.
    named = [(NILA, "Nila")]
    text_ = "We stopped shipping Nila Pickles outside Tamil Nadu."

    assert entities.without_longer_names("t2", named, text_) == []


def test_the_person_named_on_their_own_too_stays(nila):
    named = [(NILA, "Nila")]

    assert entities.without_longer_names("t2", named, "Nila loves Nila Pickles.") == named
    assert entities.without_longer_names("t2", named, "Nila has a test today") == named
    assert entities.without_longer_names("t2", named, "nila pickles orders") == named
