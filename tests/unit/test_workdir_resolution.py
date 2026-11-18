from __future__ import annotations

import uuid

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.workdir import remove_worktree, resolve_workdir


def _packet(project_context: dict | None = None) -> ContextPacket:
    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t1",
        task_type="code",
        instruction="do it",
        project_context=project_context or {},
    )


@pytest.mark.asyncio
async def test_no_project_path_returns_fallback(tmp_path):
    packet = _packet()
    cwd, worktree = await resolve_workdir(packet, tmp_path)
    assert cwd == tmp_path
    assert worktree is None


@pytest.mark.asyncio
async def test_project_path_without_isolation_returns_path_directly(tmp_path):
    real_project = tmp_path / "proj"
    real_project.mkdir()
    packet = _packet({"path": str(real_project)})

    cwd, worktree = await resolve_workdir(packet, tmp_path / "scratch")

    assert cwd == real_project
    assert worktree is None


@pytest.mark.asyncio
async def test_isolation_creates_a_git_worktree(tmp_path):
    import subprocess

    real_repo = tmp_path / "repo"
    real_repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(real_repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(real_repo), check=True, capture_output=True,
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    packet = _packet({"path": str(real_repo), "isolation": True})

    cwd, worktree = await resolve_workdir(packet, scratch)

    assert worktree is not None
    assert cwd == worktree
    assert worktree.is_dir()
    assert (worktree / ".git").exists()

    await remove_worktree(packet, worktree)
    assert not worktree.exists()


@pytest.mark.asyncio
async def test_isolation_failure_falls_back_to_scratch_not_project(tmp_path):
    """Isolation was ASKED FOR and could not be delivered — the dispatch must
    land on the inert scratch dir, NOT on the real, live project checkout.
    Silently degrading onto the real repo would hand an unattended agent_task
    write access to the developer's working tree."""
    # Not a git repo — "git worktree add" will fail.
    real_project = tmp_path / "not_a_repo"
    real_project.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    packet = _packet({"path": str(real_project), "isolation": True})

    cwd, worktree = await resolve_workdir(packet, scratch)

    assert worktree is None
    assert cwd == scratch
    assert cwd != real_project


@pytest.mark.asyncio
async def test_resolve_workdir_survives_a_missing_git_binary(tmp_path, monkeypatch):
    """create_subprocess_exec raises FileNotFoundError BEFORE there is a proc
    to check when `git` is not on PATH (the production image had none). The
    documented contract is "never raises"."""
    real_project = tmp_path / "proj"
    real_project.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    packet = _packet({"path": str(real_project), "isolation": True})

    async def _boom(*_a, **_k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _boom)

    cwd, worktree = await resolve_workdir(packet, scratch)

    assert cwd == scratch
    assert worktree is None


@pytest.mark.asyncio
async def test_remove_worktree_survives_a_missing_git_binary(tmp_path, monkeypatch):
    packet = _packet({"path": str(tmp_path)})

    async def _boom(*_a, **_k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _boom)

    # Best-effort cleanup: must return, not raise.
    await remove_worktree(packet, tmp_path / "wt_deadbeef")


@pytest.mark.asyncio
async def test_remove_worktree_honors_the_repo_path_override(tmp_path):
    """The caller may have rewritten project_context["path"] to the worktree
    itself; git cannot delete a worktree from inside it, so the origin repo
    must be passable explicitly."""
    import subprocess

    real_repo = tmp_path / "repo"
    real_repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(real_repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(real_repo), check=True, capture_output=True,
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    packet = _packet({"path": str(real_repo), "isolation": True})

    cwd, worktree = await resolve_workdir(packet, scratch)
    assert worktree is not None

    # Mimic dispatch_task: point the packet at the resolved worktree.
    packet.project_context["path"] = str(worktree)
    packet.project_context["isolation"] = False

    await remove_worktree(packet, worktree, repo_path=str(real_repo))

    assert not worktree.exists()


def _git(cwd, *args):
    import subprocess

    return subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.mark.asyncio
async def test_a_pinned_base_is_cut_from_origin_not_the_checkout(tmp_path):
    # origin has `main` at commit B; the local clone is checked out on another
    # branch and its own `main` is behind (commit A). The worktree must start
    # from origin/main (B), whatever the checkout is doing.
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-b", "main")
    _git(origin, "commit", "--allow-empty", "-m", "A")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    _git(origin, "commit", "--allow-empty", "-m", "B")
    b = _git(origin, "rev-parse", "HEAD")
    _git(clone, "checkout", "-q", "-b", "someone-elses-work")
    _git(clone, "commit", "--allow-empty", "-m", "unrelated")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    packet = _packet({"path": str(clone), "isolation": True, "base_branch": "main"})

    cwd, worktree = await resolve_workdir(packet, scratch)

    assert worktree is not None
    assert _git(worktree, "rev-parse", "HEAD") == b
    await remove_worktree(packet, worktree)


@pytest.mark.asyncio
async def test_a_pinned_base_falls_back_to_the_local_branch_without_a_remote(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "commit", "--allow-empty", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "other")
    _git(repo, "commit", "--allow-empty", "-m", "other work")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    packet = _packet({"path": str(repo), "isolation": True, "base_branch": "main"})

    cwd, worktree = await resolve_workdir(packet, scratch)

    assert worktree is not None
    assert _git(worktree, "rev-parse", "HEAD") == base
    await remove_worktree(packet, worktree)


@pytest.mark.asyncio
async def test_an_unsafe_base_branch_name_is_ignored(tmp_path):
    from life_graph.drivers.workdir import _pinned_start

    assert await _pinned_start(tmp_path, "--upload-pack=evil") is None
    assert await _pinned_start(tmp_path, "main; rm -rf /") is None
    assert await _pinned_start(tmp_path, None) is None


# ── Symlinks leaving the worktree (work order Stage 5 hardening) ──


def test_a_link_out_of_the_worktree_is_found(tmp_path):
    from life_graph.drivers.workdir import escaping_symlinks

    wt = tmp_path / "wt"
    (wt / "src").mkdir(parents=True)
    secret = tmp_path / "secret.txt"
    secret.write_text("host secret")
    (wt / "src" / "notes.txt").symlink_to(secret)
    (wt / "up").symlink_to("../")
    (wt / "dangling").symlink_to("/nonexistent/elsewhere")
    assert sorted(escaping_symlinks(wt)) == ["dangling", "src/notes.txt", "up"]


def test_links_inside_the_worktree_and_git_are_fine(tmp_path):
    from life_graph.drivers.workdir import escaping_symlinks

    wt = tmp_path / "wt"
    (wt / "docs").mkdir(parents=True)
    (wt / "docs" / "README.md").write_text("x")
    (wt / "README.md").symlink_to("docs/README.md")
    (wt / ".git").mkdir()
    (wt / ".git" / "weird").symlink_to("/etc")  # git's own business, not scanned
    assert escaping_symlinks(wt) == []


def test_not_a_path_is_not_a_crash():
    from life_graph.drivers.workdir import escaping_symlinks

    assert escaping_symlinks(object()) == []


def test_a_committed_link_is_the_projects_own_but_a_changed_one_is_flagged(tmp_path):
    import subprocess

    from life_graph.drivers.workdir import escaping_symlinks

    wt = tmp_path / "repo"
    wt.mkdir()
    (wt / "tool").symlink_to("/usr/bin/env")  # committed by the owner
    subprocess.run(["git", "init", "-q"], cwd=wt, check=True)
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
        cwd=wt, check=True,
    )  # fmt: skip
    assert escaping_symlinks(wt, git_aware=True) == []
    assert escaping_symlinks(wt) == ["tool"]  # without git, every escaping link
    (wt / "leak").symlink_to("/etc/passwd")  # the agent's
    (wt / "tool").unlink()
    (wt / "tool").symlink_to("/etc/shadow")  # retargeted by the agent
    assert sorted(escaping_symlinks(wt, git_aware=True)) == ["leak", "tool"]


def _commit_all(wt):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=wt, check=True)
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
        cwd=wt, check=True,
    )  # fmt: skip


