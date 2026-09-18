"""Per-project test settings: what tests_pass runs, how long it may take, and
checks a project requires for every dev task."""

from __future__ import annotations

import pytest

from life_graph.drivers.dispatcher import _with_required_checks
from life_graph.services import sandbox
from life_graph.services import verifiers as v


@pytest.fixture
def captured(monkeypatch, tmp_path):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    seen = {}

    async def fake_prepare(workdir, setup=None):
        seen["setup"] = setup
        return tmp_path / "venv"

    async def fake_run(argv, workdir, *, venv=None, timeout=120):
        seen["argv"], seen["timeout"] = argv, timeout
        return sandbox.SandboxResult(0, "5 passed", "")

    monkeypatch.setattr(sandbox, "prepare_env", fake_prepare)
    monkeypatch.setattr(sandbox, "run", fake_run)
    return seen


async def test_project_test_command_and_timeout_are_used(captured, tmp_path):
    passed, evidence = await v._verify_tests_pass(
        tmp_path,
        {
            "sandbox_test_command": "python -m pytest -q 'tests/unit/test a.py' -k fast",
            "sandbox_test_timeout": 900,
        },
    )
    assert passed is True
    assert captured["argv"] == [
        "python",
        "-m",
        "pytest",
        "-q",
        "tests/unit/test a.py",
        "-k",
        "fast",
    ]
    assert captured["timeout"] == 900
    assert evidence["command"] == captured["argv"]


async def test_defaults_without_project_settings(captured, tmp_path):
    await v._verify_tests_pass(tmp_path, {})
    assert captured["argv"] == v._DEFAULT_TEST_ARGV
    assert captured["timeout"] == v._DEFAULT_TEST_TIMEOUT


async def test_unparseable_command_is_inconclusive(captured, tmp_path):
    passed, evidence = await v._verify_tests_pass(
        tmp_path, {"sandbox_test_command": "pytest 'unclosed"}
    )
    assert passed is None
    assert "does not parse" in evidence["note"]
    assert "argv" not in captured  # nothing ran


def test_required_checks_are_appended_once_in_order():
    chain = _with_required_checks(
        ["build_ok_diff", "lint_clean_diff"],
        {"required_checks": ["tests_pass", "lint_clean_diff", "tests_pass"]},
    )
    assert chain == ["build_ok_diff", "lint_clean_diff", "tests_pass"]
    assert _with_required_checks(["build_ok_diff"], {}) == ["build_ok_diff"]


def test_api_rejects_unknown_required_checks():
    from pydantic import ValidationError

    from life_graph.api.kernel import ProjectUpdate

    assert ProjectUpdate(required_checks=["tests_pass", "tests_pass"]).required_checks == [
        "tests_pass"
    ]
    with pytest.raises(ValidationError, match="unknown verifier"):
        ProjectUpdate(required_checks=["rm_rf"])


def test_registry_preserves_all_user_settings_across_scans():
    from life_graph.kernel.project_registry import _USER_META_KEYS, _user_scan_metadata

    assert {
        "sandbox_setup",
        "sandbox_test_command",
        "sandbox_test_timeout",
        "required_checks",
    } <= _USER_META_KEYS
    data = {
        "name": "x",
        "sandbox_test_command": "pytest",
        "required_checks": ["tests_pass"],
        "junk": 1,
    }
    assert _user_scan_metadata(data) == {
        "sandbox_test_command": "pytest",
        "required_checks": ["tests_pass"],
    }
