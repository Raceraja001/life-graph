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
async def test_isolation_failure_falls_back_to_project_path(tmp_path):
    # Not a git repo — "git worktree add" will fail.
    real_project = tmp_path / "not_a_repo"
    real_project.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    packet = _packet({"path": str(real_project), "isolation": True})

    cwd, worktree = await resolve_workdir(packet, scratch)

    assert worktree is None
    assert cwd == real_project
