"""Verifier sandbox: routing, fail-closed behaviour, env caching, and the
worktree tamper check.

The docker-backed tests at the bottom run only where docker and the sandbox
image exist (``docker build -t life-graph-verifier:py3.12 docker/verifier``);
everything above them mocks the docker CLI.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import textwrap

import pytest

from life_graph.drivers.workdir import worktree_intact
from life_graph.services import sandbox
from life_graph.services import verifiers as v


@pytest.fixture
def docker_mode(monkeypatch, tmp_path):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))
    return settings


# ── Routing and fail-closed ──────────────────────────────────


async def test_unavailable_sandbox_is_inconclusive_not_pass(docker_mode, tmp_path, monkeypatch):
    async def boom(*a, **k):
        raise sandbox.SandboxUnavailableError("docker CLI not found")

    monkeypatch.setattr(sandbox, "prepare_env", boom)
    monkeypatch.setattr(sandbox, "run", boom)
    for check in (v._verify_tests_pass, v._verify_lint_clean, v._verify_style_conforms):
        passed, evidence = await check(tmp_path, {})
        assert passed is None, check.__name__
        assert "docker CLI not found" in evidence["note"]


async def test_sandbox_never_uses_a_worktree_venv(docker_mode, tmp_path, monkeypatch):
    """A .venv inside the worktree was planted by the agent; don't run it."""
    planted = tmp_path / ".venv" / "bin" / "python"
    planted.parent.mkdir(parents=True)
    planted.write_text("#!/bin/sh\nexit 0\n")
    planted.chmod(0o755)
    seen = {}

    async def fake_prepare(workdir, setup=None):
        seen["setup"] = setup
        return tmp_path / "envs" / "k"

    async def fake_run(argv, workdir, *, venv=None, timeout=120):
        seen["argv"], seen["venv"] = argv, venv
        return sandbox.SandboxResult(0, "1 passed", "")

    monkeypatch.setattr(sandbox, "prepare_env", fake_prepare)
    monkeypatch.setattr(sandbox, "run", fake_run)
    passed, _ = await v._verify_tests_pass(tmp_path, {"sandbox_setup": "uv sync --frozen"})
    assert passed is True
    assert seen["argv"][:3] == ["python", "-m", "pytest"]
    assert str(tmp_path) not in " ".join(seen["argv"])  # host paths don't exist in the container
    assert seen["setup"] == "uv sync --frozen"


async def test_lint_diff_passes_relative_paths(docker_mode, tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "new.py").write_text("x = 1\n")
    seen = {}

    async def fake_run(argv, workdir, *, venv=None, timeout=120):
        seen["argv"] = argv
        return sandbox.SandboxResult(0, "", "")

    monkeypatch.setattr(sandbox, "run", fake_run)
    passed, _ = await v._verify_lint_clean_diff(tmp_path, {})
    assert passed is True
    assert seen["argv"][-1] == "pkg/new.py"
    assert "--" in seen["argv"]


async def test_run_flags_lock_the_container_down(docker_mode, tmp_path, monkeypatch):
    captured = {}

    async def fake_exec(argv, timeout, container=None):
        captured["argv"] = argv
        return sandbox.SandboxResult(0, "", "")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    venv = tmp_path / "venv"
    await sandbox.run(["python", "-V"], tmp_path, venv=venv)
    argv = captured["argv"]
    joined = " ".join(argv)
    assert argv[argv.index("--network") + 1] == "none"
    assert "--read-only" in argv
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges" in argv
    assert f"{tmp_path}:/work:ro" in joined
    assert f"{venv}:/venv:ro" in joined


async def test_docker_start_failure_is_unavailable(docker_mode, tmp_path, monkeypatch):
    async def fake_exec(argv, timeout, container=None):
        return sandbox.SandboxResult(125, "", "docker: Error response from daemon")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    with pytest.raises(sandbox.SandboxUnavailableError, match="could not start"):
        await sandbox.run(["pytest"], tmp_path)


# ── Env cache ────────────────────────────────────────────────


