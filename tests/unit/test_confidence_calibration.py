"""Unit tests for P0.3 confidence decomposition, calibration, and claim uncertainty."""

from __future__ import annotations

import json
from pathlib import Path

from datetime import datetime, timedelta, timezone

from life_graph.core.evidence import (
    INFERRED,
    SAID,
    decompose_memory_confidence,
    evaluate_confidence_calibration,
    extract_claim_evidence,
)


def test_p0_3_confidence_decomposes_components_and_excludes_similarity():
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    explicit_mem = {
        "id": "m-exp",
        "source_type": "chat",
        "trust_tier": "self",
        "confidence": 0.92,
        "updated_at": now - timedelta(days=5),
        "similarity": 0.12,  # must NOT affect calibrated confidence
        "score": 0.12,
    }
    inferred_mem = {
        "id": "m-inf",
        "source_type": "distillation",
        "trust_tier": "unverified",
        "confidence": 0.92,
        "updated_at": now - timedelta(days=360),
        "similarity": 0.99,  # high vector similarity must NOT inflate truth confidence
        "score": 0.99,
    }

    exp_d = decompose_memory_confidence(explicit_mem, now=now)
    inf_d = decompose_memory_confidence(inferred_mem, now=now)

    assert exp_d["evidence_kind"] == SAID
    assert exp_d["explicit_vs_inferred"] == "explicit"
    assert inf_d["evidence_kind"] == INFERRED
    assert inf_d["explicit_vs_inferred"] == "inferred"
    assert exp_d["calibrated_confidence"] > inf_d["calibrated_confidence"]
    assert exp_d["freshness_score"] > inf_d["freshness_score"]
    assert abs(exp_d["calibrated_confidence"] + exp_d["uncertainty"] - 1.0) < 1e-3

    # Changing vector similarity alone must not change calibrated confidence
    explicit_mem_2 = {**explicit_mem, "similarity": 0.99, "score": 0.99}
    assert decompose_memory_confidence(explicit_mem_2, now=now) == exp_d


def test_p0_3_mixed_quality_claims_do_not_hide_weak_or_unsupported_claims():
    memories = [
        {"id": "m1", "source_type": "user_chat", "trust_tier": "core", "confidence": 0.95},
        {"id": "m2", "source_type": "distillation", "trust_tier": "unverified", "confidence": 0.4},
    ]
    answer = (
        "You live in Chennai [Memory 1]. "
        "You might prefer tea over coffee [Memory 1][Memory 2]. "
        "You also won a marathon yesterday."
    )
    claims = extract_claim_evidence(answer, memories)
    assert len(claims) == 3

    # First claim: strong single citation
    assert claims[0]["supported"] is True
    assert claims[0]["claim_confidence"] > 0.75

    # Second claim: co-cited with weak inferred memory -> weakest-link caps confidence
    assert claims[1]["supported"] is True
    assert claims[1]["claim_confidence"] < claims[0]["claim_confidence"]
    assert len(claims[1]["confidence_breakdown"]) == 2

    # Third claim: uncited -> maximum uncertainty
    assert claims[2]["supported"] is False
    assert claims[2]["claim_confidence"] == 0.0
    assert claims[2]["claim_uncertainty"] == 1.0


def test_p0_3_evaluate_confidence_calibration_brier_and_buckets():
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    m_good = decompose_memory_confidence(
        {"source_type": "chat", "trust_tier": "self", "confidence": 0.95, "updated_at": now},
        now=now,
    )
    m_weak = decompose_memory_confidence(
        {"source_type": "distillation", "trust_tier": "unverified", "confidence": 0.4, "updated_at": now},
        now=now,
    )
    report = evaluate_confidence_calibration(
        [
            {"confidence": m_good["calibrated_confidence"], "correct": True, "evidence_kind": m_good["evidence_kind"]},
            {"confidence": m_weak["calibrated_confidence"], "correct": False, "evidence_kind": m_weak["evidence_kind"]},
        ]
    )
    assert report["count"] == 2
    assert 0.0 <= report["brier_score"] < 0.25
    assert SAID in report["by_evidence_kind"]
    assert INFERRED in report["by_evidence_kind"]

# ── P5.3 Action thresholds and support penalties ─────────────────────────


def test_p5_3_decide_claim_action_covers_all_four_ranges():
    from life_graph.core.evidence import decide_claim_action

    # answer: >= 0.85
    assert decide_claim_action(1.0) == "answer"
    assert decide_claim_action(0.85) == "answer"
    # qualify: 0.60 <= c < 0.85 (hedge it)
    assert decide_claim_action(0.8499) == "qualify"
    assert decide_claim_action(0.60) == "qualify"
    # ask: 0.40 <= c < 0.60 (ask the owner rather than guess)
    assert decide_claim_action(0.5999) == "ask"
    assert decide_claim_action(0.40) == "ask"
    # abstain: < 0.40
    assert decide_claim_action(0.3999) == "abstain"
    assert decide_claim_action(0.0) == "abstain"

    # A confidence that is not a number is not permission to answer.
    assert decide_claim_action(None) == "abstain"
    assert decide_claim_action("high") == "abstain"
    assert decide_claim_action(float("nan")) == "abstain"


