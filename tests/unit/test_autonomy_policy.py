"""The owner's autonomy policy (docs/specs/agent-drivers.md, "Autonomy policy").

Every rule may only narrow change_policy.auto_gate: no policy row = nothing
added; a policy can add refusals but never turn one into an approval.
"""

from __future__ import annotations

import itertools
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from life_graph.services.dev import autonomy_policy as ap
from life_graph.services.dev import change_policy as cp
from tests.unit.fakes import FakeResult, FakeSession

PROOF = ["build_ok_diff", *cp.CODE_PROOF_CHECKS]


def _change(files=("docs/a.md",), lines=10, kind="docs", **extra):
    return {"files": list(files), "lines": lines, "kind": kind, "review_reasons": [], **extra}


def _payload(change=None, **extra):
    return {
        "driver": "local",
        "project_id": "p1",
        "task_id": "task-1",
        "checks": ["build_ok_diff"],
        "verified": True,
        "unverifiable_checks": [],
        "change": change or _change(),
        **extra,
    }


def _policy(**global_fields) -> ap.EffectivePolicy:
    return ap.merge(global_fields, None)


# ── validation ───────────────────────────────────────────────


def test_defaults_are_neutral():
    g = ap.GlobalAutonomyPolicy()
    assert g.conditions.is_neutral()
    assert g.daily_auto_approval_cap is None
    assert g.review_stages == [] and g.verify_fix_rounds == 0 and g.review_fix_rounds == 0
    eff = ap.merge(g.model_dump(), None)
    assert eff.configured and eff.verify_fix_rounds == 0 and not eff.review_stages
    assert ap.policy_reasons(eff, _change(), _payload()) == []


@pytest.mark.parametrize(
    "body",
    [
        {"verify_fix_rounds": ap.MAX_FIX_ROUNDS + 1},
        {"review_fix_rounds": -1},
        {"review_stages": [{"name": f"s{i}", "reviewer": "human"} for i in range(5)]},
        {"review_stages": [{"name": "a", "reviewer": "codex"}]},
        {"review_stages": [{"name": "a", "reviewer": "model:"}]},
        {"review_stages": [{"name": "A", "reviewer": "human"}, {"name": "a", "reviewer": "human"}]},
        {"daily_auto_approval_cap": -1},
        {"conditions": {"max_files": -1}},
        {"conditions": {"risk_tolerance": "some"}},
        {"conditions": {"unknown": 1}},
        {"surprise": True},
    ],
)
def test_invalid_global_policies_are_refused(body):
    with pytest.raises(ValidationError):
        ap.GlobalAutonomyPolicy.model_validate(body)


def test_project_policy_has_no_cap_and_null_means_inherit():
    with pytest.raises(ValidationError):
        ap.ProjectAutonomyPolicy.model_validate({"daily_auto_approval_cap": 3})
    p = ap.ProjectAutonomyPolicy()
    assert p.review_stages is None and p.verify_fix_rounds is None


def test_reviewers_accepted():
    for reviewer in ("human", "pr_agent", "model:gemini/gemini-2.5-flash"):
        assert ap.ReviewStage(name="x", reviewer=reviewer).reviewer == reviewer


# ── merge ────────────────────────────────────────────────────


def test_no_rows_is_neutral():
    assert ap.merge(None, None) is ap.NEUTRAL
    assert not ap.NEUTRAL.configured


def test_project_rounds_and_stages_override_but_conditions_stack():
    g = {
        "conditions": {"max_files": 5},
        "verify_fix_rounds": 2,
        "review_stages": [{"name": "sec", "reviewer": "pr_agent"}],
    }
    p = {"conditions": {"max_files": 10}, "verify_fix_rounds": 1, "review_stages": []}
    eff = ap.merge(g, p)
    assert eff.verify_fix_rounds == 1
    assert eff.review_stages == ()
    assert [label for label, _ in eff.conditions] == ["global", "project"]
    # The project's looser max_files does not loosen the global one.
    reasons = ap.policy_reasons(eff, _change(files=[f"docs/{i}.md" for i in range(7)]), _payload())
    assert any("owner rule (global): 7 files" in r for r in reasons)
    assert not any("owner rule (project)" in r for r in reasons)


def test_project_null_inherits_global():
    eff = ap.merge({"review_fix_rounds": 2}, {"conditions": {}})
    assert eff.review_fix_rounds == 2


def test_human_stage_in_either_list_sticks():
    g = {"review_stages": [{"name": "owner", "reviewer": "human"}]}
    p = {"review_stages": [{"name": "lint", "reviewer": "pr_agent"}]}
    eff = ap.merge(g, p)
    assert [s.name for s in eff.review_stages] == ["lint"]
    assert eff.human_stage
    assert "a human review stage is configured" in ap.policy_reasons(eff, _change(), _payload())[0]


def test_corrupt_row_fails_closed():
    eff = ap.merge({"verify_fix_rounds": 99}, None)
    assert eff.configured and eff.verify_fix_rounds == 0
    assert ap.policy_reasons(eff, _change(), _payload())  # refuses


