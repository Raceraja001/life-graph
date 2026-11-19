"""The driver's read-only project environment (2026-11-19, rollout decision D8).

In prod the agent had a shell in its container but no test tools, and the
egress allowlist (rightly) blocks package indexes. The fix mounts the
project's cached verifier environment read-only and ships the verifier's
pinned tools in the driver image. These tests pin the safety half: only a
read-only mount from the cache, only the project's own env, no new egress.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from life_graph.config import settings
from life_graph.drivers import claude_code
from life_graph.drivers.base import ContextPacket
from life_graph.drivers.claude_code import ClaudeCodeDriver
from life_graph.services.dev import sandbox, task_runtime
from life_graph.services.dev.sandbox import Bind

REPO = Path(__file__).resolve().parents[2]


def _packet(**kw):
    return ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code", instruction="fix it", **kw
    )


@pytest.fixture
def cache(monkeypatch, tmp_path):
    root = tmp_path / "verifier-envs"
    env = root / "abc123"
    env.mkdir(parents=True)
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(root))
    return env.resolve()


# ── The bind rule ─────────────────────────────────────────────


def test_a_cached_env_may_be_mounted_read_only(cache):
    assert sandbox._bind_violations(Bind(str(cache), "/venv", read_only=True)) == []


def test_a_cached_env_may_never_be_mounted_writable(cache):
    bad = sandbox._bind_violations(Bind(str(cache), "/venv", read_only=False))
    assert any("only be mounted read-only" in b for b in bad)


def test_the_whole_cache_root_is_refused(cache):
    bad = sandbox._bind_violations(Bind(str(cache.parent), "/venv", read_only=True))
    assert any("outside the runtime's bind roots" in b for b in bad)


def test_read_only_does_not_open_any_other_host_path(cache, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    bad = sandbox._bind_violations(Bind(str(other.resolve()), "/venv", read_only=True))
    assert any("outside the runtime's bind roots" in b for b in bad)


def test_the_runtime_mounts_the_env_read_only_at_venv(cache, monkeypatch):
    from life_graph.drivers.dispatcher import tenant_scratch_root

    work = Path(tenant_scratch_root("t1")) / f"lg_dispatch_toolenv_{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True)
    try:
        req = task_runtime.RuntimeRequest(
            task_id=str(uuid.uuid4()),
            tenant_id="t1",
            driver="claude_code",
            image="img",
            command=("true",),
            workspace=work,
            tool_env=cache,
        )
        rid = "0123456789abcdef"
        names = {
            "container": f"lg-rt-{rid}",
            "network": f"lg-rt-net-{rid}",
            "proxy": f"lg-rt-egress-{rid}",
        }
        spec = task_runtime.DockerTaskRuntime()._driver_spec(req, names, {})
        argv = sandbox.docker_run_argv(spec)
    finally:
        import shutil

        shutil.rmtree(work, ignore_errors=True)
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "--mount"]
    assert f"type=bind,source={cache},target=/venv,readonly" in mounts


# ── The driver ────────────────────────────────────────────────


@pytest.fixture
def task_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "driver_claude_sandbox", "task")
    monkeypatch.setattr(settings, "driver_claude_code_auth", "oauth")
    monkeypatch.setattr(settings, "driver_claude_code_oauth_token", "sk-ant-oat01-" + "x" * 40)
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    monkeypatch.setattr(settings, "driver_runtime_project_tools", True)


async def test_the_driver_mounts_the_projects_env_and_points_the_tools_at_it(
    task_mode, cache, tmp_path, monkeypatch
):
    seen = {}

    async def fake_prepare(workdir, setup=None, allow=None):
        seen["prepare"] = (workdir, setup)
        return cache

    async def fake_run(req):
        seen["req"] = req
        return task_runtime.RuntimeOutcome(0, '{"result": "ok"}', "", {"runtime": "task"})

    monkeypatch.setattr(sandbox, "prepare_env", fake_prepare)
    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)
    packet = _packet(project_context={"sandbox_setup": "uv sync --frozen"})
    result = await ClaudeCodeDriver(binary="claude").dispatch(packet, tmp_path)

    req = seen["req"]
    assert seen["prepare"] == (
        tmp_path,
        "uv sync --frozen",
    )  # the registry's setup, not the worktree's
    assert req.tool_env == cache
    assert req.env["PATH"].startswith("/venv/bin:")
    assert req.env["UV_NO_SYNC"] == "1" and req.env["UV_OFFLINE"] == "1"
    assert req.env["PYTEST_ADDOPTS"] == "-p no:cacheprovider"  # no .pytest_cache in the diff
    assert req.egress_allowlist == tuple(settings.driver_runtime_egress_allowlist_list)
    assert result.metadata["tool_env"] == "mounted read-only"


@pytest.mark.parametrize(
    ("setting", "value", "ctx", "note"),
    [
        ("driver_runtime_project_tools", False, {}, "off"),
        ("verifier_sandbox", "none", {}, "verifier sandbox is off"),
        (None, None, {"sandbox_toolchain": "node"}, "node toolchain"),
    ],
)
async def test_no_mount_when_off_or_not_python(
    task_mode, tmp_path, monkeypatch, setting, value, ctx, note
):
    if setting:
        monkeypatch.setattr(settings, setting, value)

    async def never(*a, **k):
        raise AssertionError("prepare_env must not run")

    seen = {}

    async def fake_run(req):
        seen["req"] = req
        return task_runtime.RuntimeOutcome(0, '{"result": "ok"}', "", {"runtime": "task"})

    monkeypatch.setattr(sandbox, "prepare_env", never)
    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)
    result = await ClaudeCodeDriver(binary="claude").dispatch(
        _packet(project_context=ctx), tmp_path
    )

    assert seen["req"].tool_env is None
    assert "PATH" not in seen["req"].env
    assert note in result.metadata["tool_env"]


async def test_a_failed_env_build_still_runs_the_agent_without_tools(
    task_mode, tmp_path, monkeypatch
):
    async def broken(*a, **k):
        raise sandbox.SandboxUnavailableError("sandbox setup failed (exit 1)")

    seen = {}

    async def fake_run(req):
        seen["req"] = req
        return task_runtime.RuntimeOutcome(0, '{"result": "ok"}', "", {"runtime": "task"})

    monkeypatch.setattr(sandbox, "prepare_env", broken)
    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path)

    assert result.success is True
    assert seen["req"].tool_env is None
    assert result.metadata["tool_env"].startswith("unavailable:")


def test_the_driver_env_vars_pass_the_spec_validator():
    env = {**claude_code._TOOL_CACHE_ENV, **claude_code._PROJECT_ENV_VARS}
    assert sandbox._env_violations(env) == []


def test_driver_and_verifier_images_pin_the_same_tools():
    def pins(path):
        text = (REPO / path).read_text()
        return sorted(re.findall(r'"(\w+==[\d.]+)"', text)), re.findall(
            r"astral-sh/uv:([\d.]+)", text
        )

    assert pins("docker/claude-driver/Dockerfile") == pins("docker/verifier/Dockerfile")


# ── Review follow-ups (PR #267) ───────────────────────────────


def test_a_half_built_env_is_refused(cache):
    partial = cache.parent / "abc123.partial-deadbeef"
    partial.mkdir()
    bad = sandbox._bind_violations(Bind(str(partial.resolve()), "/venv", read_only=True))
    assert any("not a finished cached environment" in b for b in bad)


def test_only_a_direct_child_of_the_cache_is_mountable(cache):
    deeper = cache / "lib"
    deeper.mkdir()
    bad = sandbox._bind_violations(Bind(str(deeper.resolve()), "/venv", read_only=True))
    assert any("not a finished cached environment" in b for b in bad)


def test_a_cache_inside_the_scratch_root_is_still_read_only_only(monkeypatch):
    import shutil

    from life_graph.drivers.dispatcher import tenant_scratch_root

    root = Path(tenant_scratch_root("t1")) / f"lg_dispatch_cachetest_{uuid.uuid4().hex[:6]}"
    env = root / "k1"
    env.mkdir(parents=True)
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(root))
    try:
        bad = sandbox._bind_violations(Bind(str(env.resolve()), "/venv", read_only=False))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert any("only be mounted read-only" in b for b in bad)


async def test_any_env_build_error_still_runs_the_agent(task_mode, tmp_path, monkeypatch):
    async def disk_full(*a, **k):
        raise OSError(28, "No space left on device")

    seen = {}

    async def fake_run(req):
        seen["req"] = req
        return task_runtime.RuntimeOutcome(0, '{"result": "ok"}', "", {"runtime": "task"})

    monkeypatch.setattr(sandbox, "prepare_env", disk_full)
    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path)
    assert result.success is True
    assert seen["req"].tool_env is None
    assert "OSError" in result.metadata["tool_env"]
