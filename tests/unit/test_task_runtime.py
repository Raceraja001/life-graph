"""The per-task runtime (services/dev/task_runtime.py), against a fake docker.

What is pinned here is the boundary itself — what the driver container is
given and what it is refused — plus the lifecycle: teardown always runs, is
idempotent, and the sweep removes only what is not running. The real-docker
checks live in tests/integration/test_task_runtime_docker.py.
"""

from __future__ import annotations

import contextlib
import os
import time
import uuid
from pathlib import Path

import pytest

from life_graph.config import settings
from life_graph.services.dev import sandbox, task_runtime
from life_graph.services.dev.sandbox import Bind, SandboxResult, SandboxSpec


class FakeDocker:
    """Records every docker call; answers like a healthy daemon unless told otherwise."""

    def __init__(self, **overrides):
        self.calls: list[list[str]] = []
        self.envs: list[dict | None] = []
        self.overrides = overrides  # verb -> SandboxResult | callable

    def verb(self, argv: list[str]) -> str:
        if argv[:3] == ["docker", "network", "create"]:
            return "network create"
        if argv[:3] == ["docker", "network", "inspect"]:
            return "network inspect"
        if argv[:2] == ["docker", "run"]:
            return "run proxy" if "--detach" in argv else "run driver"
        return " ".join(argv[1:3])

    async def __call__(self, argv, *, timeout, container=None, env=None):
        self.calls.append(list(argv))
        self.envs.append(env)
        verb = self.verb(argv)
        hit = self.overrides.get(verb)
        if callable(hit):
            return await hit(argv)
        if hit is not None:
            return hit
        if verb == "network inspect" and "--format" in argv:
            return SandboxResult(0, "true\n", "")
        if verb == "image inspect":
            return SandboxResult(0, "sha256:abc\n", "")
        if verb == "run driver":
            return SandboxResult(0, '{"result": "ok"}', "")
        return SandboxResult(0, "", "")

    def first(self, verb: str) -> list[str]:
        return next(c for c in self.calls if self.verb(c) == verb)

    def has(self, verb: str) -> bool:
        return any(self.verb(c) == verb for c in self.calls)


@pytest.fixture
def roots(tmp_path, monkeypatch):
    """Point the bind roots at tmp: tenant scratch + staged-creds roots."""
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "tmp"))
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "cache" / "envs"))
    scratch = tmp_path / "tmp" / "lg-tenants" / "t1" / "lg_dispatch_x"
    worktree = scratch / "wt_1"
    worktree.mkdir(parents=True)
    creds = sandbox.driver_creds_root() / uuid.uuid4().hex
    creds.mkdir(parents=True)
    return {"worktree": worktree, "creds": creds, "tmp": tmp_path}


def _req(roots, **kw) -> task_runtime.RuntimeRequest:
    base = dict(
        task_id=str(uuid.uuid4()),
        tenant_id="t1",
        driver="claude_code",
        image="life-graph-claude-driver:test",
        command=("/usr/local/bin/claude", "-p", "hi"),
        workspace=roots["worktree"],
        credentials=roots["creds"],
        egress_allowlist=("api.anthropic.com",),
        timeout=60,
    )
    base.update(kw)
    return task_runtime.RuntimeRequest(**base)


# ── What the driver container is given ─────────────────────────


async def test_driver_container_is_locked_down_and_labelled(roots):
    docker = FakeDocker()
    req = _req(roots)
    out = await task_runtime.DockerTaskRuntime(docker).run(req)

    argv = docker.first("run driver")
    joined = " ".join(argv)
    assert out.returncode == 0
    assert "--rm" in argv and "--init" in argv and "--read-only" in argv
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges:true" in argv
    assert argv[argv.index("--memory-swap") + 1] == argv[argv.index("--memory") + 1]
    assert argv[argv.index("--network") + 1].startswith("lg-rt-net-")
    user = argv[argv.index("--user") + 1]
    assert user.split(":")[0] not in ("0", "root")
    # Only typed binds; never a -v host path.
    assert not any(a == "-v" for a in argv)
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "--mount"]
    assert any(f"source={roots['worktree'].resolve()},target=/work" in m for m in mounts)
    assert any("target=/claude-config" in m for m in mounts)
    assert len(mounts) == 2
    # The in-container deadline: the container stops itself if we die.
    assert argv[argv.index("--entrypoint") + 1] == "/usr/bin/timeout"
    assert argv[-3:] == ["/usr/local/bin/claude", "-p", "hi"]
    assert f"life-graph.runtime.task={req.task_id}" in joined
    assert f"life-graph.runtime.policy={task_runtime.POLICY_VERSION}" in joined
    assert "LIFE_GRAPH_" not in joined


