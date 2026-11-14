"""The errand sandbox's isolation guarantees (life_graph/services/sandbox.py).

An errand runs code and renders pages the owner did not write, so the whole
value of the sandbox is the list of things it *cannot* do. These tests are
that list, written twice over:

* against :func:`~life_graph.services.sandbox.validate_spec`, for the specs
  the application builds at run time, and
* against ``compose.sandbox.yaml`` and the two Dockerfiles, for the stack a
  human brings up by hand.

Both paths must hold. A policy that only the Python side enforces is a
policy that stops being true the moment someone runs ``docker compose up``.

Nothing here needs docker: the manager takes an injectable runner and every
test passes a fake one.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml

from life_graph.config import settings
from life_graph.services import sandbox as sb

REPO_ROOT = Path(__file__).resolve().parents[2]


# ── Helpers ──────────────────────────────────────────────────


def tweak(spec: sb.SandboxSpec, **changes) -> sb.SandboxSpec:
    """*spec* with fields replaced — how a caller would loosen one."""
    return dataclasses.replace(spec, **changes)


def reasons(spec: sb.SandboxSpec) -> str:
    return " | ".join(sb.spec_violations(spec))


class FakeRunner:
    """Stands in for the docker CLI. Records argv, replays canned results."""

    def __init__(self, *results: sb.SandboxResult) -> None:
        self.results = list(results)
        self.calls: list[list[str]] = []

    async def __call__(self, argv: list[str], *, timeout: int) -> sb.SandboxResult:
        self.calls.append(list(argv))
        if self.results:
            return self.results.pop(0)
        return sb.SandboxResult(returncode=0, stdout="", stderr="")

    def argv(self, index: int = 0) -> list[str]:
        return self.calls[index]


def ok(stdout: str = "") -> sb.SandboxResult:
    return sb.SandboxResult(returncode=0, stdout=stdout, stderr="")


# ── The safe defaults are actually safe ──────────────────────


def test_builders_produce_specs_that_pass_policy():
    for spec in (sb.browser_spec("lg-b1"), sb.workspace_spec("lg-w1", browser="lg-b1")):
        assert sb.spec_violations(spec) == [], spec.name
        assert sb.validate_spec(spec) is spec


def test_a_bare_spec_is_locked_down_without_being_asked():
    """The defaults, not the arguments, are what make a spec safe."""
    spec = sb.SandboxSpec(name="lg-bare", image=sb.WORKSPACE_IMAGE)
    assert sb.spec_violations(spec) == []
    assert spec.privileged is False
    assert spec.read_only_root is True
    assert spec.cap_drop == ("ALL",)
    assert spec.cap_add == ()
    assert spec.mounts == ()
    assert spec.network == sb.SANDBOX_NETWORK
    assert spec.user.split(":")[0] not in ("0", "root", "")


def test_builders_refuse_to_return_an_unsafe_spec():
    with pytest.raises(sb.SandboxPolicyError):
        sb.workspace_spec("lg-w2", image="")
    with pytest.raises(sb.SandboxPolicyError):
        sb.browser_spec("lg-b2", cpus="99")


# ── Ways out of the box ──────────────────────────────────────


@pytest.mark.parametrize(
    "mount",
    [
        "/etc/passwd:/etc/passwd:ro",
        "/home/raja/projects/life-graph:/work",
        "./:/work",
        "../secrets:/secrets",
        "~/.config/life-graph:/cfg:ro",
        "$HOME/.ssh:/ssh:ro",
        "C:\\Users\\raja:/work",
    ],
)
def test_host_mounts_are_rejected(mount):
    spec = tweak(sb.workspace_spec("lg-w3"), mounts=(mount,))
    assert "host path" in reasons(spec) or "named one" in reasons(spec)
    with pytest.raises(sb.SandboxPolicyError):
        sb.validate_spec(spec)


@pytest.mark.parametrize(
    "mount",
    [
        "/var/run/docker.sock:/var/run/docker.sock",
        "/run/docker.sock:/run/docker.sock:ro",
        "/run/podman/podman.sock:/run/podman/podman.sock",
        "/run/containerd/containerd.sock:/x",
    ],
)
def test_the_container_runtime_socket_is_rejected(mount):
    spec = tweak(sb.workspace_spec("lg-w4"), mounts=(mount,))
    assert "runtime socket" in reasons(spec)
    with pytest.raises(sb.SandboxPolicyError):
        sb.validate_spec(spec)


def test_a_named_volume_is_the_only_mount_that_passes():
    assert (
        sb.spec_violations(tweak(sb.workspace_spec("lg-w5"), mounts=("lg-cache:/cache:ro",))) == []
    )


def test_privileged_mode_is_rejected():
    assert "privileged" in reasons(tweak(sb.workspace_spec("lg-w6"), privileged=True))


@pytest.mark.parametrize("mode", ["host", "bridge", "default", "container:life_graph_app"])
def test_host_and_borrowed_networking_are_rejected(mode):
    spec = tweak(sb.workspace_spec("lg-w7"), network_mode=mode)
    assert "leaves the internal sandbox network" in reasons(spec)


def test_a_network_other_than_the_internal_one_is_rejected():
    spec = tweak(sb.workspace_spec("lg-w8"), network="life_graph_default")
    assert sb.SANDBOX_NETWORK in reasons(spec)


def test_no_network_at_all_is_allowed_being_stricter():
    spec = tweak(sb.workspace_spec("lg-w9"), network_mode="none", network="")
    assert sb.spec_violations(spec) == []


# ── Restrictions that must stay switched on ──────────────────


def test_a_writable_root_filesystem_is_rejected():
    assert "read-only" in reasons(tweak(sb.workspace_spec("lg-wa"), read_only_root=False))


def test_capabilities_must_be_dropped_and_not_added_back():
    assert "cap_drop ALL" in reasons(tweak(sb.workspace_spec("lg-wb"), cap_drop=("NET_RAW",)))
    assert "added back" in reasons(tweak(sb.workspace_spec("lg-wc"), cap_add=("SYS_ADMIN",)))


def test_no_new_privileges_is_required_and_unconfined_is_rejected():
    assert "no-new-privileges" in reasons(tweak(sb.workspace_spec("lg-wd"), security_opt=()))
    loosened = tweak(
        sb.workspace_spec("lg-we"),
        security_opt=("no-new-privileges:true", "seccomp=unconfined"),
    )
    assert "switches a protection off" in reasons(loosened)


@pytest.mark.parametrize("user", ["0:0", "root", "0", ""])
def test_running_as_root_is_rejected(user):
    assert "as root" in reasons(tweak(sb.workspace_spec("lg-wf"), user=user))


@pytest.mark.parametrize(
    ("field", "value", "needle"),
    [
        ("pids_limit", 0, "pids_limit"),
        ("pids_limit", 100000, "pids_limit"),
        ("memory", "", "memory"),
        ("memory", "lots", "memory"),
        ("cpus", "", "cpus"),
        ("cpus", "0", "cpus"),
    ],
)
def test_resource_ceilings_are_required(field, value, needle):
    assert needle in reasons(tweak(sb.workspace_spec("lg-wg"), **{field: value}))


def test_a_setuid_tmpfs_is_rejected():
    spec = tweak(sb.workspace_spec("lg-wh"), tmpfs=("/tmp:rw,suid,size=64m",))
    assert "setuid" in reasons(spec)


def test_tmpfs_cannot_shadow_the_root_filesystem():
    assert "absolute path" in reasons(tweak(sb.workspace_spec("lg-wi"), tmpfs=("/:rw",)))


# ── No credentials reach the sandbox ─────────────────────────


@pytest.mark.parametrize(
    "name",
    [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "api_key",
        "GITHUB_TOKEN",
        "DB_PASSWORD",
        "CLIENT_SECRET",
        "AWS_SESSION_TOKEN",
        "SESSION_COOKIE",
        "VAULT_PRIVATE_KEY",
        "GOOGLE_AUTH_JSON",
    ],
)
def test_credential_shaped_env_names_are_rejected(name):
    spec = tweak(sb.workspace_spec("lg-wj"), env={**sb.workspace_spec("lg-wj").env, name: "x"})
    assert "credential-shaped" in reasons(spec)


@pytest.mark.parametrize(
    "name",
    ["LIFE_GRAPH_DATABASE_URL", "LIFE_GRAPH_PROFILE", "life_graph_redis_url"],
)
def test_app_configuration_is_rejected_even_when_it_is_not_secret(name):
    spec = tweak(sb.workspace_spec("lg-wk"), env={name: "postgresql://x/y"})
    assert "app configuration" in reasons(spec)


@pytest.mark.parametrize(
    "value",
    [
        "sk-ant-api03-aaaaaaaaaaaaaaaaaaaa",
        "sk-or-v1-aaaaaaaaaaaaaaaaaaaaaaaa",
        "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "xoxb-1111-2222-aaaaaaaaaaaa",
        "AIzaSyAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "hf_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "tvly-aaaaaaaaaaaaaaaaaaaaaaaa",
    ],
)
def test_key_shaped_values_are_rejected_under_an_innocent_name(value):
    spec = tweak(sb.workspace_spec("lg-wl"), env={"HELPER_ENDPOINT": value})
    assert "shaped like a provider key" in reasons(spec)


def test_a_value_configured_on_this_install_is_rejected_whatever_it_looks_like(monkeypatch):
    """The decisive check: the actual configured key, under a bland name."""
    key = "9f3c-not-key-shaped-at-all-71bd"
    monkeypatch.setattr(settings, "openrouter_api_key", key)
    spec = tweak(sb.workspace_spec("lg-wm"), env={"HELPER_ENDPOINT": key})
    assert "configured credential from settings" in reasons(spec)


def test_settings_secrets_are_discovered_by_field_name_not_a_hand_kept_list(monkeypatch):
    """A provider added to config.py tomorrow is covered without edits here."""
    monkeypatch.setattr(settings, "groq_api_key", "groq-secret-value-01")
    monkeypatch.setattr(settings, "telegram_bot_token", "telegram-secret-02")
    monkeypatch.setattr(settings, "watcher_smtp_password", "smtp-secret-03")
    monkeypatch.setattr(settings, "service_api_keys", "svc-key-one-04,svc-key-two-05")
    found = sb._settings_secret_values()
    for value in (
        "groq-secret-value-01",
        "telegram-secret-02",
        "smtp-secret-03",
        "svc-key-one-04",
        "svc-key-two-05",
    ):
        assert value in found


def test_the_runtime_socket_cannot_be_smuggled_through_the_environment():
    spec = tweak(sb.workspace_spec("lg-wn"), env={"HELPER_ENDPOINT": "unix:///var/run/docker.sock"})
    assert "runtime socket" in reasons(spec)


def test_benign_environment_is_left_alone():
    env = {"HOME": "/tmp", "TZ": "UTC", "LANG": "C.UTF-8", "SANDBOX_ROLE": "workspace"}
    assert sb.spec_violations(tweak(sb.workspace_spec("lg-wo"), env=env)) == []


def test_every_violation_is_reported_at_once():
    spec = tweak(
        sb.workspace_spec("lg-wp"),
        privileged=True,
        read_only_root=False,
        network_mode="host",
        mounts=("/var/run/docker.sock:/var/run/docker.sock",),
        env={"OPENAI_API_KEY": "sk-aaaaaaaaaaaaaaaaaaaa"},
    )
    with pytest.raises(sb.SandboxPolicyError) as caught:
        sb.validate_spec(spec)
    assert len(caught.value.violations) >= 5
    assert "lg-wp" in str(caught.value)


# ── The argv actually carries the restrictions ───────────────


def test_docker_run_argv_carries_every_restriction():
    argv = sb.docker_run_argv(sb.browser_spec("lg-b3"))
    joined = " ".join(argv)
    assert argv[:2] == ["docker", "run"]
    for flag in ("--read-only", "--init", "--detach"):
        assert flag in argv
    assert "--cap-drop ALL" in joined
    assert "--security-opt no-new-privileges:true" in joined
    assert f"--network {sb.SANDBOX_NETWORK}" in joined
    assert "--memory 1g" in joined and "--memory-swap 1g" in joined
    assert "--cpus 1.0" in joined and "--pids-limit 512" in joined
    assert "--user 1000:1000" in joined
    # No bind mount, no socket, no privilege, no published port.
    assert "-v" not in argv
    assert "--privileged" not in argv
    assert "-p" not in argv and "--publish" not in argv
    assert "docker.sock" not in joined
    assert sb.APP_ENV_PREFIX not in joined


def test_docker_run_argv_validates_before_building():
    spec = tweak(sb.workspace_spec("lg-wq"), mounts=("/:/host",))
    with pytest.raises(sb.SandboxPolicyError):
        sb.docker_run_argv(spec)


def test_undetached_runs_clean_up_after_themselves():
    argv = sb.docker_run_argv(sb.workspace_spec("lg-wr"), detach=False)
    assert "--rm" in argv and "--detach" not in argv


# ── Lifecycle, with no docker anywhere ───────────────────────


async def test_start_runs_the_validated_argv_and_returns_the_container_id():
    runner = FakeRunner(ok("c0ffee1234567890\n"))
    manager = sb.SandboxManager(runner)
    spec = sb.workspace_spec("lg-ws")
    assert await manager.start(spec) == "c0ffee1234567890"
    assert runner.argv(0) == sb.docker_run_argv(spec)


async def test_start_refuses_an_unsafe_spec_without_touching_the_runtime():
    runner = FakeRunner()
    spec = tweak(sb.workspace_spec("lg-wt"), privileged=True)
    with pytest.raises(sb.SandboxPolicyError):
        await sb.SandboxManager(runner).start(spec)
    assert runner.calls == []


async def test_a_runtime_that_refuses_is_reported_as_unavailable():
    runner = FakeRunner(sb.SandboxResult(returncode=125, stdout="", stderr="no such image"))
    with pytest.raises(sb.SandboxUnavailableError, match="no such image"):
        await sb.SandboxManager(runner).start(sb.workspace_spec("lg-wu"))


async def test_stop_stops_then_removes():
    runner = FakeRunner(ok(), ok())
    assert await sb.SandboxManager(runner).stop("lg-wv") is True
    assert runner.argv(0)[:3] == ["docker", "stop", "--time"]
    assert runner.argv(1)[:4] == ["docker", "rm", "--force", "--volumes"]


async def test_stop_is_satisfied_when_the_sandbox_is_already_gone():
    runner = FakeRunner(
        sb.SandboxResult(returncode=1, stdout="", stderr="Error: No such container: lg-ww"),
        sb.SandboxResult(returncode=1, stdout="", stderr="Error: No such container: lg-ww"),
    )
    assert await sb.SandboxManager(runner).stop("lg-ww") is True


async def test_status_reports_the_runtime_state_and_absence():
    assert await sb.SandboxManager(FakeRunner(ok("running\n"))).status("lg-wx") == "running"
    assert await sb.SandboxManager(FakeRunner(ok("exited\n"))).status("lg-wy") == "exited"
    gone = FakeRunner(sb.SandboxResult(returncode=1, stdout="", stderr="No such object"))
    assert await sb.SandboxManager(gone).status("lg-wz") == "absent"


@pytest.mark.parametrize("name", ["lg w1", "-rm", "lg;rm -rf /", "../x", ""])
async def test_lifecycle_calls_reject_an_injectable_container_name(name):
    manager = sb.SandboxManager(FakeRunner())
    with pytest.raises(sb.SandboxPolicyError):
        await manager.stop(name)
    with pytest.raises(sb.SandboxPolicyError):
        await manager.status(name)


# ── The same invariants, on the real compose file ────────────


@pytest.fixture(scope="module")
def compose() -> dict:
    path = REPO_ROOT / sb.SANDBOX_COMPOSE_FILE
    assert path.is_file(), f"{path} is missing"
    return yaml.safe_load(path.read_text())


@pytest.fixture(scope="module")
def compose_services(compose) -> dict:
    services = compose["services"]
    assert set(services) == {"browser", "workspace"}
    return services


def test_the_module_and_the_compose_file_agree():
    """The helper the application would call, run on the shipped file."""
    assert sb.compose_violations() == {}
    assert sb.compose_path() == REPO_ROOT / sb.SANDBOX_COMPOSE_FILE


def test_compose_declares_no_mounts_at_all(compose, compose_services):
    assert "volumes" not in compose, "no named volumes: sandbox state must not outlive it"
    for name, service in compose_services.items():
        assert not service.get("volumes"), f"{name} declares a mount"
        assert not service.get("volumes_from"), f"{name} inherits mounts"
        assert not service.get("devices"), f"{name} maps a host device"


def test_compose_mentions_no_container_runtime_socket():
    raw = (REPO_ROOT / sb.SANDBOX_COMPOSE_FILE).read_text()
    for socket in ("/var/run/docker.sock", "/run/podman", "podman.sock", "containerd.sock"):
        assert socket not in raw
    # The comments talk *about* the socket; only a mapping would be a problem.
    assert "docker.sock:" not in raw


def test_compose_services_are_hardened(compose_services):
    for name, service in compose_services.items():
        assert service.get("read_only") is True, f"{name} has a writable root fs"
        assert service.get("cap_drop") == ["ALL"], f"{name} keeps capabilities"
        assert not service.get("cap_add"), f"{name} adds capabilities back"
        assert "no-new-privileges:true" in service.get("security_opt", []), name
        assert service.get("privileged") in (None, False), name
        assert service.get("user"), f"{name} does not pin a user"
        assert service["user"].split(":")[0] not in ("0", "root"), f"{name} runs as root"
        assert service.get("init") is True, f"{name} has no init to reap processes"


def test_compose_services_have_resource_ceilings(compose_services):
    for name, service in compose_services.items():
        assert service.get("mem_limit"), f"{name} has no memory ceiling"
        assert service.get("memswap_limit") == service.get("mem_limit"), (
            f"{name} may swap past its memory ceiling"
        )
        assert service.get("cpus"), f"{name} has no cpu ceiling"
        assert 0 < int(service.get("pids_limit", 0)) <= 4096, f"{name} has no pid ceiling"


def test_compose_writable_space_is_tmpfs_only(compose_services):
    for name, service in compose_services.items():
        entries = service.get("tmpfs") or []
        assert entries, f"{name} has no writable scratch space"
        for entry in entries:
            target, _, options = str(entry).partition(":")
            assert target.startswith("/") and target != "/", f"{name}: {entry}"
            assert "nosuid" in options and "nodev" in options, f"{name}: {entry} is not hardened"


def test_compose_scratch_space_is_writable_by_the_user_it_pins(compose_services):
    """A tmpfs is mounted root-owned 0755 unless told otherwise.

    Without uid/gid the hardening is self-defeating: the pinned non-root user
    cannot write to its own work directory, so the sandbox looks fine and
    every errand fails. /tmp and /dev/shm come from the image already
    world-writable, so only the extra mounts need the ownership pinned.
    """
    for name, service in compose_services.items():
        uid = service["user"].split(":")[0]
        for entry in service.get("tmpfs") or []:
            target, _, options = str(entry).partition(":")
            if target in ("/tmp", "/dev/shm"):
                assert "mode=1777" in options, f"{name}: {entry}"
                continue
            assert f"uid={uid}" in options, f"{name}: {entry} is not writable by uid {uid}"
            assert f"gid={uid}" in options, f"{name}: {entry}"


def test_the_workspace_spec_pins_the_same_ownership():
    spec = sb.workspace_spec("lg-w0")
    uid = spec.user.split(":")[0]
    work = next(e for e in spec.tmpfs if e.startswith("/work:"))
    assert f"uid={uid}" in work and f"gid={uid}" in work


def test_compose_networking_is_internal_only_and_unpublished(compose, compose_services):
    networks = compose["networks"]
    assert set(networks) == {"sandbox_internal"}
    assert networks["sandbox_internal"]["internal"] is True
    assert networks["sandbox_internal"]["name"] == sb.SANDBOX_NETWORK
    for name, service in compose_services.items():
        assert service.get("networks") == ["sandbox_internal"], name
        assert "ports" not in service, f"{name} publishes a port to the host"
        assert service.get("network_mode") is None, name
        for shared in ("pid", "ipc", "uts"):
            assert service.get(shared) != "host", f"{name} shares the host {shared} namespace"


def test_compose_passes_no_secret_and_no_app_configuration(compose_services):
    configured = sb._settings_secret_values()
    for name, service in compose_services.items():
        assert "env_file" not in service, f"{name} reads an env file"
        assert "secrets" not in service, f"{name} mounts a compose secret"
        env = sb._compose_env(service.get("environment"))
        for key, value in env.items():
            assert not key.upper().startswith(sb.APP_ENV_PREFIX), f"{name}: {key}"
            assert not sb._SECRET_NAME.search(key), f"{name}: {key} is credential-shaped"
            assert not sb._KEY_SHAPED.search(value), f"{name}: {key} holds a key-shaped value"
            assert value.strip() not in configured, f"{name}: {key} holds a configured secret"


def test_the_browser_endpoint_the_workspace_is_given_is_internal(compose_services):
    url = sb._compose_env(compose_services["workspace"]["environment"])["SANDBOX_BROWSER_WS_URL"]
    assert url == f"ws://browser:{sb.BROWSER_WS_PORT}/"
    assert compose_services["browser"]["expose"] == [str(sb.BROWSER_WS_PORT)]
    assert sb.workspace_spec("lg-wn1", browser="lg-b4").env["SANDBOX_BROWSER_WS_URL"] == (
        f"ws://lg-b4:{sb.BROWSER_WS_PORT}/"
    )


# ── The images themselves ────────────────────────────────────


@pytest.mark.parametrize(
    ("dockerfile", "expected_user"),
    [("Dockerfile.browser", "pwuser"), ("Dockerfile.workspace", "65534:65534")],
)
def test_the_sandbox_images_end_up_non_root(dockerfile, expected_user):
    path = REPO_ROOT / dockerfile
    assert path.is_file(), f"{path} is missing"
    lines = [ln.strip() for ln in path.read_text().splitlines() if ln.strip().startswith("USER ")]
    assert lines, f"{dockerfile} never drops root"
    assert lines[-1] == f"USER {expected_user}", f"{dockerfile}: {lines[-1]}"


@pytest.mark.parametrize("dockerfile", ["Dockerfile.browser", "Dockerfile.workspace"])
def test_the_sandbox_images_bake_in_no_credentials(dockerfile):
    """An ARG or ENV naming a credential would ship inside the image layer."""
    for line in (REPO_ROOT / dockerfile).read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith(("ENV ", "ARG ")):
            continue
        declared = stripped.split(maxsplit=1)[1].split("=")[0].strip().rstrip("\\").strip()
        assert not sb._SECRET_NAME.search(declared), f"{dockerfile}: {stripped}"
        assert not declared.upper().startswith(sb.APP_ENV_PREFIX), f"{dockerfile}: {stripped}"


@pytest.mark.parametrize("dockerfile", ["Dockerfile.browser", "Dockerfile.workspace"])
def test_the_sandbox_images_copy_nothing_from_the_repository(dockerfile):
    """No application source in a sandbox image: it has no business reading it."""
    for line in (REPO_ROOT / dockerfile).read_text().splitlines():
        assert not line.strip().startswith(("COPY ", "ADD ")), line.strip()
