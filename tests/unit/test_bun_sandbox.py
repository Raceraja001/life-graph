"""The sandbox side of the Bun toolchain (race-app 2026-11-28-bun-sandbox, build plan 1-5, 7).

Without docker: workspace-glob expansion, the setup's argv and key, the ready
check before publish, the mount plan and its git-ignore guard, the check's
argv, the bind validator's descendant rule, cache GC, the manifest scan and
the image pins. The real-docker run is test_bun_sandbox_smoke.py (opt-in).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from life_graph.config import settings
from life_graph.services.dev import sandbox, sandbox_bun, sandbox_deps, setup_guard
from life_graph.services.dev import verifiers as v
from life_graph.services.dev.sandbox import Bind
from life_graph.services.dev.sandbox_deps import DepsMount, DepsPlan, DepsUnavailableError

REPO = Path(__file__).resolve().parents[2]
KEY = "0123456789abcdef01234567"


def _write(root: Path, rel: str, data: dict | str) -> Path:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(data if isinstance(data, str) else json.dumps(data))
    return f


@pytest.fixture
def repo(tmp_path):
    """A Bun workspace like race-app's: apps/*, packages/*, services/*."""
    root = tmp_path / "repo"
    _write(
        root, "package.json", {"name": "r", "workspaces": ["apps/*", "packages/*", "services/*"]}
    )
    _write(root, "bun.lock", '{"lockfileVersion": 1, "workspaces": {}, "packages": {},}')
    _write(root, ".gitignore", "node_modules/\n")
    _write(root, "apps/web/package.json", {"name": "web", "dependencies": {"react": "^19"}})
    _write(root, "packages/shared-types/package.json", {"name": "st", "dependencies": {"zod": "3"}})
    _write(root, "packages/plugin-sdk/package.json", {"name": "sdk"})
    _write(root, "services/gateway/package.json", {"name": "gw", "dependencies": {"hono": "4"}})
    return root


@pytest.fixture
def docker_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))
    monkeypatch.setattr(sandbox, "_setup_egress", _fake_setup_egress)
    return tmp_path / "envs"


@contextlib.asynccontextmanager
async def _fake_setup_egress(toolchain, allow):
    from life_graph.services.dev.task_runtime import SetupEgress

    _fake_setup_egress.calls.append((toolchain, allow))  # type: ignore[attr-defined]
    yield SetupEgress("lg-verify-setup-test", "lg-rt-net-test", "lg-rt-egress-test", 8080, {})


_fake_setup_egress.calls = []  # type: ignore[attr-defined]


# ── 3. Workspace globs → manifests ────────────────────────────


def test_workspaces_expand_to_every_package_dir(repo):
    assert sandbox_bun.expand_workspaces(repo) == (
        "apps/web",
        "packages/plugin-sdk",
        "packages/shared-types",
        "services/gateway",
    )


def test_the_object_form_and_exclusions_are_understood(tmp_path):
    _write(tmp_path, "package.json", {"workspaces": {"packages": ["pkgs/*", "!pkgs/skip"]}})
    _write(tmp_path, "pkgs/a/package.json", {})
    _write(tmp_path, "pkgs/skip/package.json", {})
    (tmp_path / "pkgs" / "no-manifest").mkdir()
    _write(tmp_path, "pkgs/a/node_modules/x/package.json", {})
    assert sandbox_bun.expand_workspaces(tmp_path) == ("pkgs/a",)


def test_no_workspaces_is_just_the_root(tmp_path):
    _write(tmp_path, "package.json", {"name": "single"})
    assert sandbox_bun.expand_workspaces(tmp_path) == ()
    assert sandbox_bun.manifests(tmp_path, ()) == ("package.json", "bun.lock", "bun.lockb")


@pytest.mark.parametrize(
    "glob",
    ["../outside/*", "/etc/*", "apps/../../x", "~/x", "$HOME/x", "apps\\..\\x", "", "./"],
)
def test_globs_that_leave_the_repo_are_refused(tmp_path, glob):
    _write(tmp_path, "package.json", {"workspaces": [glob]})
    with pytest.raises(sandbox_bun.BunWorkspaceError):
        sandbox_bun.expand_workspaces(tmp_path)


