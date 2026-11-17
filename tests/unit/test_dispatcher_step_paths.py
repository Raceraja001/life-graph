"""dispatch_task outcomes that no other unit test reached.

Written when dispatch_task was split into step methods (one _DispatchRun
carried between them). These four paths had no unit coverage, so they pin
what each one produces -- error text, metadata, approvals filed, events,
and what is NOT done afterwards -- and passed unchanged on the code before
and after the split:

- a check that could not run escalates without a bounce
- a second-opinion dissent blocks landing
- a driver that rewrote the worktree's .git link is neither verified nor landed
- an exception rolls back and closes a session the dispatcher opened
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

import life_graph.drivers.dispatcher as disp_mod
from life_graph.core.budget import BudgetDecision
from life_graph.core.events import EventType
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher
from life_graph.services.dev.verifiers import VerifierResult


class _Session:
    def __init__(self):
        self.calls: list[str] = []

    async def execute(self, _stmt):
        raise AssertionError("no query expected: every DB step is stubbed")

    def add(self, _obj):
        pass

    async def commit(self):
        self.calls.append("commit")

    async def rollback(self):
        self.calls.append("rollback")

    async def close(self):
        self.calls.append("close")


class _Driver:
    name = "spy"

    def __init__(self, result: DriverResult | None = None, error: Exception | None = None):
        self._result = result or DriverResult(success=True, output="did it", cost_usd=0.0)
        self._error = error

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        if self._error is not None:
            raise self._error
        return self._result


@dataclass
class _Verdict:
    ran: bool
    approved: bool
    concern: str | None = None


class _Reviewer:
    def __init__(self, verdict: _Verdict):
        self.verdict = verdict

    async def review(self, task_type, instruction, diff_text):
        return self.verdict


class _Chain:
    """Stands in for the module's verifier_chain with fixed results."""

    def __init__(self, results: list[VerifierResult]):
        self.results = results
        self.runs = 0

    async def run_chain(self, names, workdir, context):
        self.runs += 1
        return self.results

    def all_passed(self, results):
        return all(r.passed and not r.inconclusive for r in results)

    @staticmethod
    def inconclusive(results):
        return [r for r in results if r.inconclusive]


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


def _must_not_run(what):
    async def _fail(*_a, **_k):
        raise AssertionError(f"{what} must not run on this path")

    return _fail


@pytest.fixture
def wired(monkeypatch):
    """A dispatcher with every collaborator stubbed; returns (disp, record)."""
    record: dict[str, list] = {"events": [], "approvals": [], "dissents": []}

    def build(driver, *, reviewer=None, project_context=None, session_factory=None):
        disp = TaskDispatcher(
            session_factory=session_factory or (lambda: _Session()),
            event_bus=None,
            reviewer=reviewer or _Reviewer(_Verdict(ran=False, approved=True)),
        )

        async def _packet(*_a, **_k):
            return ContextPacket(
                task_id=uuid.uuid4(),
                tenant_id="t1",
                task_type="code",
                instruction="fix it",
                project_context=dict(project_context or {}),
            )

        async def _pick(*_a, **_k):
            return driver

        async def _emit(event_type, payload):
            record["events"].append(event_type)

        async def _approval(*args, **kwargs):
            record["approvals"].append(kwargs.get("v_results", args[3] if len(args) > 3 else None))

        async def _dissent(*args, **_k):
            record["dissents"].append(args)

        monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
        monkeypatch.setattr(disp, "_select_driver", _pick)
        monkeypatch.setattr(disp, "_load_persona", _noop)
        monkeypatch.setattr(disp, "_check_wip_limits", _noop)
        monkeypatch.setattr(disp, "_emit", _emit)
        monkeypatch.setattr(disp, "_emit_steps", _noop)
        monkeypatch.setattr(disp, "_record_stats", _noop)
        monkeypatch.setattr(disp, "_record_verification", _noop)
        monkeypatch.setattr(disp, "_create_approval_entry", _approval)
        monkeypatch.setattr(disp, "_create_dissent_approval_entry", _dissent)
        monkeypatch.setattr(disp, "_create_pr_approval", _must_not_run("PR approval"))
        monkeypatch.setattr(disp_mod.governor, "authorize", _allow)
        monkeypatch.setattr(disp_mod.governor, "record", _noop)
        return disp

    return build, record


def _dispatch(disp, **kw):
    return disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="fix it",
        verify_chain=kw.pop("verify_chain", ["tests_pass"]),
        **kw,
    )


