"""Unit tests for P0.6 episodic-to-decision linking and verified procedural learning."""

from __future__ import annotations

from types import SimpleNamespace

from life_graph.api.procedures import (
    build_procedure_candidate,
    can_auto_execute_side_effects,
    verify_procedure_candidate,
)
from life_graph.services.episodes import link_experience_to_decision


def test_p0_6_link_experience_to_decision_is_bounded():
    props: dict = {}
    for i in range(7):
        props = link_experience_to_decision(
            props,
            decision_id=f"dec-{i}",
            decision_title=f"Decision {i}",
            outcome="correct" if i % 2 == 0 else "pending",
            max_links=5,
        )
    assert len(props["decision_links"]) == 5
    assert [l["decision_id"] for l in props["decision_links"]] == [f"dec-{i}" for i in range(2, 7)]


def test_p0_6_procedure_candidate_requires_prerequisites_checks_recovery_and_observed_outcome():
    incomplete = build_procedure_candidate(
        trigger="deploy api",
        steps=["run deploy.sh"],
        prerequisites=["clean git status"],
        verification_checks=[],
        failure_recovery=[],
        has_side_effects=True,
    )
    res_incomplete = verify_procedure_candidate(
        incomplete,
        observed_outcomes=[{"passed": True, "observed_evidence": "health=200"}],
    )
    assert res_incomplete["verified"] is False
    assert res_incomplete["grants_side_effect_permission"] is False

    complete = build_procedure_candidate(
        trigger="deploy api",
        steps=["sync files", "restart service"],
        prerequisites=["tests pass"],
        verification_checks=["curl /health returns 200"],
        failure_recovery=["git checkout previous commit and restart"],
        has_side_effects=True,
    )
    # Without observed evidence -> not verified
    unobserved = verify_procedure_candidate(complete, observed_outcomes=[{"passed": True}])
    assert unobserved["verified"] is False

    # With full structure + observed passing evidence -> verified, still no side-effect permission
    verified = verify_procedure_candidate(
        complete,
        observed_outcomes=[{"passed": True, "observed_evidence": "systemd active + /health 200"}],
    )
    assert verified["verified"] is True
    assert verified["grants_side_effect_permission"] is False


def test_p0_6_past_success_never_grants_permanent_side_effect_permission():
    high_conf_proc = SimpleNamespace(
        times_applied=50,
        success_count=50,
        confidence=0.99,
        has_side_effects=True,
    )
    assert can_auto_execute_side_effects(high_conf_proc) is False
    assert can_auto_execute_side_effects(high_conf_proc, explicit_action_approval=True) is True


# ── P5.4 Procedural promotion needs evidence, not one lucky run ──────────


def _complete_candidate(**over):
    from life_graph.api.procedures import build_procedure_candidate

    kwargs = {
        "trigger": "deploy api",
        "steps": ["sync files", "restart service"],
        "prerequisites": ["tests pass", "clean git status"],
        "verification_checks": ["curl /health returns 200"],
        "failure_recovery": ["git checkout previous commit and restart"],
        "failure_modes": ["service binds before migrations finish"],
        "tool_versions": {"python": "3.11.9", "alembic": "1.13.2"},
        "has_side_effects": True,
    }
    kwargs.update(over)
    return build_procedure_candidate(**kwargs)


def test_p5_4_candidate_records_prerequisites_failure_modes_and_tool_versions():
    candidate = _complete_candidate()

    assert candidate["status"] == "candidate"
    assert candidate["verified_outcomes_count"] == 0
    assert candidate["is_reliable"] is False
    assert candidate["owner_confirmed"] is False
    assert candidate["prerequisites"] == ["tests pass", "clean git status"]
    assert candidate["failure_modes"] == ["service binds before migrations finish"]
    assert candidate["tool_versions"] == {"python": "3.11.9", "alembic": "1.13.2"}


def test_p5_4_one_off_run_stays_a_candidate_until_two_verified_outcomes():
    from life_graph.api.procedures import MIN_VERIFIED_OUTCOMES, verify_procedure_candidate

    assert MIN_VERIFIED_OUTCOMES == 2
    passed = {"passed": True, "observed_evidence": "systemd active + /health 200"}

    # One success: it worked, but once is an anecdote, not a procedure.
    one_off = verify_procedure_candidate(_complete_candidate(), observed_outcomes=[passed])
    assert one_off["verified"] is True
    assert one_off["verified_outcomes_count"] == 1
    assert one_off["is_reliable"] is False
    assert one_off["status"] == "candidate"

    # A second independently verified run promotes it.
    twice = verify_procedure_candidate(
        _complete_candidate(),
        observed_outcomes=[passed, {"passed": True, "observed_evidence": "/health 200 on rerun"}],
    )
    assert twice["verified_outcomes_count"] == 2
    assert twice["is_reliable"] is True
    assert twice["status"] == "reliable"

    # So does the owner saying so outright, on a single run.
    confirmed = verify_procedure_candidate(
        _complete_candidate(), observed_outcomes=[passed], owner_confirmed=True
    )
    assert confirmed["verified_outcomes_count"] == 1
    assert confirmed["owner_confirmed"] is True
    assert confirmed["is_reliable"] is True

    # Promotion never carries side-effect permission with it.
    assert twice["grants_side_effect_permission"] is False
    assert confirmed["grants_side_effect_permission"] is False


def test_p5_4_runs_without_evidence_or_structure_never_promote():
    from life_graph.api.procedures import verify_procedure_candidate

    # Self-reported passes with nothing to show for them do not count.
    unevidenced = verify_procedure_candidate(
        _complete_candidate(),
        observed_outcomes=[{"passed": True}, {"passed": True}],
    )
    assert unevidenced["verified_outcomes_count"] == 0
    assert unevidenced["verified"] is False
    assert unevidenced["is_reliable"] is False

    # Failed runs do not count either, however many there are.
    failed = verify_procedure_candidate(
        _complete_candidate(),
        observed_outcomes=[
            {"passed": False, "observed_evidence": "/health 503"},
            {"passed": False, "observed_evidence": "/health 503"},
        ],
    )
    assert failed["verified_outcomes_count"] == 0
    assert failed["is_reliable"] is False

    # Two clean runs of a candidate that cannot say how it is verified or
    # recovered are still not a procedure anyone should follow.
    passed = {"passed": True, "observed_evidence": "/health 200"}
    structureless = verify_procedure_candidate(
        _complete_candidate(verification_checks=[], failure_recovery=[]),
        observed_outcomes=[passed, passed],
    )
    assert structureless["verified_outcomes_count"] == 2
    assert structureless["verified"] is False
    assert structureless["is_reliable"] is False
