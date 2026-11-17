"""The durable execution guard and the strict personal-data route, as wired in.

tests/unit/test_durable_agent_execution.py covers execution_guard.py's helpers
in isolation; tests/unit/test_local_model_infrastructure.py covers the local
model registry's own routing. This file pins the *integration*: that
dispatch_task actually drives the checkpoint tracker through its stages, that
the independent-completion gate can veto a dispatch the driver and the verifier
chain both called a success, and that compute_router.decide never answers
"cloud" for a task carrying personal data.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

import life_graph.drivers.dispatcher as disp_mod
import life_graph.services.compute_router as router_mod
from life_graph.core.budget import BudgetDecision
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher, _changed_paths
from life_graph.drivers.execution_guard import ORDERED_DISPATCH_STAGES
from life_graph.services.compute_router import (
    CLOUD_PERSONA,
    OPENCODE_PERSONA,
    Snapshot,
    carries_personal_data,
    decide,
)
from life_graph.services.dev.verifiers import VerifierResult


class _Session:
    async def execute(self, _stmt):
        raise AssertionError("no query expected: every DB step is stubbed")

    def add(self, _obj):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def close(self):
        pass


class _Driver:
    """A driver that reports whatever success it is told to report."""

    name = "spy"

    def __init__(self, result: DriverResult | None = None):
        self._result = result or DriverResult(success=True, output="did it", cost_usd=0.0)

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        return self._result


@dataclass
class _Verdict:
    ran: bool
    approved: bool
    concern: str | None = None


class _Reviewer:
    def __init__(self, verdict: _Verdict | None = None):
        self.verdict = verdict or _Verdict(ran=False, approved=True)

    async def review(self, task_type, instruction, diff_text):
        return self.verdict


class _Chain:
    """Stands in for the module's verifier_chain with fixed results."""

    def __init__(self, results: list[VerifierResult]):
        self.results = results

    async def run_chain(self, names, workdir, context):
        return self.results

    def all_passed(self, results):
        return all(r.passed and not r.inconclusive for r in results)

    @staticmethod
    def inconclusive(results):
        return [r for r in results if r.inconclusive]


class _SequencedChain(_Chain):
    """Returns a different verdict set per run_chain call (bounce sequences)."""

    def __init__(self, sequence: list[list[VerifierResult]]):
        super().__init__(sequence[0])
        self.sequence = sequence
        self.calls = 0

    async def run_chain(self, names, workdir, context):
        results = self.sequence[min(self.calls, len(self.sequence) - 1)]
        self.calls += 1
        return results


class _Worktree:
    """Truthy stand-in for a resolved git worktree handle."""


def _never_lands():
    """A preserve_verified_work stand-in that fails if anything tries to land."""

    async def _fail(**_k):
        raise AssertionError("unverified work must never be landed")

    return _fail


async def _noop(*_a, **_k):
    return None


async def _allow(*_a, **_k):
    return BudgetDecision(
        allowed=True,
        throttled=False,
        reason="ok",
        spent_usd=0.0,
        cap_usd=10.0,
        remaining_usd=10.0,
    )


@pytest.fixture
def wired(monkeypatch):
    """A dispatcher with every collaborator stubbed; captures the run it built."""
    captured: dict = {}

    def build(driver, *, worktree=None, reviewer=None, real_bounce=False):
        disp = TaskDispatcher(
            session_factory=lambda: _Session(),
            event_bus=None,
            reviewer=reviewer or _Reviewer(),
        )

        async def _packet(*_a, **_k):
            return ContextPacket(
                task_id=uuid.uuid4(),
                tenant_id="t1",
                task_type="code",
                instruction="fix it",
                project_context={"path": "/tmp/origin-repo"},
            )

        async def _pick(*_a, **_k):
            return driver

        # Capture the live _DispatchRun so its tracker can be inspected after
        # dispatch_task returns (the run itself is a local in dispatch_task).
        real_finish = disp._finish_dispatch

        async def _finish(run):
            captured["run"] = run
            return await real_finish(run)

        monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
        monkeypatch.setattr(disp, "_select_driver", _pick)
        monkeypatch.setattr(disp, "_load_persona", _noop)
        monkeypatch.setattr(disp, "_check_wip_limits", _noop)
        monkeypatch.setattr(disp, "_emit", _noop)
        monkeypatch.setattr(disp, "_emit_steps", _noop)
        monkeypatch.setattr(disp, "_record_stats", _noop)
        monkeypatch.setattr(disp, "_record_verification", _noop)
        monkeypatch.setattr(disp, "_create_approval_entry", _noop)
        monkeypatch.setattr(disp, "_create_pr_approval", _noop)
        if not real_bounce:
            monkeypatch.setattr(disp, "_bounce_task", _noop)
        monkeypatch.setattr(disp, "_finish_dispatch", _finish)
        monkeypatch.setattr(disp_mod.governor, "authorize", _allow)
        monkeypatch.setattr(disp_mod.governor, "record", _noop)

        # Step 4's workdir resolution, without touching a real repository.
        async def _resolve(_packet, scratch):
            return scratch, worktree

        monkeypatch.setattr(disp_mod, "resolve_workdir", _resolve)
        monkeypatch.setattr(disp_mod, "remove_worktree", _noop)
        monkeypatch.setattr(disp_mod, "worktree_intact", lambda *_a, **_k: True)
        monkeypatch.setattr(disp_mod, "preserve_verified_work", _noop)
        monkeypatch.setattr(disp_mod, "_code_context", _noop)
        return disp

    return build, captured


