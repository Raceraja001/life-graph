"""Harness fixes from the first real dev-agent run on gpt-oss:20b (2026-10-16):
misnamed tool arguments are fitted or explained, and a coding run that ends its
turn without an edit is sent back to work, at most twice."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from life_graph.agents.orchestrator import AgentOrchestrator
from life_graph.tools.registry import ToolRegistry, fit_args


def _read(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    return f"{path}:{start_line}-{end_line}"


# ── Argument fitting ────────────────────────────────────────────────────────


def test_swapped_words_are_renamed():
    args, err = fit_args("code_read", _read, {"path": "a.py", "line_start": 5, "line_end": 9})
    assert err is None
    assert args == {"path": "a.py", "start_line": 5, "end_line": 9}


def test_near_spelling_is_renamed():
    args, err = fit_args("code_read", _read, {"paths": "a.py"})
    assert err is None and args == {"path": "a.py"}


def test_missing_required_lists_the_real_parameters():
    _, err = fit_args("code_read", _read, {"start_line": 70, "end_line": 140})
    assert "path" in err and "Parameters: path (required), start_line=1, end_line=None" in err


def test_unknown_argument_is_refused_not_dropped():
    _, err = fit_args("code_read", _read, {"path": "a.py", "colour": "red"})
    assert "no parameter 'colour'" in err


def test_a_named_parameter_is_never_overwritten_by_a_guess():
    # start_line is given; line_start must not silently replace it.
    _, err = fit_args("code_read", _read, {"path": "a.py", "start_line": 1, "line_start": 5})
    assert err and "line_start" in err


def test_handlers_taking_kwargs_are_left_alone():
    def anything(**kw):
        return kw

    assert fit_args("x", anything, {"whatever": 1}) == ({"whatever": 1}, None)


@pytest.mark.asyncio
async def test_registry_returns_the_fit_error_to_the_model():
    reg = ToolRegistry()
    reg.register("code_read", "read", {"type": "object", "properties": {}}, _read)
    out = json.loads(await reg.execute("code_read", {"end_line": 3}))
    assert "Parameters: path (required)" in out["error"]
    assert await reg.execute("code_read", {"path": "a.py", "line_start": 2}) == "a.py:2-None"


def test_lint_evidence_keeps_every_finding_from_the_top():
    from life_graph.services.verifiers import _ruff_issues

    short = "a.py:1:1: F821 Undefined name `logging`\nFound 1 error.\n"
    assert _ruff_issues(short) == short
    long = "".join(f"a.py:{i}:1: W291 Trailing whitespace\n" for i in range(1, 200))
    out = _ruff_issues(long)
    assert out.startswith("a.py:1:1:") and len(out) < 2100
    assert out.endswith("more lines)")


# Real `pytest -q --tb=line` output (pytest 9.1), paths shortened.
PYTEST_OUT = """.FF                                                                      [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'my secret query' not in 'found my secret query here'
/w/test_x.py:6: AssertionError: assert 'my secret query' not in 'found my secret query here'
E   KeyError: 'boom'
/w/test_x.py:8: KeyError: 'boom'
=============================== warnings summary ===============================
test_x.py::test_bad
  /w/test_x.py:5: DeprecationWarning: noise
    warnings.warn("noise", DeprecationWarning)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED test_x.py::test_bad - AssertionError: assert 'my secret query' not in ...
FAILED test_x.py::test_err - KeyError: 'boom'
2 failed, 1 passed, 1 warning in 0.04s
"""


def test_test_evidence_keeps_the_reasons_and_drops_the_warnings():
    from life_graph.services.verifiers import _test_evidence

    out = _test_evidence(PYTEST_OUT)
    assert out.startswith("=") and "FAILURES" in out.split("\n")[0]
    assert "/w/test_x.py:6: AssertionError" in out and "KeyError: 'boom'" in out
    assert "DeprecationWarning" not in out
    assert out.rstrip().endswith("2 failed, 1 passed, 1 warning in 0.04s")


def test_test_evidence_caps_a_long_section_but_keeps_the_summary():
    from life_graph.services.verifiers import _test_evidence

    many = "=== FAILURES ===\n" + "E   boom\n" * 600 + "600 failed in 1s\n"
    out = _test_evidence(many)
    assert len(out) <= 2000 and out.rstrip().endswith("600 failed in 1s")
    # No failures section (e.g. vitest): the tail, as before.
    assert _test_evidence("x" * 900) == "x" * 500


def test_bounce_feedback_is_readable_text_not_a_dict_repr():
    from life_graph.drivers.dispatcher import failure_text
    from life_graph.services.verifiers import VerifierResult

    r = VerifierResult(
        verifier="tests_pass",
        passed=False,
        evidence={
            "stdout": "=== FAILURES ===\nE   AttributeError: no get_store\n",
            "returncode": 1,
        },
    )
    text = failure_text(r)
    assert "\\n" not in text
    assert text.split("\n") == [
        "- tests_pass failed:",
        "  stdout:",
        "    === FAILURES ===",
        "    E   AttributeError: no get_store",
        "  returncode: 1",
    ]


@pytest.mark.asyncio
async def test_tool_argument_values_never_reach_info_logs(caplog):
    import logging

    reg = ToolRegistry()
    reg.register("code_read", "read", {"type": "object", "properties": {}}, _read)
    with caplog.at_level(logging.INFO, logger="life_graph.tools.registry"):
        await reg.execute("code_read", {"path": "my-private-diary.txt"})
    info = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
    assert any("code_read" in m and "['path']" in m for m in info)
    assert not any("my-private-diary" in m for m in info)


# ── Orchestrator: keep_going ────────────────────────────────────────────────


async def _stream(chunks):
    for chunk in chunks:
        yield SimpleNamespace(choices=[SimpleNamespace(delta=chunk)])


def _text(t):
    return _stream([SimpleNamespace(content=t, tool_calls=None)])


async def _events(agen):
    return [json.loads(e.removeprefix("data: ").strip()) async for e in agen]


@pytest.mark.asyncio
async def test_keep_going_sends_the_nudge_back_and_continues():
    orch = AgentOrchestrator(model="test-model")
    orch.condense = False
    asks = iter(["Edit the file now.", None])

    with patch("litellm.acompletion", new_callable=AsyncMock) as llm:
        llm.side_effect = [_text("I looked at it."), _text("Done.")]
        events = await _events(
            orch.run(
                messages=[{"role": "user", "content": "fix it"}], keep_going=lambda: next(asks)
            )
        )

    assert [e["type"] for e in events if e["type"] in ("nudge", "done")] == ["nudge", "done"]
    second = llm.call_args_list[1].kwargs["messages"]
    assert second[-2] == {"role": "assistant", "content": "I looked at it."}
    assert second[-1] == {"role": "user", "content": "Edit the file now."}


@pytest.mark.asyncio
async def test_without_keep_going_a_text_reply_ends_the_run():
    orch = AgentOrchestrator(model="test-model")
    orch.condense = False
    with patch("litellm.acompletion", new_callable=AsyncMock) as llm:
        llm.side_effect = [_text("Done.")]
        events = await _events(orch.run(messages=[{"role": "user", "content": "hi"}]))
    assert llm.await_count == 1 and events[-1]["stop_reason"] == "completed"


# ── Local driver: nudges a run that has not edited ──────────────────────────


class _Orch:
    MAX_ITERATIONS = 0

    def __init__(self, edit_after_nudges):
        self.model = "test-model"
        self.edit_after = edit_after_nudges
        self.nudges = []

    async def run(self, keep_going=None, **_kw):
        turn = 0
        while True:
            if turn == self.edit_after:
                yield "data: " + json.dumps({"type": "tool_call", "name": "code_edit"})
                yield "data: " + json.dumps(
                    {"type": "tool_result", "name": "code_edit", "result": '{"edited": "a.py"}'}
                )
            nudge = await keep_going()
            if not nudge:
                return
            self.nudges.append(nudge)
            turn += 1


async def _dispatch(orch, tmp_path, task_type="code_change", allowed_tools=None):
    from life_graph.drivers.base import ContextPacket
    from life_graph.drivers.local import LocalDriver

    with patch("life_graph.agents.orchestrator.AgentOrchestrator", lambda *a, **k: orch):
        return await LocalDriver().dispatch(
            ContextPacket(
                task_id="t1",
                tenant_id="t",
                task_type=task_type,
                instruction="do it",
                allowed_tools=allowed_tools,
            ),
            tmp_path,
            timeout=30,
        )


@pytest.mark.asyncio
async def test_a_nudged_run_that_then_edits_succeeds(tmp_path):
    orch = _Orch(edit_after_nudges=1)
    result = await _dispatch(orch, tmp_path)
    assert result.success, result.error
    assert len(orch.nudges) == 1 and result.metadata["nudges"] == 1


@pytest.mark.asyncio
async def test_nudges_stop_after_two_and_the_run_fails_honestly(tmp_path):
    orch = _Orch(edit_after_nudges=99)
    result = await _dispatch(orch, tmp_path)
    # The fake never called a tool at all, so this is no_action, not no_change.
    assert not result.success and result.metadata["stop_reason"] == "no_action"
    assert result.metadata["nudges"] == 2


@pytest.mark.asyncio
async def test_non_coding_and_read_only_runs_are_not_nudged(tmp_path):
    orch = _Orch(edit_after_nudges=99)
    await _dispatch(orch, tmp_path, task_type="research")
    await _dispatch(orch, tmp_path, allowed_tools=["code_read", "code_search"])
    assert orch.nudges == []


# ── run_tests: the agent checks its own test, in the sandbox only ───────────


@pytest.fixture
def sandboxed(monkeypatch, tmp_path):
    from life_graph.services import sandbox

    calls = {}

    async def prepare_env(workdir, setup=None):
        calls["setup"] = setup
        return tmp_path / "venv"

    async def run(argv, workdir, *, venv=None, timeout=120, **_):
        calls.update(argv=argv, workdir=workdir, venv=venv)
        return sandbox.SandboxResult(1, PYTEST_OUT, "")

    monkeypatch.setattr(sandbox, "enabled", lambda: True)
    monkeypatch.setattr(sandbox, "prepare_env", prepare_env)
    monkeypatch.setattr(sandbox, "run", run)
    return calls


@pytest.mark.asyncio
async def test_run_tests_runs_pytest_in_the_sandbox_with_the_project_setup(sandboxed, tmp_path):
    from life_graph.tools._guards import confine_to
    from life_graph.tools.run_tests import project_settings, run_tests

    with confine_to(tmp_path), project_settings({"sandbox_setup": "uv sync"}):
        out = json.loads(await run_tests(["tests/unit/test_x.py::test_bad"]))

    assert out["passed"] is False and "/w/test_x.py:6: AssertionError" in out["output"]
    assert sandboxed["setup"] == "uv sync" and sandboxed["workdir"] == tmp_path.resolve()
    assert sandboxed["argv"][:3] == ["python", "-m", "pytest"]
    assert sandboxed["argv"][-1] == "tests/unit/test_x.py::test_bad"


@pytest.mark.asyncio
async def test_run_tests_refuses_outside_a_task_and_without_the_sandbox(monkeypatch, tmp_path):
    from life_graph.services import sandbox
    from life_graph.tools._guards import confine_to
    from life_graph.tools.run_tests import project_settings, run_tests

    assert "only inside a dev task" in json.loads(await run_tests(["tests"]))["error"]
    monkeypatch.setattr(sandbox, "enabled", lambda: False)
    with confine_to(tmp_path), project_settings({}):
        assert "only in the sandbox" in json.loads(await run_tests(["tests"]))["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["/etc/passwd", "../other/test_x.py", "--rootdir=/", ""])
async def test_run_tests_takes_only_paths_inside_the_project(sandboxed, tmp_path, bad):
    from life_graph.tools._guards import confine_to
    from life_graph.tools.run_tests import project_settings, run_tests

    with confine_to(tmp_path), project_settings({}):
        out = json.loads(await run_tests([bad]))
    assert "error" in out and "argv" not in sandboxed


def test_code_fixer_local_can_run_tests():
    from life_graph.kernel.personas import _BUILTIN_PERSONAS

    local = next(p for p in _BUILTIN_PERSONAS if p["name"] == "code-fixer-local")
    assert "run_tests" in local["allowed_tools"]


# ── Self-check: the harness runs the agent's own changed tests ──────────────


def _git(cwd, *args):
    import subprocess

    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo_with_changes(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_old.py").write_text("def test_a():\n    pass\n")
    (tmp_path / "tests" / "test_gone.py").write_text("")
    (tmp_path / "mod.py").write_text("X = 1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    (tmp_path / "tests" / "test_old.py").write_text("def test_a():\n    assert 0\n")
    (tmp_path / "tests" / "unit").mkdir()
    (tmp_path / "tests" / "unit" / "test_new.py").write_text("def test_b():\n    pass\n")
    (tmp_path / "mod.py").write_text("X = 2\n")
    (tmp_path / "tests" / "test_gone.py").unlink()
    return tmp_path


@pytest.mark.asyncio
async def test_changed_tests_are_the_added_and_modified_test_files(repo_with_changes):
    from life_graph.drivers.self_check import changed_tests

    assert await changed_tests(repo_with_changes) == [
        "tests/test_old.py",
        "tests/unit/test_new.py",
    ]


@pytest.mark.asyncio
async def test_self_check_feeds_back_failing_tests_only(repo_with_changes, sandboxed):
    from life_graph.drivers.self_check import check

    feedback = await check(repo_with_changes, {"sandbox_setup": "uv sync"})
    assert feedback and "/w/test_x.py:6: AssertionError" in feedback
    assert sandboxed["argv"][-2:] == ["tests/test_old.py", "tests/unit/test_new.py"]


@pytest.mark.asyncio
async def test_self_check_is_silent_when_tests_pass_or_none_changed(
    repo_with_changes, monkeypatch, tmp_path_factory
):
    from life_graph.drivers import self_check
    from life_graph.services import sandbox

    async def prepare_env(workdir, setup=None):
        return workdir

    async def passing(argv, workdir, **_):
        return sandbox.SandboxResult(0, "2 passed in 0.01s\n", "")

    monkeypatch.setattr(sandbox, "enabled", lambda: True)
    monkeypatch.setattr(sandbox, "prepare_env", prepare_env)
    monkeypatch.setattr(sandbox, "run", passing)
    assert await self_check.check(repo_with_changes, {}) is None

    clean = tmp_path_factory.mktemp("clean")
    _git(clean, "init", "-q")
    assert await self_check.check(clean, {}) is None


class _EditingOrch(_Orch):
    """Edits on its first turn, then just keeps answering."""

    def __init__(self):
        super().__init__(edit_after_nudges=0)


@pytest.mark.asyncio
async def test_local_driver_sends_failing_tests_back_at_most_twice(tmp_path, monkeypatch):
    from life_graph.drivers import self_check

    calls = []

    async def failing(workdir, ctx):
        calls.append(workdir)
        return "The harness ran the tests you added or changed, and they fail: ..."

    monkeypatch.setattr(self_check, "check", failing)
    orch = _EditingOrch()
    result = await _dispatch(orch, tmp_path)
    assert len(calls) == 2 and result.metadata["self_checks"] == 2
    assert orch.nudges[0].startswith("The harness ran the tests")


@pytest.mark.asyncio
async def test_opencode_continues_its_session_with_the_failing_tests(tmp_path, monkeypatch):
    import stat

    from life_graph.drivers import self_check
    from life_graph.drivers.opencode import OpencodeDriver
    from tests.unit.test_opencode_driver import REAL_RUN, _packet

    seen = tmp_path / "argv.log"
    fake = tmp_path / "opencode"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(seen)!r}, 'a').write(json.dumps(sys.argv[1:]) + chr(10))\n"
        f"print({REAL_RUN!r})\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    answers = iter(["tests fail: assert -1 == 5", None])

    async def check(workdir, ctx):
        return next(answers)

    monkeypatch.setattr(self_check, "check", check)
    work = tmp_path / "work"
    work.mkdir()
    result = await OpencodeDriver(binary=str(fake)).dispatch(
        _packet(work, ["code_edit"]), work, timeout=300
    )

    runs = [json.loads(line) for line in seen.read_text().splitlines()]
    assert len(runs) == 2 and result.success and result.metadata["self_checks"] == 1
    assert "--session" not in runs[0]
    assert runs[1][runs[1].index("--session") + 1] == "ses_1"
    assert runs[1][-1] == "tests fail: assert -1 == 5"
    assert len(result.metadata["steps"]) == 12  # both runs' steps, renumbered
    assert [s["seq"] for s in result.metadata["steps"]] == list(range(1, 13))