def test_a_symlinked_workspace_dir_is_refused(tmp_path):
    outside = tmp_path / "outside"
    _write(outside, "evil/package.json", {"name": "evil"})
    root = tmp_path / "repo"
    _write(root, "package.json", {"workspaces": ["packages/*"]})
    (root / "packages").mkdir()
    (root / "packages" / "evil").symlink_to(outside / "evil")
    with pytest.raises(sandbox_bun.BunWorkspaceError, match="symlink"):
        sandbox_bun.expand_workspaces(root)


def test_a_symlinked_root_manifest_is_refused(tmp_path):
    real = _write(tmp_path, "elsewhere.json", {"workspaces": []})
    root = tmp_path / "repo"
    root.mkdir()
    (root / "package.json").symlink_to(real)
    with pytest.raises(sandbox_bun.BunWorkspaceError):
        sandbox_bun.expand_workspaces(root)


@pytest.mark.parametrize("bad", [{"workspaces": "apps/*"}, {"workspaces": [1]}, "[]"])
def test_malformed_workspaces_are_refused(tmp_path, bad):
    _write(tmp_path, "package.json", bad)
    with pytest.raises(sandbox_bun.BunWorkspaceError):
        sandbox_bun.expand_workspaces(tmp_path)


def test_too_many_workspaces_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox_bun, "MAX_WORKSPACES", 2)
    _write(tmp_path, "package.json", {"workspaces": ["p/*"]})
    for name in "abc":
        _write(tmp_path, f"p/{name}/package.json", {})
    with pytest.raises(sandbox_bun.BunWorkspaceError, match="more than 2"):
        sandbox_bun.expand_workspaces(tmp_path)


def test_manifests_are_copied_at_their_paths_and_symlinks_are_not(repo, tmp_path):
    (repo / "bun.lockb").symlink_to(repo / "bun.lock")
    names = sandbox_bun.manifests(repo, sandbox_bun.expand_workspaces(repo))
    dest = tmp_path / "dest"
    dest.mkdir()
    sandbox_bun.copy_manifests(repo, names, dest)
    got = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert got == [
        "apps/web/package.json",
        "bun.lock",
        "package.json",
        "packages/plugin-sdk/package.json",
        "packages/shared-types/package.json",
        "services/gateway/package.json",
    ]


def test_the_key_tracks_every_workspace_manifest(repo):
    names = sandbox_bun.manifests(repo, sandbox_bun.expand_workspaces(repo))
    before = sandbox._env_key(repo, "img", "cmd", names)
    _write(repo, "services/gateway/package.json", {"name": "gw", "dependencies": {"hono": "5"}})
    assert sandbox._env_key(repo, "img", "cmd", names) != before


# ── 3. prepare_bun_env: argv, key, ready check, publish ───────


def _installer(*, dirs=("node_modules",), rc=0, version="1.4.5", runs=None):
    """A fake docker CLI: the image exists; setup "installs" *dirs* into /deps."""

    async def fake_exec(argv, timeout, container=None, env=None):
        if argv[:3] == ["docker", "image", "inspect"]:
            return sandbox.SandboxResult(0, "sha256:img\n", "")
        if runs is not None:
            runs.append(argv)
        deps = next(a.split(":")[0] for a in argv if a.endswith(":/deps"))
        for d in dirs:
            (Path(deps) / d).mkdir(parents=True, exist_ok=True)
        out = f"installed\n{sandbox._BUN_READY_MARK} {version}\n" if version else "installed\n"
        return sandbox.SandboxResult(rc, out, "" if rc == 0 else "error: lockfile had changes")

    return fake_exec


ALL_DIRS = (
    "node_modules",
    "apps/web/node_modules",
    "packages/shared-types/node_modules",
    "services/gateway/node_modules",
)


