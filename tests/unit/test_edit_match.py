"""Forgiving edits: code_edit applies near-miss `old` text when exactly one place
matches, re-indents when needed, offers the closest region on a miss, and has
a line-range mode. Each case is a mistake a local model made in live trials."""

from __future__ import annotations

import json

import pytest

from life_graph.tools import code, edit_match
from life_graph.tools._guards import confine_to

SRC = """export function createStore() {
    const items = []
    return {
        add(title) {
            const todo = { id: items.length + 1, title }
            items.push(todo)
            return todo
        },
        list() {
            return items.map((t) => ({...t}))
        },
    }
}
"""


def _apply(text, old, new):
    m = edit_match.locate(text, old, new)
    assert isinstance(m, edit_match.Match), m
    return text[: m.start] + m.new + text[m.end :], m.tier


def test_exact_match_is_unchanged_behaviour():
    out, tier = _apply(SRC, "items.push(todo)", "items.unshift(todo)")
    assert tier == "exact" and "items.unshift(todo)" in out


def test_code_read_prefixes_are_stripped():
    old = "6:             items.push(todo)\n7:             return todo"
    new = "6:             items.unshift(todo)\n7:             return todo"
    out, tier = _apply(SRC, old, new)
    assert tier == "prefixes" and "            items.unshift(todo)\n" in out and "6:" not in out


def test_trailing_whitespace_differences_are_tolerated():
    old = "        list() {   \n            return items.map((t) => ({...t}))  "
    new = "        list() {\n            return [...items]"
    out, tier = _apply(SRC, old, new)
    assert tier == "trailing" and "return [...items]" in out and "map(" not in out


def test_wrong_indentation_is_matched_and_new_is_reindented():
    old = "list() {\n    return items.map((t) => ({...t}))\n},"
    new = "list() {\n    return [...items]\n},\nremove(id) {\n    return id\n},"
    out, tier = _apply(SRC, old, new)
    assert tier == "indentation"
    assert "        remove(id) {\n            return id\n        }," in out
    assert "        list() {\n            return [...items]\n        }," in out


def test_ambiguous_matches_are_refused_at_every_tier():
    text = "a = 1\n  a = 1\n"
    m = edit_match.locate(text, "a = 1", "a = 2")
    assert isinstance(m, edit_match.Miss) and m.reason == "ambiguous"
    m = edit_match.locate("x\n  y\nx\n    y\n", "x\ny", "z")
    assert isinstance(m, edit_match.Miss) and m.reason == "ambiguous" and m.tier == "indentation"


def test_a_real_miss_names_the_closest_region():
    m = edit_match.locate(SRC, "list() {\n    return items.filter(Boolean)\n}", "x")
    assert isinstance(m, edit_match.Miss) and m.reason == "not_found"
    near = edit_match.closest(SRC, "list() {\n    return items.filter(Boolean)\n}")
    assert near and "9:         list() {" in near and "10:" in near
    assert edit_match.closest(SRC, "completely unrelated words here") is None


# ── code_edit itself ────────────────────────────────────────────────────────


@pytest.fixture
def wt(tmp_path):
    (tmp_path / "todos.mjs").write_text(SRC)
    with confine_to(tmp_path):
        yield tmp_path


@pytest.mark.asyncio
async def test_code_edit_applies_a_near_miss_and_shows_the_result(wt):
    out = json.loads(
        await code.code_edit(
            "todos.mjs",
            "list() {\n    return items.map((t) => ({...t}))\n},",
            "list() {\n    return [...items]\n},",
        )
    )
    assert out["matched"] == "indentation" and "return [...items]" in out["now"]
    assert "            return [...items]" in (wt / "todos.mjs").read_text()


@pytest.mark.asyncio
async def test_code_edit_miss_returns_the_closest_lines(wt):
    out = json.loads(
        await code.code_edit("todos.mjs", "list() {\n  return items.filter(Boolean)\n}", "x")
    )
    assert "not found" in out["error"] and "closest_match" in out
    assert (wt / "todos.mjs").read_text() == SRC  # nothing written


@pytest.mark.asyncio
async def test_code_edit_line_range_mode(wt):
    out = json.loads(
        await code.code_edit(
            "todos.mjs",
            "",
            "        list() {\n            return [...items]\n        },",
            start_line=9,
            end_line=11,
        )
    )
    assert out["replaced_lines"] == "9-11" and "items.map" in out["replaced"]
    text = (wt / "todos.mjs").read_text()
    assert "return [...items]" in text and "items.map" not in text
    assert text.endswith("}\n")  # the rest of the file is intact
    bad = json.loads(await code.code_edit("todos.mjs", "", "x", start_line=40, end_line=41))
    assert "outside the file" in bad["error"]


@pytest.mark.asyncio
async def test_code_edit_still_creates_and_never_clobbers(wt):
    created = json.loads(await code.code_edit("new.mjs", "", "export {}\n"))
    assert "created" in created
    refused = json.loads(await code.code_edit("todos.mjs", "", "boom"))
    assert "File exists" in refused["error"] and (wt / "todos.mjs").read_text() == SRC
