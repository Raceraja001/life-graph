"""services/chat_history.py: search snippets and which turns a regeneration
replaced (docs/specs/web-chat-wave1.md F6)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from life_graph.services.chat_history import SNIPPET_CHARS, snippet, superseded_by, versions_of


def turn(status="completed", regenerates=None):
    inp = {"message": "q"}
    if regenerates is not None:
        inp["regenerates"] = str(regenerates.id)
    return SimpleNamespace(id=uuid.uuid4(), status=status, input=inp)


def test_a_short_text_is_whole_with_whitespace_collapsed():
    assert snippet("call  the\n dentist", "dentist") == "call the dentist"


def test_a_long_text_is_cut_around_the_first_query_word():
    text = "word " * 60 + "the DENTIST is on friday " + "more " * 60
    out = snippet(text, "dentist friday")
    assert len(out) <= SNIPPET_CHARS
    assert "DENTIST" in out and "friday" in out
    assert out.startswith("…") and out.endswith("…")


def test_a_match_near_the_start_keeps_the_start():
    text = "dentist " + "x" * 300
    out = snippet(text, "dentist")
    assert out.startswith("dentist") and out.endswith("…") and len(out) <= SNIPPET_CHARS


def test_a_match_near_the_end_keeps_the_end():
    text = "x" * 300 + " the dentist"
    out = snippet(text, "dentist")
    assert out.endswith("the dentist") and out.startswith("…") and len(out) <= SNIPPET_CHARS


def test_no_word_found_gives_the_start():
    out = snippet("y" * 300, "dentist")
    assert out.startswith("yyy") and len(out) <= SNIPPET_CHARS


def test_a_completed_regeneration_replaces_its_turn():
    a = turn()
    b = turn(regenerates=a)
    assert superseded_by([a, b]) == {str(a.id): str(b.id)}


def test_a_failed_or_running_regeneration_replaces_nothing():
    a = turn()
    assert superseded_by([a, turn("failed", a), turn("running", a)]) == {}


def test_the_chain_is_followed_through_a_failed_version():
    a = turn()
    b = turn("failed", a)
    c = turn(regenerates=b)
    assert superseded_by([a, b, c]) == {str(a.id): str(c.id), str(b.id): str(c.id)}


def test_the_newest_completed_version_wins():
    a = turn()
    b = turn(regenerates=a)
    c = turn(regenerates=b)
    assert superseded_by([a, b, c]) == {str(a.id): str(c.id), str(b.id): str(c.id)}


def test_versions_of_a_turn_are_it_and_what_it_regenerated():
    a = turn()
    b = turn("failed", a)
    c = turn(regenerates=b)
    other = turn()
    assert versions_of([a, b, c, other], c.id) == {str(a.id), str(b.id), str(c.id)}
    assert versions_of([a, b, c, other], other.id) == {str(other.id)}
