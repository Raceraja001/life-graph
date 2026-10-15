"""dispatch_task must try mechanical_autofix before spending a real bounce
(a second driver call) on a lint failure a formatter can resolve for free.
"""

from __future__ import annotations

import subprocess
import uuid

import pytest

import life_graph.drivers.dispatcher as disp_mod
from life_graph.core.budget import BudgetDecision
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher
from life_graph.services import verifiers as verifiers_mod
from tests.unit.test_mechanical_autofix import _real_ruff_path


class _FakeResult:
    def scalar(self):
        return 0

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


class _WritesAnUnusedImportDriver:
    """Simulates a driver that leaves an autofixable lint issue behind."""

    name = "sloppy"

    def __init__(self):
        self.dispatch_count = 0

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        self.dispatch_count += 1
        (workdir / "new.py").write_text("import os\n\nx = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "new.py"], cwd=str(workdir), check=True, capture_output=True)
        return DriverResult(success=True, output="added new.py", cost_usd=0.0)


async def _noop(*_a, **_k):
    return None


async def _allow(*_a, **_k):
    return BudgetDecision(
        allowed=True, throttled=False, reason="ok",
        spent_usd=0.0, cap_usd=10.0, remaining_usd=10.0,
    )


def _wire(disp, monkeypatch, driver, real_project_path):
    async def _packet(*_a, **kwargs):
        return ContextPacket(
            task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
            instruction="add a module", project_context={"path": real_project_path},
        )

    async def _pick(*_a, **_k):
        return driver

    monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
    monkeypatch.setattr(disp, "_select_driver", _pick)
    monkeypatch.setattr(disp, "_emit", _noop)
    monkeypatch.setattr(disp, "_record_stats", _noop)
    monkeypatch.setattr(disp, "_record_verification", _noop)
    monkeypatch.setattr(disp_mod.governor, "authorize", _allow)
    monkeypatch.setattr(disp_mod.governor, "record", _noop)
    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: False)


@pytest.mark.asyncio
async def test_autofixable_lint_failure_never_bounces(tmp_path, monkeypatch):
    real_ruff = _real_ruff_path()
    if real_ruff is None:
        pytest.skip("no ruff binary available in this environment")

    real_repo = tmp_path / "repo"
    real_repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(real_repo), check=True, capture_output=True)
    (real_repo / ".venv" / "bin").mkdir(parents=True)
    import os

    os.symlink(real_ruff, real_repo / ".venv" / "bin" / "ruff")
    # Committed, not left untracked: `isolate_workdir=True` runs the driver
    # and the verifier chain in a separate git WORKTREE, which only sees
    # files that are part of history — an untracked .venv in the main
    # checkout would simply not exist there.
    subprocess.run(["git", "add", "-A"], cwd=str(real_repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "-m", "init with a ruff binary"],
        cwd=str(real_repo), check=True, capture_output=True,
    )

    driver = _WritesAnUnusedImportDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver, str(real_repo))

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="add a module",
        project_id=str(uuid.uuid4()), isolate_workdir=True,
        verify_chain=["lint_clean_diff"],
    )

    # Passed WITHOUT a second driver call: the auto-fix pass resolved the
    # lint failure the driver's (simulated) sloppy edit left behind, so the
    # one-bounce rule never fired.
    assert result.success is True
    assert driver.dispatch_count == 1
