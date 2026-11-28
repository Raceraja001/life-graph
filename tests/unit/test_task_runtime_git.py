"""Read-only git metadata in the task runtime (sandbox_git + task_runtime._git_binds).

A live team run (2026-11-28) found git broken inside the agent container: the
worktree's ``.git`` file points at ``<origin>/.git/worktrees/<name>``, a host
path that was never mounted. Pinned here: which pieces of the common dir are
mounted (read-only, at their own paths), that the config is a synthesized one
with no remote or credential keys, what the validator accepts and refuses,
and that real git reads a worktree through exactly that layout. The opt-in
real-docker check runs with ``LIFE_GRAPH_DOCKER_SMOKE=1``.
"""

from __future__ import annotations

import dataclasses
import os
import shutil
import stat
import subprocess
import uuid
from pathlib import Path

import pytest

from life_graph.config import settings
from life_graph.services.dev import sandbox, sandbox_git, task_runtime
from life_graph.services.dev.sandbox import Bind, SandboxPolicyError

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

SECRET = "ghp_" + "x" * 36


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(cwd),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "LANG": "C",
    }
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, env=env, check=check
    )


def _make_origin(path: Path, *, object_format: str = "sha1") -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", f"--object-format={object_format}", "-b", "main")
    (path / "a.txt").write_text("one\n")
    _git(path, "add", "a.txt")
    _git(path, "commit", "-q", "-m", "first")
    # What a real config may hold, and what must never reach the container.
    _git(path, "remote", "add", "origin", f"https://x-access-token:{SECRET}@github.com/o/r.git")
    _git(path, "config", "credential.helper", "store --file=/home/u/.git-credentials")
    _git(path, "config", "include.path", "/home/u/.gitconfig-secret")
    _git(path, "config", "core.fsmonitor", "/tmp/evil.sh")
    _git(path, "pack-refs", "--all")
    (path / ".git" / "hooks" / "post-checkout").write_text("#!/bin/sh\n")
    return path


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """An origin repo and a linked worktree under the (tmp) tenant scratch root."""
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "tmp"))
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "cache" / "envs"))
    origin = _make_origin(tmp_path / "origin")
    scratch = tmp_path / "tmp" / "lg-tenants" / "t1" / "lg_dispatch_x"
    scratch.mkdir(parents=True)
    wt = scratch / "wt_1"
    _git(origin, "worktree", "add", "-q", "--detach", str(wt))
    yield {"origin": origin, "common": (origin / ".git").resolve(), "wt": wt.resolve()}
    for root, dirs, _files in os.walk(tmp_path):
        for d in dirs:
            with_write = Path(root) / d
            if not with_write.is_symlink():
                with_write.chmod(with_write.stat().st_mode | stat.S_IWUSR)


def _binds(repo) -> tuple[list[Bind], Path]:
    binds, stage, meta = task_runtime._git_binds(_req(repo), uuid.uuid4().hex[:16])
    assert meta["mounted"] is True, meta
    assert stage is not None
    return binds, stage


def _req(repo, **kw) -> task_runtime.RuntimeRequest:
    base = dict(
        task_id=str(uuid.uuid4()),
        tenant_id="t1",
        driver="claude_code",
        image="life-graph-claude-driver:test",
        command=("/usr/local/bin/claude", "-p", "hi"),
        workspace=repo["wt"],
        timeout=60,
    )
    base.update(kw)
    return task_runtime.RuntimeRequest(**base)


def _spec(repo, binds: list[Bind]) -> sandbox.SandboxSpec:
    names = {"container": "lg-rt-0123456789abcdef", "proxy": "p", "network": "lg-rt-net-01234567"}
    return task_runtime.DockerTaskRuntime()._driver_spec(_req(repo), names, {}, binds)


# ── Layout and argv ─────────────────────────────────────────────


