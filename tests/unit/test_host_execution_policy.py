"""With verifier_sandbox="none", host-side checks never run agent-controlled code.

The worktree is the agent's. A test suite in it is agent code; a
``.venv/bin/ruff`` (or python, or pip-audit) in it is an agent-written
program. Both used to run on the host as the API's user. By default they are
now refused (inconclusive — never a pass), unless
``verifier_allow_host_execution`` is set on a disposable dev box.
"""

from __future__ import annotations

import subprocess

import pytest

from life_graph.services.dev import verifiers as v


@pytest.fixture(autouse=True)
def _host(monkeypatch):
    monkeypatch.setattr(v.sandbox, "enabled", lambda: False)


def _plant(workdir, name):
    path = workdir / ".venv" / "bin" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\necho pwned > /tmp/lg-pwned\n")
    path.chmod(0o755)
    return path


def _no_subprocess(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("agent code must not run on the host")

    monkeypatch.setattr(subprocess, "run", boom)


async def test_tests_pass_is_inconclusive_not_run(tmp_path, monkeypatch):
    _no_subprocess(monkeypatch)
    passed, evidence = await v._verify_tests_pass(tmp_path, {})
    assert passed is None
    assert "refused to run agent-written code on the host" in evidence["note"]


async def test_acceptance_tests_are_inconclusive_not_run(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n")
    _no_subprocess(monkeypatch)
    passed, evidence = await v._verify_acceptance_tests_pass(
        tmp_path, {"acceptance_tests": ["tests/test_a.py"]}
    )
    assert passed is None
    assert "refused" in evidence["note"]


def test_a_planted_tool_in_the_worktree_is_never_chosen(tmp_path, monkeypatch):
    planted = _plant(tmp_path, "ruff")
    monkeypatch.setattr(v.shutil, "which", lambda _t: "/usr/bin/ruff")
    assert v._project_tool(tmp_path, "ruff") == "/usr/bin/ruff"
    assert v._project_tool(tmp_path, "ruff") != str(planted)


def test_a_planted_interpreter_is_never_chosen(tmp_path):
    _plant(tmp_path, "python")
    assert v._project_python(tmp_path) is None


def test_the_opt_in_restores_the_old_resolution(tmp_path, monkeypatch):
    planted = _plant(tmp_path, "ruff")
    monkeypatch.setattr(v.settings, "verifier_allow_host_execution", True)
    assert v._project_tool(tmp_path, "ruff") == str(planted)


def test_the_default_is_off():
    from life_graph.config import settings

    assert settings.verifier_allow_host_execution is False
    assert settings.driver_allow_host_shell is False
