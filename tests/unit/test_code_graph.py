"""code_graph: definitions, callers and callees of the symbols an
instruction names, from a stdlib-ast index of a real directory tree."""

from __future__ import annotations

import pytest

from life_graph.services.code_graph import build_graph, context_for, mentioned_symbols


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "core.py").write_text(
        "def helper(x):\n"
        "    return normalize(x)\n\n"
        "def normalize(x):\n"
        "    return x\n\n"
        "class Service:\n"
        "    def run(self):\n"
        "        return helper(1)\n",
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "api.py").write_text(
        "from pkg.core import helper\n\n"
        "def handler():\n"
        "    helper(2)\n"
        "    helper(3)\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_core.py").write_text(
        "class _Fake:\n"
        "    def execute(self):\n"
        "        pass\n\n"
        "def test_helper():\n"
        "    assert helper(1)\n",
        encoding="utf-8",
    )
    # Must never be indexed.
    (tmp_path / "node_modules" / "lib").mkdir(parents=True)
    (tmp_path / "node_modules" / "lib" / "x.py").write_text("def helper():\n    pass\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "y.py").write_text("def helper():\n    pass\n")
    (tmp_path / "pkg" / "broken.py").write_text("def oops(:\n")
    return tmp_path


def test_indexes_definitions_but_skips_vendored_dirs_and_broken_files(repo):
    graph = build_graph(repo)
    files = {d.file for d in graph.definitions["helper"]}
    assert files == {"pkg/core.py"}
    assert "oops" not in graph.definitions
    assert graph.find("Service.run")[0].qualname == "pkg.core.Service.run"


def test_context_lists_definition_callers_and_callees(repo):
    text = context_for(build_graph(repo), "Change `helper` to return a dict")
    assert "`pkg.core.helper` at pkg/core.py:1" in text
    assert "calls: `normalize`" in text
    assert "called from (3):" in text  # Service.run, handler, the test -- each once
    assert text.index("pkg.api.handler") < text.index("tests.test_core.test_helper")


def test_callees_defined_only_in_tests_are_left_out(tmp_path):
    (tmp_path / "svc.py").write_text("def save(db):\n    db.execute()\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_svc.py").write_text(
        "class _Fake:\n    def execute(self):\n        pass\n"
    )
    text = context_for(build_graph(tmp_path), "fix `save`")
    assert "execute" not in text


def test_ambiguous_names_list_every_candidate(tmp_path):
    (tmp_path / "a.py").write_text("def load():\n    pass\n")
    (tmp_path / "b.py").write_text("def load():\n    pass\n")
    text = context_for(build_graph(tmp_path), "speed up `load`")
    assert "2 definitions share this name" in text
    assert "a.load" in text and "b.load" in text


def test_unknown_symbols_give_no_context(repo):
    assert context_for(build_graph(repo), "Rename `does_not_exist`") == ""


def test_mentioned_symbols_finds_code_like_tokens():
    found = mentioned_symbols(
        "In `pkg/core.py`, make `helper()` faster; Service.run and TaskDispatcher "
        "call it, see track_record. Also update tests."
    )
    assert "helper" in found
    assert "Service.run" in found
    assert "TaskDispatcher" in found
    assert "track_record" in found
    assert "tests" not in found
