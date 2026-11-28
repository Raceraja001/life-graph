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
from datetime import UTC, datetime
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

    async def __call__(self, argv, *, timeout, container=None, env=None, on_stdout_line=None):
        self.calls.append(list(argv))
        self.envs.append(env)
        verb = self.verb(argv)
        hit = self.overrides.get(verb)
        if callable(hit):
            return await hit(argv)
        if hit is not None:
            return hit
        if verb == "network inspect" and "--format" in argv:
            return SandboxResult(0, "true|isolated\n", "")
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
    docker = FakeDocker(**{"network inspect": SandboxResult(0, "false|isolated\n", "")})
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


async def test_the_network_gives_the_host_no_address_on_the_bridge(roots):
    """--internal alone left the host reachable on the bridge gateway (probe
    2026-11-18: host services bound to 0.0.0.0 answered). Isolated gateway mode
    is requested and then checked."""
    docker = FakeDocker()
    await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    net = docker.first("network create")
    assert "com.docker.network.bridge.gateway_mode_ipv4=isolated" in net
    assert "com.docker.network.bridge.gateway_mode_ipv6=isolated" in net


async def test_a_daemon_that_ignores_isolated_mode_is_refused(roots):
    docker = FakeDocker(**{"network inspect": SandboxResult(0, "true|\n", "")})
    with pytest.raises(sandbox.SandboxUnavailableError, match="isolated gateway"):
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    assert not docker.has("run driver")
    assert docker.has("network rm")


# ── Where the network's addresses come from ────────────────────

_OVERLAP = SandboxResult(
    1, "", "Error response from daemon: invalid pool request: Pool overlaps with other one"
)


async def test_the_network_gets_a_subnet_from_the_configured_pool(roots, monkeypatch):
    """Docker's default pools ran out at 12 concurrent runtimes (2026-11-19)."""
    import ipaddress

    monkeypatch.setattr(settings, "driver_runtime_subnet_pool", "10.213.0.0/16")
    monkeypatch.setattr(settings, "driver_runtime_subnet_prefix", 28)
    docker = FakeDocker()
    out = await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    net = docker.first("network create")
    subnet = ipaddress.ip_network(net[net.index("--subnet") + 1])
    assert subnet.prefixlen == 28
    assert subnet.subnet_of(ipaddress.ip_network("10.213.0.0/16"))
    assert out.metadata["subnet"] == str(subnet)
    # The rest of the policy is unchanged.
    assert "--internal" in net
    assert "com.docker.network.bridge.gateway_mode_ipv4=isolated" in net
    assert net[-1].startswith("lg-rt-net-")


def test_subnet_candidates_are_distinct_spread_and_in_range():
    import ipaddress

    pool = ipaddress.ip_network("10.213.0.0/16")
    a = task_runtime._subnet_candidates("aaaa", str(pool), 28)
    b = task_runtime._subnet_candidates("bbbb", str(pool), 28)
    assert len(a) == task_runtime.SUBNET_ATTEMPTS == len(set(a))
    assert a != b and a == task_runtime._subnet_candidates("aaaa", str(pool), 28)
    assert all(ipaddress.ip_network(s).subnet_of(pool) for s in a + b)
    # A pool smaller than the attempt count yields each subnet once.
    assert len(task_runtime._subnet_candidates("x", "10.213.0.0/27", 28)) == 2


@pytest.mark.parametrize(
    ("pool", "prefix"),
    [("8.8.0.0/16", 28), ("not-a-net", 28), ("10.213.0.0/16", 12), ("10.213.0.0/16", 30)],
)
async def test_a_bad_subnet_pool_fails_closed(roots, monkeypatch, pool, prefix):
    monkeypatch.setattr(settings, "driver_runtime_subnet_pool", pool)
    monkeypatch.setattr(settings, "driver_runtime_subnet_prefix", prefix)
    docker = FakeDocker()
    with pytest.raises(sandbox.SandboxUnavailableError, match="driver_runtime_subnet"):
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    assert not docker.has("network create")
    assert not docker.has("run driver")


async def test_a_taken_subnet_is_retried_with_another(roots, monkeypatch):
    monkeypatch.setattr(settings, "driver_runtime_subnet_pool", "10.213.0.0/16")
    tries: list[str] = []

    async def create(argv):
        tries.append(argv[argv.index("--subnet") + 1])
        return _OVERLAP if len(tries) < 3 else SandboxResult(0, "netid\n", "")

    docker = FakeDocker(**{"network create": create})
    out = await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    assert out.returncode == 0
    assert len(tries) == 3 == len(set(tries))
    assert out.metadata["subnet"] == tries[-1]
    assert docker.has("run driver")


