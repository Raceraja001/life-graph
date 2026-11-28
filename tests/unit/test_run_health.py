"""Run health inside a dispatch (Phase 3b part 2): rate-limit re-dispatch, stall
retries, nudges, parking, the subscription budget (D4) and spend booking.

docs/specs/agent-drivers.md, "Phase 3b part 2". Every extra call is bounded,
gated (kill switch, cost cap, Governor) and recorded as its own attempt; with
the defaults (accounts off, rounds 0) a dispatch makes exactly one call.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

import life_graph.drivers.review_stages as rs_mod
import life_graph.drivers.run_health as rh
from life_graph.config import settings
from life_graph.core.budget import BudgetDecision
from life_graph.core.events import EventType
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher, _DispatchRun
from life_graph.services.dev import autonomy_policy as ap
from life_graph.services.dev import task_events

NOW = datetime(2026, 11, 27, 9, 0, tzinfo=UTC)


class _Driver:
    """Answers each call from a script; records packets and resumes."""

    name = "codex"
    supports_resume = True

    def __init__(self, *results: DriverResult) -> None:
        self.results = list(results)
        self.calls: list[dict] = []

    def cost_per_task(self) -> float:
        return 0.0

    def _next(self) -> DriverResult:
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]

    async def dispatch(self, packet, workdir, timeout=300):
        self.calls.append({"kind": "dispatch", "packet": packet})
        return self._next()

    async def resume(self, packet, workdir, session_id, prompt, timeout=300, *, account_id=None):
        self.calls.append(
            {"kind": "resume", "session": session_id, "prompt": prompt, "account": account_id}
        )
        return self._next()


def _limited(account="a", next_=("b-id", "b"), kind="subscription", steps=None):
    md = {
        "exit_status": "rate_limited",
        "failure": {"kind": "rate_limited", "resets_at": "2026-11-27T12:00:00Z", "message": "429"},
        "account": {
            "id": f"{account}-id",
            "name": account,
            "kind": kind,
            "cooldown_until": "2026-11-27T12:00:00Z",
            "next": {"id": next_[0], "name": next_[1], "kind": "subscription"} if next_ else None,
        },
        "billing": "subscription",
        "steps": steps or [],
    }
    return DriverResult(success=False, error="rate limited", metadata=md)


def _ok(output="done", **md):
    return DriverResult(success=True, output=output, metadata={"session_id": "sess-0001", **md})


def _run(policy=ap.NEUTRAL, *, interactive=False) -> _DispatchRun:
    task_id = str(uuid.uuid4())
    run = _DispatchRun(
        tenant_id="t1",
        task_id=task_id,
        instruction="fix app/x.py",
        task_type="code",
        persona_name=None,
        session=None,
        cost_cap_usd=2.0,
        interactive=interactive,
        spec_first=False,
        acceptance_tests=None,
    )
    run.packet = ContextPacket(
        task_id=uuid.UUID(task_id), tenant_id="t1", task_type="code", instruction=run.instruction
    )
    run.policy = policy
    run.driver = _Driver(_ok())
    return run


@pytest.fixture
def disp(monkeypatch):
    """A dispatcher whose events, steps, budget and kill switch are recorders."""
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    rec: dict = {"events": [], "steps": [], "task_events": [], "booked": [], "sleeps": []}

    async def _emit(event_type, payload):
        rec["events"].append((event_type, payload))

    async def _steps(tenant_id, task_id, driver_name, attempt, result):
        rec["steps"].append(attempt)

    def _task_event(tenant_id, task_id, kind, content="", *, data=None, source="runner"):
        rec["task_events"].append({"kind": kind, "content": content, "data": data or {}})

    async def _running(_t):
        return rec.get("paused", False)

    async def _authorize(*_a, **_k):
        if rec.get("budget_denied"):
            return BudgetDecision(False, False, "monthly cap reached", 10.0, 10.0, 0.0)
        return BudgetDecision(True, False, "ok", 0.0, 10.0, 10.0)

    async def _record(tenant_id, category, usd):
        rec["booked"].append(usd)

    async def _sleep(seconds):
        rec["sleeps"].append(seconds)

    monkeypatch.setattr(d, "_emit", _emit)
    monkeypatch.setattr(d, "_emit_steps", _steps)
    monkeypatch.setattr(task_events, "emit", _task_event)
    monkeypatch.setattr(rs_mod, "autonomy_stopped", _running)
    monkeypatch.setattr(rs_mod.governor, "authorize", _authorize)
    monkeypatch.setattr(rh.governor, "record", _record)
    monkeypatch.setattr(rh, "_sleep", _sleep)
    return d, rec


@pytest.fixture
def accounts_on(monkeypatch):
    monkeypatch.setattr(settings, "driver_accounts_enabled", True)


def _rounds(rec, kind=None):
    return [
        e for e in rec["task_events"]
        if e["kind"] == "round" and (kind is None or e["data"].get("kind") == kind)
    ]  # fmt: skip


# ── Pure helpers ─────────────────────────────────────────────


def test_classify_plan_only_vs_empty():
    assert rh.classify_empty_turn(["I will:\n1. read x\n2. edit y"]) == "plan_only"
    assert rh.classify_empty_turn(["Should I change the schema too?"]) == "plan_only"
    assert rh.classify_empty_turn(["Done. Everything already works."]) == "empty"
    assert rh.classify_empty_turn([]) == "empty"


def test_stall_backoff_doubles_and_is_capped():
    assert [rh.stall_delay(n) for n in range(7)] == [10, 20, 40, 80, 160, 300, 300]


def test_handoff_note_keeps_the_newest_1500_chars():
    note = rh.handoff_note(["a" * 1000, "b" * 1000])
    assert len(note) == rh.HANDOFF_NOTE_MAX and note.endswith("b" * 1000)
    assert rh.handoff_note(["  hi  ", "", "there"]) == "hi\nthere"


def test_park_decision_takes_the_earliest_reset_plus_grace():
    result = _limited(next_=None)
    result.metadata["account"]["next"] = {"state": "cooling", "retry_at": "2026-11-27T10:00:00Z"}
    park = rh.park_decision(result, now=NOW)
    assert park["resets_at"] == "2026-11-27T10:00:00Z"
    assert park["resume_at"] == "2026-11-27T10:01:00Z"
    # Not a rate limit -> nothing to park on.
    assert rh.park_decision(DriverResult(success=False, metadata={}), now=NOW) is None
    # A reset already past -> the default cooldown from now, never the past.
    old = DriverResult(
        success=False,
        metadata={"failure": {"kind": "rate_limited", "resets_at": "2026-11-27T08:00:00Z"}},
    )
    assert rh.park_decision(old, now=NOW, default_minutes=15)["resume_at"] == (
        "2026-11-27T09:16:00Z"
    )


# ── Defaults: one call, exactly as before ─────────────────────


async def test_defaults_make_exactly_one_call_even_when_rate_limited(disp):
    d, rec = disp
    driver = _Driver(_limited())
    run = _run()
    result, attempt = await d._drive(run, driver, run.packet, None, attempt=1, book_first=True)
    assert len(driver.calls) == 1 and attempt == 1 and result.success is False
    assert rec["events"] == [] and _rounds(rec) == [] and run.next_attempt == 2


async def test_defaults_never_retry_a_timeout(disp):
    d, rec = disp
    driver = _Driver(DriverResult(success=False, metadata={"exit_status": "timeout"}))
    run = _run()
    await d._drive(run, driver, run.packet, None, attempt=1, book_first=True)
    assert len(driver.calls) == 1 and rec["sleeps"] == []


# ── Re-dispatch on a rate limit ──────────────────────────────


async def test_rate_limit_moves_to_the_next_account_with_a_handoff(disp, accounts_on):
    d, rec = disp
    steps = [{"kind": "text", "content": "Edited x.py, now running tests"}]
    driver = _Driver(_limited(steps=steps), _ok())
    run = _run()

    result, attempt = await d._drive(run, driver, run.packet, None, attempt=1, book_first=True)

    assert result.success and attempt == 2 and run.next_attempt == 3
    second = driver.calls[1]["packet"]
    assert second.account_id == "b-id"
    assert second.instruction.startswith(rh.CONTINUE_AFTER_RATE_LIMIT)
    assert "Edited x.py, now running tests" in second.instruction
    assert second.instruction.endswith("fix app/x.py")
    # The interrupted attempt's steps were recorded under attempt 1.
    assert rec["steps"] == [1]
    (switch,) = _rounds(rec, "rate_limit_switch")
    assert switch["data"]["from"] == "a" and switch["data"]["to"] == "b"
    assert switch["data"]["attempt"] == 2
    kinds = [e for e, _ in rec["events"]]
    assert EventType.DRIVER_ACCOUNT_SWITCHED in kinds and EventType.DRIVER_RUN_HEALTH_ROUND in kinds
    assert run.autonomy["run_health"][0]["kind"] == "rate_limit_switch"


async def test_one_attempt_per_account_per_task(disp, accounts_on):
    d, rec = disp
    # a -> b, then b is limited and names a again: no third run.
    driver = _Driver(_limited("a", ("b-id", "b")), _limited("b", ("a-id", "a")))
    run = _run()
    result, _ = await d._drive(run, driver, run.packet, None, attempt=1, book_first=True)
    assert len(driver.calls) == 2 and rh.rate_limited(result)
    assert run.accounts_tried == {"a-id", "b-id"}


async def test_never_rotates_on_auth_or_other_failures(disp, accounts_on):
    d, _rec = disp
    auth = _limited()
    auth.metadata["failure"] = {"kind": "auth", "message": "signed out"}
    driver = _Driver(auth)
    run = _run()
    await d._drive(run, driver, run.packet, None, attempt=1, book_first=True)
    assert len(driver.calls) == 1


async def test_rotation_refused_by_the_kill_switch(disp, accounts_on):
    d, rec = disp
    rec["paused"] = True
    driver = _Driver(_limited(), _ok())
    run = _run()
    result, _ = await d._drive(run, driver, run.packet, None, attempt=1, book_first=True)
    assert len(driver.calls) == 1 and not result.success
    (skipped,) = _rounds(rec, "rate_limit_switch")
    assert skipped["data"]["skipped"] and "kill switch" in skipped["data"]["reason"]


# ── Stall retries ────────────────────────────────────────────


def _timeout(session="sess-0001"):
    return DriverResult(
        success=False,
        error="codex timed out",
        metadata={"exit_status": "timeout", "session_id": session},
    )


async def test_stall_retries_resume_with_backoff_and_are_bounded(disp):
    d, rec = disp
    driver = _Driver(_timeout(), _timeout(), _timeout(), _ok())
    run = _run(ap.merge({"max_stall_retries": 2}, None))

    result, attempt = await d._drive(run, driver, run.packet, None, attempt=1, book_first=True)

    # The first run plus exactly two retries, 10 s then 20 s apart.
    assert len(driver.calls) == 3 and not result.success and attempt == 3
    assert rec["sleeps"] == [10.0, 20.0]
    assert [c["kind"] for c in driver.calls] == ["dispatch", "resume", "resume"]
    assert driver.calls[1]["prompt"] == rh.STALL_TEXT and driver.calls[1]["session"] == "sess-0001"
    assert len(_rounds(rec, "stall_retry")) == 2


async def test_stall_retry_without_a_session_redispatches(disp):
    d, _rec = disp
    driver = _Driver(_timeout(session=None), _ok())
    run = _run(ap.merge({"max_stall_retries": 1}, None))
    result, _ = await d._drive(run, driver, run.packet, None, attempt=1, book_first=True)
    assert result.success and driver.calls[1]["kind"] == "dispatch"
    assert driver.calls[1]["packet"].instruction.startswith(rh.STALL_TEXT)


@pytest.mark.parametrize("gate", ["paused", "budget_denied"])
async def test_stall_retry_is_gated(disp, gate):
    d, rec = disp
    rec[gate] = True
    driver = _Driver(_timeout(), _ok())
    run = _run(ap.merge({"max_stall_retries": 3}, None))
    await d._drive(run, driver, run.packet, None, attempt=1, book_first=True)
    assert len(driver.calls) == 1 and rec["sleeps"] == []
    assert _rounds(rec, "stall_retry")[0]["data"]["skipped"]


async def test_kill_switch_during_the_backoff_stops_the_retry(disp, monkeypatch):
    d, rec = disp

    async def _sleep(seconds):
        rec["sleeps"].append(seconds)
        rec["paused"] = True

    monkeypatch.setattr(rh, "_sleep", _sleep)
    driver = _Driver(_timeout(), _ok())
    run = _run(ap.merge({"max_stall_retries": 1}, None))
    await d._drive(run, driver, run.packet, None, attempt=1, book_first=True)
    assert len(driver.calls) == 1 and rec["sleeps"] == [10.0]


# ── Nudges ───────────────────────────────────────────────────


def _nudge_run(policy, output):
    run = _run(policy)
    run.driver = _Driver(_ok("Changed app/x.py"))
    run.worktree = run.workdir = "/tmp/wt"
    run.result = _ok(output)
    run.session_ref = {"driver": "codex", "session_id": "sess-0001", "account_id": None}
    return run


@pytest.fixture
def nudge_disp(disp, monkeypatch):
    d, rec = disp
    seen = {"observed": 0}

    async def _noop(run):
        return None

    async def _observe(run):
        seen["observed"] += 1
        run.files_changed = ["app/x.py"]

    monkeypatch.setattr(d, "_check_worktree_link", _noop)
    monkeypatch.setattr(d, "_observe_files_changed", _observe)
    return d, rec, seen


async def test_plan_only_turn_is_nudged_once_then_checked_again(nudge_disp):
    d, rec, seen = nudge_disp
    run = _nudge_run(ap.merge({"max_nudges": 2}, None), "Plan:\n1. edit x\n2. run tests")
    await d._nudge_until_changed(run, True)
    (call,) = run.driver.calls
    assert call["kind"] == "resume" and call["prompt"] == rh.NUDGE_PLAN_TEXT
    assert run.result.output == "Changed app/x.py" and run.files_changed == ["app/x.py"]
    assert seen["observed"] == 1 and run.nudges == 1
    assert _rounds(rec, "nudge")[0]["data"]["attempt"] == 2 and rec["steps"] == [2]


async def test_no_nudge_by_default_or_for_an_empty_turn(nudge_disp):
    d, _rec, _seen = nudge_disp
    run = _nudge_run(ap.NEUTRAL, "Plan:\n1. edit x\n2. run tests")
    await d._nudge_until_changed(run, True)
    assert run.driver.calls == []
    run = _nudge_run(ap.merge({"max_nudges": 3}, None), "Done, nothing needed.")
    await d._nudge_until_changed(run, True)
    assert run.driver.calls == []


async def test_nudges_are_bounded(nudge_disp, monkeypatch):
    d, _rec, _seen = nudge_disp

    async def _still_nothing(run):
        run.files_changed = []

    monkeypatch.setattr(d, "_observe_files_changed", _still_nothing)
    run = _nudge_run(ap.merge({"max_nudges": 2}, None), "Should I proceed?")
    run.driver = _Driver(_ok("Shall I continue?"))
    await d._nudge_until_changed(run, True)
    assert len(run.driver.calls) == 2 and run.nudges == 2


async def test_nudge_refused_by_the_budget(nudge_disp):
    d, rec, _seen = nudge_disp
    rec["budget_denied"] = True
    run = _nudge_run(ap.merge({"max_nudges": 1}, None), "Should I proceed?")
    await d._nudge_until_changed(run, True)
    assert run.driver.calls == []
    assert "budget" in _rounds(rec, "nudge")[0]["data"]["reason"]


# ── Park ─────────────────────────────────────────────────────


def test_park_only_with_wait_for_reset():
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    run = _run()
    run.result = _limited(next_=None)
    soon = (datetime.now(UTC) + timedelta(hours=1)).replace(microsecond=0)
    run.result.metadata["account"]["cooldown_until"] = soon.isoformat().replace("+00:00", "Z")
    d._decide_park(run)
    assert "park" not in run.result.metadata
    run.policy = ap.merge({"wait_for_reset": True}, None)
    d._decide_park(run)
    park = run.result.metadata["park"]
    assert park["resets_at"] == soon.isoformat().replace("+00:00", "Z")
    assert park["resume_at"] == (soon + timedelta(seconds=60)).isoformat().replace("+00:00", "Z")


# ── Subscription budget (D4): booking and the budget gate ─────


async def test_a_subscription_account_run_books_no_dollars(disp):
    d, rec = disp
    run = _run()
    sub = DriverResult(
        success=True, cost_usd=0.7, metadata={"account": {"id": "x"}, "billing": "subscription"}
    )
    api = DriverResult(
        success=True, cost_usd=0.4, metadata={"account": {"id": "y"}, "billing": "api"}
    )
    plain = DriverResult(success=True, cost_usd=0.3, metadata={"billing": "subscription"})
    for result in (sub, api, plain):
        await d._book_spend(run, result, governor_too=True)
    # Without an account (accounts off) a subscription run books as before.
    assert rec["booked"] == [0.4, 0.3] and run.spent_usd == pytest.approx(0.7)


class _ClaudeLike:
    name = "claude_code"

    def cost_per_task(self) -> float:
        return 0.5


async def _gate(monkeypatch, preview, *, interactive=False):
    import life_graph.drivers.dispatcher as disp_mod

    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    asked: list = []
    events: list = []

    async def _authorize(*_a, **k):
        asked.append(k)
        return BudgetDecision(False, False, "monthly cap reached", 10.0, 10.0, 0.0)

    async def _preview(driver, tenant_id, *, unattended=False, now=None):
        asked.append({"preview_unattended": unattended})
        return preview

    async def _emit(*_a):
        return None

    monkeypatch.setattr(disp_mod.governor, "authorize", _authorize)
    monkeypatch.setattr(rh.accounts_hook, "preview", _preview)
    monkeypatch.setattr(d, "_emit", _emit)
    monkeypatch.setattr(
        task_events, "emit", lambda *a, **k: events.append({"kind": a[2], "text": a[3], **k})
    )
    run = _run(interactive=interactive)
    run.driver = _ClaudeLike()
    return await d._budget_gate(run), asked, events


async def test_budget_gate_unchanged_with_accounts_off(monkeypatch):
    monkeypatch.setattr(settings, "driver_accounts_enabled", False)
    denied, asked, events = await _gate(monkeypatch, None)
    assert denied is not None and denied.metadata["budget_throttled"]
    assert asked == [{"estimated_usd": 0.5, "interactive": False}] and events == []


async def test_subscription_account_skips_the_dollar_cap_and_says_why(monkeypatch, accounts_on):
    preview = {
        "state": "selected",
        "kind": "subscription",
        "name": "work",
        "budget": {"share_limit": 0.9, "used_percent": 42.0, "window": "five_hour"},
    }
    denied, asked, events = await _gate(monkeypatch, preview)
    assert denied is None and asked == [{"preview_unattended": True}]
    (event,) = events
    assert event["kind"] == "budget" and "billed to the plan" in event["text"]
    assert "five_hour 42%" in event["text"]


async def test_api_key_account_stays_under_the_dollar_cap(monkeypatch, accounts_on):
    preview = {"state": "selected", "kind": "api_key", "name": "key", "budget": None}
    denied, asked, events = await _gate(monkeypatch, preview)
    assert denied is not None and "dollar budget applies" in events[0]["text"]
