"""Diff-scoped verifiers fail closed when git cannot say what changed.

``verifiers._changed_files`` used to return ``[]`` on any git failure (git
missing, a timeout, a non-zero exit). Every diff-scoped verifier then saw "no
changed files" and passed -- a git hiccup passed a task without checking it.
Now a failure inside a git worktree raises ``DiffUnavailableError`` and the
verifier chain records a FAILED result (not a pass, not inconclusive) that
says why. A directory outside any git repository (the scratch-dir fallback)
and a clean worktree behave exactly as before.
"""

from __future__ import annotations

import subprocess

import pytest

from life_graph.services.dev import verifiers
from life_graph.services.dev.verifiers import DiffUnavailableError, verifier_chain

# Every built-in verifier that reads the diff.
DIFF_VERIFIERS = [
    "build_ok_diff",
    "lint_clean_diff",
    "no_secrets_in_diff",
    "no_vulnerable_deps_in_diff",
    "diff_within_scope",
    "tests_exercise_code",
    "no_test_weakening",
    "no_diff_in_plan",
    "change_explained",
    "diff_coverage",
    "tests_catch_mutants",
    "types_clean_diff",
]

_REAL_RUN = subprocess.run


def _git(path, *args):
    _REAL_RUN(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(path),
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "app.py").write_text("x = 1\n")
    _git(tmp_path, "add", "app.py")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _break_git(monkeypatch, how: str):
    def run(argv, *a, **k):
        if argv and argv[0] == "git":
            if how == "missing":
                raise FileNotFoundError(2, "No such file or directory: 'git'")
            if how == "timeout":
                raise subprocess.TimeoutExpired(argv, 30)
            return subprocess.CompletedProcess(argv, 128, "", "fatal: something broke")
        return _REAL_RUN(argv, *a, **k)

    monkeypatch.setattr(verifiers.subprocess, "run", run)


@pytest.mark.parametrize("how", ["missing", "timeout", "nonzero"])
def test_a_git_failure_in_a_worktree_raises(repo, monkeypatch, how):
    (repo / "new.py").write_text("y = 2\n")
    _break_git(monkeypatch, how)
    with pytest.raises(DiffUnavailableError):
        verifiers._changed_files(repo)


@pytest.mark.parametrize("how", ["missing", "timeout", "nonzero"])
async def test_every_diff_verifier_fails_closed(repo, monkeypatch, how):
    (repo / "new.py").write_text("y = (\n")  # a syntax error build_ok_diff would catch
    _break_git(monkeypatch, how)
    ctx = {"allowed_files": ["app.py"], "scope_instruction": "edit app.py"}
    results = await verifier_chain.run_chain(DIFF_VERIFIERS, repo, ctx)
    for r in results:
        assert r.passed is False, f"{r.verifier} passed without seeing the diff"
        assert r.inconclusive is False, r.verifier
        assert "could not determine the diff" in r.evidence["error"], r.verifier
    assert not verifier_chain.all_passed(results)


async def test_mechanical_autofix_reports_instead_of_raising(repo, monkeypatch):
    _break_git(monkeypatch, "missing")
    out = await verifiers.mechanical_autofix(repo, {})
    assert out["ran"] is False
    assert "could not determine the diff" in out["note"]


def test_a_deleted_test_file_counts_when_git_show_fails(repo, monkeypatch):
    _break_git(monkeypatch, "nonzero")
    assert verifiers._held_tests(repo, "tests/test_x.py") is True


# ── unchanged behaviour ──


async def test_a_clean_worktree_still_passes(repo):
    assert verifiers._changed_files(repo) == []
    results = await verifier_chain.run_chain(
        ["build_ok_diff", "lint_clean_diff", "no_diff_in_plan", "no_test_weakening"], repo, {}
    )
    assert [r.passed for r in results] == [True, True, True, True]
    assert results[0].evidence["checked"] == 0


def test_a_change_is_still_listed_when_git_works(repo):
    (repo / "app.py").write_text("x = 2\n")
    (repo / "new.py").write_text("y = 2\n")
    assert sorted(verifiers._changed_files(repo)) == [repo / "app.py", repo / "new.py"]


def test_a_repository_with_no_commit_lists_every_file_as_new(tmp_path):
    """A new project before its first commit: HEAD does not resolve, so the
    diff is against the empty tree, not a failure."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "new.py").write_text("y = 2\n")
    (tmp_path / "staged.py").write_text("z = 3\n")
    _git(tmp_path, "add", "staged.py")
    assert sorted(verifiers._changed_files(tmp_path)) == [
        tmp_path / "new.py",
        tmp_path / "staged.py",
    ]


async def test_a_directory_outside_any_repository_has_no_diff(tmp_path, monkeypatch):
    """The scratch-dir fallback: no repository, so nothing changed and nothing
    can land. git is not even asked."""
    (tmp_path / "x.py").write_text("y = (\n")
    _break_git(monkeypatch, "missing")
    assert not verifiers.in_git_worktree(tmp_path) or pytest.skip("tmp_path is inside a repo")
    assert verifiers._changed_files(tmp_path) == []
    (result,) = await verifier_chain.run_chain(["build_ok_diff"], tmp_path, {})
    assert result.passed is True
