"""End-to-end cross-cutting regression scenarios (Workstream 7, Section 5)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import life_graph.api.dependencies  # noqa: F401
from life_graph.api.procedures import (
    build_procedure_candidate,
    can_auto_execute_side_effects,
    verify_procedure_candidate,
)
from life_graph.core.evidence import (
    INFERRED,
    SAID,
    decompose_memory_confidence,
    extract_claim_evidence,
)
from life_graph.services.episodes import link_experience_to_decision
from life_graph.services.judgment import trace_causal_chain
from life_graph.services.memory.retrieval import (
    explain_retrieval_selection,
    is_bitemporally_valid,
    provenance_tiebreak_order,
    retrieve,
)


def _mem(
    mid: str,
    content: str,
    *,
    source_type: str = "chat",
    trust_tier: str = "self",
    confidence: float = 0.9,
    trust_score: float = 0.9,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    recorded_at: datetime | None = None,
    status: str = "active",
    props: dict | None = None,
):
    return SimpleNamespace(
        id=mid,
        content=content,
        source_type=source_type,
        trust_tier=trust_tier,
        confidence=confidence,
        trust_score=trust_score,
        valid_from=valid_from,
        valid_until=valid_to,
        recorded_at=recorded_at,
        created_at=recorded_at,
        status=status,
        properties=props or {},
    )


@pytest.mark.asyncio
async def test_w7_scenario_1_and_2_bitemporal_correction_and_historical_query():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t_eff = datetime(2026, 6, 1, tzinfo=timezone.utc)
    t_corr_rec = datetime(2026, 6, 5, tzinfo=timezone.utc)

    old_fact = _mem(
        "m-old",
        "User lives in Madurai",
        valid_from=t0,
        valid_to=t_eff,
        recorded_at=t0,
        status="superseded",
    )
    new_fact = _mem(
        "m-new",
        "User moved to Chennai effective June 1",
        valid_from=t_eff,
        valid_to=None,
        recorded_at=t_corr_rec,
        status="active",
        props={"lineage": {"supersedes": "m-old", "excerpt": "Moved to Chennai on June 1"}},
    )

    # Historical query before correction was recorded: only old_fact was known
    assert is_bitemporally_valid(old_fact, valid_at=t0 + timedelta(days=30), recorded_at=t_corr_rec - timedelta(days=1)) is True
    assert is_bitemporally_valid(new_fact, valid_at=t_eff + timedelta(days=1), recorded_at=t_corr_rec - timedelta(days=1)) is False

    # Current query after correction: new_fact is valid, old_fact is expired
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    assert is_bitemporally_valid(old_fact, valid_at=now, recorded_at=now) is False
    assert is_bitemporally_valid(new_fact, valid_at=now, recorded_at=now) is True

    fake_store = AsyncMock()
    fake_store.hybrid_search.return_value = [(old_fact, 0.85), (new_fact, 0.84)]
    fake_mm = AsyncMock()
    fake_mm.generate_embedding.return_value = [0.1]
    with (
        patch("life_graph.api.dependencies.get_store", return_value=fake_store),
        patch("life_graph.api.dependencies.get_memory_manager", return_value=fake_mm),
        patch("life_graph.core.tenant.get_current_tenant_id", return_value="t1"),
        patch("life_graph.services.memory.retrieval._judged", new=AsyncMock(side_effect=lambda q, ms: ms)),
        patch("life_graph.services.entities.known_in_text", new=AsyncMock(return_value=[])),
    ):
        hist = await retrieve(
            "Where did I live in March?",
            as_of=datetime(2026, 3, 15, tzinfo=timezone.utc),
            recorded_as_of=datetime(2026, 4, 1, tzinfo=timezone.utc),
            cold=False,
        )
        assert [m.id for m in hist] == ["m-old"]


def test_w7_scenario_3_and_4_explicit_vs_inferred_and_conflicting_sources():
    explicit = _mem(
        "m-exp",
        "Primary DB is Postgres 16.",
        source_type="chat",
        trust_tier="self",
        confidence=0.95,
        trust_score=0.95,
        props={"lineage": {"capture_event_id": "cap-1", "excerpt": "Primary DB is Postgres 16."}},
    )
    inferred = _mem(
        "m-inf",
        "Primary DB might be MySQL.",
        source_type="distillation",
        trust_tier="unverified",
        confidence=0.45,
        trust_score=0.40,
    )

    ordered = provenance_tiebreak_order([(inferred, 0.800), (explicit, 0.792)])
    assert [m.id for m, _ in ordered] == ["m-exp", "m-inf"]

    trace = explain_retrieval_selection([inferred, explicit], [explicit], limit=1)
    by_id = {r["memory_id"]: r for r in trace}
    assert by_id["m-exp"]["decision"] == "selected"
    assert by_id["m-inf"]["decision"] == "rejected"

    exp_conf = decompose_memory_confidence(explicit)
    inf_conf = decompose_memory_confidence(inferred)
    assert exp_conf["evidence_kind"] == SAID
    assert inf_conf["evidence_kind"] == INFERRED
    assert exp_conf["calibrated_confidence"] > inf_conf["calibrated_confidence"]

    claims = extract_claim_evidence(
        "Primary DB is Postgres 16 [Memory 1]. Conflicting guess says MySQL [Memory 1][Memory 2]. Uncited claim.",
        [
            {"id": "m-exp", "source_type": "chat", "trust_tier": "self", "confidence": 0.95},
            {"id": "m-inf", "source_type": "distillation", "trust_tier": "unverified", "confidence": 0.45},
        ],
    )
    assert claims[0]["claim_confidence"] > claims[1]["claim_confidence"]
    assert claims[2]["supported"] is False
    assert claims[2]["claim_uncertainty"] == 1.0


def test_w7_scenario_5_causal_chain_episode_link_and_safe_procedure():
    dec = SimpleNamespace(
        id=uuid.uuid4(),
        title="Enable pgvector HNSW index",
        status="decided",
        source="explicit",
        reasoning="Speed up recall",
        chosen_option="hnsw",
        capture_event_id=uuid.uuid4(),
    )
    pred = SimpleNamespace(
        id=uuid.uuid4(),
        statement="Recall latency under 50ms",
        confidence=0.85,
        outcome="correct",
        resolution_source="benchmark",
        resolution_evidence={"source_ref": "eval-run-1", "evidence_backed": True},
        resolved_at=datetime(2026, 11, 14, tzinfo=timezone.utc),
    )
    chain = trace_causal_chain(dec, [pred])
    assert chain["rationale_origin"] == "user_stated"
    assert chain["has_evidence_backed_outcome"] is True

    ep_props = link_experience_to_decision({}, decision_id=str(dec.id), decision_title=dec.title, outcome="correct")
    assert len(ep_props["decision_links"]) == 1

    cand = build_procedure_candidate(
        trigger="rebuild hnsw index",
        steps=["CREATE INDEX CONCURRENTLY ..."],
        prerequisites=["low traffic window"],
        verification_checks=["EXPLAIN ANALYZE uses index"],
        failure_recovery=["DROP INDEX CONCURRENTLY"],
        has_side_effects=True,
    )
    verified = verify_procedure_candidate(cand, observed_outcomes=[{"passed": True, "observed_evidence": "p95=12ms"}])
    assert verified["verified"] is True
    assert can_auto_execute_side_effects(verified) is False