def test_env_key_tracks_manifests_and_setup(tmp_path):
    (tmp_path / "uv.lock").write_text("a")
    k1 = sandbox._env_key(tmp_path, "img", "setup")
    assert sandbox._env_key(tmp_path, "img", "setup") == k1
    assert sandbox._env_key(tmp_path, "img", "other") != k1
    assert sandbox._env_key(tmp_path, "img2", "setup") != k1
    (tmp_path / "uv.lock").write_text("b")
    assert sandbox._env_key(tmp_path, "img", "setup") != k1


async def test_failed_setup_leaves_nothing_reusable(docker_mode, tmp_path, monkeypatch):
    workdir = tmp_path / "w"
    workdir.mkdir()

    async def fake_exec(argv, timeout, container=None):
        if argv[:3] == ["docker", "image", "inspect"]:
            return sandbox.SandboxResult(0, "sha256:abc\n", "")
        return sandbox.SandboxResult(1, "", "resolution failed")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    with pytest.raises(sandbox.SandboxUnavailableError, match="setup failed"):
        await sandbox.prepare_env(workdir)
    assert list((tmp_path / "envs").iterdir()) == []


async def test_successful_setup_is_reused(docker_mode, tmp_path, monkeypatch):
    workdir = tmp_path / "w"
    workdir.mkdir()
    runs = []

    async def fake_exec(argv, timeout, container=None):
        if argv[:3] == ["docker", "image", "inspect"]:
            return sandbox.SandboxResult(0, "sha256:abc\n", "")
        runs.append(argv)
        return sandbox.SandboxResult(0, "", "")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    first = await sandbox.prepare_env(workdir)
    second = await sandbox.prepare_env(workdir)
    assert first == second and first.is_dir()
    assert not (first / ".uv-cache").exists()
    assert len(runs) == 1
    assert f"{workdir}:/work:ro" in " ".join(runs[0])


async def test_missing_image_is_unavailable(docker_mode, tmp_path, monkeypatch):
    async def fake_exec(argv, timeout, container=None):
        return sandbox.SandboxResult(1, "", "No such image")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    with pytest.raises(sandbox.SandboxUnavailableError, match="docker build"):
        await sandbox.prepare_env(tmp_path)


# ── Driver sandbox (claude_code) ─────────────────────────────
#
# The opposite shape from the check-phase run() above: network stays on,
# the workdir is read-write, and only a throwaway credentials copy is
# mounted alongside it — never the live ~/.claude.


@pytest.fixture
def driver_docker_mode(monkeypatch, tmp_path):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "driver_claude_sandbox", "docker")
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))
    return settings


async def test_run_driver_flags_open_network_and_write_the_workdir(
    driver_docker_mode, tmp_path, monkeypatch
):
    captured = {}

    async def fake_exec(argv, timeout, container=None):
        captured["argv"] = argv
        return sandbox.SandboxResult(0, "", "")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    workdir = tmp_path / "work"
    creds = tmp_path / "creds"
    await sandbox.run_driver(["claude", "-p", "hi"], workdir, creds)
    argv = captured["argv"]
    joined = " ".join(argv)
    assert "--network" not in argv  # unlike run(): network stays on
    assert "--read-only" in argv  # root fs still locked
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert f"{workdir}:/work" in joined and f"{workdir}:/work:ro" not in joined  # rw
    # rw, not :ro: the CLI refreshes its access token in place (confirmed by
    # hand — a :ro mount left it authenticating with a stale token).
    assert f"{creds}:/claude-config" in joined and f"{creds}:/claude-config:ro" not in joined
    assert argv[argv.index("--entrypoint") + 1] == "claude"


async def test_run_driver_missing_image_is_unavailable(driver_docker_mode, tmp_path, monkeypatch):
    async def fake_exec(argv, timeout, container=None):
        return sandbox.SandboxResult(1, "", "No such image")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    with pytest.raises(sandbox.SandboxUnavailableError, match="build.sh"):
        await sandbox.run_driver(["claude"], tmp_path / "w", tmp_path / "c")


