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


# ── P5.4 Causal memory: stated vs deduced rationale, alternatives kept ───


def test_p5_4_rationale_type_separates_stated_from_deduced():
    from life_graph.core.evidence import rationale_type

    # The owner said why.
    assert rationale_type("explicit") == "explicit"
    assert rationale_type("conversation") == "explicit"
    assert rationale_type("user") == "explicit"
    assert rationale_type("OWNER") == "explicit"

    # We worked out why. A belief challenge, a distillation and a missing
    # source are all our own reasoning and must not be replayed as the
    # owner's words.
    assert rationale_type("challenge") == "inferred"
    assert rationale_type("distillation") == "inferred"
    assert rationale_type(None) == "inferred"
    assert rationale_type("") == "inferred"

    # A model cannot stamp its own rationale as the owner's: only a
    # confirmation an authenticated owner path recorded counts.
    assert rationale_type("challenge", {"rationale_type": "explicit"}) == "inferred"
    assert rationale_type("challenge", {"owner_confirmed": True}) == "inferred"
    assert (
        rationale_type("challenge", {"owner_confirmed": {"actor": "raja", "at": "2026-11-14"}})
        == "explicit"
    )


def test_p5_4_causal_chain_reports_rationale_type_and_keeps_alternatives():
    decision = SimpleNamespace(
        id=uuid.uuid4(),
        title="Pick a connection pool",
        status="decided",
        source="explicit",
        reasoning="asyncpg gave the most burst headroom in the bake-off",
        chosen_option="asyncpg",
        capture_event_id=uuid.uuid4(),
        properties={},
        options=[
            {"label": "asyncpg"},
            {"label": "psycopg3", "rejected_because": "slower under burst in our bake-off"},
            "pgbouncer only",
        ],
    )
    chain = trace_causal_chain(decision, [])

    assert chain["rationale_type"] == "explicit"
    assert chain["rationale_origin"] == "user_stated"  # the P0.5 key still works

    # Every option weighed is preserved, and the losers keep their reason.
    assert [o["option"] for o in chain["options_considered"]] == [
        "asyncpg",
        "psycopg3",
        "pgbouncer only",
    ]
    assert [o["option"] for o in chain["rejected_options"]] == ["psycopg3", "pgbouncer only"]
    rejected = {o["option"]: o["rejected_because"] for o in chain["rejected_options"]}
    assert rejected["psycopg3"] == "slower under burst in our bake-off"
    # Not knowing why an option lost is recorded as not knowing, never invented.
    assert rejected["pgbouncer only"] is None

    # A deduced decision with no options recorded says so, both ways.
    inferred = trace_causal_chain(
        SimpleNamespace(
            id=uuid.uuid4(),
            title="Owner prefers evening digests",
            status="candidate",
            source="challenge",
            reasoning="Inferred from recent read timestamps",
            chosen_option=None,
            properties={},
            options=[],
        ),
        [],
    )
    assert inferred["rationale_type"] == "inferred"
    assert inferred["rationale_origin"] == "model_inferred"
    assert inferred["options_considered"] == []