def _dispatch(disp, **kw):
    return disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="fix it",
        verify_chain=kw.pop("verify_chain", ["tests_pass"]),
        **kw,
    )


def _stages(run) -> list[str]:
    assert run.tracker is not None, "every dispatch must carry a checkpoint tracker"
    return [c.stage for c in run.tracker.checkpoints]


# ── 1. the checkpoint trail ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_dispatch_records_its_stage_checkpoints_in_order(wired, monkeypatch):
    build, captured = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([VerifierResult("lint", True, {})]))

    async def _diff(_workdir):
        return "diff --git a/life_graph/main.py b/life_graph/main.py\n+x = 1\n"

    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    worktree = _Worktree()
    disp = build(_Driver(), worktree=worktree)

    async def _landed(**_k):
        return "lg/task-branch"

    monkeypatch.setattr(disp_mod, "preserve_verified_work", _landed)

    result = await _dispatch(disp, task_type="code", project_id=str(uuid.uuid4()))

    assert result.success is True
    run = captured["run"]
    stages = _stages(run)
    assert stages == [
        "prepared",
        "budget_checked",
        "driver_executed",
        "worktree_verified",
        "files_checked",
        "verifier_completed",
        "landed",
        "finished",
    ]
    # Recorded in the canonical order the recovery logic reads them in.
    order = {s: i for i, s in enumerate(ORDERED_DISPATCH_STAGES)}
    assert [order[s] for s in stages] == sorted(order[s] for s in stages)
    assert run.tracker.last_completed_stage == "finished"


@pytest.mark.asyncio
async def test_checkpoints_carry_the_evidence_each_stage_observed(wired, monkeypatch):
    build, captured = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([VerifierResult("lint", True, {})]))

    async def _diff(_workdir):
        return "diff --git a/a.py b/a.py\n"

    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    disp = build(_Driver(), worktree=_Worktree())

    await _dispatch(disp, task_type="code", cost_cap_usd=2.5)

    state = captured["run"].tracker.to_dict()
    by_stage = {c["stage"]: c for c in state["checkpoints"]}
    assert by_stage["budget_checked"]["metadata"] == {"cost_cap_usd": 2.5}
    assert by_stage["driver_executed"]["metadata"] == {"success": True}
    assert by_stage["worktree_verified"]["metadata"]["workdir"]
    assert state["task_id"] and state["tenant_id"] == "t1"


@pytest.mark.asyncio
async def test_a_tampered_worktree_records_a_failed_checkpoint(wired, monkeypatch):
    build, captured = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([VerifierResult("lint", True, {})]))

    async def _diff(_workdir):
        return "diff --git a/a.py b/a.py\n"

    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    disp = build(_Driver(), worktree=_Worktree())
    # After build(): the fixture wires the intact case, this test is the other one.
    monkeypatch.setattr(disp_mod, "worktree_intact", lambda *_a, **_k: False)
    monkeypatch.setattr(disp_mod, "preserve_verified_work", _never_lands())

    result = await _dispatch(disp, task_type="code", project_id=str(uuid.uuid4()))

    assert result.success is False
    assert result.metadata["worktree_tampered"] is True
    run = captured["run"]
    tamper = next(c for c in run.tracker.checkpoints if c.stage == "worktree_verified")
    assert tamper.ok is False
    assert tamper.metadata["tampered"] is True
    # A failed checkpoint is not a completed stage.
    assert run.tracker.last_completed_stage != "worktree_verified"
    assert "landed" not in _stages(run)


