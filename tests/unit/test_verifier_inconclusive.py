""" "Could not check" is a third state, not a vote.

``VerifierResult.passed`` was a bool, so every verifier that shells out to a
tool had to squeeze "the tool isn't installed" into pass or fail — and they
disagreed with each other:

    tests_pass       missing python/pytest -> except -> False   (fails closed)
    lint_clean       missing ruff          -> except -> False   (fails closed)
    lint_clean_diff  missing ruff          -> FileNotFoundError -> True (fails OPEN)

Failing open means the gate silently approves everything on a host without
dev tooling — which the production image is. Failing closed means every
dispatch bounces to needs_human, burning a second frontier call to reach the
same state, because re-running the agent cannot install a linter.

Both are wrong, so neither is the fix. The check either happened or it did
not, and that is now representable.
"""

import subprocess

import pytest

import life_graph.services.verifiers as verifiers_mod
from life_graph.services.verifiers import VerifierResult, verifier_chain


def _init_repo(path):
    subprocess.run(["git", "init", "-q", "."], cwd=str(path), check=False)
    subprocess.run(["git", "add", "-A"], cwd=str(path), check=False)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i", "--allow-empty"],
        cwd=str(path),
        check=False,
    )


# ── The contract ──────────────────────────────────────────────────────


def test_inconclusive_never_reads_as_a_pass():
    r = VerifierResult("x", False, {}, inconclusive=True)
    assert not verifier_chain.all_passed([r])


def test_a_normal_pass_is_unaffected():
    """Default False keeps every existing VerifierResult construction valid."""
    r = VerifierResult("x", True, {})
    assert r.inconclusive is False
    assert verifier_chain.all_passed([r])


def test_one_inconclusive_check_taints_the_whole_chain():
    results = [
        VerifierResult("a", True, {}),
        VerifierResult("b", False, {}, inconclusive=True),
    ]
    assert not verifier_chain.all_passed(results)
    assert [r.verifier for r in verifier_chain.inconclusive(results)] == ["b"]


@pytest.mark.asyncio
async def test_none_sentinel_becomes_inconclusive():
    """Verifiers signal it with a None, keeping the (bool, dict) 2-tuple."""
    verifier_chain.register("_probe", lambda wd, ctx: _none_result())
    results = await verifier_chain.run_chain(["_probe"], None, {})
    assert results[0].inconclusive is True
    assert results[0].passed is False


async def _none_result():
    return None, {"note": "could not check"}


@pytest.mark.asyncio
async def test_a_real_failure_is_still_a_failure_not_inconclusive():
    """The third state must not swallow genuine failures."""
    verifier_chain.register("_fail", lambda wd, ctx: _false_result())
    results = await verifier_chain.run_chain(["_fail"], None, {})
    assert results[0].passed is False
    assert results[0].inconclusive is False


async def _false_result():
    return False, {"error": "genuinely broken"}


# ── Toolchain resolution ──────────────────────────────────────────────


def test_project_venv_wins_over_ambient_path(tmp_path):
    """The target project's interpreter, not Life Graph's and not the host's."""
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("#!/bin/sh\n")
    (venv_bin / "python").chmod(0o755)
    assert verifiers_mod._project_python(tmp_path) == str(venv_bin / "python")


def test_life_graphs_own_interpreter_is_never_the_fallback(tmp_path, monkeypatch):
    """sys.executable has pytest but none of the target project's deps.

    Running it would fail every import and blame the agent for it — a
    confident wrong answer, which is worse than reporting inconclusive.
    """
    monkeypatch.setattr(verifiers_mod.shutil, "which", lambda tool: None)
    assert verifiers_mod._project_python(tmp_path) is None


def test_missing_module_is_told_apart_from_a_test_failure():
    """`python -m pytest` exits 1 for both. Read literally, an uninstalled
    test runner looks exactly like broken code."""
    missing = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="No module named pytest"
    )
    real_failure = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="1 failed, 2 passed", stderr=""
    )
    assert verifiers_mod._missing_module(missing, "pytest")
    assert not verifiers_mod._missing_module(real_failure, "pytest")


@pytest.mark.asyncio
async def test_tests_pass_is_inconclusive_without_a_test_runner(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.setattr(verifiers_mod, "_project_python", lambda wd: None)
    results = await verifier_chain.run_chain(["tests_pass"], tmp_path, {})
    assert results[0].inconclusive is True
    assert not verifier_chain.all_passed(results)


@pytest.mark.asyncio
async def test_uninstalled_pytest_is_not_reported_as_failing_tests(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.setattr(verifiers_mod, "_project_python", lambda wd: "/usr/bin/python3")

    def _fake_run(cmd, *a, **kw):
        return subprocess.CompletedProcess(
            args=cmd, returncode=1, stdout="", stderr="No module named pytest"
        )

    monkeypatch.setattr(verifiers_mod.subprocess, "run", _fake_run)
    results = await verifier_chain.run_chain(["tests_pass"], tmp_path, {})
    assert results[0].inconclusive is True, (
        "an uninstalled test runner exits 1 just like a failing suite; "
        "reporting it as a test failure sends you hunting a bug that isn't there"
    )


@pytest.mark.asyncio
async def test_genuinely_failing_tests_still_fail(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.setattr(verifiers_mod, "_project_python", lambda wd: "/usr/bin/python3")

    def _fake_run(cmd, *a, **kw):
        return subprocess.CompletedProcess(
            args=cmd, returncode=1, stdout="1 failed, 2 passed", stderr=""
        )

    monkeypatch.setattr(verifiers_mod.subprocess, "run", _fake_run)
    results = await verifier_chain.run_chain(["tests_pass"], tmp_path, {})
    assert results[0].passed is False
    assert results[0].inconclusive is False