async def test_setup_installs_from_manifests_only_without_scripts(docker_mode, repo, monkeypatch):
    runs: list = []
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=ALL_DIRS, runs=runs))
    _fake_setup_egress.calls.clear()  # type: ignore[attr-defined]
    env = await sandbox.prepare_bun_env(repo)
    assert env.parent == docker_mode and re.fullmatch(r"bun-[0-9a-f]{24}", env.name)
    (argv,) = runs
    joined = " ".join(argv)
    assert f"{repo}:" not in joined  # the setup never sees the worktree
    assert argv[argv.index("--network") + 1] == "lg-rt-net-test"
    assert "HTTPS_PROXY=http://lg-rt-egress-test:8080" in argv
    assert "npm_config_ignore_scripts=true" in argv
    assert "BUN_INSTALL_CACHE_DIR=/tmp/.bun" in argv
    assert settings.verifier_sandbox_node_image in argv
    assert argv[-1].startswith("set -e; bun install --frozen-lockfile --ignore-scripts;")
    assert _fake_setup_egress.calls == [("bun", None)]  # type: ignore[attr-defined]
    assert (env / "apps/web/package.json").is_file()  # copied at its relative path
    assert setup_guard.egress_hosts("bun", None) == ("registry.npmjs.org",)


async def test_a_ready_env_is_reused(docker_mode, repo, monkeypatch):
    runs: list = []
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=ALL_DIRS, runs=runs))
    first = await sandbox.prepare_bun_env(repo)
    second = await sandbox.prepare_bun_env(repo)
    assert first == second and len(runs) == 1


async def test_concurrent_setups_install_once(docker_mode, repo, monkeypatch):
    runs: list = []
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=ALL_DIRS, runs=runs))
    a, b = await asyncio.gather(sandbox.prepare_bun_env(repo), sandbox.prepare_bun_env(repo))
    assert a == b and len(runs) == 1


async def test_a_custom_setup_still_runs_no_scripts_unless_allowed(docker_mode, repo, monkeypatch):
    runs: list = []
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=ALL_DIRS, runs=runs))
    plain = await sandbox.prepare_bun_env(repo, "bun install")
    assert "npm_config_ignore_scripts=true" in runs[-1]
    allowed = await sandbox.prepare_bun_env(repo, "bun install", allow=["scripts"])
    assert "npm_config_ignore_scripts=true" not in runs[-1]
    assert plain != allowed  # the scripts decision is part of the key


@pytest.mark.parametrize(
    ("dirs", "version", "why"),
    [
        ((), "1.4.5", "no root node_modules"),
        (ALL_DIRS, None, "bun --version"),
        (("node_modules", "apps/web/node_modules"), "1.4.5", "services/gateway/node_modules"),
    ],
)
async def test_an_env_that_is_not_ready_is_never_published(
    docker_mode, repo, monkeypatch, dirs, version, why
):
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=dirs, version=version))
    with pytest.raises(sandbox.SandboxUnavailableError, match="not ready") as exc:
        await sandbox.prepare_bun_env(repo)
    assert why in str(exc.value)
    assert [p.name for p in docker_mode.iterdir()] == []


def test_a_hoisted_install_is_ready_when_the_root_has_the_deps(tmp_path):
    env = tmp_path / "env"
    _write(env, "apps/web/package.json", {"dependencies": {"react": "1", "x": "workspace:*"}})
    (env / "node_modules" / "react").mkdir(parents=True)
    assert sandbox_bun.ready_problems(env, ("apps/web",), "1.4.5") == []


async def test_a_failed_install_publishes_nothing(docker_mode, repo, monkeypatch):
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=ALL_DIRS, rc=1))
    with pytest.raises(sandbox.SandboxUnavailableError, match="lockfile had changes"):
        await sandbox.prepare_bun_env(repo)
    assert list(docker_mode.iterdir()) == []


async def test_no_lockfile_is_refused_before_docker(docker_mode, repo, monkeypatch):
    (repo / "bun.lock").unlink()
    monkeypatch.setattr(sandbox, "_exec", _installer(runs=(runs := [])))
    with pytest.raises(sandbox.SandboxUnavailableError, match="no bun.lock"):
        await sandbox.prepare_bun_env(repo)
    assert runs == []


