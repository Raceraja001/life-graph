"""no_test_weakening: existing tests may not be made weaker to get a pass."""

from __future__ import annotations

import subprocess

import pytest

from life_graph.services.verifiers import verifier_chain

ORIGINAL = """\
import pytest


def test_add():
    assert add(1, 2) == 3
    assert add(0, 0) == 0


def test_raises():
    with pytest.raises(ValueError):
        add(None, 1)
"""


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_math.py").write_text(ORIGINAL)
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


async def _check(repo, instruction="Fix add"):
    (result,) = await verifier_chain.run_chain(
        ["no_test_weakening"], repo, {"scope_instruction": instruction}
    )
    return result


async def test_untouched_tests_pass(repo):
    (repo / "app.py").write_text("def add(a, b):\n    return b + a\n")
    (repo / "tests" / "test_new.py").write_text("def test_n():\n    pass\n")  # new: ignored
    result = await _check(repo)
    assert result.passed and result.evidence["note"] == "no existing test changed"


async def test_a_removed_assertion_fails(repo):
    (repo / "tests" / "test_math.py").write_text(
        ORIGINAL.replace("    assert add(0, 0) == 0\n", "")
    )
    result = await _check(repo)
    assert not result.passed
    assert result.evidence["problems"] == ["1 fewer assertion(s)"]
    assert "Do not weaken" in result.evidence["hint"]


async def test_a_removed_test_fails(repo):
    trimmed = ORIGINAL.split("\n\ndef test_raises")[0] + "\n"
    (repo / "tests" / "test_math.py").write_text(trimmed)
    result = await _check(repo)
    assert not result.passed
    assert "1 fewer test(s)" in result.evidence["problems"]


async def test_a_new_skip_fails(repo):
    (repo / "tests" / "test_math.py").write_text(
        ORIGINAL.replace("def test_raises", "@pytest.mark.skip(reason='flaky')\ndef test_raises")
    )
    result = await _check(repo)
    assert not result.passed
    assert result.evidence["problems"][0].startswith("new skip/xfail")


async def test_a_deleted_test_file_fails(repo):
    (repo / "tests" / "test_math.py").unlink()
    result = await _check(repo)
    assert not result.passed
    assert result.evidence["problems"] == ["deleted test files: tests/test_math.py"]


async def test_strengthening_or_rewording_a_test_passes(repo):
    (repo / "tests" / "test_math.py").write_text(
        ORIGINAL.replace(
            "    assert add(0, 0) == 0\n", "    assert add(0, 0) == 0\n    assert add(-1, 1) == 0\n"
        ).replace("== 3", "== 1 + 2")
    )
    result = await _check(repo)
    assert result.passed, result.evidence


async def test_a_task_that_asks_for_it_may_remove_tests(repo):
    (repo / "tests" / "test_math.py").unlink()
    result = await _check(repo, "Delete the obsolete tests in tests/test_math.py")
    assert result.passed


async def test_deleting_a_test_file_with_no_tests_in_it_passes(repo):
    (repo / "tests" / "test_empty.py").write_text("")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "empty")
    (repo / "tests" / "test_empty.py").unlink()
    result = await _check(repo)
    assert result.passed, result.evidence