# ── 2. the independent-completion gate ───────────────────────────────────


@pytest.mark.asyncio
async def test_a_code_task_that_changed_no_files_cannot_land_as_success(wired, monkeypatch):
    """The driver says it worked, the chain passes -- but nothing was written."""
    build, captured = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([VerifierResult("lint", True, {})]))

    async def _empty_diff(_workdir):
        return ""

    monkeypatch.setattr(disp_mod, "diff_against_head", _empty_diff)
    disp = build(_Driver(DriverResult(success=True, output="all done!")), worktree=_Worktree())
    monkeypatch.setattr(disp_mod, "preserve_verified_work", _never_lands())

    result = await _dispatch(disp, task_type="code", project_id=str(uuid.uuid4()))

    assert result.success is False
    # Step 4c diagnoses this one ("nothing to verify or land"); the invariant
    # under test is that a self-reported success never reaches "landed".
    assert result.metadata["stop_reason"] == "no_change"
    run = captured["run"]
    assert run.files_changed == []
    assert "landed" not in _stages(run)


@pytest.mark.asyncio
async def test_a_bugfix_claiming_success_with_no_observed_diff_is_vetoed(wired, monkeypatch):
    """task_type="bugfix" is a code task to the guard but not to Step 4c.

    Step 4c only guards the literal "code"/"code_change" types, so this run
    reaches Step 5 still claiming success with no file list behind it. The
    independent-completion gate is the thing that stops it.
    """
    build, captured = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([VerifierResult("lint", True, {})]))

    async def _diff(_workdir):
        return ""

    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    disp = build(_Driver(DriverResult(success=True, output="fixed the bug")), worktree=_Worktree())
    monkeypatch.setattr(disp_mod, "preserve_verified_work", _never_lands())

    result = await _dispatch(disp, task_type="bugfix", project_id=str(uuid.uuid4()))

    assert result.success is False
    assert result.error == "code_task_modified_zero_files"
    assert result.metadata["independent_verification_failed"] == "code_task_modified_zero_files"
    assert result.metadata["needs_human"] is True
    run = captured["run"]
    assert "verifier_completed" in _stages(run)
    assert "landed" not in _stages(run)


@pytest.mark.asyncio
async def test_a_code_task_with_no_independent_verifier_is_vetoed(wired, monkeypatch):
    """A passing *empty* chain is not evidence: nobody checked the work."""
    build, captured = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([]))

    async def _diff(_workdir):
        return "diff --git a/a.py b/a.py\n"

    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    disp = build(_Driver(), worktree=_Worktree())
    monkeypatch.setattr(disp_mod, "preserve_verified_work", _never_lands())

    result = await _dispatch(disp, task_type="refactor", project_id=str(uuid.uuid4()))

    assert result.success is False
    assert result.error == "missing_independent_verifier_for_code_task"
    assert "landed" not in _stages(captured["run"])


@pytest.mark.asyncio
async def test_a_code_task_with_a_real_diff_and_a_passing_verifier_is_verified(wired, monkeypatch):
    """The gate is a gate, not a wall: real evidence still lands."""
    build, captured = wired
    monkeypatch.setattr(
        disp_mod, "verifier_chain", _Chain([VerifierResult("tests_pass", True, {})])
    )

    async def _diff(_workdir):
        return "diff --git a/life_graph/api/health.py b/life_graph/api/health.py\n-a\n+b\n"

    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    disp = build(_Driver(), worktree=_Worktree())

    async def _landed(**_k):
        return "lg/fix-branch"

    monkeypatch.setattr(disp_mod, "preserve_verified_work", _landed)

    result = await _dispatch(disp, task_type="code", project_id=str(uuid.uuid4()))

    assert result.success is True
    assert result.error is None
    assert result.metadata["landed_branch"] == "lg/fix-branch"
    run = captured["run"]
    assert run.files_changed == ["life_graph/api/health.py"]
    assert _stages(run)[-2:] == ["landed", "finished"]