async def test_refused_manifests_never_reach_setup(docker_mode, repo, monkeypatch):
    _write(repo, "apps/web/package.json", {"dependencies": {"x": "github:evil/x"}})
    monkeypatch.setattr(sandbox, "_exec", _installer(runs=(runs := [])))
    with pytest.raises(setup_guard.SetupRefusedError, match="apps/web/package.json"):
        await sandbox.prepare_bun_env(repo)
    assert runs == []


# ── setup_guard for bun ───────────────────────────────────────


def _lock(packages: dict) -> str:
    return json.dumps({"lockfileVersion": 1, "workspaces": {}, "packages": packages}) + "\n"


@pytest.mark.parametrize(
    ("entry", "needle"),
    [
        (["x@https://evil.example/x.tgz", {}, ""], "evil.example"),
        (["x@github:evil/x#abc", {}, "x-abc"], "github.com"),
        (["x@1.0.0", "https://evil-registry.example/", {}, "sha512-"], "evil-registry"),
        (["x@file:../../outside", {}], "outside the worktree"),
    ],
)
def test_bun_lock_entries_from_elsewhere_are_refused(repo, entry, needle):
    _write(repo, "bun.lock", _lock({"x": entry}))
    found = setup_guard.scan(repo, "bun", None, manifests=("package.json", "bun.lock"))
    assert any(needle in f for f in found), found


def test_registry_and_workspace_lock_entries_are_clean(repo):
    _write(
        repo,
        "bun.lock",
        _lock(
            {
                "zod": ["zod@3.24.2", "", {}, "sha512-abc"],
                "@race/st": ["@race/st@workspace:packages/shared-types"],
                "@scope/x": ["@scope/x@1.0.0-beta.1", "", {}, "sha512-def"],
            }
        ),
    )
    assert setup_guard.scan(repo, "bun", None, manifests=("package.json", "bun.lock")) == []


def test_race_app_style_lockfile_with_trailing_commas_parses(repo):
    _write(
        repo,
        "bun.lock",
        '{\n  "lockfileVersion": 1,\n  "workspaces": {\n    "": {\n      "name": "r",\n    },\n'
        '  },\n  "packages": {\n    "a": ["a@1.0.0", "", {}, "sha512-x,]"],\n  },\n}\n',
    )
    assert setup_guard.scan(repo, "bun", None, manifests=("package.json", "bun.lock")) == []


def test_a_binary_lockfile_alone_is_refused(repo):
    (repo / "bun.lock").unlink()
    (repo / "bun.lockb").write_bytes(b"\x00bun")
    found = setup_guard.scan(repo, "bun", None, manifests=("package.json", "bun.lockb"))
    assert any("binary lockfile" in f for f in found)


def test_the_scripts_token_is_not_a_host():
    assert setup_guard.parse_allow(["scripts", "example.com"]) == (
        frozenset({"example.com"}),
        False,
    )
    assert setup_guard.allows_scripts("scripts, path")
    assert not setup_guard.allows_scripts(["path"])
    assert not setup_guard.allows_scripts(None)


# ── 4. deps_mounts: plan, mountpoints, git-ignore guard ───────


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def git_repo(repo):
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


async def test_other_toolchains_get_no_plan(git_repo):
    for tc in (None, "", "python", "node", "jvm"):
        assert await sandbox_deps.deps_mounts({"sandbox_toolchain": tc}, git_repo) is None