def test_p5_3_contradicted_and_unresolved_citations_cost_confidence():
    """The four components stay separate; failed support multiplies on top."""
    memory = {"id": "m1", "source_type": "chat", "trust_tier": "self", "confidence": 0.9}

    clean = decompose_memory_confidence(memory)
    supported = decompose_memory_confidence(memory, support_status="supported")
    unsupported = decompose_memory_confidence(memory, support_status="unsupported")
    unresolved = decompose_memory_confidence(memory, support_status="unresolved_source")
    contradicted = decompose_memory_confidence(memory, support_status="contradicted")

    # Extraction, source trust, evidence prior and freshness are reported
    # independently, and the penalty touches none of them.
    for part in ("extraction_confidence", "trust_score", "evidence_prior", "freshness_score"):
        assert clean[part] == contradicted[part]
        assert 0.0 <= clean[part] <= 1.0
    assert clean["base_confidence"] == contradicted["base_confidence"]

    # A verified citation costs nothing; a failed one costs, worst last.
    assert supported["calibrated_confidence"] == clean["base_confidence"]
    assert unresolved["calibrated_confidence"] < unsupported["calibrated_confidence"]
    assert contradicted["calibrated_confidence"] < unresolved["calibrated_confidence"]

    # And the penalty is enough to move the decision, not just the number.
    assert clean["recommended_action"] in ("answer", "qualify")
    assert contradicted["recommended_action"] == "abstain"
    assert abs(contradicted["calibrated_confidence"] + contradicted["uncertainty"] - 1.0) < 1e-3


def test_p5_3_unsupported_claim_recommends_abstention_not_a_hedge():
    """A strong memory cited for something it does not say still gets no answer."""
    memories = [
        {
            "id": "m1",
            "source_type": "chat",
            "trust_tier": "self",
            "confidence": 0.98,
            "capture_event_id": "cap-1",
            "content": "Raja likes painting watercolours.",
        }
    ]
    claims = extract_claim_evidence(
        "You live in London [Memory 1]. You like painting [Memory 1].", memories
    )
    assert claims[0]["support_status"] == "unsupported"
    assert claims[0]["recommended_action"] == "abstain"
    # The same high-trust memory, cited for what it actually says, is usable.
    assert claims[1]["support_status"] == "supported"
    assert claims[1]["recommended_action"] in ("answer", "qualify")
    assert claims[1]["claim_confidence"] > claims[0]["claim_confidence"]


# ── P1 §6 Extended calibration, ECE, contradiction and dataset tests ───────


def test_evaluate_confidence_calibration_ece_bins_and_metrics():
    """Verify ECE calculation, equal-width binning, and classification metrics."""
    # Empty samples
    empty_res = evaluate_confidence_calibration([])
    assert empty_res["count"] == 0
    assert empty_res["ece"] == 0.0
    assert empty_res["mce"] == 0.0
    assert empty_res["bins"] == []

    # Perfectly calibrated synthetic predictions:
    # 10 samples with confidence 0.8 and 8 of them correct (acc = 0.8)
    # 10 samples with confidence 0.2 and 2 of them correct (acc = 0.2)
    samples = []
    for _ in range(8):
        samples.append({"confidence": 0.8, "correct": True, "evidence_kind": "said"})
    for _ in range(2):
        samples.append({"confidence": 0.8, "correct": False, "evidence_kind": "said"})
    for _ in range(2):
        samples.append({"confidence": 0.2, "correct": True, "evidence_kind": "inferred"})
    for _ in range(8):
        samples.append({"confidence": 0.2, "correct": False, "evidence_kind": "inferred"})

    res = evaluate_confidence_calibration(samples, num_bins=10)
    assert res["count"] == 20
    assert res["ece"] == 0.0  # perfectly calibrated!
    assert res["mce"] == 0.0
    assert res["calibration_gap"] == 0.0
    assert res["precision"] == 0.80
    assert res["recall"] == 0.80
    assert res["f1"] == 0.80

    # Abstention at threshold 0.4:
    # 10 items in the lower bin (<0.4), 8 of which are false -> abstention precision = 8/10 = 0.8
    assert res["abstention_rate"] == 0.50
    assert res["abstention_precision"] == 0.80
    # 10 items in upper bin, 8 correct -> answering accuracy = 8/10 = 0.8
    assert res["answering_accuracy"] == 0.80

    # Non-empty bins count check (10 bins total)
    assert len(res["bins"]) == 10
    active_bins = [b for b in res["bins"] if b["count"] > 0]
    assert len(active_bins) == 2


