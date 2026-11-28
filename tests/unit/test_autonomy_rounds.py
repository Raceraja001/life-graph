"""Owner-enabled fix rounds and review stages inside a dispatch.

docs/specs/agent-drivers.md, "Autonomy policy" (owner decision D2): rounds
are bounded, budget- and kill-switch-gated, recorded as verification
attempts, never approve; default 0 rounds = the one-bounce rule unchanged.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

import life_graph.drivers.review_stages as rs_mod
from life_graph.core.budget import BudgetDecision
from life_graph.core.events import EventType
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher, _DispatchRun
from life_graph.services.dev import autonomy_policy as ap
from life_graph.services.dev import review_stages as stages_mod
from life_graph.services.dev.verifiers import VerifierResult

FAIL = VerifierResult("tests_pass", False, {"stdout": "1 failed"})
PASS = VerifierResult("tests_pass", True, {})


class _Driver:
    name = "spy"

    def cost_per_task(self) -> float:
        return 0.0


@dataclass
class _Verdict:
    ran: bool
    approved: bool
    concern: str | None = None


class _Reviewer:
    """A stage reviewer answering from a script, recording what it saw."""

    def __init__(self, *verdicts: _Verdict):
        self.verdicts = list(verdicts)
        self.calls: list[dict] = []

    async def review(self, task_type, instruction, diff_text, focus=None):
        self.calls.append({"diff": diff_text, "focus": focus})
        return self.verdicts.pop(0) if len(self.verdicts) > 1 else self.verdicts[0]


def _policy(**fields) -> ap.EffectivePolicy:
    return ap.merge(fields, None)


def _run(policy=ap.NEUTRAL, tmp_path=None, cost_cap=2.0) -> _DispatchRun:
    task_id = str(uuid.uuid4())
    run = _DispatchRun(
        tenant_id="t1",
        task_id=task_id,
        instruction="fix the bug in app/x.py",
        task_type="code",
        persona_name=None,
        session=object(),
        cost_cap_usd=cost_cap,
        interactive=False,
        spec_first=False,
        acceptance_tests=None,
    )
    run.packet = ContextPacket(
        task_id=uuid.UUID(task_id), tenant_id="t1", task_type="code", instruction=run.instruction
    )
    run.driver = _Driver()
    run.verify_chain = ["tests_pass"]
    run.workdir = tmp_path
    run.result = DriverResult(success=True, output="first try", cost_usd=0.1)
    run.policy = policy
    return run


@pytest.fixture
def disp(monkeypatch):
    """A dispatcher whose DB, events and approval filers are recorders."""
    d = TaskDispatcher(session_factory=lambda: None, reviewer=_Reviewer(_Verdict(True, True)))
    rec: dict = {"events": [], "approvals": [], "dissents": [], "props": [], "bounces": []}

    async def _emit(event_type, payload):
        rec["events"].append((event_type, payload))

    async def _approval(tenant_id, task_id, driver_name, v_results, session, attempts=1):
        rec["approvals"].append({"results": v_results, "attempts": attempts})

    async def _dissent(tenant_id, task_id, driver_name, concern, session):
        rec["dissents"].append(concern)

    async def _props(run, updates):
        rec["props"].append(updates)

    async def _observe(run):
        rec.setdefault("observed", 0)
        rec["observed"] += 1

    async def _diff(_workdir):
        return "diff --git a/app/x.py b/app/x.py\n+++ b/app/x.py\n@@ -1 +1 @@\n+x = 1\n"

    async def _running(_t):
        return False

    async def _allow(*_a, **_k):
        return BudgetDecision(True, False, "ok", 0.0, 10.0, 10.0)

    monkeypatch.setattr(d, "_emit", _emit)
    monkeypatch.setattr(d, "_create_approval_entry", _approval)
    monkeypatch.setattr(d, "_create_dissent_approval_entry", _dissent)
    monkeypatch.setattr(d, "_persist_task_props", _props)
    monkeypatch.setattr(d, "_observe_files_changed", _observe)
    monkeypatch.setattr(d, "_worktree_diff", _diff)
    monkeypatch.setattr(rs_mod, "autonomy_stopped", _running)
    monkeypatch.setattr(rs_mod.governor, "authorize", _allow)
    return d, rec


def _script_bounces(monkeypatch, d, rec, outcomes):
    """Replace _bounce_task: each call consumes one outcome.

    "pass" → returns a fresh success; "fail" → verification failed again;
    "driver" → the round's driver run failed.
    """
    outcomes = list(outcomes)

    async def _bounce(**kw):
        run = kw["run"]
        outcome = outcomes.pop(0)
        rec["bounces"].append(
            {"attempt": kw["attempt"], "report": [r.verifier for r in kw["failure_report"]]}
        )
        run.spent_usd += 0.1
        if outcome == "pass":
            run.bounce_outcome = "passed"
            run.verifier_results = [PASS]
            return DriverResult(success=True, output=f"attempt {kw['attempt']}", metadata={})
        if outcome == "driver":
            run.bounce_outcome = "driver_failed"
            return None
        run.bounce_outcome = "verify_failed"
        run.verifier_results = [
            VerifierResult("tests_pass", False, {"stdout": f"still failing @{kw['attempt']}"})
        ]
        return None

    monkeypatch.setattr(d, "_bounce_task", _bounce)


# ── verify-fix rounds ────────────────────────────────────────


async def test_default_zero_rounds_is_exactly_one_bounce(disp, monkeypatch):
    d, rec = disp
    _script_bounces(monkeypatch, d, rec, ["fail"])
    run = _run()

    await d._bounce_or_escalate(run, [FAIL])

    assert [b["attempt"] for b in rec["bounces"]] == [2]
    assert run.result.error == "Verification failed after bounce — needs human review"
    assert run.result.metadata == {
        "needs_human": True,
        "verification_failures": [
            {"verifier": "tests_pass", "passed": False, "evidence": {"stdout": "1 failed"},
             "inconclusive": False}
        ],
    }  # fmt: skip
    assert rec["approvals"] == [{"results": [FAIL], "attempts": 1}]
    assert "verify_fix" not in run.autonomy


async def test_default_bounce_success_is_unchanged(disp, monkeypatch):
    d, rec = disp
    _script_bounces(monkeypatch, d, rec, ["pass"])
    run = _run()
    await d._bounce_or_escalate(run, [FAIL])
    assert run.result.success and run.result.output == "attempt 2"
    assert rec["approvals"] == [] and rec["observed"] == 1


async def test_rounds_continue_with_the_latest_failure_and_are_bounded(disp, monkeypatch):
    d, rec = disp
    _script_bounces(monkeypatch, d, rec, ["fail", "fail", "fail", "fail"])
    run = _run(_policy(verify_fix_rounds=2))

    await d._bounce_or_escalate(run, [FAIL])

    # The bounce (attempt 2) plus exactly two rounds (3, 4); never a fifth.
    assert [b["attempt"] for b in rec["bounces"]] == [2, 3, 4]
    assert run.next_attempt == 5
    assert run.result.success is False and run.result.metadata["verify_fix_rounds"] == 2
    assert "2 verify-fix round(s)" in run.result.error
    # Escalated with the LAST failure, and the approval says how many attempts.
    [approval] = rec["approvals"]
    assert approval["attempts"] == 3
    assert approval["results"][0].evidence["stdout"] == "still failing @4"
    assert run.autonomy["verify_fix"] == {"rounds": 2, "allowed": 2, "stopped": None}


async def test_a_round_that_fixes_it_lands_like_a_bounce(disp, monkeypatch):
    d, rec = disp
    _script_bounces(monkeypatch, d, rec, ["fail", "pass"])
    run = _run(_policy(verify_fix_rounds=3))
    await d._bounce_or_escalate(run, [FAIL])
    assert run.result.success and run.result.output == "attempt 3"
    assert rec["approvals"] == []
    assert run.autonomy["verify_fix"]["rounds"] == 1


async def test_rounds_stop_when_the_driver_run_fails(disp, monkeypatch):
    d, rec = disp
    _script_bounces(monkeypatch, d, rec, ["driver", "pass"])
    run = _run(_policy(verify_fix_rounds=3))
    await d._bounce_or_escalate(run, [FAIL])
    assert len(rec["bounces"]) == 1
    assert run.autonomy["verify_fix"]["stopped"] == "the fix round's driver run failed"


@pytest.mark.parametrize("gate", ["kill_switch", "budget", "cost_cap", "budget_error"])
async def test_rounds_are_gated(disp, monkeypatch, gate):
    d, rec = disp
    _script_bounces(monkeypatch, d, rec, ["fail", "pass"])
    run = _run(_policy(verify_fix_rounds=3), cost_cap=0.15 if gate == "cost_cap" else 2.0)

    async def _paused(_t):
        return True

    async def _deny(*_a, **_k):
        return BudgetDecision(False, True, "monthly cap", 10.0, 10.0, 0.0)

    async def _boom(*_a, **_k):
        raise RuntimeError("redis down")

    if gate == "kill_switch":
        monkeypatch.setattr(rs_mod, "autonomy_stopped", _paused)
    elif gate == "budget":
        monkeypatch.setattr(rs_mod.governor, "authorize", _deny)
    elif gate == "budget_error":
        monkeypatch.setattr(rs_mod.governor, "authorize", _boom)
    run.spent_usd = 0.1  # the first run

    await d._bounce_or_escalate(run, [FAIL])

    assert len(rec["bounces"]) == 1  # the bounce only; no round
    assert run.result.success is False
    stopped = run.autonomy["verify_fix"]["stopped"]
    assert {
        "kill_switch": "kill switch",
        "budget": "budget: monthly cap",
        "cost_cap": "cost cap",
        "budget_error": "could not be checked",
    }[gate] in stopped


# ── review stages ────────────────────────────────────────────


def _stages(*stages, rounds=0):
    return _policy(review_stages=[dict(s) for s in stages], review_fix_rounds=rounds)


def _use_reviewers(monkeypatch, by_name):
    monkeypatch.setattr(
        rs_mod,
        "reviewer_for",
        lambda stage: None if stage.reviewer == "human" else by_name[stage.name],
    )


async def test_no_stages_keeps_the_single_default_review(disp, monkeypatch):
    d, rec = disp
    called = []
    monkeypatch.setattr(d, "_run_review_stages", lambda run: called.append(run))
    run = _run()
    await d._second_opinion_review(run)
    assert called == [] and run.result.success
    assert rec["props"] == []


async def test_stages_run_in_order_with_their_focus(disp, monkeypatch):
    d, rec = disp
    a, b = _Reviewer(_Verdict(True, True)), _Reviewer(_Verdict(True, True))
    _use_reviewers(monkeypatch, {"security": a, "tests": b})
    run = _run(
        _stages(
            {"name": "security", "reviewer": "model:m1", "focus": "secrets, auth"},
            {"name": "tests", "reviewer": "pr_agent", "focus": "test quality"},
        )
    )
    await d._second_opinion_review(run)
    assert a.calls[0]["focus"] == "secrets, auth" and b.calls[0]["focus"] == "test quality"
    assert run.result.success
    assert [(r["name"], r["verdict"]) for r in run.review_results] == [
        ("security", "no_objection"),
        ("tests", "no_objection"),
    ]
    assert run.autonomy["review_stages"] == [
        {"index": 0, "name": "security", "reviewer": "model:m1", "verdict": "no_objection",
         "fix_round": 0},
        {"index": 1, "name": "tests", "reviewer": "pr_agent", "verdict": "no_objection",
         "fix_round": 0},
    ]  # fmt: skip
    assert rec["props"][-1]["review_stages"] == run.review_results
    assert rec["dissents"] == []


async def test_objection_with_no_rounds_goes_to_a_person(disp, monkeypatch):
    d, rec = disp
    later = _Reviewer(_Verdict(True, True))
    _use_reviewers(
        monkeypatch, {"sec": _Reviewer(_Verdict(True, False, "leaks a token")), "later": later}
    )
    _script_bounces(monkeypatch, d, rec, [])
    run = _run(
        _stages({"name": "sec", "reviewer": "model:m"}, {"name": "later", "reviewer": "pr_agent"})
    )

    await d._second_opinion_review(run)

    assert run.result.success is False
    assert run.result.error == "Review stage dissent: review stage 'sec': leaks a token"
    assert run.result.metadata["review_stage"] == "sec"
    assert rec["dissents"] == ["review stage 'sec': leaks a token"]
    assert rec["bounces"] == [] and later.calls == []
    assert EventType.SECOND_OPINION_DISSENT in [e for e, _ in rec["events"]]


async def test_objection_gets_a_fix_round_then_that_stage_reruns(disp, monkeypatch):
    d, rec = disp
    sec = _Reviewer(_Verdict(True, False, "missing tenant filter"), _Verdict(True, True))
    _use_reviewers(monkeypatch, {"sec": sec})
    _script_bounces(monkeypatch, d, rec, ["pass"])
    run = _run(_stages({"name": "sec", "reviewer": "model:m", "focus": "tenancy"}, rounds=2))

    await d._second_opinion_review(run)

    assert run.result.success and run.result.output == "attempt 2"
    assert rec["bounces"] == [{"attempt": 2, "report": ["review:sec"]}]
    assert len(sec.calls) == 2  # reviewed, fixed, reviewed again
    assert [(r["verdict"], r["fix_round"]) for r in run.review_results] == [
        ("objection", 0),
        ("no_objection", 1),
    ]
    assert run.autonomy["review_fix"] == {"rounds": 1, "allowed": 2}
    assert rec["dissents"] == []


async def test_review_rounds_are_bounded_then_a_person_decides(disp, monkeypatch):
    d, rec = disp
    _use_reviewers(monkeypatch, {"sec": _Reviewer(_Verdict(True, False, "still wrong"))})
    _script_bounces(monkeypatch, d, rec, ["pass", "pass", "pass"])
    run = _run(_stages({"name": "sec", "reviewer": "model:m"}, rounds=2))

    await d._second_opinion_review(run)

    assert [b["attempt"] for b in rec["bounces"]] == [2, 3]
    assert run.result.success is False and rec["dissents"] == ["review stage 'sec': still wrong"]
    assert [r["verdict"] for r in run.review_results] == ["objection"] * 3


async def test_review_fix_that_breaks_verification_needs_a_person(disp, monkeypatch):
    d, rec = disp
    _use_reviewers(monkeypatch, {"sec": _Reviewer(_Verdict(True, False, "bad"))})
    _script_bounces(monkeypatch, d, rec, ["fail"])
    run = _run(_stages({"name": "sec", "reviewer": "model:m"}, rounds=1))

    await d._second_opinion_review(run)

    assert run.result.success is False
    assert "Review-fix round for stage 'sec' failed (verification failed afterwards)" in (
        run.result.error
    )
    assert rec["approvals"][0]["results"][0].evidence["stdout"] == "still failing @2"


async def test_human_stage_stops_the_chain(disp, monkeypatch):
    d, rec = disp
    first, after = _Reviewer(_Verdict(True, True)), _Reviewer(_Verdict(True, False, "x"))
    _use_reviewers(monkeypatch, {"lint": first, "after": after})
    run = _run(
        _stages(
            {"name": "lint", "reviewer": "pr_agent"},
            {"name": "owner", "reviewer": "human"},
            {"name": "after", "reviewer": "model:m"},
        )
    )
    await d._second_opinion_review(run)
    assert run.result.success  # lands for a person
    assert after.calls == []
    assert [(r["name"], r["verdict"]) for r in run.review_results] == [
        ("lint", "no_objection"),
        ("owner", "human"),
        ("after", "skipped"),
    ]
    assert run.autonomy["human_stage"] is True
    # ...and the payload it produces refuses auto-approval.
    payload = {"autonomy": d._autonomy_payload(run), "verified": True, "checks": ["x"]}
    assert ap.policy_reasons(run.policy, {"files": ["a"], "lines": 1}, payload)


async def test_unavailable_stage_is_recorded_and_refuses_auto_approval(disp, monkeypatch):
    d, rec = disp
    _use_reviewers(monkeypatch, {"sec": _Reviewer(_Verdict(False, True, "pr-agent missing"))})
    run = _run(_stages({"name": "sec", "reviewer": "pr_agent"}))
    await d._second_opinion_review(run)
    assert run.result.success  # never fails the task on its own
    assert run.review_results[0]["verdict"] == "unavailable"
    payload = {"autonomy": d._autonomy_payload(run)}
    reasons = ap.policy_reasons(run.policy, {"files": ["a"], "lines": 1}, payload)
    assert "review stage 'sec' could not run" in reasons


# ── the stage reviewer itself (veto-only) ────────────────────


@pytest.mark.parametrize(
    ("text", "approved", "ran"),
    [
        ('{"verdict": "ok", "reason": "fine"}', True, True),
        ('sure: {"verdict": "object", "reason": "drops auth"}', False, True),
        ('{"verdict": "approve!"}', True, False),
        ("no json", True, False),
        (None, True, False),
    ],
)
def test_parse_verdict(text, approved, ran):
    v = stages_mod.parse_verdict(text)
    assert (v.approved, v.ran) == (approved, ran)


async def test_model_reviewer_failure_is_unavailable_not_a_pass(monkeypatch):
    class _LLM:
        async def chat(self, *_a, **_k):
            raise RuntimeError("no model")

    monkeypatch.setattr(stages_mod, "get_resilient_llm", lambda: _LLM())
    v = await stages_mod.ModelStageReviewer("m").review("code", "x", "diff --git a b")
    assert v.ran is False
    v = await stages_mod.ModelStageReviewer("m").review("code", "x", "")
    assert v.ran is False


def test_reviewer_for():
    assert stages_mod.reviewer_for(ap.ReviewStage(name="h", reviewer="human")) is None
    r = stages_mod.reviewer_for(ap.ReviewStage(name="p", reviewer="pr_agent"))
    assert type(r).__name__ == "PRAgentReviewer" and r._enabled
    m = stages_mod.reviewer_for(ap.ReviewStage(name="m", reviewer="model:gemini/flash"))
    assert isinstance(m, stages_mod.ModelStageReviewer) and m._model == "gemini/flash"


# ── the risk report is stored and summarized for the approval ─


async def test_risk_report_is_stored_and_summarized(disp):
    d, rec = disp
    run = _run()
    run.files_changed = ["app/x.py"]
    await d._record_risk_report(run)
    report = rec["props"][-1]["risk_report"]
    assert report["complete"] and report["files"] == 1
    assert run.autonomy["risk"] == {"block": 0, "warn": 0, "complete": True}


async def test_empty_diff_with_changed_files_is_an_incomplete_report(disp, monkeypatch):
    d, rec = disp

    async def _empty(_w):
        return ""

    monkeypatch.setattr(d, "_worktree_diff", _empty)
    run = _run()
    run.files_changed = ["app/x.py"]
    await d._record_risk_report(run)
    assert run.autonomy["risk"]["complete"] is False


async def test_policy_load_failure_is_neutral():
    d = TaskDispatcher(session_factory=lambda: None, reviewer=_Reviewer(_Verdict(True, True)))
    assert await d._load_autonomy_policy(_run()) is ap.NEUTRAL


# ── the real _bounce_task records the round's attempt ─────────


async def test_a_fix_round_is_recorded_as_its_own_attempt(monkeypatch, tmp_path):
    import life_graph.drivers.dispatcher as disp_mod

    seen: dict = {"verifications": [], "steps": [], "booked": []}

    class _Chain:
        async def run_chain(self, chain, workdir, ctx):
            return [PASS]

        def all_passed(self, results):
            return all(r.passed for r in results)

        def inconclusive(self, results):
            return []

    class _FixDriver(_Driver):
        async def dispatch(self, packet, workdir, timeout=300):
            return DriverResult(success=True, output="fixed", cost_usd=0.25)

    d = TaskDispatcher(session_factory=lambda: None)

    async def _record(tenant_id, task_id, attempt, v_results, session):
        seen["verifications"].append(attempt)

    async def _steps(tenant_id, task_id, driver_name, attempt, result):
        seen["steps"].append(attempt)

    async def _book(tenant_id, category, usd):
        seen["booked"].append(usd)

    async def _noop(*_a, **_k):
        return None

    monkeypatch.setattr(d, "_record_verification", _record)
    monkeypatch.setattr(d, "_emit_steps", _steps)
    monkeypatch.setattr(d, "_emit", _noop)
    monkeypatch.setattr(d, "_check_worktree_link", _noop)
    monkeypatch.setattr(disp_mod, "verifier_chain", _Chain())
    monkeypatch.setattr(disp_mod.governor, "record", _book)
    run = _run(tmp_path=tmp_path)
    run.driver = _FixDriver()

    for attempt in (2, 3):
        out = await d._bounce_task(
            tenant_id="t1",
            task_id=run.task_id,
            driver=run.driver,
            packet=run.packet,
            workdir=tmp_path,
            failure_report=[FAIL],
            session=None,
            verify_chain=["tests_pass"],
            run=run,
            attempt=attempt,
        )
        assert out is not None and run.bounce_outcome == "passed"

    assert seen["verifications"] == [2, 3] and seen["steps"] == [2, 3]
    # Only the owner-enabled round books its spend anew; the bounce is as before.
    assert seen["booked"] == [0.25]
    assert run.spent_usd == pytest.approx(0.5)


async def test_approval_entry_says_how_many_rounds_ran():
    from life_graph.autonomy.models import ApprovalQueueEntry

    added: list = []

    class _S:
        def add(self, obj):
            added.append(obj)

    d = TaskDispatcher(session_factory=lambda: None)
    await d._create_approval_entry("t1", "task-1", "spy", [FAIL], _S())
    await d._create_approval_entry("t1", "task-1", "spy", [FAIL], _S(), attempts=3)
    assert all(isinstance(a, ApprovalQueueEntry) for a in added)
    assert "after one bounce. Failures: tests_pass" in added[0].trigger_detail
    assert "after one bounce and 2 verify-fix round(s)" in added[1].trigger_detail