async def test_the_plan_for_a_race_app_layout(docker_mode, git_repo, monkeypatch):
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=ALL_DIRS))
    plan = await sandbox_deps.deps_mounts({"sandbox_toolchain": "bun"}, git_repo)
    assert plan is not None
    env = docker_mode / plan.env_key
    assert plan.toolchain == "bun" and env.is_dir()
    assert plan.mounts == tuple(
        DepsMount(source=env / rel, target=f"/work/{rel}") for rel in ALL_DIRS
    )
    assert plan.mountpoints == ALL_DIRS  # plugin-sdk has no deps, so no node_modules
    assert plan.path_prepend == ("/work/node_modules/.bin",)
    assert plan.env == {"BUN_INSTALL_CACHE_DIR": "/tmp/.bun", "DO_NOT_TRACK": "1"}
    for rel in ALL_DIRS:
        assert (git_repo / rel).is_dir() and not any((git_repo / rel).iterdir())
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=git_repo, capture_output=True, text=True
    )
    assert status.stdout == ""  # the agent's diff is unaffected
    for m in plan.mounts:  # the runtime's validator accepts every source, read-only
        assert sandbox._bind_violations(Bind(str(m.source), m.target, read_only=True)) == []


async def test_a_mountpoint_git_does_not_ignore_is_refused(docker_mode, git_repo, monkeypatch):
    (git_repo / ".gitignore").write_text("dist/\n")
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=ALL_DIRS))
    with pytest.raises(DepsUnavailableError, match="not ignored by git"):
        await sandbox_deps.deps_mounts({"sandbox_toolchain": "bun"}, git_repo)
    assert not (git_repo / "node_modules").exists()  # refused before any mkdir


async def test_a_non_git_worktree_is_refused(docker_mode, repo, monkeypatch):
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=ALL_DIRS))
    with pytest.raises(DepsUnavailableError, match="not ignored by git"):
        await sandbox_deps.deps_mounts({"sandbox_toolchain": "bun"}, repo)


async def test_a_planted_symlink_mountpoint_is_refused(
    docker_mode, git_repo, monkeypatch, tmp_path
):
    (tmp_path / "elsewhere").mkdir()
    (git_repo / "apps/web/node_modules").symlink_to(tmp_path / "elsewhere")
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=ALL_DIRS))
    with pytest.raises(DepsUnavailableError, match="not a plain directory|not ignored by git"):
        await sandbox_deps.deps_mounts({"sandbox_toolchain": "bun"}, git_repo)


async def test_setup_failure_is_deps_unavailable(docker_mode, git_repo, monkeypatch):
    monkeypatch.setattr(sandbox, "_exec", _installer(rc=1))
    with pytest.raises(DepsUnavailableError) as exc:
        await sandbox_deps.deps_mounts({"sandbox_toolchain": "bun"}, git_repo)
    assert isinstance(exc.value, sandbox.SandboxUnavailableError)  # every verifier: inconclusive


# ── 5. The check: in place, read-only, no network ─────────────


def _plan(tmp_path: Path) -> DepsPlan:
    env = tmp_path / "envs" / f"bun-{KEY}"
    return DepsPlan(
        toolchain="bun",
        env_key=env.name,
        mounts=(
            DepsMount(env / "apps/web/node_modules", "/work/apps/web/node_modules"),
            DepsMount(env / "node_modules", "/work/node_modules"),
        ),
        path_prepend=("/work/node_modules/.bin",),
        env={"BUN_INSTALL_CACHE_DIR": "/tmp/.bun"},
        mountpoints=("node_modules", "apps/web/node_modules"),
    )


async def test_a_bun_check_runs_in_place_with_each_tree_read_only(tmp_path, monkeypatch):
    captured = {}

    async def fake_exec(argv, timeout, container=None, env=None):
        captured["argv"] = argv
        return sandbox.SandboxResult(0, "ok", "")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    plan = _plan(tmp_path)
    await sandbox.run(["bun", "test"], tmp_path / "w", deps=plan)
    argv = captured["argv"]
    vols = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
    env = tmp_path / "envs" / f"bun-{KEY}"
    assert vols == [  # worktree first, then parents before children
        f"{tmp_path / 'w'}:/work:ro",
        f"{env / 'node_modules'}:/work/node_modules:ro",
        f"{env / 'apps/web/node_modules'}:/work/apps/web/node_modules:ro",
    ]
    assert argv[argv.index("--network") + 1] == "none"
    assert "--read-only" in argv and "--user" in argv
    assert settings.verifier_sandbox_node_image in argv
    assert "PATH=/work/node_modules/.bin:/usr/local/bin:/usr/bin:/bin" in argv
    assert "BUN_INSTALL_CACHE_DIR=/tmp/.bun" in argv
    assert not any("cp -a" in a for a in argv)  # in place: no /tmp copy
    assert argv[argv.index("--entrypoint") + 1] == "bun" and argv[-1] == "test"


