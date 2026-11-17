"""The daily brief surfaces decisions a change has overtaken (§3.B).

``services/judgment.assess_decision_revisit`` has known when a decision went
stale since Order 4, but nothing told the owner: a ``review_at`` column nobody
is shown is not a review. These tests pin the brief as that delivery path —
and pin the two noise gates with it, because a revisit line that fires every
morning forever teaches the owner to skip the whole brief.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from life_graph.services.brief import (
    REVISIT_MAX_LINES,
    BriefComposer,
    build_brief_evidence,
)
from tests.unit.fakes import FakeSession, session_factory, sql

TENANT = "t_brief"
NOW = datetime(2026, 11, 17, 6, 0, tzinfo=UTC)


def _decision(title: str, **overrides):
    base = {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "title": title,
        "status": "decided",
        "source": "explicit",
        "options": [],
        "chosen_option": None,
        "review_at": None,
        "reviewed_at": None,
        "decided_at": NOW - timedelta(days=90),
        "created_at": NOW - timedelta(days=90),
        "properties": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _prediction(decision_id, **overrides):
    base = {
        "id": uuid.uuid4(),
        "decision_id": decision_id,
        "statement": "Monthly hosting stays under 20 EUR",
        "confidence": 0.8,
        "outcome": "incorrect",
        "resolved_at": NOW - timedelta(hours=3),
        "resolution_source": "invoice",
        "resolution_evidence": {"observation": "Invoice was 64 EUR", "evidence_backed": True},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _memory(content: str, **props):
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        properties=dict(props),
        created_at=NOW - timedelta(hours=2),
    )


def _composer(decisions, predictions=(), memories=()):
    session = FakeSession(list(decisions), list(predictions), list(memories))
    return BriefComposer(session_factory(session)), session


# ── What gets surfaced ────────────────────────────────────────


async def test_review_date_reached_surfaces_a_revisit_alert():
    decision = _decision("Self-host the vector store", review_at=NOW - timedelta(days=2))
    composer, session = _composer([decision])

    lines = await composer._decision_revisit_lines(TENANT, NOW)

    assert len(lines) == 1
    assert lines[0].startswith("Revisit decision 'Self-host the vector store': ")
    assert "scheduled review date reached (2026-11-15)" in lines[0]
    # Tenant isolation: every one of the three reads is scoped.
    assert all(f"'{TENANT}'" in sql(stmt) for stmt in session.statements)


async def test_falsified_prediction_surfaces_a_revisit_alert():
    decision = _decision("Stay on the 20 EUR hosting tier")
    composer, _ = _composer([decision], [_prediction(decision.id)])

    lines = await composer._decision_revisit_lines(TENANT, NOW)

    assert len(lines) == 1
    assert "prediction falsified by evidence: Monthly hosting stays under 20 EUR" in lines[0]


async def test_a_memory_that_explicitly_invalidates_the_premise_surfaces_it():
    decision = _decision("Keep the analytics store on Firebase")
    changed = _memory("The free Firebase tier was withdrawn.", circumstance_changed=True)
    composer, _ = _composer([decision], [], [changed])

    lines = await composer._decision_revisit_lines(TENANT, NOW)

    assert len(lines) == 1
    assert "circumstance change in memory" in lines[0]


async def test_a_decision_nothing_has_overtaken_stays_silent():
    composer, _ = _composer([_decision("Use pgvector for embeddings")])

    assert await composer._decision_revisit_lines(TENANT, NOW) == []


async def test_no_decisions_reads_nothing_further():
    composer, session = _composer([])

    assert await composer._decision_revisit_lines(TENANT, NOW) == []
    assert len(session.statements) == 1, "predictions and memories were queried for no decisions"


# ── Noise gates ───────────────────────────────────────────────


async def test_a_recorded_review_stops_the_daily_nag():
    decision = _decision(
        "Self-host the vector store",
        review_at=NOW - timedelta(days=30),
        reviewed_at=NOW - timedelta(days=29),
    )
    composer, _ = _composer([decision])

    assert await composer._decision_revisit_lines(TENANT, NOW) == []


async def test_a_recorded_review_does_not_hide_a_newly_falsified_prediction():
    decision = _decision(
        "Self-host the vector store",
        review_at=NOW - timedelta(days=30),
        reviewed_at=NOW - timedelta(days=29),
    )
    composer, _ = _composer([decision], [_prediction(decision.id)])

    lines = await composer._decision_revisit_lines(TENANT, NOW)

    assert len(lines) == 1
    assert "prediction falsified by evidence" in lines[0]


async def test_a_prediction_falsified_long_ago_is_not_surfaced_again():
    decision = _decision("Stay on the 20 EUR hosting tier")
    old = _prediction(decision.id, resolved_at=NOW - timedelta(days=40))
    composer, _ = _composer([decision], [old])

    assert await composer._decision_revisit_lines(TENANT, NOW) == []


async def test_ordinary_memories_about_change_are_not_circumstance_evidence():
    """``assess_decision_revisit`` reads free text for "changed" / "no longer".

    An ordinary day's captures are full of both, so the brief offers it only
    memories whose own properties claim an invalidation — otherwise every
    decision would be revisit-worthy every day.
    """
    decision = _decision("Keep the analytics store on Firebase")
    chatter = [
        _memory("I changed the kitchen light bulb."),
        _memory("Raja no longer uses the old laptop."),
    ]
    composer, _ = _composer([decision], [], chatter)

    assert await composer._decision_revisit_lines(TENANT, NOW) == []


async def test_at_most_three_revisit_lines_a_day():
    decisions = [
        _decision(f"Decision {i}", review_at=NOW - timedelta(days=i + 1)) for i in range(6)
    ]
    composer, _ = _composer(decisions)

    lines = await composer._decision_revisit_lines(TENANT, NOW)

    assert len(lines) == REVISIT_MAX_LINES


async def test_a_database_failure_does_not_cost_the_brief():
    class _Boom:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def execute(self, *_a, **_k):
            raise RuntimeError("decisions table is unreachable")

    composer = BriefComposer(lambda: _Boom())

    assert await composer._decision_revisit_lines(TENANT, NOW) == []


# ── Rendering ─────────────────────────────────────────────────


def test_the_body_shows_revisits_above_the_questions_and_below_attention():
    body = BriefComposer._format_body(
        held=[{"id": "n1", "title": "Deploy failed", "priority": "critical"}],
        questions=[{"id": "q1", "question": "Is X still a goal?", "origin": "drift"}],
        capture_summary={"captures": 0, "memories": 0, "decisions": 0, "total": 0},
        watcher_summary={},
        decision_revisits=["Revisit decision 'Self-host the vector store': review date reached"],
    )

    assert body.index("Needs attention") < body.index("Revisit a decision")
    assert body.index("Revisit a decision") < body.index("Questions for you")
    assert "- Revisit decision 'Self-host the vector store': review date reached" in body


def test_revisits_alone_still_produce_a_body():
    body = BriefComposer._format_body(
        held=[],
        questions=[],
        capture_summary={"captures": 0, "memories": 0, "decisions": 0, "total": 0},
        watcher_summary={},
        decision_revisits=["Revisit decision 'A': prediction falsified by evidence: x"],
    )

    assert body.startswith("## Revisit a decision")


def test_no_revisits_leaves_the_body_unchanged():
    empty = {
        "held": [],
        "questions": [],
        "capture_summary": {"captures": 0, "memories": 0, "decisions": 0, "total": 0},
        "watcher_summary": {},
    }

    assert BriefComposer._format_body(**empty, decision_revisits=[]) == ""
    assert BriefComposer._format_body(**empty) == ""


def test_revisits_are_explained_in_the_why_am_i_seeing_this_evidence():
    evidence = build_brief_evidence(
        held=[],
        questions=[],
        capture_summary={"total": 0},
        watcher_summary={},
        big_decisions=[],
        decision_revisits=["Revisit decision 'A': scheduled review date reached (2026-11-15)"],
    )

    assert [item["section"] for item in evidence] == ["decision_revisits"]
    assert evidence[0]["count"] == 1
    assert "review date" in evidence[0]["why"]
