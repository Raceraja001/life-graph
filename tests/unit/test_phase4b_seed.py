"""Phase 4b: branch hand-off and seeding a worktree from other tasks' branches.

Real git, in a temporary repository: workers land on ``lg/task-*`` branches,
the integration worktree gets their changes with ``git apply --3way``
(conflicts left as markers), a dependent worker commits its seed.
"""

from __future__ import annotations

import subprocess
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from life_graph.config import settings
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher, _DispatchRun
from life_graph.drivers.seed_branches import (
    apply_handoff,
    apply_handoffs,
    commit_seed,
    seed_report,
    unresolved_markers,
)
from life_graph.drivers.workdir import preserve_verified_work

if TYPE_CHECKING:
    from pathlib import Path


def git(cwd, *args) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "a.py").write_text("def a():\n    return 1\n")
    (root / "b.py").write_text("def b():\n    return 2\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return root


def worktree(repo: Path, name: str) -> Path:
    path = repo.parent / name
    git(repo, "worktree", "add", "-q", "--detach", str(path))
    return path


async def land(repo: Path, task_id: str, edits: dict[str, str]) -> dict:
    """A worker's run: edit in its own worktree, land on its branch, hand off."""
    wt = worktree(repo, f"wt-{task_id[:8]}")
    base = git(wt, "rev-parse", "HEAD")
    for name, text in edits.items():
        (wt / name).write_text(text)
    branch = await preserve_verified_work(wt, repo, task_id, summary="worker")
    assert branch == f"lg/task-{task_id[:8]}"
    return {
        "task_id": task_id,
        "branch": branch,
        "base_commit": base,
        "head_commit": git(wt, "rev-parse", "HEAD"),
    }


def tid() -> str:
    return str(uuid.uuid4())


async def test_two_non_overlapping_branches_apply_cleanly_and_stay_uncommitted(repo):
    one = await land(repo, tid(), {"a.py": "def a():\n    return 10\n"})
    two = await land(repo, tid(), {"b.py": "def b():\n    return 20\n"})
    integ = worktree(repo, "integ")
    head = git(integ, "rev-parse", "HEAD")

    results = await apply_handoffs(integ, [one, two])

    assert [r.status for r in results] == ["applied", "applied"]
    assert (integ / "a.py").read_text() == "def a():\n    return 10\n"
    assert (integ / "b.py").read_text() == "def b():\n    return 20\n"
    assert git(integ, "rev-parse", "HEAD") == head  # nothing committed
    assert git(integ, "diff", "--cached", "--name-only") == ""  # index reset
    assert "applied cleanly" in seed_report(results)
    # The branches themselves are untouched.
    assert git(repo, "rev-parse", one["branch"]) == one["head_commit"]


async def test_overlapping_branches_leave_conflict_markers_for_the_agent(repo):
    one = await land(repo, tid(), {"a.py": "def a():\n    return 10\n"})
    two = await land(repo, tid(), {"a.py": "def a():\n    return 99\n"})
    integ = worktree(repo, "integ")

    results = await apply_handoffs(integ, [one, two])

    assert results[0].status == "applied"
    assert results[1].status == "conflicts" and results[1].files == ["a.py"]
    text = (integ / "a.py").read_text()
    assert "<<<<<<<" in text and ">>>>>>>" in text
    assert unresolved_markers(integ, ["a.py"]) == ["a.py"]
    assert "CONFLICTS in a.py" in seed_report(results)
    (integ / "a.py").write_text("def a():\n    return 109\n")
    assert unresolved_markers(integ, ["a.py"]) == []


async def test_a_dependent_worker_commits_its_seed_so_its_branch_holds_only_its_delta(repo):
    first = await land(repo, tid(), {"a.py": "def a():\n    return 10\n"})
    wt = worktree(repo, "dependent")
    base = git(wt, "rev-parse", "HEAD")

    [result] = await apply_handoffs(wt, [first])
    seed_head = await commit_seed(wt, "Seed: changes of " + first["branch"])

    assert result.status == "applied"
    assert seed_head and seed_head != base
    assert git(wt, "status", "--porcelain") == ""
    # The worker then changes its own file; its delta from the seed is only that.
    (wt / "a.py").write_text("def a():\n    return 10\n\n\ndef c():\n    return 3\n")
    task = tid()
    await preserve_verified_work(wt, repo, task, summary="dependent")
    own = git(repo, "diff", "--name-only", seed_head, f"lg/task-{task[:8]}")
    assert own == "a.py"
    delta = git(repo, "diff", seed_head, f"lg/task-{task[:8]}")
    assert "+    return 10" not in delta and "-    return 1" not in delta


async def test_bad_hand_offs_fail_without_touching_the_worktree(repo):
    wt = worktree(repo, "x")
    bad_branch = await apply_handoff(wt, {"branch": "main", "base_commit": "a" * 40})
    no_commit = await apply_handoff(wt, {"branch": "lg/task-1234abcd"})
    missing = await apply_handoff(
        wt, {"branch": "lg/task-1234abcd", "base_commit": "a" * 40, "head_commit": "b" * 40}
    )
    assert [r.status for r in (bad_branch, no_commit, missing)] == ["failed"] * 3
    assert git(wt, "status", "--porcelain") == ""


async def test_an_empty_hand_off_is_reported_empty(repo):
    head = git(repo, "rev-parse", "HEAD")
    wt = worktree(repo, "y")
    result = await apply_handoff(
        wt, {"task_id": "t", "branch": "lg/task-abcd1234", "base_commit": head, "head_commit": head}
    )
    assert result.status == "empty"


# ── Inside the dispatcher ───────────────────────────────────────


def _run(repo: Path, wt: Path, **kw) -> _DispatchRun:
    run = _DispatchRun(
        tenant_id="t1", task_id=kw.pop("task_id", tid()), instruction="do it",
        task_type="code_change", persona_name=None, session=None, cost_cap_usd=2.0,
        interactive=False, spec_first=False, acceptance_tests=None, **kw,
    )  # fmt: skip
    run.packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code_change", instruction="do it",
        project_context={"path": str(wt)},
    )  # fmt: skip
    run.worktree, run.workdir, run.worktree_origin = wt, wt, str(repo)
    run.driver = SimpleNamespace(name="fake")
    return run