async def test_a_plan_target_outside_work_is_refused(tmp_path):
    bad = DepsPlan("bun", "k", (DepsMount(tmp_path, "/etc"),))
    with pytest.raises(sandbox.SandboxUnavailableError, match="not under /work"):
        await sandbox.run(["bun", "test"], tmp_path, deps=bad)


async def test_tests_pass_on_bun_runs_bun_test_with_the_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    seen = {}

    async def fake_deps(ctx, worktree):
        return _plan(tmp_path)

    async def fake_run(argv, workdir, **kw):
        seen.update(argv=argv, **kw)
        return sandbox.SandboxResult(0, " 3 pass\n 0 fail\n", "")

    monkeypatch.setattr(sandbox_deps, "deps_mounts", fake_deps)
    monkeypatch.setattr(sandbox, "run", fake_run)
    passed, evidence = await v._verify_tests_pass(tmp_path, {"sandbox_toolchain": "bun"})
    assert passed is True and seen["argv"] == ["bun", "test"]
    assert seen["deps"] == _plan(tmp_path) and "node_deps" not in seen


@pytest.mark.parametrize(
    "check",
    [v._verify_tests_pass, v._verify_acceptance_tests_pass, v._verify_app_e2e_pass],
)
async def test_unavailable_deps_are_inconclusive_never_pass(tmp_path, monkeypatch, check):
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")

    async def boom(ctx, worktree):
        raise DepsUnavailableError("bun sandbox setup is not ready")

    monkeypatch.setattr(sandbox_deps, "deps_mounts", boom)
    _write(tmp_path, "a.test.ts", "")
    ctx = {
        "sandbox_toolchain": "bun",
        "acceptance_tests": ["a.test.ts::adds"],
        "sandbox_start_command": "bun run start",
        "sandbox_e2e_command": "bun run e2e",
    }
    passed, evidence = await check(tmp_path, ctx)
    assert passed is None and "not ready" in evidence["note"]


@pytest.mark.parametrize(("out", "ok"), [(" 1 pass\n 0 fail\n", True), (" 0 pass\n", False)])
async def test_bound_bun_tests_use_bun_and_must_really_run(tmp_path, monkeypatch, out, ok):
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    seen = {}

    async def fake_deps(ctx, worktree):
        return _plan(tmp_path)

    async def fake_run(argv, workdir, **kw):
        seen["argv"] = argv
        return sandbox.SandboxResult(0, out, "")

    monkeypatch.setattr(sandbox_deps, "deps_mounts", fake_deps)
    monkeypatch.setattr(sandbox, "run", fake_run)
    _write(tmp_path, "src/a.test.ts", "")
    passed, _ = await v._verify_acceptance_tests_pass(
        tmp_path, {"sandbox_toolchain": "bun", "acceptance_tests": ["src/a.test.ts::adds one"]}
    )
    assert passed is ok
    assert seen["argv"] == ["bun", "test", "./src/a.test.ts", "-t", "adds\\ one"]


# ── 6. The bind validator: descendants of a finished env ──────


@pytest.fixture
def cache(monkeypatch, tmp_path):
    root = tmp_path / "verifier-envs"
    env = root / f"bun-{KEY}"
    (env / "node_modules").mkdir(parents=True)
    (env / "apps/web/node_modules").mkdir(parents=True)
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(root))
    return root.resolve()


def _bad(src, read_only=True, target="/work/node_modules") -> list[str]:
    return sandbox._bind_violations(Bind(str(src), target, read_only=read_only))