async def test_egress_goes_through_a_per_task_allowlisting_proxy(roots):
    docker = FakeDocker()
    await task_runtime.DockerTaskRuntime(docker).run(_req(roots))

    proxy = docker.first("run proxy")
    net = docker.first("network create")
    assert "--internal" in net
    internal = net[-1]
    assert proxy[proxy.index("--network") + 1] == internal
    assert "--allowed-origin" in proxy
    assert proxy[proxy.index("--allowed-origin") + 1] == "https://api.anthropic.com"
    assert proxy[proxy.index("--allowed-port") + 1] == "443"
    assert "--read-only" in proxy and proxy[proxy.index("--cap-drop") + 1] == "ALL"
    connect = next(c for c in docker.calls if c[:3] == ["docker", "network", "connect"])
    assert connect[3] == task_runtime.OUTBOUND_NETWORK
    driver = " ".join(docker.first("run driver"))
    assert "HTTPS_PROXY=http://lg-rt-egress-" in driver


async def test_an_api_key_is_passed_by_name_never_in_argv(roots):
    docker = FakeDocker()
    secret = "sk-ant-api03-" + "x" * 40
    req = _req(roots, credentials=None, secret_env={"ANTHROPIC_API_KEY": secret})
    await task_runtime.DockerTaskRuntime(docker).run(req)

    argv = docker.first("run driver")
    assert secret not in " ".join(argv)
    assert "ANTHROPIC_API_KEY" in argv
    idx = docker.calls.index(argv)
    assert docker.envs[idx] == {"ANTHROPIC_API_KEY": secret}


# ── What it is refused (fail closed, nothing started) ──────────


@pytest.mark.parametrize(
    "where",
    ["live_checkout", "home", "root_of_scratch"],
)
async def test_a_workspace_outside_the_scratch_root_is_refused(roots, where, tmp_path):
    if where == "live_checkout":
        ws = tmp_path / "projects" / "life-graph"
        ws.mkdir(parents=True)
    elif where == "home":
        ws = Path.home()
    else:
        ws = tmp_path / "tmp" / "lg-tenants"
    docker = FakeDocker()
    with pytest.raises(sandbox.SandboxUnavailableError, match="policy refused"):
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots, workspace=ws))
    assert not docker.has("run driver")
    assert not docker.has("network create")


async def test_a_symlinked_workspace_is_refused(roots, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = roots["worktree"].parent / "wt_link"
    link.symlink_to(outside)
    docker = FakeDocker()
    with pytest.raises(sandbox.SandboxUnavailableError):
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots, workspace=link))
    assert not docker.has("run driver")


async def test_app_configuration_in_the_environment_is_refused(roots):
    docker = FakeDocker()
    req = _req(roots, env={"LIFE_GRAPH_DATABASE_URL": "postgresql://x"})
    with pytest.raises(sandbox.SandboxUnavailableError, match="policy refused"):
        await task_runtime.DockerTaskRuntime(docker).run(req)
    assert not docker.has("run driver")


async def test_only_the_api_key_may_be_passed_through(roots):
    docker = FakeDocker()
    req = _req(roots, secret_env={"GITHUB_TOKEN": "ghp_x"})
    with pytest.raises(sandbox.SandboxUnavailableError):
        await task_runtime.DockerTaskRuntime(docker).run(req)
    assert not docker.has("run driver")


async def test_a_missing_image_fails_before_anything_is_created(roots):
    docker = FakeDocker(**{"image inspect": SandboxResult(1, "", "No such image")})
    with pytest.raises(sandbox.SandboxUnavailableError, match="not found"):
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    assert not docker.has("network create")
    assert not docker.has("run driver")


async def test_a_network_that_is_not_internal_is_refused_and_removed(roots):
    docker = FakeDocker(**{"network inspect": SandboxResult(0, "false\n", "")})
    with pytest.raises(sandbox.SandboxUnavailableError, match="not internal"):
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    assert not docker.has("run driver")
    assert docker.has("network rm")


async def test_a_proxy_that_never_answers_fails_closed(roots, monkeypatch):
    async def no_sleep(_s):
        return None

    monkeypatch.setattr(task_runtime.asyncio, "sleep", no_sleep)

    class ProxyNeverReady(FakeDocker):
        def verb(self, argv):
            return "probe" if argv[:2] == ["docker", "exec"] else super().verb(argv)

    docker = ProxyNeverReady(probe=SandboxResult(1, "", "connection refused"))
    with pytest.raises(sandbox.SandboxUnavailableError, match="never became ready"):
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    assert not docker.has("run driver")
    assert docker.has("rm -f")


async def test_a_container_that_cannot_start_is_unavailable_not_a_failed_run(roots):
    docker = FakeDocker(**{"run driver": SandboxResult(125, "", "docker: invalid mount")})
    with pytest.raises(sandbox.SandboxUnavailableError, match="could not start"):
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots))


async def test_the_deadline_is_reported_as_a_timeout(roots):
    async def slow(argv):
        time.sleep(1.05)
        return SandboxResult(124, "", "")

    docker = FakeDocker(**{"run driver": slow})
    with pytest.raises(sandbox.SandboxUnavailableError, match="timed out") as info:
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots, timeout=1))
    assert info.value.runtime_metadata["timed_out"] is True


