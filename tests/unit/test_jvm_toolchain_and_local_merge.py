"""The JVM (Gradle) sandbox toolchain and local-only landing (pr_mode: local).

Docker is replaced at ``sandbox._exec`` (the argv it would run is what these
tests pin: offline, read-only, no network for checks). The local merge runs
against real throwaway git repositories.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from life_graph.services import sandbox


def test_toolchain_and_task_parsing():
    assert sandbox.jvm_toolchain({"sandbox_toolchain": "JVM "})
    assert not sandbox.jvm_toolchain({"sandbox_toolchain": "node"})
    assert sandbox.gradle_tasks("./gradlew testDebugUnitTest") == ["testDebugUnitTest"]
    assert sandbox.gradle_tasks("gradle test --info") == ["test", "--info"]
    assert sandbox.gradle_tasks(None) == ["test"]


@pytest.fixture
def captured(monkeypatch):
    calls: list[list[str]] = []

    async def fake_exec(argv, timeout, container=None):
        calls.append(argv)
        if argv[:3] == ["docker", "image", "inspect"]:
            return sandbox.SandboxResult(0, "sha256:abc\n", "")
        # The setup run: pretend the wrapper downloaded Gradle.
        for i, a in enumerate(argv):
            if a.endswith(":/gradle") and argv[i - 1] == "-v":
                Path(a.rsplit(":", 1)[0], "wrapper", "dists").mkdir(parents=True, exist_ok=True)
        return sandbox.SandboxResult(0, "BUILD SUCCESSFUL", "")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    return calls


def _android_project(tmp_path: Path) -> Path:
    (tmp_path / "gradlew").write_text("#!/bin/sh\n")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "build.gradle.kts").write_text('plugins { id("com.android.application") }')
    return tmp_path


@pytest.mark.asyncio
async def test_setup_resolves_and_compiles_but_never_runs_tests(tmp_path, monkeypatch, captured):
    monkeypatch.setattr(sandbox.settings, "verifier_sandbox_cache_dir", str(tmp_path / "cache"))
    (tmp_path / "w").mkdir()
    work = _android_project(tmp_path / "w")
    home = await sandbox.prepare_gradle_env(work)
    setup = captured[-1]
    script = setup[-1]
    # Resolving runs on its own, then the Android default: the unit tests' compile.
    assert "-I /gradle/lg-resolve.gradle lgResolveAll;" in script
    assert "--continue compileDebugUnitTestKotlin;" in script
    assert "testDebugUnitTest" not in script and " test;" not in script  # tests never run here
    assert "--network" not in setup  # setup is the phase with network
    assert f"{work}:/work:ro" in setup  # worktree read-only even in setup
    assert (home / "lg-resolve.gradle").is_file()
    # Cached: a second call does not run setup again.
    n = len(captured)
    assert await sandbox.prepare_gradle_env(work) == home
    assert len(captured) == n + 1  # only the image inspect


@pytest.mark.asyncio
async def test_setup_needs_a_wrapper(tmp_path, captured):
    with pytest.raises(sandbox.SandboxUnavailableError, match="no gradlew"):
        await sandbox.prepare_gradle_env(tmp_path)


@pytest.mark.asyncio
async def test_checks_run_gradle_offline_with_a_read_only_cache(tmp_path, captured):
    home = tmp_path / "home"
    await sandbox.run(["testDebugUnitTest", "--tests", "*FooTest"], tmp_path, gradle_home=home)
    argv = captured[-1]
    assert argv[argv.index("--network") + 1] == "none"
    assert "--read-only" in argv
    assert f"{home}:{sandbox.GRADLE_RO}:ro" in argv
    assert f"GRADLE_RO_DEP_CACHE={sandbox.GRADLE_RO}/caches" in argv
    assert sandbox.settings.verifier_sandbox_jvm_image in argv
    script = argv[argv.index("-c") + 1]
    assert "--offline" in script and "cp -a /work/. /tmp/work/" in script
    assert argv[-3:] == ["testDebugUnitTest", "--tests", "*FooTest"]


def test_gradle_evidence_keeps_the_reasons():
    from life_graph.services.verifiers import _gradle_evidence

    out = "\n".join(
        [
            "> Task :app:compileDebugKotlin",
            "e: file:///w/app/src/main/java/x/Api.kt:12:5 Unresolved reference: foo",
            "noise " * 50,
            "x.FooTest > parses_code FAILED",
            "    org.opentest4j.AssertionFailedError: expected: <1> but was: <2>",
            "        at x.FooTest.parses_code(FooTest.kt:9)",
            "",
            "* What went wrong:",
            "Execution failed for task ':app:testDebugUnitTest'.",
            "* Try:",
            "> Run with --stacktrace",
        ]
    )
    text = _gradle_evidence(out)
    assert "Unresolved reference: foo" in text
    assert "expected: <1> but was: <2>" in text
    assert "Execution failed for task" in text and "--stacktrace" not in text
    assert "noise" not in text


def test_run_tests_filters_from_test_files():
    from life_graph.tools.run_tests import gradle_filters

    assert gradle_filters(["app/src/test/java/com/x/PairingTest.kt", "FooTest"]) == [
        "--tests",
        "*PairingTest",
        "--tests",
        "*FooTest",
    ]
    assert gradle_filters(["app/src/test/java/com/x/bad-name.kt"]) == []


# ── Local merge ──────────────────────────────────────────────


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    from life_graph.tools import _guards

    monkeypatch.setattr(_guards, "resolve_in_roots", lambda p, tool_name=None: Path(p))
    r = tmp_path / "app"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "a.kt").write_text("val a = 1\n")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "base")
    base = _git(r, "rev-parse", "HEAD")
    _git(r, "checkout", "-qb", "lg/task-1234abcd")
    (r / "b.kt").write_text("val b = 2\n")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "task")
    head = _git(r, "rev-parse", "HEAD")
    _git(r, "checkout", "-q", "main")
    payload = {
        "branch": "lg/task-1234abcd",
        "head_commit": head,
        "base_commit": base,
        "base_branch": "main",
        "repo_path": str(r),
        "instruction": "Add b",
    }
    return r, payload


@pytest.mark.asyncio
async def test_merges_into_the_checked_out_base(repo):
    from life_graph.services.local_merge import merge_locally

    r, payload = repo
    out = await merge_locally(payload)
    assert out["merged"] and not out["existing"]
    assert _git(r, "rev-parse", "main") == out["merge_commit"]
    assert (r / "b.kt").is_file()  # the working tree followed
    assert _git(r, "log", "-1", "--format=%s") == "Merge lg/task-1234abcd: Add b"
    again = await merge_locally(payload)
    assert again["existing"] and again["merge_commit"] == out["merge_commit"]


@pytest.mark.asyncio
async def test_merges_a_base_that_is_not_checked_out(repo):
    from life_graph.services.local_merge import merge_locally

    r, payload = repo
    _git(r, "checkout", "-qb", "elsewhere")
    out = await merge_locally(payload)
    assert _git(r, "rev-parse", "main") == out["merge_commit"]
    assert _git(r, "symbolic-ref", "--short", "HEAD") == "elsewhere"


@pytest.mark.asyncio
async def test_refuses_what_was_not_verified_or_would_lose_work(repo):
    from life_graph.services.github_pr import PullRequestError
    from life_graph.services.local_merge import merge_locally

    r, payload = repo
    (r / "a.kt").write_text("val a = 99  // uncommitted\n")
    with pytest.raises(PullRequestError, match="uncommitted changes"):
        await merge_locally(payload)
    _git(r, "checkout", "-q", "--", "a.kt")

    with pytest.raises(PullRequestError, match="moved since it was verified"):
        await merge_locally({**payload, "head_commit": payload["base_commit"]})

    # A base changed in a conflicting way.
    (r / "b.kt").write_text("val b = 3\n")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "conflicting")
    with pytest.raises(PullRequestError, match="conflicts"):
        await merge_locally(payload)
    assert _git(r, "log", "-1", "--format=%s") == "conflicting"  # nothing moved
