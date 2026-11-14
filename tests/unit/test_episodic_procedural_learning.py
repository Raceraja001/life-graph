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