def test_many_committed_links_cannot_hide_the_agents_link(tmp_path):
    """Review 2026-11-18: the git filter ran after the 20-finding cap, so 20
    committed links filled it and the planted one was never looked at."""
    from life_graph.drivers.workdir import escaping_symlinks

    wt = tmp_path / "repo"
    wt.mkdir()
    for i in range(25):
        (wt / f"l{i:02d}").symlink_to("/usr/share/doc")
    _commit_all(wt)
    (wt / "zz_leak").symlink_to("/etc/passwd")
    assert escaping_symlinks(wt, git_aware=True) == ["zz_leak"]


def test_a_symlink_named_git_below_the_top_is_checked(tmp_path):
    """Review 2026-11-18: every ".git" was skipped, so src/.git -> /etc hid."""
    from life_graph.drivers.workdir import escaping_symlinks

    wt = tmp_path / "wt"
    (wt / "src").mkdir(parents=True)
    (wt / "src" / ".git").symlink_to("/etc")
    assert escaping_symlinks(wt) == ["src/.git"]


def test_without_commits_every_escaping_link_counts(tmp_path):
    import subprocess

    from life_graph.drivers.workdir import escaping_symlinks

    wt = tmp_path / "repo"
    wt.mkdir()
    (wt / "tool").symlink_to("/usr/bin/env")
    subprocess.run(["git", "init", "-q"], cwd=wt, check=True)
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)  # indexed, never committed
    assert escaping_symlinks(wt, git_aware=True) == ["tool"]