def test_node_modules_inside_a_finished_env_may_be_mounted_read_only(cache):
    assert _bad(cache / f"bun-{KEY}" / "node_modules") == []
    assert _bad(cache / f"bun-{KEY}" / "apps/web/node_modules") == []
    assert _bad(cache / f"bun-{KEY}") == []  # the env itself, as before


def test_a_writable_bind_of_an_env_path_is_refused(cache):
    assert any("read-only" in b for b in _bad(cache / f"bun-{KEY}/node_modules", False))


def test_dotdot_escapes_are_refused(cache):
    src = f"{cache}/bun-{KEY}/node_modules/../../bun-{KEY}/node_modules"
    assert any("canonical" in b for b in _bad(src))


def test_a_symlinked_node_modules_pointing_outside_is_refused(cache, tmp_path):
    outside = tmp_path / "outside" / "node_modules"
    outside.mkdir(parents=True)
    link = cache / f"bun-{KEY}" / "packages" / "x" / "node_modules"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    bad = _bad(link)
    assert any("symlink" in b for b in bad) and any("canonical" in b for b in bad)


def test_a_symlinked_env_dir_is_refused(cache, tmp_path):
    real = tmp_path / "real-env"
    (real / "node_modules").mkdir(parents=True)
    (cache / "bun-ffffffffffffffffffffffff").symlink_to(real)
    assert _bad(cache / "bun-ffffffffffffffffffffffff" / "node_modules") != []


@pytest.mark.parametrize("name", [f"bun-{KEY}.partial-deadbeef", f"bun-{KEY}.gc-deadbeef"])
def test_half_built_or_doomed_envs_are_refused(cache, name):
    nm = cache / name / "node_modules"
    nm.mkdir(parents=True)
    assert any("not a finished" in b for b in _bad(nm))
    assert any("not a finished" in b for b in _bad(cache / name))


@pytest.mark.parametrize(
    "rel",
    ["abc123/node_modules", "node_modules/x/node_modules", f"bun-{KEY}/src", f"bun-{KEY}/apps"],
)
def test_other_paths_under_the_cache_are_refused(cache, rel):
    (cache / rel).mkdir(parents=True, exist_ok=True)
    assert any("not a finished" in b for b in _bad(cache / rel))


def test_the_cache_root_itself_is_refused(cache):
    assert _bad(cache) != []


# ── 7. Cache GC ───────────────────────────────────────────────

HOUR = 3600.0


def _env(root: Path, toolchain: str, n: int, *, used: float, projects=("p1",)) -> str:
    name = f"{toolchain}-{n:024x}"
    (root / name / "node_modules").mkdir(parents=True)
    meta = root / f"{name}.lg-meta.json"
    meta.write_text(json.dumps({"toolchain": toolchain, "projects": list(projects)}))
    os.utime(meta, (used, used))
    return name


def test_gc_keeps_the_newest_two_per_project_and_toolchain(tmp_path):
    now = 1_000_000.0
    olds = [_env(tmp_path, "bun", i, used=now - (10 + i) * HOUR * 24) for i in range(4)]
    node = [_env(tmp_path, "node", i, used=now - 100 * HOUR) for i in range(2)]
    other = _env(tmp_path, "bun", 9, used=now - 900 * HOUR, projects=("p2",))
    removed = sandbox.gc_envs(tmp_path, keep=2, grace_seconds=24 * HOUR, now=now)
    assert sorted(removed) == sorted(olds[2:])
    left = {p.name for p in tmp_path.iterdir() if p.is_dir()}
    assert left == {*olds[:2], *node, other}
    assert not (tmp_path / f"{olds[3]}.lg-meta.json").exists()


def test_gc_waits_out_the_grace_period(tmp_path):
    now = 1_000_000.0
    names = [_env(tmp_path, "bun", i, used=now - i * HOUR) for i in range(4)]
    assert sandbox.gc_envs(tmp_path, keep=2, grace_seconds=24 * HOUR, now=now) == []
    assert sandbox.gc_envs(tmp_path, keep=2, grace_seconds=2.5 * HOUR, now=now) == [names[3]]