async def test_every_subnet_taken_fails_closed_without_a_fallback(roots, monkeypatch):
    monkeypatch.setattr(settings, "driver_runtime_subnet_pool", "10.213.0.0/16")
    docker = FakeDocker(**{"network create": _OVERLAP})
    with pytest.raises(sandbox.SandboxUnavailableError, match="all taken"):
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    creates = [c for c in docker.calls if docker.verb(c) == "network create"]
    assert len(creates) == task_runtime.SUBNET_ATTEMPTS
    # Never a network from docker's default pools, never a container.
    assert all("--subnet" in c and "--internal" in c for c in creates)
    assert not docker.has("run driver") and not docker.has("run proxy")
    assert docker.has("network rm")


async def test_a_non_overlap_create_error_is_not_retried(roots, monkeypatch):
    monkeypatch.setattr(settings, "driver_runtime_subnet_pool", "10.213.0.0/16")
    docker = FakeDocker(**{"network create": SandboxResult(1, "", "permission denied")})
    with pytest.raises(sandbox.SandboxUnavailableError, match="permission denied"):
        await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    assert sum(docker.verb(c) == "network create" for c in docker.calls) == 1


async def test_an_empty_pool_keeps_dockers_default_pools(roots, monkeypatch):
    monkeypatch.setattr(settings, "driver_runtime_subnet_pool", "")
    docker = FakeDocker()
    out = await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    net = docker.first("network create")
    assert "--subnet" not in net
    labels = [x for i, x in enumerate(net) if i and net[i - 1] == "--label"]
    assert net == [
        "docker", "network", "create", "--internal",
        "-o", "com.docker.network.bridge.gateway_mode_ipv4=isolated",
        "-o", "com.docker.network.bridge.gateway_mode_ipv6=isolated",
        *[x for lab in labels for x in ("--label", lab)],
        out.metadata["network"],
    ]  # fmt: skip
    assert out.metadata["subnet"] is None


async def test_everything_is_labelled_with_this_install(roots):
    docker = FakeDocker()
    await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    label = f"life-graph.runtime.instance={task_runtime.instance_id()}"
    assert label in " ".join(docker.first("run driver"))
    assert label in " ".join(docker.first("run proxy"))
    assert label in " ".join(docker.first("network create"))


async def test_the_sweep_never_looks_at_another_installs_runtimes(roots):
    """Prod and dev share one docker daemon; each has its own database, so the
    other's running task is never in active_task_ids."""
    docker = FakeDocker()
    await task_runtime.DockerTaskRuntime(docker).sweep(set())
    want = f"label=life-graph.runtime.instance={task_runtime.instance_id()}"
    assert want in docker.first("ps -a")
    assert want in docker.first("network ls")