@pytest.mark.asyncio
async def test_a_non_code_task_needs_no_file_changes(wired, monkeypatch):
    """A research/general task legitimately changes nothing."""
    build, _captured = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([VerifierResult("lint", True, {})]))
    disp = build(_Driver())

    result = await _dispatch(disp, task_type="general")

    assert result.success is True and result.output == "did it"


def test_changed_paths_reads_the_diff_git_headers():
    diff = (
        "diff --git a/life_graph/main.py b/life_graph/main.py\n"
        "index 1..2 100644\n"
        "--- a/life_graph/main.py\n"
        "+++ b/life_graph/main.py\n"
        "+x\n"
        "diff --git a/old/name.py b/new/name.py\n"
        "similarity index 90%\n"
    )
    assert _changed_paths(diff) == ["life_graph/main.py", "new/name.py"]
    assert _changed_paths("") == []
    assert _changed_paths("no headers here") == []
    # git quotes a path containing whitespace; the quotes are not part of it.
    assert _changed_paths('diff --git "a/a b.py" "b/a b.py"\n') == ["a b.py"]


@pytest.mark.asyncio
async def test_the_gate_weighs_the_bounce_verdicts_not_the_superseded_ones(wired, monkeypatch):
    """A bounce re-runs the driver and re-verifies; the gate must read those.

    Reading the pre-bounce failures instead would veto every task the
    one-bounce rule successfully rescued.
    """
    build, captured = wired
    chain = _SequencedChain(
        [
            [VerifierResult("lint_clean_diff", False, {"error": "E401"})],
            [VerifierResult("lint_clean_diff", True, {})],
        ]
    )
    monkeypatch.setattr(disp_mod, "verifier_chain", chain)

    async def _no_autofix(*_a, **_k):
        return {}

    monkeypatch.setattr(disp_mod, "mechanical_autofix", _no_autofix)

    async def _diff(_workdir):
        return "diff --git a/a.py b/a.py\n"

    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    disp = build(_Driver(), worktree=_Worktree(), real_bounce=True)

    async def _landed(**_k):
        return "lg/bounced"

    monkeypatch.setattr(disp_mod, "preserve_verified_work", _landed)

    result = await disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="fix it",
        task_type="code",
        verify_chain=["lint_clean_diff"],
    )

    assert result.success is True, result.error
    run = captured["run"]
    assert [r.verifier for r in run.verifier_results] == ["lint_clean_diff"]
    assert all(r.passed for r in run.verifier_results)


@pytest.mark.asyncio
async def test_a_bounce_that_undid_every_change_is_vetoed(wired, monkeypatch):
    """The file list is re-read after a bounce, not carried over from before it."""
    build, captured = wired
    chain = _SequencedChain(
        [
            [VerifierResult("lint_clean_diff", False, {"error": "E401"})],
            [VerifierResult("lint_clean_diff", True, {})],
        ]
    )

    async def _no_autofix(*_a, **_k):
        return {}

    diffs = ["diff --git a/a.py b/a.py\n", ""]

    async def _diff(_workdir):
        return diffs.pop(0) if diffs else ""

    disp = build(_Driver(), worktree=_Worktree(), real_bounce=True)
    monkeypatch.setattr(disp_mod, "verifier_chain", chain)
    monkeypatch.setattr(disp_mod, "mechanical_autofix", _no_autofix)
    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    monkeypatch.setattr(disp_mod, "preserve_verified_work", _never_lands())

    result = await disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="fix it",
        task_type="code",
        verify_chain=["lint_clean_diff"],
    )

    assert result.success is False
    assert result.error == "code_task_modified_zero_files"
    assert captured["run"].files_changed == []


@pytest.mark.asyncio
async def test_a_code_task_with_no_worktree_still_needs_an_independent_verifier(wired, monkeypatch):
    """No worktree means no diff to read -- the verifier half of the gate stands."""
    build, captured = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([]))
    disp = build(_Driver())  # worktree=None

    result = await _dispatch(disp, task_type="code")

    assert result.success is False
    assert result.error == "missing_independent_verifier_for_code_task"
    assert captured["run"].files_changed is None


@pytest.mark.asyncio
async def test_an_unobservable_file_list_is_not_reported_as_an_empty_one(wired, monkeypatch):
    """A dispatch with no worktree is not vetoed for a file list nobody could read.

    "Not observed" is not evidence that the run changed nothing, and there is
    no worktree for _land_verified_work to land either way.
    """
    build, captured = wired
    monkeypatch.setattr(
        disp_mod, "verifier_chain", _Chain([VerifierResult("tests_pass", True, {})])
    )
    disp = build(_Driver())  # worktree=None

    result = await _dispatch(disp, task_type="code")

    assert result.success is True
    assert captured["run"].files_changed is None