async def test_stage_credentials_copies_not_links_and_is_private(tmp_path, monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))
    source = tmp_path / ".credentials.json"
    source.write_text('{"token": "abc"}')
    staged = await sandbox.stage_credentials(source)
    try:
        copy = staged / ".credentials.json"
        assert copy.read_text() == '{"token": "abc"}'
        assert not copy.is_symlink()
        assert staged != source.parent
    finally:
        shutil.rmtree(staged, ignore_errors=True)


async def test_stage_credentials_missing_file_is_unavailable(tmp_path):
    with pytest.raises(sandbox.SandboxUnavailableError, match="no claude CLI credentials"):
        await sandbox.stage_credentials(tmp_path / "nope" / ".credentials.json")


# ── Worktree tamper check ────────────────────────────────────


@pytest.fixture
def worktree(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()

    def git(*args, cwd=origin):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    git("init", "-q")
    (origin / "f.txt").write_text("x")
    git("add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    wt = tmp_path / "wt"
    git("worktree", "add", "--detach", str(wt))
    return origin, wt


def test_fresh_worktree_is_intact(worktree):
    origin, wt = worktree
    assert worktree_intact(wt, origin)


def test_git_dir_swapped_in_is_tampered(worktree):
    origin, wt = worktree
    (wt / ".git").unlink()
    (wt / ".git").mkdir()
    (wt / ".git" / "config").write_text("[core]\n\tfsmonitor = /bin/sh\n")
    assert not worktree_intact(wt, origin)


def test_git_link_repointed_is_tampered(worktree, tmp_path):
    origin, wt = worktree
    elsewhere = tmp_path / "evil" / ".git" / "worktrees" / "wt"
    elsewhere.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {elsewhere}\n")
    assert not worktree_intact(wt, origin)


def test_git_link_symlinked_is_tampered(worktree, tmp_path):
    origin, wt = worktree
    real = tmp_path / "gitfile"
    real.write_text((wt / ".git").read_text())
    (wt / ".git").unlink()
    (wt / ".git").symlink_to(real)
    assert not worktree_intact(wt, origin)


# ── Real docker ──────────────────────────────────────────────


def _image_present() -> bool:
    if shutil.which("docker") is None:
        return False
    from life_graph.config import settings

    probe = subprocess.run(
        ["docker", "image", "inspect", settings.verifier_sandbox_image],
        capture_output=True,
    )
    return probe.returncode == 0


needs_docker = pytest.mark.skipif(not _image_present(), reason="docker sandbox image not built")


@needs_docker
def test_real_sandbox_contains_agent_test_code(docker_mode, tmp_path):
    """Test code that tries to escape: reach the network, write the worktree,
    write the host. It must pass *as tests* (every attempt fails inside the
    container) and leave no trace on the host."""
    project = tmp_path / "proj"
    project.mkdir()
    host_marker = tmp_path / "escaped"
    (project / "test_escape.py").write_text(
        textwrap.dedent(
            f"""
            import pathlib, socket, pytest

            def test_no_network():
                with pytest.raises(OSError):
                    socket.create_connection(("1.1.1.1", 53), timeout=3)

            def test_worktree_read_only():
                with pytest.raises(OSError):
                    pathlib.Path("/work/planted.py").write_text("x")

            def test_host_path_not_visible():
                with pytest.raises(OSError):
                    pathlib.Path({str(host_marker)!r}).write_text("x")
            """
        )
    )
    passed, evidence = asyncio.run(v._verify_tests_pass(project, {}))
    assert passed is True, evidence
    assert evidence["sandbox"] == "docker"
    assert not host_marker.exists()
    assert not (project / "planted.py").exists()


@needs_docker
def test_real_sandbox_reports_failing_tests(docker_mode, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "test_fail.py").write_text("def test_it():\n    assert 1 == 2\n")
    passed, evidence = asyncio.run(v._verify_tests_pass(project, {}))
    assert passed is False
    assert evidence["returncode"] == 1
