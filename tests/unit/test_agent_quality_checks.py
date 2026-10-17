"""Two checks from what free-engine runs got past the gates on 2026-10-17:
diff_within_scope now takes its scope from the files the task names, and
tests_exercise_code fails a test that reads the code instead of running it."""

from __future__ import annotations

import subprocess

import pytest

from life_graph.services.verifiers import (
    _test_smells,
    _verify_diff_within_scope,
    _verify_tests_exercise_code,
    named_paths,
)

TASK = (
    "In life_graph/tools/memory_search.py, two log calls include the user's raw search "
    "query. Change them. Add a unit test in tests/unit/test_memory_search_logging.py "
    "that runs both paths with caplog. Change nothing else."
)

# The test OpenCode wrote on task d917e132, which passed every check.
USELESS_TEST = """from life_graph.tools.memory_search import memory_search


def test_memory_search_log_statements_are_sanitized():
    with open("life_graph/tools/memory_search.py") as f:
        content = f.read()
    assert 'logger.info("memory_search returned %d memories", len(results))' in content
    assert memory_search is not None
"""

REAL_TEST = """import logging

from life_graph.tools import memory_search as ms


async def test_query_text_is_not_logged(monkeypatch, caplog):
    monkeypatch.setattr("life_graph.api.dependencies.get_store", lambda: None)
    with caplog.at_level(logging.INFO):
        await ms.memory_search("my secret query")
    assert "my secret query" not in caplog.text
"""


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
    )


