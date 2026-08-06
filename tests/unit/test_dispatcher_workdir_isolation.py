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