async def test_the_integration_seed_is_reported_to_the_agent_and_guards_landing(repo):
    one = await land(repo, tid(), {"a.py": "def a():\n    return 10\n"})
    two = await land(repo, tid(), {"a.py": "def a():\n    return 99\n"})
    wt = worktree(repo, "integ")
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    run = _run(repo, wt, seed={"handoffs": [one, two], "commit": False})

    await d._seed_worktree(run)

    assert run.seed_error is None
    assert run.seed_conflicts == ["a.py"]
    assert "THE TEAM'S CHANGES" in run.packet.instruction
    assert "CONFLICTS in a.py" in run.packet.instruction
    # The agent left the markers: the run is not landed.
    run.result = DriverResult(success=True, output="done")
    d._check_seed_conflicts(run)
    assert not run.result.success
    assert run.result.metadata["stop_reason"] == "unresolved_conflicts"
    # Resolved: it passes.
    (wt / "a.py").write_text("def a():\n    return 109\n")
    run.result = DriverResult(success=True, output="done")
    d._check_seed_conflicts(run)
    assert run.result.success


async def test_a_worker_whose_dependency_does_not_apply_is_not_run(repo):
    one = await land(repo, tid(), {"a.py": "def a():\n    return 10\n"})
    two = await land(repo, tid(), {"a.py": "def a():\n    return 99\n"})
    wt = worktree(repo, "dep")
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    run = _run(repo, wt, seed={"handoffs": [one, two], "commit": True})

    await d._seed_worktree(run)

    assert run.seed_error and "Could not start from the changes" in run.seed_error


async def test_a_worker_hands_off_on_its_branch_and_files_no_approval(repo, monkeypatch):
    monkeypatch.setattr(settings, "driver_land_verified_work", True)
    wt = worktree(repo, "worker")
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    task = tid()
    run = _run(repo, wt, task_id=task, handoff="branch")
    run.result = DriverResult(success=True, output="did it")
    (wt / "b.py").write_text("def b():\n    return 22\n")

    async def no_risk(_run):
        return None

    async def no_approval(**_kw):
        raise AssertionError("a team worker must not file an approval")

    async def no_tx(_s):
        return None

    monkeypatch.setattr(d, "_record_risk_report", no_risk)
    monkeypatch.setattr(d, "_create_pr_approval", no_approval)
    monkeypatch.setattr(d, "_end_transaction", no_tx)

    await d._land_verified_work(run)

    handoff = run.result.metadata["handoff"]
    assert handoff["branch"] == f"lg/task-{task[:8]}"
    assert git(repo, "rev-parse", handoff["branch"]) == handoff["head_commit"]
    assert (
        git(repo, "diff", "--name-only", handoff["base_commit"], handoff["head_commit"]) == "b.py"
    )
    # A worker's worktree is never kept for continue_task.
    monkeypatch.setattr(settings, "driver_continue_enabled", True)
    run.session_ref = {"session_id": "s1", "driver": "fake"}
    assert await d._retain_for_continuation(run) is False


async def test_a_pinned_driver_that_is_not_available_fails_the_dispatch(monkeypatch):
    from life_graph.drivers import dispatcher as mod
    from life_graph.drivers.errors import DispatchError

    class _Off:
        name = "codex"

        async def available(self):
            return False

    monkeypatch.setattr(
        mod.driver_registry, "get", lambda name: _Off() if name == "codex" else None
    )
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    with pytest.raises(DispatchError):
        await d._pinned_task_driver("codex")
    with pytest.raises(DispatchError):
        await d._pinned_task_driver("nope")
