"""dispatch_task must resolve ONE workdir and hand it to both the driver
and the verifier chain — a verifier chain checking a different directory
than the one the driver wrote to verifies nothing (the bug this plan
closes: build_ok/lint_clean checking an always-empty scratch dir).
"""

from __future__ import annotations

import subprocess
import uuid

import pytest

import life_graph.drivers.dispatcher as disp_mod
from life_graph.core.budget import BudgetDecision
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher


class _FakeResult:
    def __init__(self, count: int = 0):
        self._count = count

    def scalar(self):
        return self._count

    def scalar_one_or_none(self):
        return None


class _FakeSession:
    async def execute(self, _stmt):
        return _FakeResult()

    def add(self, _obj):
        pass

    async def close(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


class _SpyDriver:
    name = "spy"

    def __init__(self):
        self.workdir_seen = None
        # Captured DURING dispatch (before dispatch_task's own `finally`
        # removes the worktree) — asserting on this rather than re-checking
        # the filesystem after `dispatch_task` returns, since the worktree
        # cleanup runs inside that same call before control comes back here.
        self.had_git_dir = None

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        self.workdir_seen = workdir
        self.had_git_dir = (workdir / ".git").exists()
        return DriverResult(success=True, output="ran", cost_usd=0.0)


async def _noop(*_a, **_k):
    return None


async def _allow(*_a, **_k):
    return BudgetDecision(
        allowed=True, throttled=False, reason="ok",
        spent_usd=0.0, cap_usd=10.0, remaining_usd=10.0,
    )


def _wire(disp, monkeypatch, driver, real_project_path=None):
    async def _packet(*_a, **kwargs):
        ctx = {"path": real_project_path} if real_project_path else {}
        return ContextPacket(
            task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
            instruction="fix it", project_context=ctx,
        )

    async def _pick(*_a, **_k):
        return driver

    monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
    monkeypatch.setattr(disp, "_select_driver", _pick)
    monkeypatch.setattr(disp, "_emit", _noop)
    monkeypatch.setattr(disp, "_record_stats", _noop)
    monkeypatch.setattr(disp_mod.governor, "authorize", _allow)
    monkeypatch.setattr(disp_mod.governor, "record", _noop)


@pytest.mark.asyncio
async def test_isolate_workdir_false_is_byte_identical_to_today(monkeypatch):
    """Default behavior: no project, no isolation — scratch temp dir."""
    driver = _SpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver)

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="fix it",
        verify_chain=[],
    )

    assert result.success is True
    assert driver.workdir_seen is not None
    assert driver.workdir_seen.is_dir()


@pytest.mark.asyncio
async def test_isolate_workdir_true_with_real_project_creates_worktree(tmp_path, monkeypatch):
    real_repo = tmp_path / "repo"
    real_repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(real_repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(real_repo), check=True, capture_output=True,
    )

    driver = _SpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver, real_project_path=str(real_repo))

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="fix it",
        project_id=str(uuid.uuid4()), isolate_workdir=True, verify_chain=[],
    )

    assert result.success is True
    assert driver.workdir_seen is not None
    # A real git worktree — verified while it existed (dispatch_task cleans
    # it up in its own `finally`, which runs before this call returns).
    assert driver.had_git_dir is True
    assert driver.workdir_seen != real_repo  # isolated, not the real repo dir
    # cleaned up after dispatch
    assert not driver.workdir_seen.exists()


@pytest.mark.asyncio
async def test_isolate_workdir_true_without_project_falls_back(monkeypatch):
    """isolate_workdir=True with no real project path is a no-op — today's
    scratch-dir behavior, not an error."""
    driver = _SpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver)  # no real_project_path

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="fix it",
        isolate_workdir=True, verify_chain=[],
    )

    assert result.success is True
    assert driver.workdir_seen is not None


# ── Double-isolation guard ───────────────────────────────────
#
# dispatch_task resolves the workdir itself, but a driver may ALSO call
# resolve_workdir on the packet it receives (ClaudeCodeDriver.dispatch does).
# If the packet still advertised the ORIGINAL project root with isolation
# still True, that second call would create a SECOND worktree nested inside
# the first one's scratch area, run there, and delete it — while the verifier
# chain checks the FIRST worktree, which the driver never touched. That is
# the founding bug of this whole branch, reintroduced.


class _ReResolvingSpyDriver:
    """Mirrors what ClaudeCodeDriver.dispatch actually does."""

    name = "re_resolving_spy"

    def __init__(self):
        self.workdir_seen = None
        self.cwd_seen = None
        self.second_worktree = None
        self.project_context_seen = None

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        from life_graph.drivers.workdir import resolve_workdir

        self.workdir_seen = workdir
        self.project_context_seen = dict(packet.project_context)
        cwd, worktree = await resolve_workdir(packet, workdir)
        self.cwd_seen = cwd
        self.second_worktree = worktree
        return DriverResult(success=True, output="ran", cost_usd=0.0)


@pytest.mark.asyncio
async def test_driver_that_re_resolves_the_packet_gets_the_same_dir(tmp_path, monkeypatch):
    real_repo = tmp_path / "repo"
    real_repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(real_repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(real_repo), check=True, capture_output=True,
    )

    driver = _ReResolvingSpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver, real_project_path=str(real_repo))

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="fix it",
        project_id=str(uuid.uuid4()), isolate_workdir=True, verify_chain=[],
    )

    assert result.success is True
    # The driver's own resolve_workdir was idempotent: same dir, no second
    # worktree created.
    assert driver.second_worktree is None
    assert driver.cwd_seen == driver.workdir_seen
    # And the packet described the ALREADY-resolved location.
    assert driver.project_context_seen["path"] == str(driver.workdir_seen)
    assert driver.project_context_seen["isolation"] is False
    # Cleanup still ran, from the origin repo (git refuses to delete a
    # worktree from inside it).
    assert not driver.workdir_seen.exists()
    remaining = subprocess.run(
        ["git", "worktree", "list"], cwd=str(real_repo),
        capture_output=True, text=True,
    )
    assert "wt_" not in remaining.stdout


@pytest.mark.asyncio
async def test_no_isolation_leaves_project_context_untouched(monkeypatch):
    """The mutation is guarded on a worktree actually having been created —
    a caller that never opted into isolation must keep its (empty) context,
    since LocalDriver gates a whole prompt section on `if project_context:`."""
    driver = _ReResolvingSpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver)  # no project path at all

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="fix it",
        verify_chain=[],
    )

    assert result.success is True
    assert driver.project_context_seen == {}


@pytest.mark.asyncio
async def test_isolation_failure_does_not_hand_the_driver_the_real_repo(
    tmp_path, monkeypatch
):
    """`git worktree add` fails (not a git repo) → the dispatch lands on the
    scratch dir, never on the live checkout."""
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()

    driver = _ReResolvingSpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver, real_project_path=str(not_a_repo))

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="fix it",
        project_id=str(uuid.uuid4()), isolate_workdir=True, verify_chain=[],
    )

    assert result.success is True
    assert driver.workdir_seen != not_a_repo
    assert driver.workdir_seen.is_dir()
