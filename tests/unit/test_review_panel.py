"""The two-model review panel on risky diffs (shadow first).

docs/specs/agent-drivers.md, "Amendment 2026-11-28 -- Review panel": any
objection objects, any not-reviewed is not-reviewed, no chairman, no vote;
local models only; shadow records and never gates; enforce sends anything
but a unanimous approval to a person and never approves.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

import life_graph.drivers.review_stages as rs_mod
from life_graph.config import settings
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher, _DispatchRun
from life_graph.services.dev import review_panel as rp

A, OBJ, N = rp.APPROVE, rp.OBJECTION, rp.NOT_REVIEWED
Q14, Q30 = "ollama_chat/qwen3:14b", "ollama_chat/qwen3-coder:30b"

SMALL_DIFF = "diff --git a/app/x.py b/app/x.py\n+++ b/app/x.py\n@@ -1 +1 @@\n+x = 1\n"
PROTECTED_DIFF = (
    "diff --git a/pyproject.toml b/pyproject.toml\n+++ b/pyproject.toml\n@@ -1 +1 @@\n+a = 1\n"
)
CLEAN = {"complete": True, "block": 0, "warn": 0, "findings": []}
WARN = {"complete": True, "block": 0, "warn": 1, "findings": []}


def _m(model: str, verdict: str, reason: str | None = None) -> rp.MemberVerdict:
    return rp.MemberVerdict(model, verdict, reason)


def _answer(verdict: str, reason: str = "because") -> str:
    return f'{{"verdict": "{verdict}", "reason": "{reason}"}}'


class _Chat:
    """A scripted local model: answers per model id, records every prompt."""

    def __init__(self, answers: dict[str, str] | None = None, *, delay: float = 0.0):
        self.answers = answers or {}
        self.delay = delay
        self.calls: list[tuple[str, str]] = []
        self.gate: asyncio.Event | None = None

    async def __call__(self, model: str, prompt: str) -> str:
        self.calls.append((model, prompt))
        if self.gate is not None:
            await self.gate.wait()
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.answers.get(model, _answer("approve"))


# ── Aggregation ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("verdicts", "expected"),
    [
        ((A, A), A),
        ((OBJ, A), OBJ),
        ((A, OBJ), OBJ),
        ((OBJ, OBJ), OBJ),
        ((N, A), N),
        ((A, N), N),
        ((N, N), N),
        # An objection is the stronger signal; both send the task to a person.
        ((OBJ, N), OBJ),
        ((N, OBJ), OBJ),
        # An unknown verdict is never an approval.
        (("maybe", A), N),
        ((A,), A),
        ((), N),
    ],
)
def test_aggregate_rules(verdicts, expected):
    members = [_m(f"ollama_chat/m{i}", v) for i, v in enumerate(verdicts)]
    assert rp.aggregate(members).verdict == expected


def test_aggregate_single_objection_is_not_outvoted():
    members = [_m("ollama_chat/a", A), _m("ollama_chat/b", A), _m("ollama_chat/c", OBJ, "bug")]
    verdict = rp.aggregate(members)
    assert verdict.verdict == OBJ
    assert "ollama_chat/c: bug" in (verdict.reason or "")
    assert verdict.needs_person


def test_only_unanimous_approval_does_not_need_a_person():
    assert not rp.aggregate([_m(Q14, A), _m(Q30, A)]).needs_person
    assert rp.aggregate([_m(Q14, A), _m(Q30, N)]).needs_person


# ── Parsing ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "verdict"),
    [
        (_answer("approve"), A),
        (_answer("ok"), A),
        (_answer("object", "null deref in app/x.py"), OBJ),
        ('<think>maybe {"verdict": "object"}</think>' + _answer("approve"), A),
        ("not json at all", N),
        ('{"verdict": "unsure"}', N),
        ("", N),
        (None, N),
        ("[1, 2]", N),
    ],
)
def test_parse_member(text, verdict):
    assert rp.parse_member(Q14, text).verdict == verdict


def test_parse_member_keeps_reason():
    got = rp.parse_member(Q14, _answer("object", "SQL injection in app/db.py"))
    assert got.reason == "SQL injection in app/db.py"


# ── Members: local only, timeouts, failures ───────────────────


@pytest.mark.parametrize(
    "model",
    ["openrouter/qwen/qwen3-coder:free", "claude-opus", "gpt-4o", "groq/llama", "", "lm_studio/x"],
)
async def test_non_local_model_is_refused_and_never_called(model):
    chat = _Chat()
    got = await rp.review_one(model, "do x", SMALL_DIFF, timeout=5, chat=chat)
    assert got.verdict == N
    assert "not a local model" in (got.reason or "")
    assert chat.calls == []


async def test_panel_with_a_cloud_member_never_approves():
    chat = _Chat()
    verdict = await rp.run_panel(
        "do x", SMALL_DIFF, models=[Q14, "openrouter/some-model"], timeout=5, chat=chat
    )
    assert verdict.verdict == N
    assert [m for m, _ in chat.calls] == [Q14]


async def test_timeout_is_not_reviewed():
    chat = _Chat(delay=1.0)
    verdict = await rp.run_panel("do x", SMALL_DIFF, models=[Q14, Q30], timeout=0.01, chat=chat)
    assert verdict.verdict == N
    assert all(m.verdict == N and "timed out" in (m.reason or "") for m in verdict.members)


async def test_one_member_timing_out_makes_the_panel_not_reviewed():
    class _Slow(_Chat):
        async def __call__(self, model, prompt):
            if model == Q30:
                await asyncio.sleep(1.0)
            return _answer("approve")

    verdict = await rp.run_panel("do x", SMALL_DIFF, models=[Q14, Q30], timeout=0.05, chat=_Slow())
    assert verdict.verdict == N
    assert [m.verdict for m in verdict.members] == [A, N]


async def test_model_error_is_not_reviewed():
    async def _boom(model, prompt):
        raise RuntimeError("ollama down")

    verdict = await rp.run_panel("do x", SMALL_DIFF, models=[Q14, Q30], timeout=5, chat=_boom)
    assert verdict.verdict == N
    assert all("RuntimeError" in (m.reason or "") for m in verdict.members)


async def test_empty_diff_is_not_reviewed():
    chat = _Chat()
    verdict = await rp.run_panel("do x", "  ", models=[Q14, Q30], timeout=5, chat=chat)
    assert verdict.verdict == N
    assert chat.calls == []


async def test_members_review_in_parallel_and_independently():
    chat = _Chat({Q14: _answer("approve"), Q30: _answer("object", "breaks tenant filter")})
    chat.gate = asyncio.Event()
    pending = asyncio.ensure_future(
        rp.run_panel("fix app/x.py", SMALL_DIFF, models=[Q14, Q30], timeout=5, chat=chat)
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    # Both started before either answered: neither can see the other's verdict.
    assert sorted(m for m, _ in chat.calls) == sorted([Q14, Q30])
    chat.gate.set()
    verdict = await pending
    assert verdict.verdict == OBJ
    prompts = [p for _, p in chat.calls]
    assert prompts[0] == prompts[1] == rp.build_prompt("fix app/x.py", SMALL_DIFF)


def test_prompt_has_instruction_diff_and_focus_only():
    prompt = rp.build_prompt("fix the bug in app/x.py", SMALL_DIFF)
    assert "fix the bug in app/x.py" in prompt
    assert "+x = 1" in prompt
    for focus in ("correctness", "security", "scope"):
        assert focus in prompt
    for private in ("memor", "preference", "procedure"):
        assert private not in prompt.lower()


def test_default_models_are_local_and_two():
    models = rp.panel_models()
    assert models == [Q14, Q30]
    assert all(rp.is_local_model(m) for m in models)
    assert rp.panel_models(" a, b ,a,,") == ["a", "b"]


def test_mode_defaults_off():
    assert type(settings).model_fields["driver_review_panel_mode"].default == "off"


# ── Which diffs are risky ─────────────────────────────────────


def test_clean_small_diff_is_not_risky():
    assert rp.risky_reasons(CLEAN, SMALL_DIFF, min_lines=150) == []


def test_risk_findings_make_it_risky():
    reasons = rp.risky_reasons(WARN, SMALL_DIFF, min_lines=150)
    assert reasons == ["risk report: 0 block, 1 warn"]
    block = {**CLEAN, "block": 2}
    assert rp.risky_reasons(block, SMALL_DIFF, min_lines=150) == ["risk report: 2 block, 0 warn"]


def test_missing_or_incomplete_report_is_risky():
    assert rp.risky_reasons(None, SMALL_DIFF, min_lines=150) == ["no risk report"]
    incomplete = {**CLEAN, "complete": False}
    assert rp.risky_reasons(incomplete, SMALL_DIFF, min_lines=150) == ["risk report incomplete"]


def test_protected_path_is_risky_default_and_project_globs():
    reasons = rp.risky_reasons(CLEAN, PROTECTED_DIFF, min_lines=150)
    assert reasons == ["touches protected paths: pyproject.toml"]
    got = rp.risky_reasons(CLEAN, SMALL_DIFF, protected_globs=["app/*"], min_lines=150)
    assert got == ["touches protected paths: app/x.py"]


def test_size_over_threshold_is_risky():
    body = "".join(f"+line {i}\n" for i in range(12))
    diff = "diff --git a/app/y.py b/app/y.py\n+++ b/app/y.py\n@@ -1 +1,12 @@\n" + body
    assert rp.risky_reasons(CLEAN, diff, min_lines=12) == []
    assert rp.risky_reasons(CLEAN, diff, min_lines=11) == ["12 changed lines (panel threshold 11)"]


# ── The record W2's outcome log reads ─────────────────────────


def test_panel_for_outcome():
    assert rp.panel_for_outcome(None) is None
    assert rp.panel_for_outcome({}) is None
    assert rp.panel_for_outcome({rp.PANEL_KEY: "junk"}) is None
    verdict = rp.aggregate([_m(Q14, A), _m(Q30, OBJ, "bug")])
    props = {rp.PANEL_KEY: rp.record("shadow", verdict, risky=["risk report: 0 block, 1 warn"])}
    got = rp.panel_for_outcome(props)
    assert got is not None
    assert got["mode"] == "shadow"
    assert got["verdict"] == OBJ
    assert got["gated"] is False
    assert got["members"] == [{"model": Q14, "verdict": A}, {"model": Q30, "verdict": OBJ}]
    assert got["risky"] == ["risk report: 0 block, 1 warn"]
    skipped = rp.panel_for_outcome({rp.PANEL_KEY: rp.record("shadow", None, skipped="not risky")})
    assert skipped is not None and skipped["verdict"] == rp.SKIPPED


# ── The dispatcher hook ───────────────────────────────────────


def _run(instruction: str = "fix the bug in app/x.py") -> _DispatchRun:
    task_id = str(uuid.uuid4())
    run = _DispatchRun(
        tenant_id="t1",
        task_id=task_id,
        instruction=instruction,
        task_type="code",
        persona_name=None,
        session=object(),
        cost_cap_usd=2.0,
        interactive=False,
        spec_first=False,
        acceptance_tests=None,
    )
    run.packet = ContextPacket(
        task_id=uuid.UUID(task_id), tenant_id="t1", task_type="code", instruction=instruction
    )
    run.result = DriverResult(success=True, output="done", cost_usd=0.0)
    run.files_changed = ["app/x.py"]
    return run


@pytest.fixture
def hook(monkeypatch):
    """A dispatcher whose diff, task props and kill switch are scripted."""
    d = TaskDispatcher(session_factory=lambda: None)
    state: dict = {"props": [], "diff": PROTECTED_DIFF, "stopped": False, "chat": _Chat()}

    async def _props(run, updates):
        state["props"].append(updates)
        return True

    async def _diff(_workdir):
        return state["diff"]

    async def _stopped(_tenant):
        return state["stopped"]

    async def _chat(model, prompt):
        return await state["chat"](model, prompt)

    monkeypatch.setattr(d, "_persist_task_props", _props)
    monkeypatch.setattr(d, "_worktree_diff", _diff)
    monkeypatch.setattr(rs_mod, "autonomy_stopped", _stopped)
    monkeypatch.setattr(rp, "_chat_local", _chat)
    monkeypatch.setattr(settings, "driver_review_panel_timeout_seconds", 5.0)
    return d, state


def _panel_records(state) -> list[dict]:
    return [u[rp.PANEL_KEY] for u in state["props"] if rp.PANEL_KEY in u]


async def test_off_mode_never_runs(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "off")
    run = _run()
    await d._record_risk_report(run)
    assert state["chat"].calls == []
    assert _panel_records(state) == []
    assert "risk" in run.autonomy  # the risk report itself is unchanged


async def test_shadow_does_not_wait_and_never_gates(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "shadow")
    state["chat"] = _Chat({Q14: _answer("object", "deletes the tenant filter")})
    state["chat"].gate = asyncio.Event()
    run = _run()
    await d._record_risk_report(run)
    # Returned while both reviewers are still blocked: nothing waited on them.
    assert rp.in_flight() == 1
    assert run.hold_auto is False
    assert "review_panel" not in run.autonomy
    state["chat"].gate.set()
    await rp.drain()
    (rec,) = _panel_records(state)
    assert rec["mode"] == "shadow"
    assert rec["verdict"] == OBJ
    assert rec["gated"] is False
    # protected_path + out_of_scope warnings, and the protected path itself.
    assert rec["risky"] == [
        "risk report: 0 block, 2 warn",
        "touches protected paths: pyproject.toml",
    ]
    # An objection arriving later still changes nothing on the run.
    assert run.hold_auto is False
    assert "review_panel" not in run.autonomy


async def test_shadow_timeout_is_recorded_not_reviewed(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "shadow")
    monkeypatch.setattr(settings, "driver_review_panel_timeout_seconds", 0.01)
    state["chat"] = _Chat(delay=1.0)
    run = _run()
    await d._record_risk_report(run)
    await rp.drain()
    (rec,) = _panel_records(state)
    assert rec["verdict"] == N
    assert run.hold_auto is False


async def test_shadow_skips_when_busy(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "shadow")
    monkeypatch.setattr(rp, "MAX_SHADOW_IN_FLIGHT", 0)
    run = _run()
    await d._record_risk_report(run)
    (rec,) = _panel_records(state)
    assert rec["verdict"] == rp.SKIPPED and rec["reason"] == "panel busy"
    assert state["chat"].calls == []


@pytest.mark.parametrize("mode", ["shadow", "enforce"])
async def test_not_risky_is_skipped(hook, monkeypatch, mode):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", mode)
    state["diff"] = SMALL_DIFF
    run = _run()
    await d._record_risk_report(run)
    await rp.drain()
    (rec,) = _panel_records(state)
    assert rec["verdict"] == rp.SKIPPED and rec["reason"] == "not risky"
    assert state["chat"].calls == []
    assert run.hold_auto is False


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        ({Q14: _answer("object", "bug"), Q30: _answer("approve")}, OBJ),
        ({Q14: _answer("approve"), Q30: "garbled"}, N),
    ],
)
async def test_enforce_routes_objection_and_not_reviewed_to_a_person(
    hook, monkeypatch, answers, expected
):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "enforce")
    state["chat"] = _Chat(answers)
    run = _run()
    await d._record_risk_report(run)
    assert run.hold_auto is True  # no auto-open, no auto-merge: a person decides
    assert run.autonomy["review_panel"]["verdict"] == expected
    (rec,) = _panel_records(state)
    assert rec["gated"] is True and rec["verdict"] == expected


async def test_enforce_timeout_routes_to_a_person(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "enforce")
    monkeypatch.setattr(settings, "driver_review_panel_timeout_seconds", 0.01)
    state["chat"] = _Chat(delay=1.0)
    run = _run()
    await d._record_risk_report(run)
    assert run.hold_auto is True
    assert run.autonomy["review_panel"]["verdict"] == N


async def test_enforce_approval_never_approves_anything(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "enforce")
    run = _run()
    run.hold_auto = True  # e.g. an arena racer: the panel cannot lift a hold
    await d._record_risk_report(run)
    assert run.hold_auto is True
    assert run.autonomy["review_panel"]["verdict"] == A
    (rec,) = _panel_records(state)
    assert rec["gated"] is False
    # The panel's approval adds no approval of its own to the run.
    assert run.result.success is True
    assert "human_stage" not in run.autonomy


async def test_enforce_unanimous_approval_leaves_the_task_as_it_was(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "enforce")
    run = _run()
    await d._record_risk_report(run)
    assert run.hold_auto is False


async def test_enforce_refuses_a_cloud_member_and_holds(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "enforce")
    monkeypatch.setattr(settings, "driver_review_panel_models", f"{Q14},openrouter/free-coder")
    run = _run()
    await d._record_risk_report(run)
    assert [m for m, _ in state["chat"].calls] == [Q14]
    assert run.hold_auto is True
    assert run.autonomy["review_panel"]["verdict"] == N


async def test_kill_switch(hook, monkeypatch):
    d, state = hook
    state["stopped"] = True
    monkeypatch.setattr(settings, "driver_review_panel_mode", "shadow")
    run = _run()
    await d._record_risk_report(run)
    await rp.drain()
    (rec,) = _panel_records(state)
    assert rec["verdict"] == rp.SKIPPED and rec["reason"] == "kill switch"
    assert run.hold_auto is False

    state["props"].clear()
    monkeypatch.setattr(settings, "driver_review_panel_mode", "enforce")
    run = _run()
    await d._record_risk_report(run)
    assert state["chat"].calls == []
    assert run.hold_auto is True
    (rec,) = _panel_records(state)
    assert rec["verdict"] == N and rec["gated"] is True


async def test_risk_report_failure_still_runs_the_panel_and_enforce_holds(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "enforce")

    def _boom(*_a, **_k):
        raise RuntimeError("parser broke")

    monkeypatch.setattr(rs_mod, "build_report", _boom)
    run = _run()
    await d._record_risk_report(run)
    # "no risk report" is risky; the panel still reviewed the diff it had.
    (rec,) = _panel_records(state)
    assert "no risk report" in rec["risky"]
    assert rec["verdict"] == A


async def test_panel_crash_in_enforce_holds_and_never_raises(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "enforce")

    async def _crash(*_a, **_k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(rp, "run_panel", _crash)
    run = _run()
    await d._record_risk_report(run)
    assert run.hold_auto is True
    (rec,) = _panel_records(state)
    assert rec["verdict"] == N


async def test_shadow_crash_never_raises(hook, monkeypatch):
    d, state = hook
    monkeypatch.setattr(settings, "driver_review_panel_mode", "shadow")

    async def _crash(*_a, **_k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(rp, "run_panel", _crash)
    run = _run()
    await d._record_risk_report(run)
    await rp.drain()
    assert _panel_records(state) == []
    assert run.hold_auto is False
