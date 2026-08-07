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