def test_exactly_the_git_metadata_is_mounted_read_only_at_its_own_paths(repo):
    binds, stage = _binds(repo)
    common = repo["common"]
    gitdir = common / "worktrees" / "wt_1"
    by_target = {b.target: b for b in binds}
    assert set(by_target) == {
        str(common / "objects"),
        str(common / "refs"),
        str(common / "packed-refs"),
        str(common / "HEAD"),
        str(common / "info"),
        str(gitdir),
        str(common / "config"),
    }
    assert all(b.read_only and b.git for b in binds)
    for target, b in by_target.items():
        if target != str(common / "config"):
            assert b.source == target  # same absolute path: the pointers resolve
    # The config is the staged one, never the real file.
    assert by_target[str(common / "config")].source == str(stage / "config")
    assert stage.resolve().parent == sandbox.driver_creds_root().resolve()

    argv = sandbox.docker_run_argv(_spec(repo, binds), detach=False)
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "--mount"]
    git_mounts = [m for m in mounts if "target=/work," not in m + ","]
    assert len(git_mounts) == len(binds)
    assert all(m.endswith(",readonly") for m in git_mounts)
    assert f"type=bind,source={stage / 'config'},target={common / 'config'},readonly" in mounts
    joined = " ".join(argv)
    for never in ("/hooks", "/logs", str(common) + ","):
        assert never not in joined
    # The worktree itself stays the one writable mount.
    assert f"type=bind,source={repo['wt']},target=/work" in mounts


def test_the_synthesized_config_has_no_remote_or_credential_keys(repo):
    binds, stage = _binds(repo)
    text = (stage / "config").read_text()
    assert text == "[core]\n\trepositoryformatversion = 0\n\tbare = false\n"
    lowered = text.lower()
    for key in ("remote", "url", "credential", "include", "fsmonitor", "hookspath", SECRET):
        assert key.lower() not in lowered
    assert not os.access(stage / "config", os.W_OK) or os.getuid() == 0


def test_sha256_repositories_carry_their_object_format(tmp_path):
    origin = _make_origin(tmp_path / "o256", object_format="sha256")
    text = sandbox_git.synthesize_config(origin / ".git")
    assert "[extensions]\n\tobjectformat = sha256\n" in text
    assert "repositoryformatversion = 1" in text
    assert not sandbox_git.config_violations(text)


def test_unknown_extensions_are_dropped(tmp_path):
    origin = _make_origin(tmp_path / "o")
    _git(origin, "config", "core.repositoryformatversion", "1")
    _git(origin, "config", "extensions.worktreeConfig", "true")
    _git(origin, "config", "extensions.partialclone", "origin")
    text = sandbox_git.synthesize_config(origin / ".git")
    assert "worktreeconfig" not in text.lower() and "partialclone" not in text.lower()


async def test_the_runtime_mounts_git_and_removes_the_staged_config(repo):
    from tests.unit.test_task_runtime import FakeDocker

    docker = FakeDocker()
    out = await task_runtime.DockerTaskRuntime(docker).run(_req(repo))
    argv = docker.first("run driver")
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "--mount"]
    assert any(m.endswith(f"target={repo['common'] / 'config'},readonly") for m in mounts)
    assert out.metadata["git"]["mounted"] is True
    assert out.metadata["policy_version"] == "2026-11-28.2"
    assert not list(sandbox.driver_creds_root().glob("git-*"))  # cleaned up


async def test_a_plain_directory_gets_no_git_binds(repo, tmp_path):
    from tests.unit.test_task_runtime import FakeDocker

    plain = repo["wt"].parent / "wt_plain"
    plain.mkdir()
    docker = FakeDocker()
    out = await task_runtime.DockerTaskRuntime(docker).run(_req(repo, workspace=plain))
    argv = docker.first("run driver")
    assert [argv[i + 1] for i, a in enumerate(argv) if a == "--mount"] == [
        f"type=bind,source={plain.resolve()},target=/work"
    ]
    assert out.metadata["git"]["mounted"] is False


