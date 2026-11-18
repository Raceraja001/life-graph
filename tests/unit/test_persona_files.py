"""The built-in personas load from kernel/builtin_personas/ (persona_files.py).

The prompts moved there from personas.py on 2026-11-18, unchanged: the move
was checked equal to the old definitions, field by field. These tests hold
the format, so a typo in a file fails here instead of seeding a broken
persona.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from life_graph.kernel.persona_files import (
    PERSONA_DIR,
    PersonaFileError,
    load_builtin_personas,
    load_fragments,
)
from life_graph.kernel.personas import _BUILTIN_PERSONAS
from life_graph.kernel.propose_contract import COMMAND_PROPOSE_CONTRACT

if TYPE_CHECKING:
    from pathlib import Path

HEADER = """---
name: {name}
display_name: Test
icon: x
description: A test persona.
intent_tags: [test]
temperature: 0.2
allowed_tools: null
{extra}---

"""


def _write(d: Path, filename: str, body: str, name: str | None = None, extra: str = "") -> None:
    (d / "fragments").mkdir(exist_ok=True)
    stem = name or filename[3:-3]
    (d / filename).write_text(HEADER.format(name=stem, extra=extra) + body, encoding="utf-8")


def test_every_built_in_file_loads() -> None:
    assert load_builtin_personas() == _BUILTIN_PERSONAS
    assert len(_BUILTIN_PERSONAS) == len(list(PERSONA_DIR.glob("[0-9][0-9]-*.md")))
    for p in _BUILTIN_PERSONAS:
        assert p["system_prompt"], p["name"]
        assert "<<" not in p["system_prompt"], p["name"]
        assert "  " not in p["system_prompt"], p["name"]


def test_wrapping_does_not_change_the_prompt(tmp_path: Path) -> None:
    _write(tmp_path, "01-a.md", "One two\n   three.\nFour.\n\nNew paragraph\nhere.\n")
    _write(tmp_path, "02-b.md", "One two three. Four.\n\nNew paragraph here.\n")
    a, b = load_builtin_personas(tmp_path)
    assert (
        a["system_prompt"] == b["system_prompt"] == ("One two three. Four.\n\nNew paragraph here.")
    )


def test_windows_line_endings_load_the_same(tmp_path: Path) -> None:
    _write(tmp_path, "01-a.md", "Line one\nline two.\n")
    p = tmp_path / "01-a.md"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert load_builtin_personas(tmp_path)[0]["system_prompt"] == "Line one line two."


def test_markers_put_in_fragments_and_contracts(tmp_path: Path) -> None:
    _write(tmp_path, "01-a.md", "Do it. <<shared>> Then <<command_propose_contract>>\n")
    (tmp_path / "fragments" / "shared.md").write_text(
        "---\n# why this passage exists\n---\n\nShared\ntext.\n", encoding="utf-8"
    )
    prompt = load_builtin_personas(tmp_path)[0]["system_prompt"]
    assert prompt == "Do it. Shared text. Then" + COMMAND_PROPOSE_CONTRACT


def test_files_load_in_number_order(tmp_path: Path) -> None:
    _write(tmp_path, "02-first.md", "B.")
    _write(tmp_path, "01-second.md", "A.")
    assert [p["name"] for p in load_builtin_personas(tmp_path)] == ["second", "first"]


def test_optional_fields_come_through(tmp_path: Path) -> None:
    extra = "driver: local\nverifier_chain:\n- build_ok_diff\ncontext_profile: {domains: [code]}\n"
    _write(tmp_path, "01-a.md", "A.", extra=extra)
    p = load_builtin_personas(tmp_path)[0]
    assert p["driver"] == "local"
    assert p["verifier_chain"] == ["build_ok_diff"]
    assert p["context_profile"] == {"domains": ["code"]}
    assert p["allowed_tools"] is None
    assert list(p)[:5] == ["name", "display_name", "icon", "description", "system_prompt"]


@pytest.mark.parametrize(
    ("filename", "body", "kwargs", "error"),
    [
        ("01-a.md", "A.", {"extra": "allowed_tool: [x]\n"}, "unknown"),
        ("01-a.md", "A.", {"name": "b"}, "must match the file"),
        ("01-a.md", "A. <<nope>>", {}, "unknown fragment"),
        ("01-a.md", "\n\n", {}, "empty"),
        ("1-a.md", "A.", {"name": "a"}, "NN-<persona name>.md"),
    ],
)
def test_a_malformed_file_fails_the_load(
    tmp_path: Path, filename: str, body: str, kwargs: dict, error: str
) -> None:
    _write(tmp_path, filename, body, **kwargs)
    with pytest.raises(PersonaFileError, match=error):
        load_builtin_personas(tmp_path)


def test_a_missing_field_fails_the_load(tmp_path: Path) -> None:
    (tmp_path / "fragments").mkdir()
    (tmp_path / "01-a.md").write_text("---\nname: a\n---\n\nA.\n", encoding="utf-8")
    with pytest.raises(PersonaFileError, match="missing"):
        load_builtin_personas(tmp_path)


def test_a_file_without_a_header_fails_the_load(tmp_path: Path) -> None:
    (tmp_path / "fragments").mkdir()
    (tmp_path / "01-a.md").write_text("You are A.\n", encoding="utf-8")
    with pytest.raises(PersonaFileError, match="header"):
        load_builtin_personas(tmp_path)


def test_a_number_used_twice_fails_the_load(tmp_path: Path) -> None:
    _write(tmp_path, "01-a.md", "A.")
    _write(tmp_path, "01-b.md", "B.")
    with pytest.raises(PersonaFileError, match="used twice"):
        load_builtin_personas(tmp_path)


def test_a_fragment_cannot_carry_fields(tmp_path: Path) -> None:
    (tmp_path / "fragments").mkdir()
    (tmp_path / "fragments" / "f.md").write_text("---\nkey: 1\n---\n\nText.\n", encoding="utf-8")
    with pytest.raises(PersonaFileError, match="comments only"):
        load_fragments(tmp_path)


def test_a_fragment_cannot_shadow_a_contract(tmp_path: Path) -> None:
    (tmp_path / "fragments").mkdir()
    (tmp_path / "fragments" / "command_propose_contract.md").write_text(
        "---\n---\n\nText.\n", encoding="utf-8"
    )
    with pytest.raises(PersonaFileError, match="already exists"):
        load_fragments(tmp_path)
