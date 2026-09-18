"""Guards for the read-only git tools.

These tools used to run git in any ``repo_path`` for any tenant, and passed a
model-supplied ``target`` straight to ``git diff``. Each test pins one of the
holes that allowed, so reopening it is a test failure.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from life_graph.tools import filesystem as fs
from life_graph.tools import git as git_tools


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A one-commit repo inside the only allowed root."""
    from life_graph.config import settings

    root = tmp_path / "root"
    repo = root / "repo"
    repo.mkdir(parents=True)
    monkeypatch.setattr(settings, "tool_fs_roots", str(root))
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("one\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-qm", "init")
    return repo


async def test_status_inside_root_works(repo):
    out = json.loads(await git_tools.git_status(str(repo)))
    assert out["exit_code"] == 0


async def test_repo_outside_root_denied(repo, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    for call in (
        git_tools.git_status(str(outside)),
        git_tools.git_log(str(outside)),
        git_tools.git_diff(str(outside)),
        git_tools.git_branch(str(outside)),
    ):
        out = json.loads(await call)
        assert "outside the permitted roots" in out["error"]


async def test_unprivileged_tenant_denied(repo, monkeypatch):
    from life_graph.config import settings
    from life_graph.core import tenant as tenant_mod

    monkeypatch.setattr(settings, "tool_privileged_tenants", "default")
    # Set and reset in the test's own context: an async test runs in a
    # different Context from a sync fixture's teardown.
    token = tenant_mod._tenant_id_var.set("acme-corp")
    try:
        out = json.loads(await git_tools.git_status(str(repo)))
    finally:
        tenant_mod._tenant_id_var.reset(token)
    assert "not available to this tenant" in out["error"]


async def test_diff_target_cannot_inject_output_option(repo, tmp_path):
    """``git diff --output=<file>`` is an arbitrary file write."""
    (repo / "a.txt").write_text("two\n")
    victim = tmp_path / "written_by_diff.txt"
    out = json.loads(await git_tools.git_diff(str(repo), target=f"--output={victim}"))
    assert "error" in out
    assert not victim.exists()


async def test_diff_path_and_revision_targets_still_work(repo):
    (repo / "a.txt").write_text("two\n")
    by_path = json.loads(await git_tools.git_diff(str(repo), target="a.txt"))
    assert by_path["exit_code"] == 0
    assert "a.txt" in by_path["stdout"]
    by_rev = json.loads(await git_tools.git_diff(str(repo), target="HEAD"))
    assert by_rev["exit_code"] == 0
    assert "a.txt" in by_rev["stdout"]


async def test_repo_fsmonitor_does_not_execute(repo, tmp_path):
    """A repo's own ``core.fsmonitor`` must not run during git_status."""
    marker = tmp_path / "fsmonitor_ran"
    hook = tmp_path / "hook.sh"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    _git(repo, "config", "core.fsmonitor", str(hook))
    await git_tools.git_status(str(repo))
    assert not marker.exists()


async def test_log_count_is_clamped(repo):
    out = json.loads(await git_tools.git_log(str(repo), count=10**9))
    assert out["exit_code"] == 0
    bad = json.loads(await git_tools.git_log(str(repo), count="-p"))
    assert "count must be an integer" in bad["error"]


async def test_file_write_cannot_plant_git_config(repo):
    """Writing .git/config would turn file_write into a shell via fsmonitor."""
    config = repo / ".git" / "config"
    before = config.read_text()
    out = json.loads(await fs.file_write(str(config), "[core]\n\tfsmonitor = /bin/sh\n"))
    assert "inside a .git directory" in out["error"]
    assert config.read_text() == before
    hook = json.loads(await fs.file_write(str(repo / ".git" / "hooks" / "pre-commit"), "x"))
    assert "error" in hook