# ── each condition only narrows ──────────────────────────────


@pytest.mark.parametrize(
    ("conditions", "change", "payload_extra", "needle"),
    [
        ({"max_changed_lines": 5}, _change(lines=6), {}, "6 changed lines"),
        ({"max_files": 1}, _change(files=["a.md", "b.md"]), {}, "2 files changed"),
        ({"paths_allowed": ["docs/*"]}, _change(files=["docs/a.md", "x.py"]), {}, "x.py"),
        ({"paths_forbidden": ["*secret*"]}, _change(files=["cfg/secret.md"]), {}, "forbidden"),
        ({"require_verification_passed": True}, _change(), {"verified": False}, "verification"),
        ({"require_verification_passed": True}, _change(), {"checks": []}, "verification"),
        (
            {"require_verification_passed": True},
            _change(),
            {"unverifiable_checks": ["tests_pass"]},
            "verification",
        ),
        ({"require_no_reviewer_objection": True}, _change(), {}, "no reviewer looked"),
        ({"risk_tolerance": "warnings"}, _change(), {}, "no complete risk report"),
        (
            {"risk_tolerance": "warnings"},
            _change(),
            {"autonomy": {"risk": {"block": 1, "warn": 0, "complete": True}}},
            "1 blocking",
        ),
        (
            {"risk_tolerance": "none"},
            _change(),
            {"autonomy": {"risk": {"block": 0, "warn": 2, "complete": True}}},
            "2 risk warning",
        ),
        (
            {"risk_tolerance": "none"},
            _change(),
            {"autonomy": {"risk": {"block": 0, "warn": 0, "complete": False}}},
            "no complete risk report",
        ),
    ],
)
def test_each_condition_refuses(conditions, change, payload_extra, needle):
    eff = _policy(conditions=conditions)
    reasons = ap.policy_reasons(eff, change, _payload(change, **payload_extra))
    assert any(needle in r for r in reasons), reasons


@pytest.mark.parametrize(
    ("conditions", "payload_extra"),
    [
        ({"max_changed_lines": 10, "max_files": 1}, {}),
        ({"paths_allowed": ["docs/*"], "paths_forbidden": ["*.py"]}, {}),
        ({"require_verification_passed": True}, {}),
        (
            {"require_no_reviewer_objection": True},
            {"autonomy": {"review_stages": [{"name": "a", "verdict": "no_objection"}]}},
        ),
        (
            {"risk_tolerance": "warnings"},
            {"autonomy": {"risk": {"block": 0, "warn": 3, "complete": True}}},
        ),
    ],
)
def test_each_condition_holds_when_met(conditions, payload_extra):
    eff = _policy(conditions=conditions)
    assert ap.policy_reasons(eff, _change(), _payload(**payload_extra)) == []


def test_second_opinion_ok_counts_as_a_reviewer_looking():
    eff = _policy(conditions={"require_no_reviewer_objection": True})
    change = _change(second_opinion="second opinion: ok (fine)")
    assert ap.policy_reasons(eff, change, _payload(change)) == []


def test_stage_objection_or_unavailable_always_refuses_when_configured():
    eff = _policy()
    for verdict, needle in (("objection", "objected"), ("unavailable", "could not run")):
        payload = _payload(autonomy={"review_stages": [{"name": "sec", "verdict": verdict}]})
        assert any(needle in r for r in ap.policy_reasons(eff, _change(), payload))


def test_payload_human_stage_refuses():
    payload = _payload(autonomy={"human_stage": True})
    assert ap.policy_reasons(_policy(), _change(), payload)


def test_daily_cap_and_kill_switch():
    eff = _policy(daily_auto_approval_cap=2)
    assert ap.policy_reasons(eff, _change(), _payload(), auto_today=1) == []
    assert "cap reached (2 of 2" in ap.policy_reasons(eff, _change(), _payload(), auto_today=2)[0]
    assert "could not be counted" in ap.policy_reasons(eff, _change(), _payload())[0]
    zero = _policy(daily_auto_approval_cap=0)
    assert ap.policy_reasons(zero, _change(), _payload(), auto_today=0)
    paused = ap.policy_reasons(_policy(), _change(), _payload(), paused=True)
    assert paused == ["autonomy is paused (kill switch)"]


def test_unconfigured_policy_adds_nothing_whatever_the_change():
    huge = _change(files=[f"f{i}.py" for i in range(500)], lines=10**6, kind="code")
    payload = _payload(huge, verified=False, autonomy={"human_stage": True})
    assert ap.policy_reasons(ap.NEUTRAL, huge, payload, auto_today=10**6, paused=True) == []