@pytest.mark.asyncio
async def test_a_check_that_could_not_run_escalates_without_a_bounce(wired, monkeypatch):
    build, record = wired
    missing = VerifierResult("tests_pass", False, {"error": "pytest missing"}, inconclusive=True)
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([missing]))
    monkeypatch.setattr(disp_mod, "mechanical_autofix", _must_not_run("auto-fix"))
    disp = build(_Driver())
    monkeypatch.setattr(disp, "_bounce_task", _must_not_run("bounce"))

    result = await _dispatch(disp)

    assert result.success is False
    assert result.error == "Could not verify — checks did not run: tests_pass"
    assert result.metadata["needs_human"] is True
    assert [u["verifier"] for u in result.metadata["unverifiable"]] == ["tests_pass"]
    assert result.output == "did it"
    assert record["approvals"] == [[missing]]
    assert EventType.VERIFICATION_FAILED not in record["events"]


@pytest.mark.asyncio
async def test_a_second_opinion_dissent_blocks_landing(wired, monkeypatch):
    build, record = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([VerifierResult("lint", True, {})]))

    async def _diff(_workdir):
        return "diff --git a/x b/x"

    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    disp = build(
        _Driver(), reviewer=_Reviewer(_Verdict(ran=True, approved=False, concern="drops a check"))
    )

    result = await _dispatch(disp)

    assert result.success is False
    assert result.error == "Second-opinion dissent: drops a check"
    assert result.metadata == {"needs_human": True, "second_opinion_concern": "drops a check"}
    assert record["events"] == [
        EventType.DRIVER_DISPATCHED,
        EventType.VERIFICATION_PASSED,
        EventType.SECOND_OPINION_DISSENT,
        EventType.DRIVER_RESULT,
    ]
    assert len(record["dissents"]) == 1
    assert record["dissents"][0][2:4] == ("spy", "drops a check")


@pytest.mark.asyncio
async def test_a_dissent_with_no_concern_says_so(wired, monkeypatch):
    build, _record = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([VerifierResult("lint", True, {})]))

    async def _diff(_workdir):
        return ""

    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    disp = build(_Driver(), reviewer=_Reviewer(_Verdict(ran=True, approved=False)))

    result = await _dispatch(disp)

    assert result.error == "Second-opinion dissent: unspecified concern"


@pytest.mark.asyncio
async def test_an_approving_review_leaves_the_result_alone(wired, monkeypatch):
    build, record = wired
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain([VerifierResult("lint", True, {})]))

    async def _diff(_workdir):
        return "diff"

    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    disp = build(_Driver(), reviewer=_Reviewer(_Verdict(ran=True, approved=True)))

    result = await _dispatch(disp)

    assert result.success is True and result.output == "did it"
    assert EventType.SECOND_OPINION_DISSENT not in record["events"]
    assert record["dissents"] == []


@pytest.mark.asyncio
async def test_a_rewritten_worktree_git_link_is_neither_verified_nor_landed(
    wired, monkeypatch, tmp_path
):
    build, record = wired
    worktree = tmp_path / "wt"
    worktree.mkdir()
    removed: list[dict] = []

    async def _resolve(packet, scratch):
        return worktree, worktree

    async def _remove(packet, wt, repo_path=None):
        removed.append({"worktree": wt, "repo_path": repo_path})

    async def _no_context(*_a, **_k):
        return ""

    chain = _Chain([VerifierResult("lint", True, {})])
    monkeypatch.setattr(disp_mod, "resolve_workdir", _resolve)
    monkeypatch.setattr(disp_mod, "remove_worktree", _remove)
    monkeypatch.setattr(disp_mod, "_code_context", _no_context)
    monkeypatch.setattr(disp_mod, "worktree_intact", lambda wt, origin: False)
    monkeypatch.setattr(disp_mod, "verifier_chain", chain)
    monkeypatch.setattr(disp_mod, "preserve_verified_work", _must_not_run("landing"))
    disp = build(_Driver(), project_context={"path": "/origin/repo"})

    result = await _dispatch(disp, project_id=str(uuid.uuid4()), isolate_workdir=True)

    assert result.success is False
    assert result.error == "Worktree .git was modified by the driver — not verified or landed"
    assert result.metadata == {"needs_human": True, "worktree_tampered": True}
    assert chain.runs == 0
    [[tamper]] = record["approvals"]
    assert tamper.verifier == "worktree_intact" and tamper.passed is False
    # Cleaned up from the origin repo, not from inside the worktree.
    assert removed == [{"worktree": worktree, "repo_path": "/origin/repo"}]


@pytest.mark.asyncio
async def test_an_exception_rolls_back_and_closes_the_session_it_opened(wired):
    build, _record = wired
    session = _Session()
    disp = build(_Driver(error=RuntimeError("driver crashed")), session_factory=lambda: session)

    with pytest.raises(RuntimeError, match="driver crashed"):
        await _dispatch(disp, verify_chain=[])

    assert session.calls == ["rollback", "close"]


@pytest.mark.asyncio
async def test_a_session_the_caller_passed_is_left_to_the_caller(wired):
    build, _record = wired
    session = _Session()
    disp = build(_Driver(error=RuntimeError("driver crashed")))

    with pytest.raises(RuntimeError):
        await _dispatch(disp, verify_chain=[], session=session)

    assert session.calls == []
