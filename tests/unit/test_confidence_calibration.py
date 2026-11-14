"""Unit tests for P0.3 confidence decomposition, calibration, and claim uncertainty."""

from __future__ import annotations

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