def test_conditions_only_ever_add_reasons():
    """Property: adding any condition never removes a reason another produced."""
    options = [
        {"max_changed_lines": 3},
        {"max_files": 1},
        {"paths_allowed": ["docs/*"]},
        {"paths_forbidden": ["docs/b.md"]},
        {"require_verification_passed": True},
        {"require_no_reviewer_objection": True},
        {"risk_tolerance": "none"},
    ]
    change = _change(files=["docs/a.md", "docs/b.md", "src/x.py"], lines=12)
    payload = _payload(change, verified=False)
    for a, b in itertools.combinations(options, 2):
        ra = set(ap.policy_reasons(_policy(conditions=a), change, payload))
        both = set(ap.policy_reasons(_policy(conditions={**a, **b}), change, payload))
        assert ra <= both


# ── owner_policy_reasons: reads, counts, fails closed ─────────


def _row(scope, policy, tenant="raja"):
    return SimpleNamespace(scope=scope, policy=policy, tenant_id=tenant)


async def test_no_row_adds_nothing():
    assert await ap.owner_policy_reasons(FakeSession(), "raja", _payload(), _change()) == []


async def test_unreadable_policy_refuses():
    class Broken(FakeSession):
        async def execute(self, *_a, **_k):
            raise RuntimeError("db down")

    reasons = await ap.owner_policy_reasons(Broken(), "raja", _payload(), _change())
    assert reasons == ["the owner's autonomy policy could not be read"]


async def test_other_tenants_rows_are_ignored():
    session = FakeSession([_row("global", {"daily_auto_approval_cap": 0}, tenant="other")])
    assert await ap.owner_policy_reasons(session, "raja", _payload(), _change()) == []


async def test_cap_is_counted_from_todays_auto_approvals(monkeypatch):
    async def running(_t):
        return False

    monkeypatch.setattr(ap, "autonomy_stopped", running)
    session = FakeSession([_row("global", {"daily_auto_approval_cap": 3})], FakeResult([3]))
    reasons = await ap.owner_policy_reasons(session, "raja", _payload(), _change())
    assert reasons == ["daily auto-approval cap reached (3 of 3 today)"]
    count_sql = str(session.statements[1].compile(compile_kwargs={"literal_binds": True}))
    assert "count(DISTINCT approvals.source_ref)" in count_sql
    assert "approvals.kind IN ('driver_pr', 'driver_merge')" in count_sql
    assert "tenant_id = 'raja'" in count_sql and "'auto:%'" in count_sql
    assert "source_ref != 'task-1'" in count_sql


async def test_kill_switch_refuses_when_a_policy_exists(monkeypatch):
    async def paused(_t):
        return True

    monkeypatch.setattr(ap, "autonomy_stopped", paused)
    session = FakeSession([_row("global", {})])
    reasons = await ap.owner_policy_reasons(session, "raja", _payload(), _change())
    assert reasons == ["autonomy is paused (kill switch)"]


# ── auto_gate: the policy is asked last and only narrows ──────


def _records(monkeypatch, records):
    async def track(_s, _t, agent_id, _p):
        merged, failed = records.get(agent_id, (0, 0))
        total = merged + failed
        return {
            "merged": merged,
            "total": total,
            "merge_rate": merged / total if total else None,
            "established": total >= 3,
        }

    import life_graph.services.dev.outcomes as outcomes

    monkeypatch.setattr(outcomes, "track_record", track)


async def test_auto_gate_refuses_with_the_owner_reason(monkeypatch):
    _records(monkeypatch, {"local": (8, 1)})

    async def owner(_s, _t, _payload, _change):
        return ["owner rule (global): 2 files changed (at most 1)"]

    monkeypatch.setattr(cp, "owner_policy_reasons", owner)
    ok, why, record = await cp.auto_gate(FakeSession(), "raja", _payload(_change(kind="tests")))
    assert not ok and why == "owner policy: owner rule (global): 2 files changed (at most 1)"
    assert record["merged"] == 8


async def test_auto_gate_existing_refusals_win_and_policy_is_not_asked(monkeypatch):
    _records(monkeypatch, {"local": (1, 5)})
    asked = []

    async def owner(*_a):
        asked.append(True)
        return []

    monkeypatch.setattr(cp, "owner_policy_reasons", owner)
    ok, why, _ = await cp.auto_gate(FakeSession(), "raja", _payload(_change(kind="tests")))
    assert not ok and why.startswith("not yet trusted") and not asked  # 1 of 6 merged
    ok, why, _ = await cp.auto_gate(
        FakeSession(), "raja", _payload(_change(kind="code"), checks=["build_ok_diff"])
    )
    assert not ok and why.startswith("needs review") and not asked


async def test_auto_gate_with_a_permissive_policy_is_unchanged(monkeypatch):
    _records(monkeypatch, {"local": (8, 1), "local:code": (6, 0)})
    session = FakeSession([_row("global", {"conditions": {"max_files": 100}})], FakeResult([0]))

    async def running(_t):
        return False

    monkeypatch.setattr(ap, "autonomy_stopped", running)
    ok, why, _ = await cp.auto_gate(
        session, "raja", _payload(_change(kind="code", files=["a.py"]), checks=PROOF)
    )
    assert ok and "6/6 code PRs merged" in why
