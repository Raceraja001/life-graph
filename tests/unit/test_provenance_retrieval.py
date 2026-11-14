"""Unit tests for P0.4 provenance-aware near-tie retrieval ordering and selection explanation."""

from __future__ import annotations

from types import SimpleNamespace

from life_graph.services.memory_retrieval import (
    explain_retrieval_selection,
    provenance_score,
    provenance_tiebreak_order,
)


def _mem(mid: str, *, source_type: str = "chat", trust_tier: str = "self", confidence: float = 0.8, trust_score: float = 0.8, props: dict | None = None):
    return SimpleNamespace(
        id=mid,
        source_type=source_type,
        trust_tier=trust_tier,
        confidence=confidence,
        trust_score=trust_score,
        properties=props or {},
    )


def test_p0_4_direct_statement_beats_inferred_on_near_tie():
    inferred = _mem("m-inf", source_type="distillation", trust_tier="unverified", confidence=0.75, trust_score=0.5)
    direct = _mem("m-dir", source_type="chat", trust_tier="self", confidence=0.75, trust_score=0.9)

    assert provenance_score(direct) > provenance_score(inferred)

    # Near-tie scores (within 2%): direct statement must be promoted above inferred
    ordered = provenance_tiebreak_order([(inferred, 0.800), (direct, 0.790)])
    assert [m.id for m, _ in ordered] == ["m-dir", "m-inf"]


def test_p0_4_clear_relevance_winner_is_not_overridden_by_provenance():
    inferred_high_rel = _mem("m-rel", source_type="distillation", trust_tier="unverified", confidence=0.6, trust_score=0.4)
    direct_low_rel = _mem("m-low", source_type="chat", trust_tier="self", confidence=0.95, trust_score=0.95)

    ordered = provenance_tiebreak_order([(direct_low_rel, 0.50), (inferred_high_rel, 0.90)])
    assert [m.id for m, _ in ordered] == ["m-rel", "m-low"]


def test_p0_4_corroborated_memory_outranks_uncorroborated_peer():
    plain = _mem("m-plain", source_type="chat", trust_tier="verified", confidence=0.7, trust_score=0.7)
    corrob = _mem("m-corrob", source_type="chat", trust_tier="verified", confidence=0.7, trust_score=0.7, props={"corroboration_count": 3})

    ordered = provenance_tiebreak_order([(plain, 0.800), (corrob, 0.795)])
    assert [m.id for m, _ in ordered] == ["m-corrob", "m-plain"]


def test_p0_4_explain_retrieval_selection_records_decisions():
    m1 = _mem("m1")
    m2 = _mem("m2")
    m3 = _mem("m3", source_type="distillation", trust_tier="unverified")
    trace = explain_retrieval_selection([m1, m2, m3], [m1, m2], limit=1)
    by_id = {row["memory_id"]: row for row in trace}
    assert by_id["m1"]["decision"] == "selected"
    assert by_id["m2"]["decision"] == "truncated"
    assert by_id["m3"]["decision"] == "rejected"