# ── Validator ──────────────────────────────────────────────────


def test_the_validator_accepts_the_planned_binds(repo):
    binds, _ = _binds(repo)
    sandbox.validate_spec(_spec(repo, binds))


def _refused(repo, binds: list[Bind], match: str) -> None:
    with pytest.raises(SandboxPolicyError, match=match):
        _spec(repo, binds)


def test_a_writable_git_bind_is_refused(repo):
    binds, _ = _binds(repo)
    binds[0] = dataclasses.replace(binds[0], read_only=False)
    _refused(repo, binds, "must be read-only")


def test_the_real_config_is_refused(repo):
    binds, _ = _binds(repo)
    real = str(repo["common"] / "config")
    binds = [dataclasses.replace(b, source=real) if b.target == real else b for b in binds]
    _refused(repo, binds, "not a staged file")


def test_a_staged_config_with_a_remote_is_refused(repo):
    binds, stage = _binds(repo)
    cfg = stage / "config"
    cfg.chmod(0o644)
    cfg.write_text(cfg.read_text() + '[remote "origin"]\n\turl = https://t@github.com/o/r\n')
    _refused(repo, binds, "not a plain allowed entry|is not allowed")


@pytest.mark.parametrize("extra", ["hooks", "logs", "config", "."])
def test_other_parts_of_the_common_dir_are_refused(repo, extra):
    binds, _ = _binds(repo)
    path = str((repo["common"] / extra).resolve())
    if extra == "config":
        binds = [b for b in binds if b.target != path]  # the real config as a plain git bind
    binds.append(Bind(path, path, read_only=True, git=True))
    _refused(repo, binds, "not part of the worktree's git metadata|not a staged file")


def test_a_git_bind_at_another_target_is_refused(repo):
    binds, _ = _binds(repo)
    binds[0] = dataclasses.replace(binds[0], target="/elsewhere")
    _refused(repo, binds, "not part of the worktree's git metadata")


def test_git_binds_without_a_linked_worktree_are_refused(repo):
    binds, _ = _binds(repo)
    plain = repo["wt"].parent / "wt_plain"
    plain.mkdir()
    names = {"container": "lg-rt-0123456789abcdef", "proxy": "p", "network": "lg-rt-net-01234567"}
    with pytest.raises(SandboxPolicyError, match="git metadata binds refused"):
        task_runtime.DockerTaskRuntime()._driver_spec(_req(repo, workspace=plain), names, {}, binds)


def test_a_git_flag_does_not_widen_the_normal_bind_roots(repo, tmp_path):
    binds, _ = _binds(repo)
    outside = tmp_path / "outside"
    outside.mkdir()
    binds.append(Bind(str(outside), str(outside), read_only=True, git=True))
    _refused(repo, binds, "not part of the worktree's git metadata")


def test_a_redirected_dot_git_is_not_followed(repo, tmp_path):
    binds, _ = _binds(repo)
    other = _make_origin(tmp_path / "other")
    (repo["wt"] / ".git").write_text(f"gitdir: {other / '.git'}\n")
    _refused(repo, binds, "git metadata binds refused")


def test_per_worktree_config_is_not_mounted(repo):
    (repo["common"] / "worktrees" / "wt_1" / "config.worktree").write_text("[x]\n")
    _binds_meta = task_runtime._git_binds(_req(repo), "r")
    assert _binds_meta[0] == [] and _binds_meta[2]["mounted"] is False


# ── Real git through the planned layout ─────────────────────────


def _read_only_tree(path: Path) -> None:
    for root, dirs, files in os.walk(path):
        for f in files:
            (Path(root) / f).chmod(0o444)
        for d in dirs:
            (Path(root) / d).chmod(0o555)
    path.chmod(0o555)


