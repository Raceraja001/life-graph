"""dispatch_task(task_type="plan"): a plan dispatch may only write a spec --
any file change bounces it, and a clean plan files a driver_plan approval
instead of landing/opening a PR.
"""

from __future__ import annotations

import subprocess
import uuid

import pytest

import life_graph.drivers.dispatcher as disp_mod
from life_graph.core.budget import BudgetDecision
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher, _parse_tasks


class _FakeResult:
    def scalar(self):
        return 0

    def scalar_one_or_none(self):
        return None


class _FakeSession:
    def __init__(self):
        self.added = []

    async def execute(self, _stmt):
        return _FakeResult()

    def add(self, obj):
        self.added.append(obj)

    async def close(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass

    def begin_nested(self):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _cm():
            yield

        return _cm()


def _init_repo(path):
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init"],
        cwd=str(path), check=True, capture_output=True,
    )


class _PlanDriver:
    """Writes only a spec in its narrative output -- no file changes."""

    name = "planner"

    def __init__(self, output: str):
        self._output = output
        self.dispatch_count = 0

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        self.dispatch_count += 1
        return DriverResult(success=True, output=self._output, cost_usd=0.0)


class _SloppyPlanDriver:
    """Ignores the "don't touch files" instruction on its first attempt,
    behaves on the (bounced) retry."""

    name = "sloppy-planner"

    def __init__(self, output: str):
        self._output = output
        self.dispatch_count = 0

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        self.dispatch_count += 1
        if self.dispatch_count == 1:
            (workdir / "oops.py").write_text("x = 1\n", encoding="utf-8")
        return DriverResult(success=True, output=self._output, cost_usd=0.0)


async def _noop(*_a, **_k):
    return None


async def _allow(*_a, **_k):
    return BudgetDecision(
        allowed=True, throttled=False, reason="ok",
        spent_usd=0.0, cap_usd=10.0, remaining_usd=10.0,
    )


def _wire(disp, monkeypatch, driver, repo_path):
    async def _packet(*_a, **kwargs):
        return ContextPacket(
            task_id=uuid.uuid4(), tenant_id="t1", task_type="plan",
            instruction="Add a helper function", project_context={"path": str(repo_path)},
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


_SPEC_OUTPUT = (
    "## Spec\n**Requirements:** must not break callers.\n"
    "**Tasks:** 1. add function 2. add test\n"
)


# ── _parse_tasks: the spec's Tasks list -> child task instructions ──


def test_parse_tasks_inline_numbering():
    spec = "**Requirements:** x.\n**Tasks:** 1. Add the function 2. Add a test 3. Update docs"
    assert _parse_tasks(spec) == ["Add the function", "Add a test", "Update docs"]


def test_parse_tasks_multiline_numbering():
    spec = "**Tasks:**\n1. Add the function\n2. Add a test\n3. Update docs\n"
    assert _parse_tasks(spec) == ["Add the function", "Add a test", "Update docs"]


def test_parse_tasks_stops_at_a_trailing_heading():
    spec = "**Tasks:** 1. Add the function 2. Add a test\n**Design notes:** irrelevant here"
    assert _parse_tasks(spec) == ["Add the function", "Add a test"]


def test_parse_tasks_single_item():
    spec = "**Tasks:** 1. Just this one thing"
    assert _parse_tasks(spec) == ["Just this one thing"]


def test_parse_tasks_no_tasks_section_returns_empty():
    assert _parse_tasks("**Requirements:** x.\n**Design:** y.") == []


def test_parse_tasks_none_or_empty_returns_empty():
    assert _parse_tasks(None) == []
    assert _parse_tasks("") == []


@pytest.mark.asyncio
async def test_clean_plan_files_a_driver_plan_approval(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    driver = _PlanDriver(_SPEC_OUTPUT)
    session = _FakeSession()
    disp = TaskDispatcher(session_factory=lambda: session, event_bus=None)
    _wire(disp, monkeypatch, driver, repo)

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="Add a helper function",
        project_id=str(uuid.uuid4()), isolate_workdir=True, task_type="plan",
        verify_chain=["no_diff_in_plan"], session=session,
    )

    assert result.success is True
    assert driver.dispatch_count == 1  # no bounce needed
    from life_graph.drivers.dispatcher import _extract_spec

    expected_spec = _extract_spec(_SPEC_OUTPUT)
    assert result.metadata["spec"] == expected_spec
    plans = [a for a in session.added if getattr(a, "kind", None) == "driver_plan"]
    assert len(plans) == 1
    assert plans[0].payload["spec"] == expected_spec
    assert plans[0].payload["project_id"]


@pytest.mark.asyncio
async def test_touching_a_file_bounces_then_escalates_if_still_sloppy(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    # Both attempts touch a file -- the bounce should NOT help, and no
    # driver_plan approval should ever be filed for work that broke the rule.
    class _AlwaysSloppy(_SloppyPlanDriver):
        async def dispatch(self, packet, workdir, timeout=300):
            self.dispatch_count += 1
            (workdir / f"oops{self.dispatch_count}.py").write_text("x = 1\n", encoding="utf-8")
            return DriverResult(success=True, output=self._output, cost_usd=0.0)

    driver = _AlwaysSloppy(_SPEC_OUTPUT)
    session = _FakeSession()
    disp = TaskDispatcher(session_factory=lambda: session, event_bus=None)
    _wire(disp, monkeypatch, driver, repo)

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="Add a helper function",
        project_id=str(uuid.uuid4()), isolate_workdir=True, task_type="plan",
        verify_chain=["no_diff_in_plan"], session=session,
    )

    assert result.success is False
    assert driver.dispatch_count == 2  # one bounce, then gave up
    assert result.metadata["needs_human"] is True
    assert not [a for a in session.added if getattr(a, "kind", None) == "driver_plan"]


@pytest.mark.asyncio
async def test_no_spec_section_fails_even_with_no_file_changes(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    driver = _PlanDriver("I looked at the code and it seems fine.")
    session = _FakeSession()
    disp = TaskDispatcher(session_factory=lambda: session, event_bus=None)
    _wire(disp, monkeypatch, driver, repo)

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="Add a helper function",
        project_id=str(uuid.uuid4()), isolate_workdir=True, task_type="plan",
        verify_chain=["no_diff_in_plan"], session=session,
    )

    assert result.success is False
    assert "no '## Spec'" in result.error
    assert not [a for a in session.added if getattr(a, "kind", None) == "driver_plan"]
