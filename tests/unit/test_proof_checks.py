"""proof_checks: coverage of changed lines, mutants caught, changes explained, types."""

from __future__ import annotations

import ast
import json
import subprocess

import pytest

from life_graph.services import proof_checks as pc
from life_graph.services import sandbox

APP = """\
def sign(x):
    if x > 0:
        return "pos"
    if x == 0 and True:
        return "zero"
    return "neg"


class Box:
    def size(self, items):
        return len(items) + 1
"""


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("")
    (tmp_path / "app" / "logic.py").write_text(APP)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_logic.py").write_text(
        "from app.logic import sign\n\ndef test_sign():\n    assert sign(1) == 'pos'\n"
    )
    (tmp_path / "tests" / "unit" / "test_other.py").write_text("def test_x():\n    assert 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def _change_logic(repo):
    (repo / "app" / "logic.py").write_text(
        APP.replace("return len(items) + 1", "return len(items)")
    )


CTX = {"sandbox_test_command": "python -m pytest -q tests/unit --deselect tests/unit/x.py::y"}


# ── what changed ──


def test_changed_lines_and_production_files(repo):
    _change_logic(repo)
    (repo / "docs").mkdir()
    (repo / "docs" / "n.md").write_text("x\n")
    (repo / "app" / "new.py").write_text("a = 1\nb = 2\n")
    assert pc.production_files(repo) == ["app/logic.py", "app/new.py"]
    assert pc.changed_lines(repo, "app/logic.py") == {11}
    assert pc.changed_lines(repo, "app/new.py") == {1, 2}  # untracked: every line


def test_defs_touching_names_the_innermost_definition():
    assert pc._defs_touching(APP, {11}) == ["size"]  # not Box too
    assert pc._defs_touching(APP, {3, 11}) == ["sign", "size"]
    assert pc._defs_touching(APP, {8}) == []


# ── change_explained ──

GOOD = (
    "Done.\n\n## Understanding\nCurrent behaviour: size counted one too many.\n"
    "Change: size now returns len(items).\nRisk: callers relying on +1; test_size covers it.\n"
)


async def test_change_explained(repo):
    assert (await pc.change_explained(repo, {"output": ""}))[0] is True  # nothing changed
    _change_logic(repo)
    ok, ev = await pc.change_explained(repo, {"output": "I fixed it."})
    assert not ok and ev["problems"] == ["no '## Understanding' section in the reply"]
    assert "## Understanding" in ev["hint"]
    ok, ev = await pc.change_explained(repo, {"output": "## Understanding\nChange: x\n"})
    assert not ok and "Current behaviour, Risk" in ev["problems"][0]
    ok, ev = await pc.change_explained(repo, {"output": GOOD.replace("size", "it")})
    assert not ok and ev["problems"] == ["it does not name: size"]
    ok, ev = await pc.change_explained(repo, {"output": GOOD})
    assert ok, ev


# ── diff_coverage ──


def test_related_tests_are_the_ones_importing_the_changed_module(repo):
    _change_logic(repo)
    assert pc._test_root(CTX) == "tests/unit"
    assert pc.related_tests(repo, ["app/logic.py"], CTX) == ["tests/unit/test_logic.py"]


def _fake_sandbox(monkeypatch, stdout):
    calls = []

    async def prepare_env(workdir, setup=None):
        return workdir

    async def run(argv, workdir, **kw):
        calls.append((argv, kw))
        return sandbox.SandboxResult(0, stdout, "")

    monkeypatch.setattr(sandbox, "enabled", lambda: True)
    monkeypatch.setattr(sandbox, "prepare_env", prepare_env)
    monkeypatch.setattr(sandbox, "run", run)
    return calls


def _cov_output(executed, missing, rc=0):
    report = {"files": {"app/logic.py": {"executed_lines": executed, "missing_lines": missing}}}
    return f"@@RC {rc}\n1 passed\n@@COV\n{json.dumps(report)}"


async def test_diff_coverage_passes_when_changed_lines_ran(repo, monkeypatch):
    _change_logic(repo)
    calls = _fake_sandbox(monkeypatch, _cov_output([1, 2, 10, 11], [3]))
    ok, ev = await pc.diff_coverage(repo, CTX)
    assert ok and ev["ratio"] == 1.0 and ev["tests"] == ["tests/unit/test_logic.py"]
    argv = calls[0][0]
    assert argv[-1] == "tests/unit/test_logic.py" and "--cov=." in argv[2]


async def test_diff_coverage_fails_when_changed_lines_never_ran(repo, monkeypatch):
    _change_logic(repo)
    _fake_sandbox(monkeypatch, _cov_output([1, 2], [10, 11]))
    ok, ev = await pc.diff_coverage(repo, CTX)
    assert not ok and ev["uncovered"] == {"app/logic.py": [11]} and "hint" in ev


async def test_diff_coverage_fails_when_the_tests_fail(repo, monkeypatch):
    _change_logic(repo)
    _fake_sandbox(monkeypatch, _cov_output([11], [], rc=1))
    ok, ev = await pc.diff_coverage(repo, CTX)
    assert not ok and "fail (exit 1)" in ev["problems"][0]


async def test_diff_coverage_without_tests_or_python(repo, monkeypatch):
    (repo / "app" / "logic.py").write_text(APP + "\n")
    (repo / "tests" / "unit" / "test_logic.py").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "drop test")
    _change_logic(repo)
    ok, ev = await pc.diff_coverage(repo, CTX)
    assert ok is False and ev["problems"] == ["no test imports the changed modules"]

    _git(repo, "checkout", "-q", "--", ".")
    (repo / "web.ts").write_text("export const x = 1\n")
    ok, ev = await pc.diff_coverage(repo, CTX)
    assert ok is None and "Python only" in ev["note"]