def test_instance_id_differs_between_editions(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://u:p@h:1/life_graph")
    monkeypatch.setattr(settings, "edition", "prod")
    prod = task_runtime.instance_id()
    monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://u:p@h:1/life_graph_dev")
    monkeypatch.setattr(settings, "edition", "dev")
    assert task_runtime.instance_id() != prod


def test_a_bind_must_be_its_own_canonical_path(roots):
    wt = roots["worktree"]
    sneaky = f"{wt.parent}/../{wt.parent.name}/{wt.name}"  # resolves inside, mounts as given
    spec = SandboxSpec(name="x", image="img", binds=(Bind(sneaky, "/work"),))
    assert any("canonical" in v for v in sandbox.spec_violations(spec))


async def test_a_teardown_that_raises_does_not_mask_the_outcome(roots):
    async def boom(argv):
        raise RuntimeError("docker CLI vanished")

    docker = FakeDocker(**{"network rm": boom})
    out = await task_runtime.DockerTaskRuntime(docker).run(_req(roots))
    assert out.returncode == 0
    assert out.metadata["teardown"]["ok"] is False


# ── Periodic sweep (2026-11-19: a SIGKILLed worker left its proxy + network) ──


def test_docker_created_at_is_read_for_containers_and_networks():
    from datetime import datetime as dt

    now = dt(2026, 11, 19, 6, 51, 26, tzinfo=UTC)
    assert task_runtime._age_seconds("2026-11-19 06:41:26 +0000 UTC", now) == 600
    assert task_runtime._age_seconds("2026-11-19 06:41:26.380002525 +0000 UTC", now) == 600
    assert task_runtime._age_seconds("2026-11-19 12:11:26 +0530 IST", now) == 600
    assert task_runtime._age_seconds("", now) is None
    assert task_runtime._age_seconds("yesterday", now) is None


async def test_periodic_sweep_keeps_young_and_unknown_age_runtimes(roots, monkeypatch):
    dead = str(uuid.uuid4())
    listing = SandboxResult(
        0,
        f"lg-rt-old|{dead}|2026-11-19 06:00:00 +0000 UTC\n"
        f"lg-rt-young|{dead}|2026-11-19 06:59:00 +0000 UTC\n"
        f"lg-rt-unknown|{dead}|\n",
        "",
    )
    nets = SandboxResult(0, f"lg-rt-net-old|{dead}|2026-11-19 06:00:00.5 +0000 UTC\n", "")
    docker = FakeDocker(**{"ps -a": listing, "network ls": nets})
    fixed = datetime(2026, 11, 19, 7, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(
        task_runtime, "_age_seconds", lambda c, now=None, f=task_runtime._age_seconds: f(c, fixed)
    )

    report = await task_runtime.DockerTaskRuntime(docker).sweep(set(), min_age_seconds=300)

    assert report["containers"] == ["lg-rt-old"]
    assert report["networks"] == ["lg-rt-net-old"]
    assert "CreatedAt" in " ".join(docker.first("ps -a"))


async def test_sweep_orphans_periodic_mode_uses_the_age_floor_and_skips_event_expiry(monkeypatch):
    from life_graph.services.dev import task_events

    seen = {}

    class _Rows:
        def scalars(self):
            return self

        def all(self):
            return []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *_):
            return _Rows()

    async def fake_sweep(active, **kw):
        seen["kw"] = kw
        return {"containers": [], "networks": [], "credentials": 0, "errors": []}

    async def no_expire(*a, **k):
        raise AssertionError("the periodic pass must not expire events")

    monkeypatch.setattr(task_runtime.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(task_runtime.runtime, "sweep", fake_sweep)
    monkeypatch.setattr(task_events, "expire", no_expire)

    await task_runtime.sweep_orphans(lambda: _Session(), expire_events=False)
    assert seen["kw"] == {"min_age_seconds": task_runtime.PERIODIC_MIN_AGE_SECONDS}


# ── NO_PROXY: loopback, and only loopback, skips the egress proxy (2026-11-28) ──

_LOOPBACK = "localhost,127.0.0.1,::1"
_NAMES = {"container": "lg-rt-0123456789abcdef", "network": "lg-rt-net-0123456789abcdef",
          "proxy": "lg-rt-egress-0123456789abcdef"}  # fmt: skip


def _spec_env(roots, **kw) -> dict[str, str]:
    rt = task_runtime.DockerTaskRuntime(FakeDocker())
    return rt._driver_spec(_req(roots, **kw), _NAMES, {}).env


def test_a_proxied_driver_gets_exactly_the_loopback_no_proxy(roots):
    env = _spec_env(roots)
    assert env["HTTPS_PROXY"].startswith("http://lg-rt-egress-")
    assert env["NO_PROXY"] == _LOOPBACK
    assert env["no_proxy"] == _LOOPBACK


def test_no_proxy_means_no_no_proxy(roots):
    env = _spec_env(roots, egress_allowlist=())
    assert not {"HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "no_proxy"} & set(env)


def test_an_existing_no_proxy_is_merged_but_keeps_loopback_only(roots):
    env = _spec_env(
        roots,
        env={"NO_PROXY": "127.0.0.2, internal.corp,localhost", "no_proxy": "[::1],10.0.0.0/8"},
    )
    expected = "localhost,127.0.0.1,::1,127.0.0.2"
    assert env["NO_PROXY"] == env["no_proxy"] == expected


@pytest.mark.parametrize(
    ("existing", "expected"),
    [
        (None, _LOOPBACK),
        ("", _LOOPBACK),
        ("127.0.0.0/8", _LOOPBACK + ",127.0.0.0/8"),
        ("LOCALHOST,[::1],127.0.0.2", _LOOPBACK + ",127.0.0.2"),
        ("example.com,.corp,*,0.0.0.0,10.1.2.3,169.254.169.254", _LOOPBACK),
        ("127.0.0.0/7", _LOOPBACK),  # wider than loopback
    ],
)
def test_loopback_no_proxy_never_adds_a_non_loopback_host(existing, expected):
    assert sandbox.loopback_no_proxy(existing) == expected


def test_the_validator_accepts_the_proxy_env():
    env = sandbox.proxy_env("http://lg-rt-egress-0123456789abcdef:8080")
    assert env["NO_PROXY"] == env["no_proxy"] == _LOOPBACK
    assert sandbox._env_violations(env) == []


def test_setup_containers_get_the_loopback_no_proxy():
    egress = task_runtime.SetupEgress(
        container="lg-verify-setup-x", network="lg-rt-net-x",
        proxy_host="lg-rt-egress-x", proxy_port=8080, labels={},
    )  # fmt: skip
    args = sandbox._setup_net_args(egress, "node")
    env = [args[i + 1] for i, a in enumerate(args) if a == "-e"]
    assert f"NO_PROXY={_LOOPBACK}" in env and f"no_proxy={_LOOPBACK}" in env
    assert "HTTPS_PROXY=http://lg-rt-egress-x:8080" in env


@pytest.mark.parametrize(
    "path", ["docker/claude-driver/Dockerfile", "docker/verifier-node/Dockerfile"]
)
def test_the_agent_and_node_images_install_curl(path):
    text = (Path(__file__).resolve().parents[2] / path).read_text()
    install = next(line for line in text.splitlines() if "apt-get install" in line)
    words = install.split()
    assert "--no-install-recommends" in words
    assert "curl" in words and "ca-certificates" in words
    assert "rm -rf /var/lib/apt/lists/*" in text
