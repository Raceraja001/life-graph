"""acceptance_tests_pass: runs exactly the tests bound to a task's acceptance
criteria, against real pytest. A bound test that's missing or fails is a
failure; only a missing runner is inconclusive.

Host (non-sandboxed) path, with the interpreter pinned to this test run's own
-- the interpreter lookup isn't what's under test here.
"""

from __future__ import annotations

import sys

import pytest

from life_graph.services import verifiers as verifiers_mod
from life_graph.services.verifiers import verifier_chain


@pytest.fixture(autouse=True)
def _host_mode(monkeypatch):
    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: False)
    monkeypatch.setattr(verifiers_mod, "_project_python", lambda _workdir: sys.executable)


@pytest.fixture
def workdir(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_feature.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n\n"
        "def test_broken():\n    assert 1 + 1 == 3\n",
        encoding="utf-8",
    )
    return tmp_path


async def _run(workdir, refs):
    [result] = await verifier_chain.run_chain(
        ["acceptance_tests_pass"], workdir, {"acceptance_tests": refs}
    )
    return result


@pytest.mark.asyncio
async def test_passing_bound_test_passes(workdir):
    result = await _run(workdir, ["tests/test_feature.py::test_ok"])
    assert result.passed is True
    assert result.inconclusive is False


@pytest.mark.asyncio
async def test_failing_bound_test_fails(workdir):
    result = await _run(workdir, ["tests/test_feature.py::test_broken"])
    assert result.passed is False
    assert result.inconclusive is False
    assert result.evidence["returncode"] == 1


@pytest.mark.asyncio
async def test_only_the_bound_tests_run(workdir):
    """test_broken exists in the same file but isn't bound -- it must not count."""
    result = await _run(workdir, ["tests/test_feature.py::test_ok"])
    assert result.passed is True


@pytest.mark.asyncio
async def test_missing_test_file_is_a_failure_not_inconclusive(workdir):
    result = await _run(workdir, ["tests/test_never_written.py::test_x"])
    assert result.passed is False
    assert result.inconclusive is False
    assert result.evidence["missing"] == ["tests/test_never_written.py::test_x"]


@pytest.mark.asyncio
async def test_missing_test_name_in_an_existing_file_fails(workdir):
    result = await _run(workdir, ["tests/test_feature.py::test_that_isnt_there"])
    assert result.passed is False


@pytest.mark.asyncio
async def test_unsafe_reference_is_refused_before_pytest_runs(workdir):
    result = await _run(workdir, ["-p", "tests/test_feature.py::test_ok"])
    assert result.passed is False
    assert result.evidence["error"] == "unsafe test reference(s)"


@pytest.mark.asyncio
async def test_no_bound_tests_passes(workdir):
    result = await _run(workdir, [])
    assert result.passed is True


@pytest.mark.asyncio
async def test_no_interpreter_is_inconclusive(workdir, monkeypatch):
    monkeypatch.setattr(verifiers_mod, "_project_python", lambda _workdir: None)
    result = await _run(workdir, ["tests/test_feature.py::test_ok"])
    assert result.inconclusive is True