@pytest.fixture
def project(tmp_path):
    for rel in (
        "life_graph/__init__.py",
        "life_graph/tools/__init__.py",
        "life_graph/tools/memory_search.py",
        "life_graph/api/__init__.py",
        "life_graph/api/dependencies.py",
        "tests/unit/test_memory_search_tool.py",
    ):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("X = 1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def test_named_paths_are_the_files_the_task_mentions():
    assert named_paths(TASK) == [
        "life_graph/tools/memory_search.py",
        "tests/unit/test_memory_search_logging.py",
    ]
    assert named_paths("Bump the version in ./pyproject.toml.") == ["pyproject.toml"]
    assert named_paths("Make the search faster.") == []


@pytest.mark.asyncio
async def test_scope_allows_the_named_files_and_any_tests(project):
    (project / "life_graph/tools/memory_search.py").write_text("X = 2\n")
    (project / "tests/unit/test_memory_search_logging.py").write_text("def test(): pass\n")
    (project / "tests/unit/test_memory_search_tool.py").write_text("X = 2\n")
    passed, evidence = await _verify_diff_within_scope(project, {"scope_instruction": TASK})
    assert passed, evidence


@pytest.mark.asyncio
async def test_scope_fails_production_edits_and_stray_files_outside_the_task(project):
    (project / "life_graph/tools/memory_search.py").write_text("X = 2\n")
    # What gpt-oss:20b and OpenCode did on 2026-10-17.
    (project / "life_graph/api/dependencies.py").write_text("def get_current_task_context(): ...\n")
    (project / "run_test.sh").write_text("pytest\n")
    passed, evidence = await _verify_diff_within_scope(project, {"scope_instruction": TASK})
    assert not passed
    assert sorted(evidence["out_of_scope"]) == ["life_graph/api/dependencies.py", "run_test.sh"]
    assert "Revert them" in evidence["hint"]


@pytest.mark.asyncio
async def test_a_task_naming_no_files_has_no_scope(project):
    (project / "life_graph/api/dependencies.py").write_text("X = 3\n")
    passed, evidence = await _verify_diff_within_scope(
        project, {"scope_instruction": "Make the search faster."}
    )
    assert passed and evidence == {"note": "No scope constraint"}


def test_the_useless_test_is_caught_twice():
    smells = _test_smells(USELESS_TEST, {"life_graph"})
    assert any("reads the source file 'life_graph/tools/memory_search.py'" in s for s in smells)
    assert any("imports memory_search but never calls or patches it" in s for s in smells)


def test_a_test_that_calls_and_patches_the_code_is_fine():
    assert _test_smells(REAL_TEST, {"life_graph"}) == []


@pytest.mark.asyncio
async def test_tests_exercise_code_checks_only_changed_tests(project):
    (project / "tests/unit/test_memory_search_logging.py").write_text(USELESS_TEST)
    passed, evidence = await _verify_tests_exercise_code(project, {})
    assert not passed and list(evidence["problems"]) == ["tests/unit/test_memory_search_logging.py"]
    (project / "tests/unit/test_memory_search_logging.py").write_text(REAL_TEST)
    passed, evidence = await _verify_tests_exercise_code(project, {})
    assert passed, evidence


def test_the_free_code_fixers_run_both_checks():
    from life_graph.kernel.personas import _BUILTIN_PERSONAS

    for name in ("code-fixer-local", "code-fixer-opencode", "code-fixer-auto"):
        chain = next(p for p in _BUILTIN_PERSONAS if p["name"] == name)["verifier_chain"]
        assert {"diff_within_scope", "tests_exercise_code"} <= set(chain), name


@pytest.mark.parametrize(
    ("sent", "paths"),
    [
        # What qwen3-coder sent through OpenCode on task 954c8a51.
        (
            "['tests/unit/test_memory_search_logging.py']",
            ["tests/unit/test_memory_search_logging.py"],
        ),
        ('["tests/a.py", "tests/b.py::test_x"]', ["tests/a.py", "tests/b.py::test_x"]),
        ("tests/a.py, tests/b.py", ["tests/a.py", "tests/b.py"]),
        ("tests/a.py", ["tests/a.py"]),
        (["tests/a.py"], ["tests/a.py"]),
        ("[tests/a.py]", ["tests/a.py"]),
    ],
)
def test_run_tests_takes_the_path_shapes_models_send(sent, paths):
    from life_graph.tools.run_tests import as_paths

    assert as_paths(sent) == paths


def test_task_of_recovers_the_original_task_from_a_bounce():
    from life_graph.drivers.self_check import task_of
    from life_graph.services.verifiers import BOUNCE_TASK_MARKER

    bounce = f"Your previous attempt ... failed:\n- x\n\n{BOUNCE_TASK_MARKER}\n{TASK}"
    assert task_of(bounce) == TASK
    assert task_of(TASK) == TASK
    assert task_of(None) == ""


@pytest.mark.asyncio
async def test_self_check_reports_a_failing_cheap_check(project, monkeypatch):
    from life_graph.drivers import self_check
    from life_graph.services import verifiers
    from life_graph.services.verifiers import VerifierResult

    async def no_tests(workdir, ctx):
        return None

    async def autofix(workdir, ctx):
        return {"ran": False}

    seen = {}

    async def run_chain(chain, workdir, ctx):
        seen.update(chain=chain, scope=ctx.get("scope_instruction"))
        return [
            VerifierResult(
                "lint_clean_diff", False, {"issues": "t.py:44:5: F841 unused `result`\n"}
            ),
            VerifierResult("diff_within_scope", True, {}),
            VerifierResult("tests_exercise_code", False, {"note": "x"}, inconclusive=True),
        ]

    monkeypatch.setattr(self_check, "_test_feedback", no_tests)
    monkeypatch.setattr(verifiers, "mechanical_autofix", autofix)
    monkeypatch.setattr(verifiers.verifier_chain, "run_chain", run_chain)
    bounce = f"Fix it.\n\n{verifiers.BOUNCE_TASK_MARKER}\n{TASK}"
    feedback = await self_check.check(project, {}, bounce)

    assert "F841 unused `result`" in feedback and "lint_clean_diff failed" in feedback
    assert "tests_exercise_code" not in feedback  # inconclusive is not the agent's to fix
    assert seen["scope"] == TASK
    assert seen["chain"] == list(self_check.CHEAP_CHECKS)


@pytest.mark.asyncio
async def test_the_bounce_leads_with_the_failures_and_keeps_the_task_last(monkeypatch, tmp_path):
    from life_graph.drivers.base import ContextPacket, DriverResult
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.services.verifiers import BOUNCE_TASK_MARKER, VerifierResult

    sent = {}

    class Driver:
        name = "fake"

        async def dispatch(self, packet, workdir, timeout=300):
            sent["instruction"] = packet.instruction
            return DriverResult(success=False, error="stop here")

    disp = TaskDispatcher(session_factory=lambda: None, event_bus=None)

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(disp, "_emit", noop)
    monkeypatch.setattr(disp, "_emit_steps", noop)
    packet = ContextPacket(task_id="t", tenant_id="t", task_type="code_change", instruction=TASK)
    await disp._bounce_task(
        tenant_id="t",
        task_id="task-1",
        driver=Driver(),
        packet=packet,
        workdir=tmp_path,
        failure_report=[VerifierResult("lint_clean_diff", False, {"issues": "F841\n"})],
        session=None,
        verify_chain=["lint_clean_diff"],
    )
    text = sent["instruction"]
    assert text.startswith("Your previous attempt at this task is already in the working tree")
    assert text.index("lint_clean_diff failed") < text.index(BOUNCE_TASK_MARKER)
    assert text.endswith(TASK)
