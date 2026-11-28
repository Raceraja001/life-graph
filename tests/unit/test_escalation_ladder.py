"""Escalation ladder and deterministic starting floor (2026-11-28).

docs/specs/agent-drivers.md, "Escalation ladder, starting floor, outcome log
(2026-11-28)": a bounce after failed verification moves one rung up
(local qwen3:14b -> local qwen3-coder:30b -> claude_code), cloud is never a
rung, pins don't climb unless allowed, the kill switch / metered billing /
subscription share / daily top-rung cap refuse a rung, and a refused climb
bounces on the same driver as before. The floor starts protected-path or
failed-before code tasks at the top rung; pins win.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

import life_graph.drivers.ladder_steps as ls_mod
import life_graph.drivers.review_stages as rs_mod
from life_graph.config import settings
from life_graph.core.budget import BudgetDecision
from life_graph.drivers import escalation as esc
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher, _DispatchRun
from life_graph.services.dev import autonomy_policy as ap
from life_graph.services.dev.verifiers import VerifierResult

FAIL = VerifierResult("tests_pass", False, {"stdout": "1 failed"})
PASS = VerifierResult("tests_pass", True, {})

Q14 = "ollama_chat/qwen3:14b"
Q30 = "ollama_chat/qwen3-coder:30b"


class _D:
    def __init__(self, name, billing, *, available=True, pin_required=False, cost=0.0):
        self.name = name
        self.billing = billing
        self._available = available
        self.pin_required = pin_required
        self._cost = cost

    async def available(self):
        return self._available

    def cost_per_task(self):
        return self._cost


class _Registry:
    def __init__(self, *drivers):
        self._d = {d.name: d for d in drivers}

    def get(self, name):
        return self._d.get(name)


def _fleet(**over):
    return _Registry(
        over.get("local", _D("local", "local")),
        over.get("claude_code", _D("claude_code", "subscription", cost=2.0)),
        _D("cloud", "api", pin_required=True),
    )


def _run(driver, model=Q14, *, task_type="code", instruction="fix the bug in app/x.py", **kw):
    task_id = str(uuid.uuid4())
    run = _DispatchRun(
        tenant_id="t1",
        task_id=task_id,
        instruction=instruction,
        task_type=task_type,
        persona_name=None,
        session=object(),
        cost_cap_usd=2.0,
        interactive=False,
        spec_first=False,
        acceptance_tests=None,
        **kw,
    )
    run.packet = ContextPacket(
        task_id=uuid.UUID(task_id),
        tenant_id="t1",
        task_type=task_type,
        instruction=instruction,
        persona_model=model,
    )
    run.driver = driver
    run.persona_model = model
    run.verify_chain = ["tests_pass"]
    run.result = DriverResult(success=True, output="first try", cost_usd=0.0)
    return run


@pytest.fixture
def disp(monkeypatch):
    """A dispatcher on a fake fleet: kill switch off, cap open, accounts off."""
    reg = _fleet()
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    state = {"stopped": False, "usage": (0, 0), "failed": False}

    async def _stopped(_t):
        return state["stopped"]

    async def _usage(_run):
        return state["usage"]

    async def _failed(_run):
        return state["failed"]

    async def _noop(*_a, **_k):
        return None

    monkeypatch.setattr(ls_mod, "driver_registry", reg)
    monkeypatch.setattr(ls_mod, "autonomy_stopped", _stopped)
    monkeypatch.setattr(rs_mod, "autonomy_stopped", _stopped)
    monkeypatch.setattr(d, "_top_usage", _usage)
    monkeypatch.setattr(d, "_recent_failure", _failed)
    monkeypatch.setattr(d, "_emit", _noop)
    monkeypatch.setattr(settings, "driver_escalation_ladder", "")
    monkeypatch.setattr(settings, "driver_escalation_enabled", True)
    monkeypatch.setattr(settings, "driver_escalation_allow_metered", False)
    monkeypatch.setattr(settings, "driver_escalation_top_share", 0.25)
    monkeypatch.setattr(settings, "driver_escalation_top_daily_min", 2)
    monkeypatch.setattr(settings, "driver_start_floor_enabled", True)
    monkeypatch.setattr(settings, "driver_accounts_enabled", False)
    return d, reg, state


# ── Pure rules ───────────────────────────────────────────────


def test_parse_ladder_keeps_order_and_model_colons():
    rungs = esc.parse_ladder(" local:ollama_chat/qwen3:14b , ,claude_code,claude_code")
    assert rungs == [esc.Rung("local", "ollama_chat/qwen3:14b"), esc.Rung("claude_code")]
    assert [r.label for r in rungs] == ["local:ollama_chat/qwen3:14b", "claude_code"]


def test_default_ladder_skips_unregistered_and_never_has_cloud(monkeypatch):
    monkeypatch.setattr(settings, "driver_escalation_ladder", "")
    assert [r.label for r in esc.configured_ladder(_fleet())] == [
        f"local:{Q14}",
        f"local:{Q30}",
        "claude_code",
    ]
    only_local = _Registry(_D("local", "local"))
    assert [r.driver for r in esc.configured_ladder(only_local)] == ["local", "local"]
    # Even when the owner lists it, a pin_required driver is not a rung.
    monkeypatch.setattr(settings, "driver_escalation_ladder", "local,cloud,claude_code")
    assert [r.label for r in esc.configured_ladder(_fleet())] == ["local", "claude_code"]


def test_position_and_tiers():
    ladder = esc.configured_ladder(_fleet())
    assert esc.position(ladder, "local", "qwen3:14b") == 0  # provider prefix ignored
    assert esc.position(ladder, "local", Q30) == 1
    assert esc.position(ladder, "local", "gemini/gemini-3.6-flash") == 0  # off-model: lowest
    assert esc.position(ladder, "claude_code", None) == 2
    assert esc.position(ladder, "opencode", None) is None
    assert [esc.tier_of(i, 3) for i in range(3)] == ["cheap", "balanced", "best"]
    assert esc.tier_of(None, 3) is None and esc.tier_of(0, 1) == "best"


def test_pin_state():
    assert esc.pin_state(None, None) == (False, True)
    assert esc.pin_state(None, "codex") == (True, False)  # arena racer
    assert esc.pin_state(SimpleNamespace(driver="auto", properties={}), None) == (False, True)
    assert esc.pin_state(SimpleNamespace(driver=None, properties={}), None) == (False, True)
    pinned = SimpleNamespace(driver="claude_code", properties={})
    assert esc.pin_state(pinned, None) == (True, False)
    allowing = SimpleNamespace(driver="local", properties={"allow_escalation": True})
    assert esc.pin_state(allowing, None) == (True, True)


def test_top_cap(monkeypatch):
    monkeypatch.setattr(settings, "driver_escalation_top_share", 0.25)
    monkeypatch.setattr(settings, "driver_escalation_top_daily_min", 2)
    assert esc.top_cap_allows(0, 0) and esc.top_cap_allows(1, 1)  # the daily minimum
    assert not esc.top_cap_allows(2, 3)
    assert esc.top_cap_allows(2, 11)  # 25% of 12 = 3
    assert not esc.top_cap_allows(3, 11)
    monkeypatch.setattr(settings, "driver_escalation_top_daily_min", 0)
    monkeypatch.setattr(settings, "driver_escalation_top_share", 0.0)
    assert not esc.top_cap_allows(0, 100)


@pytest.mark.parametrize(
    ("instruction", "hit"),
    [
        ("Fix the bug in app/x.py.", None),
        ("Add a column in alembic/versions/069_x.py", "alembic/versions/069_x.py"),
        ("Bump the pin in `pyproject.toml`", "pyproject.toml"),
        ("Tidy .github/workflows/ci.yml", ".github/workflows/ci.yml"),
        ("Rotate the key in .env", ".env"),
        ("Add a helper function", None),
    ],
)
def test_protected_reason_from_the_instruction(instruction, hit):
    why = esc.protected_reason(instruction)
    assert (why is None) if hit is None else (why == f"protected path: {hit}")


def test_protected_reason_uses_declared_files_and_project_globs():
    assert esc.protected_reason("do it", ["uv.lock"]) == "protected path: uv.lock"
    assert esc.protected_reason("edit life_graph/auth/x.py", None, ["life_graph/auth/*"])


def test_shadow_tier_is_a_simple_placeholder():
    def tier(instruction="x", protected=False, failed=False):
        return esc.shadow_tier(
            instruction=instruction, task_type="code", protected=protected, failed_before=failed
        )[0]

    assert tier(protected=True) == "best" and tier(failed=True) == "best"
    assert tier("touch a/b.py, c/d.py and e/f.py") == "balanced"
    assert tier() == "cheap"


# ── The climb ────────────────────────────────────────────────


async def test_climb_swaps_the_local_model_then_goes_to_claude_code(disp):
    d, reg, _ = disp
    run = _run(reg.get("local"), Q14)
    await d._climb(run, 2, [FAIL])
    assert run.driver.name == "local" and run.packet.persona_model == Q30
    assert run.escalations[-1]["from"] == f"local:{Q14}"
    assert run.escalations[-1]["to"] == f"local:{Q30}"
    assert "tests_pass" in run.escalations[-1]["reason"]
    assert not run.reached_top
    await d._climb(run, 3, [FAIL])
    assert run.driver.name == "claude_code" and run.reached_top
    # A driver-only rung restores the persona's own model.
    assert run.packet.persona_model == Q14
    await d._climb(run, 4, [FAIL])  # already at the top: nothing more
    assert run.driver.name == "claude_code" and len(run.escalations) == 2


async def test_climb_skips_an_unavailable_rung(disp, monkeypatch):
    d, _, _ = disp
    reg = _fleet(claude_code=_D("claude_code", "subscription", available=False))
    monkeypatch.setattr(ls_mod, "driver_registry", reg)
    run = _run(reg.get("local"), Q30)
    await d._climb(run, 2, [FAIL])
    assert run.driver.name == "local" and run.packet.persona_model == Q30  # unchanged
    assert run.escalations[-1]["to"] is None
    assert "claude_code: not available" in run.escalations[-1]["blocked"]


async def test_climb_skips_a_metered_rung_unless_allowed(disp, monkeypatch):
    d, _, _ = disp
    reg = _fleet(claude_code=_D("claude_code", "api", cost=0.5))
    monkeypatch.setattr(ls_mod, "driver_registry", reg)
    run = _run(reg.get("local"), Q30)
    await d._climb(run, 2, [FAIL])
    assert run.driver.name == "local" and "metered" in run.escalations[-1]["blocked"]

    async def _allow(*_a, **_k):
        return BudgetDecision(True, False, "ok", 0.0, 10.0, 10.0)

    monkeypatch.setattr(settings, "driver_escalation_allow_metered", True)
    monkeypatch.setattr(ls_mod.governor, "authorize", _allow)
    await d._climb(run, 3, [FAIL])
    assert run.driver.name == "claude_code"


async def test_kill_switch_stops_the_climb(disp):
    d, reg, state = disp
    state["stopped"] = True
    run = _run(reg.get("local"), Q14)
    await d._climb(run, 2, [FAIL])
    assert run.packet.persona_model == Q14
    assert run.escalations == [
        {
            "attempt": 2,
            "from": f"local:{Q14}",
            "to": None,
            "reason": "verification failed (tests_pass)",
            "blocked": "autonomy is paused",
        }
    ]


async def test_top_rung_cap_refuses_claude_code(disp):
    d, reg, state = disp
    state["usage"] = (2, 3)  # already 2 of 3 today, minimum 2: full
    run = _run(reg.get("local"), Q30)
    await d._climb(run, 2, [FAIL])
    assert run.driver.name == "local"
    assert "top-rung cap reached (2 of 3 today)" in run.escalations[-1]["blocked"]


async def test_unreadable_top_usage_refuses_the_top_rung(disp):
    d, reg, state = disp
    state["usage"] = None
    run = _run(reg.get("local"), Q30)
    await d._climb(run, 2, [FAIL])
    assert run.driver.name == "local" and "could not be counted" in run.escalations[-1]["blocked"]


async def test_subscription_share_refuses_claude_code(disp, monkeypatch):
    d, reg, _ = disp
    monkeypatch.setattr(settings, "driver_accounts_enabled", True)

    async def _preview(*_a, **_k):
        return {"state": "over_budget"}

    monkeypatch.setattr(ls_mod.accounts_hook, "preview", _preview)
    run = _run(reg.get("local"), Q30)
    await d._climb(run, 2, [FAIL])
    assert run.driver.name == "local" and "over_budget" in run.escalations[-1]["blocked"]


async def test_pins_do_not_climb_unless_allowed(disp):
    d, reg, _ = disp
    run = _run(reg.get("local"), Q14)
    run.pinned, run.pin_allows_escalation = True, False
    await d._climb(run, 2, [FAIL])
    assert run.packet.persona_model == Q14 and run.escalations == []
    run.pin_allows_escalation = True
    await d._climb(run, 2, [FAIL])
    assert run.packet.persona_model == Q30


async def test_disabled_ladder_and_off_ladder_drivers_do_not_climb(disp, monkeypatch):
    d, reg, _ = disp
    off = _run(_D("opencode", "local"), None)
    await d._climb(off, 2, [FAIL])
    assert off.driver.name == "opencode" and off.escalations == []
    monkeypatch.setattr(settings, "driver_escalation_enabled", False)
    run = _run(reg.get("local"), Q14)
    await d._climb(run, 2, [FAIL])
    assert run.packet.persona_model == Q14 and run.escalations == []


# ── Inside the bounce loop: limits and rounds unchanged ──────


def _script(monkeypatch, d, outcomes, seen):
    outcomes = list(outcomes)

    async def _bounce(**kw):
        run = kw["run"]
        seen.append((kw["attempt"], kw["driver"].name, run.packet.persona_model))
        if outcomes.pop(0) == "pass":
            run.bounce_outcome = "passed"
            run.verifier_results = [PASS]
            return DriverResult(success=True, output="ok", metadata={})
        run.bounce_outcome = "verify_failed"
        run.verifier_results = [FAIL]
        return None

    async def _noop(*_a, **_k):
        return None

    async def _allow(*_a, **_k):
        return BudgetDecision(True, False, "ok", 0.0, 10.0, 10.0)

    monkeypatch.setattr(d, "_bounce_task", _bounce)
    monkeypatch.setattr(d, "_create_approval_entry", _noop)
    monkeypatch.setattr(d, "_observe_files_changed", _noop)
    monkeypatch.setattr(rs_mod.governor, "authorize", _allow)


async def test_default_one_bounce_runs_one_rung_up_then_needs_a_person(disp, monkeypatch):
    d, reg, _ = disp
    seen: list = []
    _script(monkeypatch, d, ["fail"], seen)
    run = _run(reg.get("local"), Q14)
    await d._bounce_or_escalate(run, [FAIL])
    assert seen == [(2, "local", Q30)]  # exactly one bounce, on the next rung
    assert run.result.metadata["needs_human"] is True


async def test_fix_rounds_climb_to_the_top_and_stay_bounded(disp, monkeypatch):
    d, reg, _ = disp
    seen: list = []
    _script(monkeypatch, d, ["fail", "fail", "fail"], seen)
    run = _run(reg.get("local"), Q14)
    run.policy = ap.merge({"verify_fix_rounds": 2}, None)
    await d._bounce_or_escalate(run, [FAIL])
    assert seen == [(2, "local", Q30), (3, "claude_code", Q14), (4, "claude_code", Q14)]
    assert run.reached_top and run.result.metadata["verify_fix_rounds"] == 2


async def test_a_bounce_that_passes_on_the_next_rung_keeps_that_driver(disp, monkeypatch):
    d, reg, _ = disp
    seen: list = []
    _script(monkeypatch, d, ["pass"], seen)
    run = _run(reg.get("local"), Q30)
    await d._bounce_or_escalate(run, [FAIL])
    assert seen == [(2, "claude_code", Q30)]  # the persona's own model, kept
    assert run.result.success and run.driver.name == "claude_code"


# ── Starting floor ───────────────────────────────────────────


async def test_floor_starts_a_protected_path_task_at_the_top(disp):
    d, reg, _ = disp
    run = _run(reg.get("local"), Q14, instruction="Add a migration in alembic/versions/069_x.py")
    await d._apply_start_floor(run)
    assert run.driver.name == "claude_code" and run.reached_top
    assert run.start_reason == "floor: protected path: alembic/versions/069_x.py"
    assert run.start_driver == "claude_code"


async def test_floor_starts_a_failed_before_task_at_the_top(disp):
    d, reg, state = disp
    state["failed"] = True
    run = _run(reg.get("local"), Q14)
    await d._apply_start_floor(run)
    assert run.driver.name == "claude_code"
    assert run.start_reason.startswith("floor: failed before")


async def test_persona_pin_beats_the_floor(disp):
    d, reg, state = disp
    state["failed"] = True
    run = _run(reg.get("local"), Q14, instruction="Edit pyproject.toml")
    run.persona = SimpleNamespace(driver="local", properties={})
    await d._apply_start_floor(run)
    assert run.driver.name == "local" and run.start_reason == "pinned"
    assert run.floor_trigger == "protected path: pyproject.toml"  # still logged (shadow)


async def test_floor_respects_the_top_cap_and_logs_why(disp):
    d, reg, state = disp
    state["usage"] = (5, 5)
    run = _run(reg.get("local"), Q14, instruction="Edit pyproject.toml")
    await d._apply_start_floor(run)
    assert run.driver.name == "local" and not run.reached_top
    assert run.start_reason.startswith("selection (floor protected path: pyproject.toml")
    assert "top-rung cap" in run.start_reason


async def test_no_floor_for_plain_or_non_code_tasks_or_when_off(disp, monkeypatch):
    d, reg, _ = disp
    plain = _run(reg.get("local"), Q14)
    await d._apply_start_floor(plain)
    assert plain.driver.name == "local" and plain.start_reason == "selection"
    research = _run(reg.get("local"), Q14, task_type="research", instruction="read CLAUDE.md")
    await d._apply_start_floor(research)
    assert research.driver.name == "local"
    monkeypatch.setattr(settings, "driver_start_floor_enabled", False)
    off = _run(reg.get("local"), Q14, instruction="Edit pyproject.toml")
    await d._apply_start_floor(off)
    assert off.driver.name == "local" and off.floor_trigger


async def test_arena_driver_pin_never_floors(disp):
    d, reg, _ = disp
    run = _run(reg.get("local"), Q14, instruction="Edit pyproject.toml", driver_pin="local")
    await d._apply_start_floor(run)
    assert run.driver.name == "local" and run.pinned and not run.pin_allows_escalation


async def test_a_local_top_rung_is_not_capped(disp, monkeypatch):
    d, _, state = disp
    state["usage"] = (99, 99)
    reg = _Registry(_D("local", "local"))
    monkeypatch.setattr(ls_mod, "driver_registry", reg)
    run = _run(reg.get("local"), Q14)
    await d._climb(run, 2, [FAIL])
    assert run.packet.persona_model == Q30 and run.reached_top
