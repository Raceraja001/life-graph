"""build_ok_diff/lint_clean_diff must check ONLY files changed since HEAD,
not the whole workdir tree — the whole-tree originals (build_ok/lint_clean)
would fail on this repo's pre-existing ruff debt the moment workdir points
at a real checkout instead of an always-empty scratch dir.
"""

from __future__ import annotations

import subprocess

import pytest

from life_graph.services.verifiers import verifier_chain


def _init_repo(path):
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(path), check=True, capture_output=True,
    )


@pytest.mark.asyncio
async def test_lint_clean_diff_ignores_pre_existing_issues_outside_the_diff(tmp_path):
    _init_repo(tmp_path)
    # A pre-existing, already-committed file with a lint issue (unused import) —
    # NOT part of this run's diff, must not fail lint_clean_diff.
    bad_file = tmp_path / "old.py"
    bad_file.write_text("import os\n", encoding="utf-8")
    subprocess.run(["git", "add", "old.py"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "pre-existing"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    # A NEW, clean file — the actual change under test. Staged (not committed)
    # so `git diff --name-only HEAD` picks it up — an untracked file would
    # NOT appear in that diff at all, which would make this test pass for
    # the wrong reason (nothing "changed" as far as git is concerned, rather
    # than old.py being correctly excluded by diff-scoping).
    (tmp_path / "new.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["lint_clean_diff"], tmp_path, {})

    assert results[0].passed is True


@pytest.mark.asyncio
async def test_build_ok_diff_only_compiles_changed_files(tmp_path):
    _init_repo(tmp_path)
    # A pre-existing, already-committed file with a syntax error — not
    # part of the diff, must not fail build_ok_diff.
    broken = tmp_path / "broken.py"
    broken.write_text("def f(:\n", encoding="utf-8")
    subprocess.run(["git", "add", "broken.py"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "pre-existing"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    # Staged (not committed) so `git diff --name-only HEAD` picks it up —
    # see the comment in test_lint_clean_diff_ignores_pre_existing_issues_
    # outside_the_diff for why an untracked file wouldn't prove anything here.
    (tmp_path / "new.py").write_text("y = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["build_ok_diff"], tmp_path, {})

    assert results[0].passed is True


@pytest.mark.asyncio
async def test_build_ok_diff_fails_on_a_syntax_error_in_the_diff(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "new.py").write_text("def f(:\n", encoding="utf-8")
    # Staged so git diff --name-only HEAD actually reports it as changed —
    # git add doesn't validate Python syntax, so this is fine to stage as-is.
    subprocess.run(["git", "add", "new.py"], cwd=str(tmp_path), check=True, capture_output=True)

    results = await verifier_chain.run_chain(["build_ok_diff"], tmp_path, {})

    assert results[0].passed is False


@pytest.mark.asyncio
async def test_diff_scoped_verifiers_tolerate_a_non_git_directory(tmp_path):
    """No .git at all (the scratch-temp-dir fallback case) — must not raise,
    trivially passes (nothing to check)."""
    results = await verifier_chain.run_chain(
        ["build_ok_diff", "lint_clean_diff"], tmp_path, {}
    )

    assert all(r.passed for r in results)