async def test_gc_never_removes_an_env_whose_setup_is_running(tmp_path):
    now = 1_000_000.0
    names = [_env(tmp_path, "bun", i, used=now - (i + 1) * 100 * HOUR) for i in range(3)]
    lock = sandbox._setup_locks.setdefault(names[2], asyncio.Lock())
    async with lock:
        assert sandbox.gc_envs(tmp_path, keep=2, grace_seconds=HOUR, now=now) == []
    assert sandbox.gc_envs(tmp_path, keep=2, grace_seconds=HOUR, now=now) == [names[2]]


def test_an_env_shared_by_two_projects_stays_while_either_keeps_it(tmp_path):
    now = 1_000_000.0
    shared = _env(tmp_path, "bun", 0, used=now - 500 * HOUR, projects=("p1", "p2"))
    for i in (1, 2):
        _env(tmp_path, "bun", i, used=now - i * 100 * HOUR, projects=("p1",))
    assert sandbox.gc_envs(tmp_path, keep=2, grace_seconds=HOUR, now=now) == []
    assert (tmp_path / shared).is_dir()  # p2's newest


def test_gc_touches_only_bun_and_node_envs_and_old_leftovers(tmp_path):
    now = 1_000_000.0
    (tmp_path / "abcdef0123456789abcdef01").mkdir()  # a Python venv
    (tmp_path / f"jvm-{KEY}").mkdir()
    partial = tmp_path / f"bun-{KEY}.partial-deadbeef"
    partial.mkdir()
    os.utime(partial, (now - 100 * HOUR, now - 100 * HOUR))
    fresh = tmp_path / f"bun-{KEY}.partial-cafebabe"
    fresh.mkdir()
    os.utime(fresh, (now, now))
    removed = sandbox.gc_envs(tmp_path, keep=2, grace_seconds=HOUR, now=now)
    assert removed == [partial.name]
    assert {p.name for p in tmp_path.iterdir()} == {
        "abcdef0123456789abcdef01",
        f"jvm-{KEY}",
        fresh.name,
    }


async def test_prepare_marks_use_for_gc_and_groups_by_repository(
    docker_mode, git_repo, monkeypatch
):
    monkeypatch.setattr(sandbox, "_exec", _installer(dirs=ALL_DIRS))
    env = await sandbox.prepare_bun_env(git_repo)
    meta = json.loads((docker_mode / f"{env.name}.lg-meta.json").read_text())
    assert meta["toolchain"] == "bun" and meta["projects"] == [sandbox._project_id(git_repo)]
    assert meta["projects"] != ["?"]


def test_worktrees_of_one_repo_share_a_project_id(tmp_path):
    main, wt = tmp_path / "main", tmp_path / "wt"
    (main / ".git" / "worktrees" / "wt").mkdir(parents=True)
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'wt'}\n")
    (tmp_path / "other").mkdir()
    assert sandbox._project_id(wt) == sandbox._project_id(main) != "?"
    assert sandbox._project_id(tmp_path / "other") == "?"


# ── 1-2. Images and the registry ──────────────────────────────

_BUN_PIN = re.compile(r"^FROM (oven/bun:[\w.-]+@sha256:[0-9a-f]{64}) AS bun$", re.M)


def test_driver_and_verifier_images_pin_the_same_bun():
    pins = {
        path: _BUN_PIN.findall((REPO / path).read_text())
        for path in ("docker/verifier-node/Dockerfile", "docker/claude-driver/Dockerfile")
    }
    (verifier,), (driver,) = pins.values()
    assert verifier == driver and verifier.startswith("oven/bun:1.4.5@sha256:")
    for path in pins:
        text = (REPO / path).read_text()
        assert "COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun" in text
        assert re.search(r"apt-get install[^\n]*\bgit\b", text)


def test_the_registry_api_accepts_the_bun_toolchain():
    from life_graph.api.kernel import _ProjectOpsSettings

    assert _ProjectOpsSettings(sandbox_toolchain="bun").sandbox_toolchain == "bun"
    assert _ProjectOpsSettings(sandbox_js_test_runner="bun").sandbox_js_test_runner == "bun"
