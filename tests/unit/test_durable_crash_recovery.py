"""Crash recovery across a restart: the stage trail is durable, and read.

tests/unit/test_durable_agent_execution.py covers execution_guard's helpers in
isolation and tests/unit/test_dispatcher_execution_guard.py pins that a
dispatch records its stages *in memory*. What this file pins is the part that
only matters to a process that has already died:

1. ``TaskDispatcher._persist_checkpoint`` flushes the trail to the task row at
   every stage, so a restarted process can read how far the run actually got.
2. ``dev_tasks.fail_interrupted`` reads that trail instead of blindly
   re-queueing -- work that already landed is not redone, and a run that had
   already passed verification is not sent back through a paid LLM dispatch.
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime

import pytest

import life_graph.drivers.dispatcher as disp_mod
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher
from life_graph.drivers.execution_guard import (
    ORDERED_DISPATCH_STAGES,
    ExecutionCheckpointTracker,
)
from life_graph.models.db import AgentTask
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev.verifiers import VerifierResult


def _trail(*stages: str) -> dict:
    """The persisted checkpoint dict a crash would have left behind."""
    tracker = ExecutionCheckpointTracker(task_id=str(uuid.uuid4()), tenant_id="t1")
    for stage in stages:
        tracker.record_stage(stage)
    return tracker.to_dict()


# ── 1. the trail reaches the database ────────────────────────────────────


class _Row:
    """Minimal stand-in for the agent_tasks row the checkpoints land in."""

    def __init__(self) -> None:
        self.properties: dict | None = {"kind": dev_tasks.KIND}


class _Store:
    """Records one snapshot per distinct stage written to the row."""

    def __init__(self) -> None:
        self.row = _Row()
        self.stages: list[str] = []
        self.trails: list[dict] = []

    def snapshot(self) -> None:
        trail = (self.row.properties or {}).get("checkpoints")
        stage = (trail or {}).get("last_completed_stage")
        if stage and (not self.stages or self.stages[-1] != stage):
            self.stages.append(stage)
            self.trails.append(copy.deepcopy(trail))


class _Scalar:
    def __init__(self, row) -> None:
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _Session:
    """Both sessions the dispatcher asks the factory for.

    ``dispatch_task`` uses the object directly; ``_persist_checkpoint`` enters
    it as an async context manager. One class serves both so a single factory
    can stand in for ``async_sessionmaker``.
    """

    def __init__(self, store: _Store, *, row: _Row | None = None) -> None:
        self._store = store
        self._row = row if row is not None else store.row

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    async def execute(self, stmt) -> _Scalar:
        # The checkpoint write is the only query the pipeline is not stubbed
        # out of, and it must stay scoped to the run's own tenant.
        where = str(stmt.whereclause)
        assert "agent_tasks.tenant_id" in where, f"unscoped checkpoint query: {where}"
        return _Scalar(self._row)

    def add(self, _obj) -> None:
        pass

    async def commit(self) -> None:
        self._store.snapshot()

    async def rollback(self) -> None:
        pass

    async def close(self) -> None:
        pass


async def _noop(*_a, **_k):
    return None


async def _allow(*_a, **_k):
    from life_graph.core.budget import BudgetDecision

    return BudgetDecision(
        allowed=True,
        throttled=False,
        reason="ok",
        spent_usd=0.0,
        cap_usd=10.0,
        remaining_usd=10.0,
    )


class _Driver:
    name = "spy"

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        return DriverResult(success=True, output="did it", cost_usd=0.0)


class _Chain:
    async def run_chain(self, names, workdir, context):
        return [VerifierResult("lint", True, {})]

    def all_passed(self, results):
        return all(r.passed and not r.inconclusive for r in results)

    @staticmethod
    def inconclusive(results):
        return [r for r in results if r.inconclusive]


class _Reviewer:
    async def review(self, task_type, instruction, diff_text):
        from dataclasses import dataclass

        @dataclass
        class _V:
            ran: bool = False
            approved: bool = True
            concern: str | None = None

        return _V()


class _Worktree:
    """Truthy stand-in for a resolved git worktree handle."""


def _wire(monkeypatch, disp: TaskDispatcher) -> None:
    async def _packet(*_a, **_k):
        return ContextPacket(
            task_id=uuid.uuid4(),
            tenant_id="t1",
            task_type="code",
            instruction="fix it",
            project_context={"path": "/tmp/origin-repo"},
        )

    async def _pick(*_a, **_k):
        return _Driver()

    async def _diff(_workdir):
        return "diff --git a/life_graph/main.py b/life_graph/main.py\n+x = 1\n"

    async def _landed(**_k):
        return "lg/task-branch"

    async def _resolve(_packet, scratch):
        return scratch, _Worktree()

    monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
    monkeypatch.setattr(disp, "_select_driver", _pick)
    for name in (
        "_load_persona",
        "_check_wip_limits",
        "_emit",
        "_emit_steps",
        "_record_stats",
        "_record_verification",
        "_create_approval_entry",
        "_create_pr_approval",
        "_bounce_task",
    ):
        monkeypatch.setattr(disp, name, _noop)
    monkeypatch.setattr(disp_mod.governor, "authorize", _allow)
    monkeypatch.setattr(disp_mod.governor, "record", _noop)
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain())
    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    monkeypatch.setattr(disp_mod, "resolve_workdir", _resolve)
    monkeypatch.setattr(disp_mod, "remove_worktree", _noop)
    monkeypatch.setattr(disp_mod, "worktree_intact", lambda *_a, **_k: True)
    monkeypatch.setattr(disp_mod, "preserve_verified_work", _landed)
    monkeypatch.setattr(disp_mod, "_code_context", _noop)


@pytest.mark.asyncio
async def test_every_dispatch_stage_is_flushed_to_the_task_row(monkeypatch):
    """The in-memory tracker is useless to a restarted process: it must be written."""
    store = _Store()
    disp = TaskDispatcher(
        session_factory=lambda: _Session(store), event_bus=None, reviewer=_Reviewer()
    )
    _wire(monkeypatch, disp)

    result = await disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="fix it",
        task_type="code",
        project_id=str(uuid.uuid4()),
        verify_chain=["tests_pass"],
    )

    assert result.success is True
    # One write per stage, in pipeline order -- a crash after any of them
    # leaves the row saying exactly how far the run got.
    assert store.stages == list(ORDERED_DISPATCH_STAGES)
    # Each write carries the whole trail so far, not just the latest stage.
    assert [c["stage"] for c in store.trails[-1]["checkpoints"]] == list(ORDERED_DISPATCH_STAGES)
    assert store.trails[2]["last_completed_stage"] == "driver_executed"
    assert len(store.trails[2]["checkpoints"]) == 3
    assert store.row.properties["kind"] == dev_tasks.KIND  # untouched keys survive


@pytest.mark.asyncio
async def test_persisting_checkpoints_never_breaks_the_dispatch(monkeypatch, caplog):
    """A dispatch is not worth failing over a bookkeeping write."""
    store = _Store()

    class _Broken(_Session):
        async def execute(self, _stmt):
            raise RuntimeError("database is gone")

    disp = TaskDispatcher(
        session_factory=lambda: _Broken(store), event_bus=None, reviewer=_Reviewer()
    )
    _wire(monkeypatch, disp)

    result = await disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="fix it",
        task_type="code",
        project_id=str(uuid.uuid4()),
        verify_chain=["tests_pass"],
    )

    assert result.success is True
    assert store.stages == []
    assert "Could not persist dispatch checkpoints" in caplog.text


@pytest.mark.asyncio
async def test_a_dispatch_with_no_task_row_writes_nothing(monkeypatch):
    """The test endpoint dispatches throwaway ids that have no agent_tasks row."""
    store = _Store()

    class _Empty(_Session):
        async def execute(self, _stmt) -> _Scalar:
            return _Scalar(None)

    disp = TaskDispatcher(
        session_factory=lambda: _Empty(store), event_bus=None, reviewer=_Reviewer()
    )
    _wire(monkeypatch, disp)

    result = await disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="fix it",
        task_type="code",
        project_id=str(uuid.uuid4()),
        verify_chain=["tests_pass"],
    )

    assert result.success is True
    assert store.row.properties == {"kind": dev_tasks.KIND}


# ── 2. the restart reads the trail ───────────────────────────────────────


class _RecoveryResult:
    def __init__(self, rows: list[AgentTask]) -> None:
        self._rows = rows

    def scalars(self) -> _RecoveryResult:
        return self

    def all(self) -> list[AgentTask]:
        return self._rows


class _RecoverySession:
    def __init__(self, rows: list[AgentTask]) -> None:
        self.rows = rows
        self.commits = 0

    async def __aenter__(self) -> _RecoverySession:
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    async def execute(self, _stmt) -> _RecoveryResult:
        return _RecoveryResult(self.rows)

    async def commit(self) -> None:
        self.commits += 1


def _abandoned(properties: dict, *, status: str = "running") -> AgentTask:
    return AgentTask(
        id=uuid.uuid4(),
        tenant_id="t1",
        agent_name=dev_tasks.AGENT_NAME,
        title="fix it",
        status=status,
        started_at=datetime.now(UTC),
        properties={"kind": dev_tasks.KIND, "instruction": "fix it", **properties},
        status_history=[{"status": "running", "at": datetime.now(UTC).isoformat()}],
    )


async def _recover(task: AgentTask) -> tuple[int, _RecoverySession]:
    session = _RecoverySession([task])
    failed = await dev_tasks.fail_interrupted(lambda: session)
    assert session.commits == 1
    return failed, session


@pytest.mark.asyncio
async def test_work_that_already_landed_is_completed_not_redone():
    """The branch and the PR approval are already there; re-dispatching would duplicate them."""
    task = _abandoned({"checkpoints": _trail("prepared", "driver_executed", "landed")})

    failed, _ = await _recover(task)

    assert failed == 0
    assert task.status == "completed"
    assert task.completed_at is not None
    assert task.status_history[-1]["note"] == "already landed before restart"
    # Nothing was queued and no re-queue was spent on it.
    assert "interrupt_requeues" not in task.properties
    assert task.properties.get("run_mode") is None


@pytest.mark.asyncio
async def test_a_finished_dispatch_is_also_left_alone():
    task = _abandoned({"checkpoints": _trail("prepared", "landed", "finished")})

    failed, _ = await _recover(task)

    assert failed == 0
    assert task.status == "completed"


@pytest.mark.asyncio
async def test_a_verified_run_is_re_queued_to_land_only():
    """Verification passed before the crash -- landing it again must not cost a second LLM dispatch."""
    task = _abandoned(
        {
            "checkpoints": _trail(
                "prepared", "driver_executed", "files_checked", "verifier_completed"
            )
        }
    )

    failed, _ = await _recover(task)

    assert failed == 0
    assert task.status == "queued"
    assert task.started_at is None
    assert task.properties["run_mode"] == dev_tasks.QUEUE_MODE
    assert task.properties["interrupt_requeues"] == 1
    assert task.properties["resume_action"] == "land_only"
    assert task.properties["checkpoint"]["stage"] == "land_only"
    # Honest: the task is re-run today (land-only resume is work-order Stage 3).
    assert "re-run from the start" in task.properties["checkpoint"]["resume_instructions"]
    assert task.status_history[-1]["note"] == "re-queued to land verified changes after restart"


@pytest.mark.asyncio
async def test_a_crash_before_verification_is_re_dispatched_in_a_clean_worktree():
    task = _abandoned(
        {
            "checkpoints": _trail("prepared", "budget_checked", "driver_executed"),
            "routed_from": "code-fixer-local",
        }
    )
    task.assigned_agent = "cloud-coder"

    failed, _ = await _recover(task)

    assert failed == 0
    assert task.status == "queued"
    assert task.properties["checkpoint"]["stage"] == "re_dispatch_in_clean_worktree"
    assert "resume_action" not in task.properties
    assert task.status_history[-1]["note"] == "re-queued after an API restart"
    # The cloud route was for that one run: it is routed afresh.
    assert task.assigned_agent == "code-fixer-local"
    assert "routed_from" not in task.properties


@pytest.mark.asyncio
async def test_a_task_with_no_trail_at_all_starts_fresh():
    """Rows written before checkpoints existed, and runs that died before stage one."""
    task = _abandoned({})

    failed, _ = await _recover(task)

    assert failed == 0
    assert task.status == "queued"
    assert task.properties["interrupt_requeues"] == 1
    assert task.properties["checkpoint"]["stage"] == "re_dispatch_in_clean_worktree"


@pytest.mark.asyncio
async def test_a_task_out_of_re_queues_is_failed():
    task = _abandoned(
        {
            "checkpoints": _trail("prepared", "driver_executed"),
            "interrupt_requeues": dev_tasks.INTERRUPT_REQUEUES,
        }
    )

    failed, _ = await _recover(task)

    assert failed == 1
    assert task.status == "failed"
    assert task.error == dev_tasks._INTERRUPTED
    assert task.completed_at is not None
    assert task.properties["interrupt_requeues"] == dev_tasks.INTERRUPT_REQUEUES


@pytest.mark.asyncio
async def test_landed_work_is_completed_even_with_no_re_queues_left():
    """The "already landed" verdict outranks the retry budget: there is nothing to retry."""
    task = _abandoned(
        {
            "checkpoints": _trail("prepared", "landed"),
            "interrupt_requeues": dev_tasks.INTERRUPT_REQUEUES,
        }
    )

    failed, _ = await _recover(task)

    assert failed == 0
    assert task.status == "completed"


# ── 3. the checkpoint says what the stage decided, not only that it ran ──


def _trail_with(*stages: tuple[str, bool]) -> dict:
    tracker = ExecutionCheckpointTracker(task_id=str(uuid.uuid4()), tenant_id="t1")
    for stage, ok in stages:
        tracker.record_stage(stage, ok=ok)
    return tracker.to_dict()


@pytest.mark.asyncio
async def test_a_failed_verification_is_not_read_as_verified_work():
    """verifier_completed used to be recorded whatever the verdict; a failed
    check then read as 'verified' after a restart."""
    trail = _trail_with(
        ("prepared", True), ("driver_executed", True), ("files_checked", True),
        ("verifier_completed", False),
    )  # fmt: skip
    task = _abandoned({"checkpoints": trail})

    failed, _ = await _recover(task)

    assert failed == 0
    assert task.status == "queued"
    assert task.properties.get("resume_action") is None
    assert task.properties["checkpoint"]["stage"] == "re_dispatch_in_clean_worktree"


@pytest.mark.asyncio
async def test_a_dispatch_that_finished_failing_stays_failed():
    """'finished' was recorded before the row's final status; a crash in between
    turned a failed dispatch into 'completed'."""
    trail = _trail_with(("prepared", True), ("verifier_completed", False), ("finished", False))
    task = _abandoned({"checkpoints": trail})

    failed, _ = await _recover(task)

    assert failed == 1
    assert task.status == "failed"
    assert "interrupt_requeues" not in task.properties


@pytest.mark.asyncio
async def test_a_dispatch_that_finished_succeeding_is_still_completed():
    trail = _trail_with(("prepared", True), ("landed", True), ("finished", True))
    task = _abandoned({"checkpoints": trail})

    failed, _ = await _recover(task)

    assert failed == 0
    assert task.status == "completed"