def test_real_git_reads_the_worktree_through_exactly_the_mount_layout(repo):
    """Rebuild the common dir from ONLY the binds (same paths, read-only), then run git."""
    binds, _ = _binds(repo)
    common = repo["common"]
    real = common.with_name(".git-real")
    common.rename(real)
    common.mkdir()
    for b in binds:
        src = Path(b.source)
        if src.is_relative_to(common):
            src = real / src.relative_to(common)
        dst = Path(b.target)
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
    _read_only_tree(common)
    assert sorted(p.name for p in common.iterdir()) == [
        "HEAD", "config", "info", "objects", "packed-refs", "refs", "worktrees"
    ]  # fmt: skip

    wt = repo["wt"]
    (wt / "a.txt").write_text("one\ntwo\n")
    (wt / "new.txt").write_text("n\n")
    status = _git(wt, "status", "--porcelain")
    assert status.stdout.splitlines() == [" M a.txt", "?? new.txt"]
    assert "+two" in _git(wt, "diff").stdout
    assert _git(wt, "log", "--oneline").stdout.strip().endswith("first")
    # Writes fail read-only (acceptable: Life Graph commits on the host).
    assert _git(wt, "add", "a.txt", check=False).returncode != 0
    assert _git(wt, "remote", "-v").stdout == ""


# ── Opt-in: the real container ─────────────────────────────────

DRIVER_IMAGE = (
    os.environ.get("LIFE_GRAPH_SMOKE_DRIVER_IMAGE") or settings.driver_claude_sandbox_image
)


@pytest.mark.skipif(
    os.environ.get("LIFE_GRAPH_DOCKER_SMOKE") != "1",
    reason="real-docker smoke test; set LIFE_GRAPH_DOCKER_SMOKE=1",
)
async def test_git_works_read_only_in_a_real_runtime_container(tmp_path, monkeypatch):
    from life_graph.drivers.dispatcher import tenant_scratch_root

    if shutil.which("docker") is None:
        pytest.skip("no docker CLI")
    probe = subprocess.run(["docker", "image", "inspect", DRIVER_IMAGE], capture_output=True)
    if probe.returncode != 0:
        pytest.skip(f"image {DRIVER_IMAGE} not present")
    origin = _make_origin(tmp_path / "origin")
    scratch = Path(tenant_scratch_root("it-git")) / f"lg_dispatch_{uuid.uuid4().hex[:6]}"
    scratch.mkdir(parents=True)
    wt = scratch / "wt_1"
    try:
        _git(origin, "worktree", "add", "-q", "--detach", str(wt))
        (wt / "a.txt").write_text("one\ntwo\n")
        script = (
            "set -u; git status --porcelain; echo ---; git diff --stat; echo ---;"
            " git log --oneline; echo ---; git remote -v; echo ---;"
            ' cat "$(git rev-parse --git-common-dir)/config"; echo ---;'
            " git add a.txt >/dev/null 2>&1 && echo add-ok || echo add-failed"
        )
        req = task_runtime.RuntimeRequest(
            task_id=str(uuid.uuid4()),
            tenant_id="it",
            driver="probe",
            image=DRIVER_IMAGE,
            command=("sh", "-c", script),
            workspace=wt,
            memory="256m",
            cpus="0.5",
            pids_limit=64,
            timeout=60,
        )
        out = await task_runtime.DockerTaskRuntime().run(req)
        assert out.returncode == 0, out.stderr
        status, diff, log, remotes, config, add = out.stdout.split("---\n")
        assert status.strip() == "M a.txt"
        assert "a.txt" in diff
        assert log.strip().endswith("first")
        assert remotes.strip() == ""
        assert SECRET not in out.stdout and "credential" not in config
        assert add.strip() == "add-failed"
        assert out.metadata["git"]["mounted"] is True
    finally:
        subprocess.run(["git", "-C", str(origin), "worktree", "remove", "--force", str(wt)])
        shutil.rmtree(scratch, ignore_errors=True)