def test_evaluate_confidence_calibration_contradiction_metrics():
    """Verify contradiction detection precision, recall, and F1 calculation."""
    samples = [
        {"confidence": 0.2, "correct": False, "contradiction_predicted": True, "contradiction_ground_truth": True},
        {"confidence": 0.2, "correct": False, "contradiction_predicted": True, "contradiction_ground_truth": True},
        {"confidence": 0.2, "correct": False, "contradiction_predicted": True, "contradiction_ground_truth": False},  # FP
        {"confidence": 0.2, "correct": False, "contradiction_predicted": False, "contradiction_ground_truth": True},  # FN
        {"confidence": 0.9, "correct": True, "contradiction_predicted": False, "contradiction_ground_truth": False},  # TN
    ]
    res = evaluate_confidence_calibration(samples)
    assert "contradiction_detection" in res
    cd = res["contradiction_detection"]
    assert cd["count"] == 5
    # TP=2, FP=1, FN=1 -> precision=2/3 (~0.6667), recall=2/3 (~0.6667), F1=2/3
    assert abs(cd["precision"] - 0.6667) < 1e-3
    assert abs(cd["recall"] - 0.6667) < 1e-3
    assert abs(cd["f1"] - 0.6667) < 1e-3


def test_extract_claim_evidence_passes_now_to_decompose():
    """Passing now to extract_claim_evidence ensures deterministic freshness scoring."""
    now_past = datetime(2025, 1, 1, tzinfo=timezone.utc)
    now_future = datetime(2027, 1, 1, tzinfo=timezone.utc)
    memories = [
        {
            "id": "m1",
            "source_type": "chat",
            "trust_tier": "self",
            "confidence": 0.95,
            "content": "Raja lives in Chennai.",
            "updated_at": "2025-01-01T00:00:00+00:00",
        }
    ]
    fresh = extract_claim_evidence("You live in Chennai [Memory 1].", memories, now=now_past)[0]
    stale = extract_claim_evidence("You live in Chennai [Memory 1].", memories, now=now_future)[0]

    assert fresh["claim_confidence"] > stale["claim_confidence"]
    assert fresh["confidence_breakdown"][0]["freshness_score"] > stale["confidence_breakdown"][0]["freshness_score"]


def test_antonym_state_contradiction_detection():
    """State and antonym pairs (running vs stopped, free vs paid, active vs inactive) trigger contradiction."""
    memory_stopped = {
        "id": "m1",
        "source_type": "scan",
        "trust_tier": "verified",
        "confidence": 0.90,
        "content": "Observed Redis service is stopped and inactive.",
    }
    claim_running = extract_claim_evidence(
        "Redis service is active and running [Memory 1].", [memory_stopped]
    )[0]
    assert claim_running["support_status"] == "contradicted"
    assert claim_running["recommended_action"] == "abstain"

    memory_free = {
        "id": "m2",
        "source_type": "web",
        "trust_tier": "unverified",
        "confidence": 0.40,
        "content": "External API documentation states tier is free with no charge.",
    }
    claim_paid = extract_claim_evidence(
        "The tier requires a paid subscription [Memory 1].", [memory_free]
    )[0]
    assert claim_paid["support_status"] == "contradicted"
    assert claim_paid["recommended_action"] == "abstain"


def test_confidence_calibration_dataset_runs_and_meets_criteria():
    """Evaluate evals/confidence_calibration_dataset.json and assert Section 6 acceptance thresholds."""
    dataset_path = Path("evals/confidence_calibration_dataset.json")
    if not dataset_path.exists():
        # Handle running from root or elsewhere
        dataset_path = Path("/home/raja/life-graph/evals/confidence_calibration_dataset.json")

    assert dataset_path.exists(), f"Dataset not found at {dataset_path}"
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "calibration_set" in data and len(data["calibration_set"]) >= 50
    assert "held_out_set" in data and len(data["held_out_set"]) >= 50

    from scripts.eval_confidence_calibration import evaluate_split

    for split_name in ("calibration_set", "held_out_set"):
        summary, details = evaluate_split(data[split_name])
        assert summary["count"] == len(data[split_name])
        # Section 6 Quality Gates:
        assert summary["brier_score"] <= 0.20, f"{split_name} Brier score {summary['brier_score']} > 0.20"
        assert summary["ece"] <= 0.20, f"{split_name} ECE {summary['ece']} > 0.20"
        assert summary["abstention_precision"] >= 0.85, (
            f"{split_name} Abstention precision {summary['abstention_precision']} < 0.85"
        )
        assert len(summary["by_evidence_kind"]) == 6, (
            f"Expected all 6 evidence kinds, got {list(summary['by_evidence_kind'].keys())}"
        )
        for kind in ("said", "document", "observed", "summary", "inferred", "outside"):
            assert kind in summary["by_evidence_kind"]
            assert summary["by_evidence_kind"][kind]["count"] > 0