async def test_diff_coverage_with_no_production_change(repo):
    (repo / "tests" / "unit" / "test_more.py").write_text("def test_y():\n    assert 2\n")
    assert (await pc.diff_coverage(repo, CTX)) == (True, {"note": "no production code changed"})


# ── tests_catch_mutants ──


def test_mutants_are_valid_and_different():
    tree = ast.parse(APP)
    func = tree.body[0]
    points = pc._mutation_points(func)
    descs = [d for _i, d in points]
    assert any("`>` flipped" in d for d in descs)
    assert any("`and` flipped" in d for d in descs)
    assert any("returns None instead" in d for d in descs)
    for index, _desc in points:
        mutated = pc._mutate(func, index)
        assert mutated is not None
        assert ast.unparse(mutated) != ast.unparse(func)


def test_build_mutants_targets_what_the_tests_import(repo):
    (repo / "tests" / "unit" / "test_new.py").write_text(
        "from app.logic import Box, sign\n\ndef test_b():\n    assert Box().size([]) == 1\n"
    )
    targets = pc._test_targets(repo, ["tests/unit/test_new.py"])
    assert targets == [("app/logic.py", "Box"), ("app/logic.py", "sign")]
    mutants = pc.build_mutants(repo, targets, limit=4)
    assert len(mutants) == 4
    assert {m["desc"].split(",")[0] for m in mutants} == {"app/logic.py Box", "app/logic.py sign"}
    for m in mutants:
        ast.parse(m["source"])  # every mutant is still valid Python
        assert m["source"] != APP


async def test_tests_catch_mutants_needs_most_mutants_killed(repo, monkeypatch):
    (repo / "tests" / "unit" / "test_new.py").write_text(
        "from app.logic import sign\n\ndef test_s():\n    assert sign(1) == 'pos'\n"
    )
    survivors = {
        "baseline": 0,
        "mutants": [{"desc": f"m{i}", "rc": 0 if i < 6 else 1} for i in range(10)],
    }
    calls = _fake_sandbox(monkeypatch, "@@MUT " + json.dumps(survivors))
    ok, ev = await pc.tests_catch_mutants(repo, {})
    assert not ok and ev["killed"] == 4 and ev["survived"][:2] == ["m0", "m1"]
    kw = calls[0][1]
    assert list(kw["extra_ro"].values()) == ["/mutants"] and kw["tmp_size"] == "2g"

    killed = {"baseline": 0, "mutants": [{"desc": "m", "rc": 1}] * 8 + [{"desc": "s", "rc": 0}] * 2}
    _fake_sandbox(monkeypatch, "@@MUT " + json.dumps(killed))
    ok, ev = await pc.tests_catch_mutants(repo, {})
    assert ok and ev["ratio"] == 0.8


