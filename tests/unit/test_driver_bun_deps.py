"""The agent side of the Bun toolchain (race-app 2026-11-28-bun-sandbox, build plan step 6).

A Bun project's prepared dependencies (sandbox_deps.DepsPlan) reach the
claude_code container as read-only binds at each workspace's node_modules,
with the plan's PATH first and only allowlisted env. Any failure leaves the
agent running without project tools. The Python path is pinned byte for byte.
OpenCode has no task runtime, so Bun stays explicitly unsupported there.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

import pytest

from life_graph.config import settings
from life_graph.drivers import claude_code, opencode
from life_graph.drivers.base import ContextPacket
from life_graph.drivers.claude_code import ClaudeCodeDriver
from life_graph.services.dev import sandbox, sandbox_deps, task_runtime
from life_graph.services.dev.sandbox_deps import DepsMount, DepsPlan, DepsUnavailableError

RID = "0123456789abcdef"
NAMES = {
    "container": f"lg-rt-{RID}",
    "network": f"lg-rt-net-{RID}",
    "proxy": f"lg-rt-egress-{RID}",
}
BUN_CTX = {"sandbox_toolchain": "bun"}


def _packet(ctx: dict | None = None, **kw) -> ContextPacket:
    return ContextPacket(
        task_id=uuid.UUID(int=1),
        tenant_id="t1",
        task_type="code",
        instruction="fix it",
        project_context=ctx or {},
        **kw,
    )


@pytest.fixture
def task_mode(monkeypatch):
    monkeypatch.setattr(settings, "driver_claude_sandbox", "task")
    monkeypatch.setattr(settings, "driver_claude_code_auth", "oauth")
    monkeypatch.setattr(settings, "driver_claude_code_oauth_token", "sk-ant-oat01-" + "x" * 40)
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    monkeypatch.setattr(settings, "driver_runtime_project_tools", True)
    monkeypatch.setattr(settings, "driver_runtime_egress_allowlist", "api.anthropic.com")
    monkeypatch.setattr(settings, "driver_claude_sandbox_image", "life-graph-claude-driver:latest")
    monkeypatch.setattr(settings, "driver_claude_sandbox_memory", "4g")
    monkeypatch.setattr(settings, "driver_claude_sandbox_cpus", "4")
    monkeypatch.setattr(settings, "driver_runtime_pids_limit", 512)
    monkeypatch.setattr(settings, "driver_runtime_kill_grace_seconds", 15)


@pytest.fixture
def work():
    """A worktree inside the runtime's writable bind root (the validator's rule)."""
    from life_graph.drivers.dispatcher import tenant_scratch_root

    path = Path(tenant_scratch_root("t1")) / f"lg_dispatch_bun_{uuid.uuid4().hex[:6]}"
    path.mkdir(parents=True)
    yield path.resolve()
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def env_dirs(work):
    """Stand-ins for a finished env's node_modules trees.

    Under the scratch root, so today's validator accepts them; whether a
    cache-root descendant is mountable is the validator's own rule (W1's tests).
    """
    root = work.parent / f"{work.name}-env"
    dirs = {"root": root / "node_modules", "app": root / "packages" / "app" / "node_modules"}
    for d in dirs.values():
        d.mkdir(parents=True)
    yield {k: v.resolve() for k, v in dirs.items()}
    shutil.rmtree(root, ignore_errors=True)


def _plan(env_dirs, **kw) -> DepsPlan:
    fields: dict = {
        "toolchain": "bun",
        "env_key": "k1",
        "mounts": (
            DepsMount(env_dirs["root"], "/work/node_modules"),
            DepsMount(env_dirs["app"], "/work/packages/app/node_modules"),
        ),
        "path_prepend": ("/work/node_modules/.bin",),
        "env": {"BUN_INSTALL_CACHE_DIR": "/tmp/.bun-cache"},
        "mountpoints": ("node_modules", "packages/app/node_modules"),
    }
    fields.update(kw)
    return DepsPlan(**fields)


def _capture(monkeypatch, *, plan=None, error=None):
    seen: dict = {}

    async def fake_deps(ctx, worktree):
        seen["deps"] = (ctx, worktree)
        if error is not None:
            raise error
        return plan

    async def never_prepare(*a, **k):
        raise AssertionError("a Bun project never builds the Python env")

    async def fake_run(req):
        seen["req"] = req
        return task_runtime.RuntimeOutcome(0, '{"result": "ok"}', "", {"runtime": "task"})

    monkeypatch.setattr(sandbox_deps, "deps_mounts", fake_deps)
    monkeypatch.setattr(sandbox, "prepare_env", never_prepare)
    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)
    return seen


def _argv(req) -> list[str]:
    spec = task_runtime.DockerTaskRuntime()._driver_spec(req, NAMES, {})
    return sandbox.docker_run_argv(spec, detach=False)


def _mounts(argv: list[str]) -> list[str]:
    return [argv[i + 1] for i, a in enumerate(argv) if a == "--mount"]


def _envs(argv: list[str]) -> dict[str, str]:
    pairs = [argv[i + 1] for i, a in enumerate(argv) if a == "-e" and "=" in argv[i + 1]]
    return dict(p.split("=", 1) for p in pairs)


# ── Bun: the plan becomes read-only binds, PATH and allowlisted env ──


async def test_a_bun_plan_mounts_every_tree_read_only_at_its_target(
    task_mode, work, env_dirs, monkeypatch
):
    seen = _capture(monkeypatch, plan=_plan(env_dirs))
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(BUN_CTX), work)

    assert result.success is True
    assert seen["deps"] == (BUN_CTX, work)
    req = seen["req"]
    assert req.tool_env is None  # no /venv for a Bun project
    assert req.read_only_binds == (
        (env_dirs["root"], "/work/node_modules"),
        (env_dirs["app"], "/work/packages/app/node_modules"),
    )
    argv = _argv(req)
    assert _mounts(argv) == [
        f"type=bind,source={work},target=/work",
        f"type=bind,source={env_dirs['root']},target=/work/node_modules,readonly",
        f"type=bind,source={env_dirs['app']},target=/work/packages/app/node_modules,readonly",
    ]
    env = _envs(argv)
    # PATH is the container's (the -e flag), not the host's.
    assert env["PATH"] == (
        "/work/node_modules/.bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    )
    assert env["BUN_INSTALL_CACHE_DIR"] == "/tmp/.bun-cache"
    for python_only in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH"):
        assert python_only not in env
    assert result.metadata["tool_env"] == "mounted read-only (bun: 2 node_modules)"


async def test_the_agent_is_told_bun_is_there_and_deps_are_read_only(
    task_mode, work, env_dirs, monkeypatch
):
    seen = _capture(monkeypatch, plan=_plan(env_dirs))
    await ClaudeCodeDriver(binary="claude").dispatch(_packet(BUN_CTX), work)

    command = seen["req"].command
    i = command.index("--append-system-prompt")
    note = command[i + 1]
    assert "`bun` is on PATH" in note
    assert "READ-ONLY" in note and "`bun add`" in note
    assert "propose it in the diff" in note
    assert "/work/node_modules, /work/packages/app/node_modules" in note
    # The prompt itself is untouched; the note is extra system text.
    assert command[:3] == (sandbox.DRIVER_CLI, "-p", "fix it\n\n## Project context\n"
                           + json.dumps(BUN_CTX))  # fmt: skip


async def test_plan_env_is_cut_to_the_allowlist(task_mode, work, env_dirs, monkeypatch):
    plan = _plan(
        env_dirs,
        env={
            "BUN_INSTALL_CACHE_DIR": "/tmp/.bun-cache",
            "DO_NOT_TRACK": "1",
            "PATH": "/evil",
            "HOME": "/work",
            "HTTPS_PROXY": "http://elsewhere",
            "NODE_OPTIONS": "--require /work/x.js",
        },
    )
    seen = _capture(monkeypatch, plan=plan)
    await ClaudeCodeDriver(binary="claude").dispatch(_packet(BUN_CTX), work)

    env = _envs(_argv(seen["req"]))
    assert env["DO_NOT_TRACK"] == "1"
    assert env["PATH"].startswith("/work/node_modules/.bin:")
    assert env["HOME"] == "/tmp"
    assert env["HTTPS_PROXY"] == f"http://{NAMES['proxy']}:{task_runtime.EGRESS_PORT}"
    assert "NODE_OPTIONS" not in env


def test_the_allowlist_is_minimal_and_passes_the_spec_validator():
    assert {
        "BUN_INSTALL_CACHE_DIR",
        "BUN_RUNTIME_TRANSPILER_CACHE_PATH",
        "XDG_CACHE_HOME",
        "DO_NOT_TRACK",
    } == claude_code._DEPS_ENV_ALLOWED
    plan = DepsPlan(
        "bun",
        "k",
        (DepsMount(Path("/x"), "/work/node_modules"),),
        ("/work/node_modules/.bin",),
        {"BUN_INSTALL_CACHE_DIR": "/tmp/.bun-cache", "XDG_CACHE_HOME": "/tmp/.cache"},
    )
    assert sandbox._env_violations(claude_code._deps_env(plan)) == []


# ── Failure never fails the dispatch ──


@pytest.mark.parametrize(
    ("plan_kw", "error", "reason"),
    [
        (None, DepsUnavailableError("setup failed (exit 1)"), "DepsUnavailableError"),
        (None, sandbox.SandboxUnavailableError("docker is down"), "SandboxUnavailableError"),
        (None, OSError(28, "No space left on device"), "OSError"),
        ("none", None, "no dependency plan"),
        ({"mounts": ()}, None, "mounts nothing"),
        ({"toolchain": "npm"}, None, "not bun"),
        ({"mounts": "target=/etc/node_modules"}, None, "not under /work"),
        ({"mounts": "target=/work"}, None, "not under /work"),
        ({"mounts": "target=/work/../etc"}, None, "not under /work"),
        ({"mounts": "target=/work/a:b"}, None, "not under /work"),
        ({"path_prepend": ("/usr/evil/bin",)}, None, "not under /work"),
        ({"mounts": "twice"}, None, "one target twice"),
    ],
)
async def test_an_unusable_plan_runs_the_agent_without_project_tools(
    task_mode, work, env_dirs, monkeypatch, plan_kw, error, reason
):
    plan = None
    if isinstance(plan_kw, dict):
        kw = dict(plan_kw)
        if isinstance(kw.get("mounts"), str):
            spec = kw.pop("mounts")
            if spec == "twice":
                kw["mounts"] = (DepsMount(env_dirs["root"], "/work/node_modules"),) * 2
            else:
                kw["mounts"] = (DepsMount(env_dirs["root"], spec.removeprefix("target=")),)
        plan = _plan(env_dirs, **kw)
    seen = _capture(monkeypatch, plan=plan, error=error)
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(BUN_CTX), work)

    assert result.success is True
    req = seen["req"]
    assert req.read_only_binds == () and req.tool_env is None
    assert "PATH" not in req.env
    assert "--append-system-prompt" not in req.command
    assert result.metadata["tool_env"].startswith("unavailable:")
    assert reason in result.metadata["tool_env"]


async def test_bun_is_gated_like_python(task_mode, work, monkeypatch):
    monkeypatch.setattr(settings, "verifier_sandbox", "none")
    seen = _capture(monkeypatch, plan=None)
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(BUN_CTX), work)
    assert "deps" not in seen
    assert result.metadata["tool_env"] == "not mounted: verifier sandbox is off"


def test_the_runtime_refuses_a_read_only_bind_outside_work(work, env_dirs):
    req = task_runtime.RuntimeRequest(
        task_id="t",
        tenant_id="t1",
        driver="claude_code",
        image="img",
        command=("true",),
        workspace=work,
        read_only_binds=((env_dirs["root"], "/etc/node_modules"),),
    )
    with pytest.raises(sandbox.SandboxPolicyError, match="not under /work"):
        task_runtime.DockerTaskRuntime()._driver_spec(req, NAMES, {})


# ── Python: byte for byte what it was before Bun ──

# Captured from the pre-Bun driver (commit ab4d48a9) with the settings in task_mode.
# Plus NO_PROXY/no_proxy = loopback (2026-11-28: local test servers must not go via the proxy).
_PYTHON_ARGV = [
    "docker", "run", "--name", "lg-rt-0123456789abcdef", "--init",
    "--label", "life-graph.sandbox=1", "--label", "life-graph.sandbox.role=driver", "--rm",
    "--network", "lg-rt-net-0123456789abcdef", "--read-only", "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges:true", "--pids-limit", "512", "--memory", "4g",
    "--memory-swap", "4g", "--cpus", "4", "--user", "<UID>",
    "--tmpfs", "/tmp:rw,nosuid,nodev,exec,size=512m,mode=1777",
    "--mount", "type=bind,source=<WORK>,target=/work",
    "--mount", "type=bind,source=<CACHE>,target=/venv,readonly",
    "--label", "life-graph.runtime.role=driver",
    "-e", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1", "-e", "CLAUDE_CONFIG_DIR=/tmp/.claude",
    "-e", "DISABLE_AUTOUPDATER=1", "-e", "HOME=/tmp",
    "-e", "HTTPS_PROXY=http://lg-rt-egress-0123456789abcdef:8080",
    "-e", "HTTP_PROXY=http://lg-rt-egress-0123456789abcdef:8080", "-e", "LANG=C.UTF-8",
    "-e", "MYPY_CACHE_DIR=/tmp/.mypy_cache", "-e", "NO_PROXY=localhost,127.0.0.1,::1",
    "-e", "PATH=/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "-e", "PYTEST_ADDOPTS=-p no:cacheprovider", "-e", "PYTHONDONTWRITEBYTECODE=1",
    "-e", "PYTHONPATH=/work:/work/src", "-e", "RUFF_NO_CACHE=true", "-e", "TZ=UTC",
    "-e", "UV_CACHE_DIR=/tmp/.uv-cache", "-e", "UV_NO_SYNC=1", "-e", "UV_OFFLINE=1",
    "-e", "UV_PROJECT_ENVIRONMENT=/venv", "-e", "UV_PYTHON_DOWNLOADS=never",
    "-e", "VIRTUAL_ENV=/venv",
    "-e", "http_proxy=http://lg-rt-egress-0123456789abcdef:8080",
    "-e", "https_proxy=http://lg-rt-egress-0123456789abcdef:8080",
    "-e", "no_proxy=localhost,127.0.0.1,::1",
    "-e", "CLAUDE_CODE_OAUTH_TOKEN", "-w", "/work", "--entrypoint", "/usr/bin/timeout",
    "life-graph-claude-driver:latest", "-k", "7", "300", "/usr/local/bin/claude",
    "-p", 'fix it\n\n## Project context\n{"sandbox_setup": "uv sync --frozen"}',
    "--output-format", "stream-json", "--verbose",
]  # fmt: skip


async def test_the_python_argv_is_unchanged(task_mode, work, tmp_path, monkeypatch):
    root = tmp_path / "envs"
    cache = root / "k1"
    cache.mkdir(parents=True)
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(root))
    seen: dict = {}

    async def fake_prepare(*a, **k):
        return cache.resolve()

    async def never_deps(*a, **k):
        raise AssertionError("a Python project never asks for a dependency plan")

    async def fake_run(req):
        seen["req"] = req
        return task_runtime.RuntimeOutcome(0, '{"result": "ok"}', "", {})

    monkeypatch.setattr(sandbox, "prepare_env", fake_prepare)
    monkeypatch.setattr(sandbox_deps, "deps_mounts", never_deps)
    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)
    packet = _packet({"sandbox_setup": "uv sync --frozen"})
    result = await ClaudeCodeDriver(binary="claude").dispatch(packet, work)

    argv = [
        a.replace(str(work), "<WORK>")
        .replace(str(cache.resolve()), "<CACHE>")
        .replace(f"{os.getuid()}:{os.getgid()}", "<UID>")
        for a in _argv(seen["req"])
    ]
    assert argv == _PYTHON_ARGV
    assert result.metadata["tool_env"] == "mounted read-only"


# ── OpenCode: no task runtime, so Bun is explicitly unsupported ──


@pytest.mark.parametrize(
    ("ctx", "status"),
    [
        ({}, "offered"),
        ({"sandbox_toolchain": "jvm"}, "offered"),
        (BUN_CTX, "unsupported: bun toolchain (opencode has no task runtime)"),
    ],
)
def test_opencode_offers_run_tests_only_where_it_can(monkeypatch, ctx, status):
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    packet = _packet(ctx)
    assert opencode._run_tests_status(packet) == status
    assert opencode._can_run_tests(packet) is (status == "offered")
    assert (opencode._run_tests_server(packet, Path("/w")) is None) is (status != "offered")


def test_opencode_says_why_tests_are_not_offered(monkeypatch):
    monkeypatch.setattr(settings, "verifier_sandbox", "none")
    assert opencode._run_tests_status(_packet()) == "not offered: sandbox is off"
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    packet = _packet(allowed_tools=["file_read"])
    assert opencode._run_tests_status(packet) == "not offered: not in the persona's tools"
