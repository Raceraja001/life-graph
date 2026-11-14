"""Unit tests for P0.5 causal memory integration (decision -> prediction -> outcome + evidence)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.services.judgment import trace_causal_chain
from life_graph.services.outcome_resolver import OutcomeResolver


def test_p0_5_trace_causal_chain_distinguishes_user_vs_inferred_and_links_evidence():
    dec_user = SimpleNamespace(
        id=uuid.uuid4(),
        title="Migrate service to async pool",
        status="decided",
        source="explicit",
        reasoning="Reduce p99 latency during bursts",
        chosen_option="asyncpg",
        capture_event_id=uuid.uuid4(),
    )
    dec_inferred = SimpleNamespace(
        id=uuid.uuid4(),
        title="User prefers evening digests",
        status="candidate",
        source="challenge",
        reasoning="Inferred from recent timestamps",
        chosen_option=None,
        capture_event_id=None,
    )
    pred = SimpleNamespace(
        id=uuid.uuid4(),
        statement="p99 drops below 50ms",
        confidence=0.8,
        outcome="correct",
        resolution_source="metrics",
        resolution_evidence={"source_ref": "prom-query-1", "evidence_backed": True},
        resolved_at=datetime(2026, 11, 14, tzinfo=timezone.utc),
    )
    mem = SimpleNamespace(
        id=uuid.uuid4(),
        content="We chose asyncpg for burst headroom.",
        source_type="chat",
        trust_tier="self",
        properties={},
    )

    chain_user = trace_causal_chain(dec_user, [pred], memories=[mem])
    chain_inf = trace_causal_chain(dec_inferred, [])

    assert chain_user["rationale_origin"] == "user_stated"
    assert chain_user["has_evidence_backed_outcome"] is True
    assert chain_user["predictions"][0]["evidence_backed"] is True
    assert chain_user["supporting_memories"][0]["evidence_kind"] == "said"

    assert chain_inf["rationale_origin"] == "model_inferred"
    assert chain_inf["has_evidence_backed_outcome"] is False


@pytest.mark.asyncio
async def test_p0_5_record_evidence_backed_outcome_rejects_missing_evidence_and_records_valid():
    pred_id = uuid.uuid4()
    pred = SimpleNamespace(
        id=pred_id,
        tenant_id="t1",
        outcome="pending",
        confidence=0.75,
        resolved_at=None,
        resolution_source=None,
        resolution_evidence=None,
        actual_vs_predicted=None,
    )
    scalars = MagicMock()
    scalars.first.return_value = pred
    exec_res = MagicMock()
    exec_res.scalars.return_value = scalars
    session = AsyncMock()
    session.execute.return_value = exec_res

    resolver = OutcomeResolver(session)
    with pytest.raises(ValueError, match="Evidence-backed outcome"):
        await resolver.record_evidence_backed_outcome(
            tenant_id="t1",
            prediction_id=pred_id,
            outcome="correct",
            source="git",
            evidence={},
        )

    resolved = await resolver.record_evidence_backed_outcome(
        tenant_id="t1",
        prediction_id=pred_id,
        outcome="correct",
        source="git",
        evidence={"source_ref": "commit:abc123", "observation": "CI passed"},
    )
    assert resolved.outcome == "correct"
    assert resolved.resolution_evidence["evidence_backed"] is True
    assert resolved.resolution_evidence["source_ref"] == "commit:abc123"