async def test_tests_catch_mutants_edge_cases(repo, monkeypatch):
    assert (await pc.tests_catch_mutants(repo, {}))[1]["note"] == "no changed test files"
    (repo / "tests" / "unit" / "test_new.py").write_text(
        "from app.logic import sign\n\ndef test_s():\n    assert sign(1) == 'pos'\n"
    )
    _fake_sandbox(monkeypatch, "@@MUT " + json.dumps({"baseline": 1, "mutants": []}))
    ok, ev = await pc.tests_catch_mutants(repo, {})
    assert not ok and "fail on the unmutated code" in ev["problems"][0]
    _fake_sandbox(monkeypatch, "no marker")
    assert (await pc.tests_catch_mutants(repo, {}))[0] is None  # inconclusive, not a pass


# ── types_clean_diff ──


async def test_types_clean_diff_counts_errors_on_changed_lines_only(repo, monkeypatch):
    _change_logic(repo)
    _fake_sandbox(
        monkeypatch,
        "app/logic.py:2:5: error: old problem  [misc]\n"
        "app/logic.py:11:9: error: Incompatible return value  [return-value]\n@@RC 1\n",
    )
    ok, ev = await pc.types_clean_diff(repo, {})
    assert not ok and ev["errors"] == ["app/logic.py:11: Incompatible return value  [return-value]"]

    _fake_sandbox(monkeypatch, "app/logic.py:2:5: error: old problem  [misc]\n@@RC 1\n")
    assert (await pc.types_clean_diff(repo, {}))[0] is True

    _fake_sandbox(monkeypatch, "@@NOMYPY\n")
    assert (await pc.types_clean_diff(repo, {}))[0] is None


def test_statement_lines_map_a_changed_line_to_its_statement():
    """coverage.py counts a multi-line statement under its first line: a
    change inside a comprehension must be measured at the comprehension
    (the live trial reported "no executable lines changed", 2026-10-20)."""
    source = (
        "def f(parts):\n"  # 1
        "    # a comment\n"  # 2
        "    words = [\n"  # 3
        "        p\n"  # 4
        "        for p in parts\n"  # 5
        "        if p not in {'UPI', 'BIL'}\n"  # 6
        "    ]\n"  # 7
        "\n"  # 8
        "    return words\n"  # 9
    )
    assert pc.statement_lines(source, {6}) == {3}
    assert pc.statement_lines(source, {2, 8}) == set()  # comment and blank: not code
    assert pc.statement_lines(source, {1, 9}) == {1, 9}


async def test_diff_coverage_measures_a_change_inside_a_multiline_statement(repo, monkeypatch):
    (repo / "app" / "logic.py").write_text(
        APP
        + "\n\ndef pick(parts):\n    words = [\n        p\n        for p in parts\n        if p\n    ]\n    return words\n"
    )
    _git(repo, "commit", "-qam", "pick")
    (repo / "app" / "logic.py").write_text(
        (repo / "app" / "logic.py")
        .read_text()
        .replace("        if p\n", "        if p and p != 'x'\n")
    )
    report = {"files": {"app/logic.py": {"executed_lines": [], "missing_lines": [14, 15, 20]}}}
    _fake_sandbox(monkeypatch, f"@@RC 0\n@@COV\n{json.dumps(report)}")
    ok, ev = await pc.diff_coverage(repo, CTX)
    assert not ok and ev["uncovered"] == {"app/logic.py": [15]} and ev["changed_lines"] == 1