# ── 3. strict local-only routing for personal data ───────────────────────


@pytest.fixture
def routing_on(monkeypatch):
    monkeypatch.setattr(router_mod.settings, "dev_route_queue", True)
    monkeypatch.setattr(router_mod.settings, "dev_local_hours", "")


def _snap(*, active: str | None, cloud: tuple[str, ...]) -> Snapshot:
    return Snapshot(active=active, local_hours=True, free_gb=32.0, cloud=cloud)


_FREE_CLOUD = ("openrouter/some-model:free", "nvidia_nim/other")


def test_carries_personal_data_reads_the_flag_and_the_task_kinds():
    assert carries_personal_data({"personal_data": True}) is True
    assert carries_personal_data({"task_kind": "personal_memory_extraction"}) is True
    assert carries_personal_data({"task_type": "episode_summarization"}) is True
    assert carries_personal_data({"task_kind": "dependency_bump"}) is False
    assert carries_personal_data({}) is False
    assert carries_personal_data(None) is False


@pytest.mark.parametrize(
    "props",
    [
        {"personal_data": True},
        {"task_kind": "personal_memory_extraction"},
        {"task_type": "personal_chat"},
        # local_only would have routed to "wait" anyway; personal data must
        # not depend on the caller also remembering to set it.
        {"personal_data": True, "interactive": True},
    ],
)
def test_personal_data_never_routes_to_cloud_while_the_user_is_active(routing_on, props):
    route = decide("code-fixer-local", props, _snap(active="chat 2 min ago", cloud=_FREE_CLOUD))

    assert route.where == "wait"
    assert route.persona == "code-fixer-local"
    assert "personal data never leaves the local machine" in route.reason


def test_personal_data_runs_locally_while_the_user_is_away(routing_on):
    route = decide(
        "code-fixer-local",
        {"task_kind": "personal_memory_extraction", "capability": "extraction"},
        _snap(active=None, cloud=_FREE_CLOUD),
    )

    assert route.where == "local"
    assert route.persona == "code-fixer-local"
    assert "local-only" in route.reason


def test_personal_data_waits_when_local_vram_is_constrained(routing_on):
    route = decide(
        "code-fixer-local",
        {"personal_data": True, "capability": "extraction", "vram_free_gb": 0.5},
        _snap(active=None, cloud=_FREE_CLOUD),
    )

    assert route.where == "wait"
    assert "personal data never leaves the local machine" in route.reason


def test_personal_data_is_refused_on_the_cloud_persona(routing_on):
    route = decide(CLOUD_PERSONA, {"personal_data": True}, _snap(active=None, cloud=_FREE_CLOUD))

    assert route.where == "wait"
    assert route.persona == CLOUD_PERSONA


def test_personal_data_is_never_cloud_under_any_snapshot(routing_on):
    """Exhaustive over the facts that make the non-personal path choose cloud."""
    for active in (None, "switch says active"):
        for cloud in ((), _FREE_CLOUD):
            for persona in ("code-fixer-local", OPENCODE_PERSONA, CLOUD_PERSONA):
                route = decide(persona, {"personal_data": True}, _snap(active=active, cloud=cloud))
                assert route.where != "cloud", (persona, active, cloud)
                assert route.persona != CLOUD_PERSONA or persona == CLOUD_PERSONA


def test_routing_disabled_still_keeps_personal_data_off_the_cloud(monkeypatch):
    monkeypatch.setattr(router_mod.settings, "dev_route_queue", False)
    route = decide(
        "code-fixer-local", {"personal_data": True}, _snap(active=None, cloud=_FREE_CLOUD)
    )

    assert route.where == "as_assigned"
    assert route.persona == "code-fixer-local"
    assert "personal data never leaves the local machine" in route.reason


def test_a_non_personal_task_still_reaches_the_free_cloud_model(routing_on):
    """The existing behaviour the personal-data branch must not have eaten."""
    route = decide(
        "code-fixer-local",
        {"task_kind": "dependency_bump"},
        _snap(active="voice", cloud=_FREE_CLOUD),
    )

    assert route.where == "cloud"
    assert route.persona == CLOUD_PERSONA