# ── Teardown and audit ────────────────────────────────────────


async def test_teardown_runs_after_success_and_failure(roots):
    for overrides in ({}, {"run driver": SandboxResult(125, "", "boom")}):
        docker = FakeDocker(**overrides)
        with contextlib.suppress(sandbox.SandboxUnavailableError):
            await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
        rms = [c[3] for c in docker.calls if c[:3] == ["docker", "rm", "-f"]]
        assert len(rms) == 2  # driver container + proxy
        assert any(n.startswith("lg-rt-egress-") for n in rms)
        assert docker.has("network rm")


async def test_teardown_treats_already_gone_as_done():
    gone = SandboxResult(1, "", "Error: No such container: lg-rt-x")
    docker = FakeDocker(**{"rm -f": gone, "network rm": SandboxResult(1, "", "No such network")})
    names = {"container": "lg-rt-x", "proxy": "lg-rt-egress-x", "network": "lg-rt-net-x"}
    report = await task_runtime.DockerTaskRuntime(docker).teardown(names)
    assert report == {"ok": True, "errors": []}


async def test_a_real_teardown_error_is_recorded(roots):
    docker = FakeDocker(**{"network rm": SandboxResult(1, "", "network has active endpoints")})
    out = await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    assert out.metadata["teardown"]["ok"] is False
    assert "active endpoints" in out.metadata["teardown"]["errors"][0]


async def test_metadata_records_what_the_run_was_allowed(roots):
    out = await task_runtime.DockerTaskRuntime(FakeDocker()).run(_req(roots))
    m = out.metadata
    assert m["runtime"] == "task"
    assert m["policy_version"] == task_runtime.POLICY_VERSION
    assert m["image_id"] == "sha256:abc"
    assert m["egress_allowlist"] == ["api.anthropic.com"]
    assert m["limits"]["timeout_s"] == 60
    assert {b["target"] for b in m["binds"]} == {"/work", "/claude-config"}
    assert m["teardown"]["ok"] is True
    assert m["exit_code"] == 0


# ── Sweep ──────────────────────────────────────────────────────


async def test_sweep_removes_only_leftovers_of_tasks_not_running(roots):
    live, dead = str(uuid.uuid4()), str(uuid.uuid4())
    listing = SandboxResult(0, f"lg-rt-a|{live}\nlg-rt-b|{dead}\n", "")
    nets = SandboxResult(0, f"lg-rt-net-a|{live}\nlg-rt-net-b|{dead}\n", "")
    docker = FakeDocker(**{"ps -a": listing, "network ls": nets})
    old = sandbox.driver_creds_root() / "old"
    old.mkdir(parents=True)
    os.utime(old, (time.time() - 10_000, time.time() - 10_000))

    report = await task_runtime.DockerTaskRuntime(docker).sweep({live}, creds_max_age_seconds=60)

    assert report["containers"] == ["lg-rt-b"]
    assert report["networks"] == ["lg-rt-net-b"]
    assert report["credentials"] == 1
    assert not old.exists()
    assert roots["creds"].exists()  # fresh staged copy kept
    ps = docker.first("ps -a")
    assert "label=life-graph.runtime=1" in ps  # by label, never by name pattern


# ── The validator's new typed exceptions ───────────────────────


def test_errand_specs_still_refuse_every_host_path(roots):
    spec = SandboxSpec(name="x", image="img", mounts=(f"{roots['worktree']}:/work",))
    assert any("binds a host path" in v for v in sandbox.spec_violations(spec))


@pytest.mark.parametrize("src_suffix", [",readonly=false", "\nx"])
def test_a_bind_that_could_rewrite_the_mount_option_is_refused(roots, src_suffix):
    bind = Bind(str(roots["worktree"]) + src_suffix, "/work")
    spec = SandboxSpec(name="x", image="img", binds=(bind,))
    assert sandbox.spec_violations(spec)


def test_runtime_networks_must_match_the_generated_name():
    ok = SandboxSpec(name="x", image="img", network="lg-rt-net-0123456789abcdef")
    bad = SandboxSpec(name="x", image="img", network="lg-rt-net-host")
    assert not sandbox.spec_violations(ok)
    assert sandbox.spec_violations(bad)


def test_running_as_root_is_still_refused_for_the_driver(roots, monkeypatch):
    monkeypatch.setattr(os, "getuid", lambda: 0)
    monkeypatch.setattr(os, "getgid", lambda: 0)
    rt = task_runtime.DockerTaskRuntime(FakeDocker())
    names = {"container": "lg-rt-x", "proxy": "lg-rt-egress-x", "network": "lg-rt-net-0123456789"}
    with pytest.raises(sandbox.SandboxPolicyError, match="root"):
        rt._driver_spec(_req(roots), names, {})
