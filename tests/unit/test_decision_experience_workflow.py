"""Tests for P2 Order 4: Decision, Prediction, and Causal Experience Workflow.

Covers the 7-stage experience chain:
  Situation -> Options -> Decision -> Rationale -> Prediction -> Outcome -> Lesson
plus hypothetical counterfactual fencing and circumstance-change revisit triggers.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from life_graph.services.episodes import link_experience_to_decision
from life_graph.services.judgment import (
    HYPOTHETICAL_COUNTERFACTUAL_PREFIX,
    assess_decision_revisit,
    derive_decision_lessons,
    trace_causal_chain,
)


def _make_decision(**overrides):
    base = {
        "id": uuid.uuid4(),
        "tenant_id": "t_dec",
        "title": "Migrate analytics store from Firebase to PostgreSQL",
        "reasoning": "Need relational joins, pgvector, and strict transactional guarantees.",
        "source": "explicit",
        "status": "decided",
        "chosen_option": "PostgreSQL + pgvector",
        "options": [
            {"label": "PostgreSQL + pgvector", "pros": "ACID + hybrid search"},
            {"label": "Firebase", "rejected_because": "Weak relational query support"},
            {"label": "MongoDB", "rejected_because": "Additional operational surface"},
        ],
        "domain_tags": ["architecture", "database"],
        "capture_event_id": uuid.uuid4(),
        "review_at": None,
        "properties": {"situation": "Search latency and relational integrity became bottlenecks."},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_prediction(
    outcome="pending",
    confidence=0.85,
    evidence=None,
    statement="P95 query latency stays under 50ms",
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        statement=statement,
        confidence=confidence,
        outcome=outcome,
        resolution_source="metric" if evidence else None,
        resolution_evidence=evidence or {},
        resolved_at=datetime.now(UTC) if outcome != "pending" else None,
    )


def test_seven_stage_experience_chain_and_stated_vs_inferred_rationale():
    dec_stated = _make_decision(source="explicit")
    pred_ok = _make_prediction(
        outcome="correct",
        confidence=0.9,
        evidence={"observation": "Measured P95=18ms in production", "evidence_backed": True},
    )
    mem = SimpleNamespace(
        id=uuid.uuid4(),
        content="Owner noted Firebase join workarounds were slowing feature delivery.",
        source_type="user_explicit",
        trust_tier="self",
        properties={},
    )

    chain = trace_causal_chain(dec_stated, [pred_ok], memories=[mem])
    assert chain["experience_stages"] == [
        "situation",
        "options",
        "decision",
        "rationale",
        "prediction",
        "outcome",
        "lesson",
    ]
    assert chain["rationale_origin"] == "user_stated"
    assert chain["rationale_type"] == "explicit"
    assert (
        chain["situation"]["summary"]
        == "Search latency and relational integrity became bottlenecks."
    )
    assert len(chain["options_considered"]) == 3
    assert len(chain["rejected_options"]) == 2
    assert chain["has_evidence_backed_outcome"] is True
    assert chain["prediction_evaluation"]["accuracy"] == 1.0
    assert chain["prediction_evaluation"]["brier_score"] == pytest.approx(0.01, abs=1e-4)
    assert len(chain["lessons"]) == 1
    assert chain["lessons"][0]["lesson_type"] == "validated_hypothesis"

    # Inferred rationale is distinguished from user-stated rationale
    dec_inferred = _make_decision(source="inferred", properties={"rationale_type": "inferred"})
    chain_inf = trace_causal_chain(dec_inferred, [])
    assert chain_inf["rationale_origin"] == "model_inferred"


def test_lessons_require_evidence_backed_outcomes():
    dec = _make_decision()
    unverified_pred = _make_prediction(outcome="correct", confidence=0.8, evidence={})
    pending_pred = _make_prediction(outcome="pending", confidence=0.8, evidence={})

    lessons = derive_decision_lessons(dec, [unverified_pred, pending_pred])
    assert lessons == []

    ev_pred = _make_prediction(
        outcome="incorrect",
        confidence=0.8,
        evidence={
            "observation": "Migration took 3 weeks instead of 1 week",
            "evidence_backed": True,
        },
        statement="Migration finishes within 1 week",
    )
    lessons_ev = derive_decision_lessons(dec, [ev_pred])
    assert len(lessons_ev) == 1
    assert lessons_ev[0]["lesson_type"] == "falsified_assumption"
    assert lessons_ev[0]["evidence_backed"] is True


def test_counterfactuals_are_explicitly_labeled_hypothetical_never_fact():
    dec = _make_decision()
    chain = trace_causal_chain(dec, [])
    cfs = chain["counterfactuals"]
    assert len(cfs) == 2
    for cf in cfs:
        assert cf["is_hypothetical"] is True
        assert cf["epistemic_status"] == "hypothetical_counterfactual"
        assert cf["never_remembered_as_fact"] is True
        assert cf["statement"].startswith(HYPOTHETICAL_COUNTERFACTUAL_PREFIX)


def test_decision_revisit_triggers_on_falsified_prediction_schedule_or_circumstance_change():
    now = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
    dec = _make_decision(review_at=now - timedelta(days=1))
    falsified = _make_prediction(
        outcome="incorrect",
        confidence=0.85,
        evidence={"observation": "Write throughput saturated", "evidence_backed": True},
    )
    changed_mem = SimpleNamespace(
        id=uuid.uuid4(),
        content="Workload requirements changed: now requires multi-region active-active writes.",
        properties={"circumstance_changed": True},
    )
    revisit = assess_decision_revisit(dec, [falsified], memories=[changed_mem], now=now)
    assert revisit["should_revisit"] is True
    assert len(revisit["reasons"]) == 3

    ep_props = link_experience_to_decision(
        {"kind": "episode", "date": "2026-11-17"},
        decision_id=str(dec.id),
        decision_title=dec.title,
        outcome="incorrect",
    )
    assert ep_props["decision_links"][0]["decision_id"] == str(dec.id)
    assert ep_props["decision_links"][0]["outcome"] == "incorrect"
