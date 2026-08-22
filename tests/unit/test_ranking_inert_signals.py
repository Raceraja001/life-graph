"""A weighted ranking signal that is constant across candidates ranks nothing.

RecallRanker combines seven weighted signals. If one has the same value on
every candidate it adds the same constant to every final score: it does not
misorder anything, it simply takes no part in the ordering, and the weight it
was given is spent on nothing. Every score still looks plausible.

Two signals were in that state and neither was visible:

    context   0.20 — scored from project/module/tools/files, none of which
                     were ever written into Memory.properties. Fixed; a
                     memory stored with context now competes on relevance.
    semantic  0.20 — still a hardcoded 0.5, because _retrieve_candidates uses
                     list_memories rather than vector search. Deliberate and
                     documented as a placeholder, but its price — a fifth of
                     the ranking weight — was not.

The reporting added here does not fix the semantic placeholder. It makes the
condition observable, so the next signal to go inert is noticed rather than
discovered a year later by reading the ranker.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest

from life_graph.scoring import ranking
from life_graph.scoring.ranking import (
    _SIGNAL_WEIGHTS,
    RecallRanker,
    inert_signals,
)

_NOW = datetime.now(UTC)


def _cand(
    cid, *, importance=0.5, project="", trust=0.5, access=1, days_old=0, impact=0.5, semantic=0.5
):
    return {
        "id": cid,
        "content": f"memory {cid}",
        "importance": importance,
        "impact_score": impact,
        "trust_score": trust,
        "access_count": access,
        "last_accessed": _NOW - timedelta(days=days_old),
        "created_at": _NOW - timedelta(days=days_old),
        "project": project,
        "module": "",
        "tools": [],
        "files": [],
        "semantic_score": semantic,
        "tags": [],
        "properties": {},
    }


@pytest.fixture(autouse=True)
def _clear_report_memo():
    ranking._reported_inert.clear()
    yield
    ranking._reported_inert.clear()


# ── inert_signals ─────────────────────────────────────────────────────


def test_weights_sum_to_one():
    """Otherwise 'x% of the weight' in the report means nothing."""
    assert sum(_SIGNAL_WEIGHTS.values()) == pytest.approx(1.0)


def test_no_report_for_a_single_candidate():
    """One candidate is trivially constant in every signal; that is not news."""
    ranked = RecallRanker().rank([_cand("A")], current_context={"project": "p"})
    assert inert_signals(ranked) == {}


def test_no_report_for_an_empty_result():
    assert inert_signals([]) == {}


def test_a_varying_signal_is_not_reported():
    ranked = RecallRanker().rank(
        [_cand("A", importance=0.9), _cand("B", importance=0.2)],
        current_context={"project": "p"},
    )
    assert "importance" not in inert_signals(ranked)


def test_a_constant_signal_is_reported_with_its_weight():
    ranked = RecallRanker().rank(
        [_cand("A", importance=0.9), _cand("B", importance=0.2)],
        current_context={"project": "p"},
    )
    inert = inert_signals(ranked)
    assert inert["semantic"] == pytest.approx(0.20)
    assert inert["trust"] == pytest.approx(0.05)


def test_context_is_inert_when_no_candidate_carries_it():
    """The state the codebase was in for every memory ever stored."""
    ranked = RecallRanker().rank(
        [_cand("A", importance=0.9), _cand("B", importance=0.2)],
        current_context={"project": "life_graph"},
    )
    assert "context" in inert_signals(ranked)


def test_context_stops_being_inert_once_it_is_stored():
    """The fix, observed through the same lens."""
    ranked = RecallRanker().rank(
        [
            _cand("A", importance=0.9),
            _cand("B", importance=0.2, project="life_graph"),
        ],
        current_context={"project": "life_graph"},
    )
    assert "context" not in inert_signals(ranked)


# ── the ordering claim itself ─────────────────────────────────────────


def test_a_constant_signal_does_not_change_the_order():
    """Precisely why this was invisible: the scores stay plausible.

    An inert signal shifts every score by the same amount. Ordering is
    untouched — which is why nothing ever looked wrong. What is lost is that
    the signal never *contributes* to ordering, so recall surfaced the
    globally most important memories rather than the ones relevant to the
    work in hand.
    """
    ranker = RecallRanker()
    rows = [_cand("A", importance=0.9), _cand("B", importance=0.5), _cand("C", importance=0.4)]

    without = [c["id"] for c in ranker.rank([dict(r) for r in rows], current_context={})]
    with_ctx = [
        c["id"]
        for c in ranker.rank([dict(r) for r in rows], current_context={"project": "life_graph"})
    ]
    assert without == with_ctx == ["A", "B", "C"]


def test_stored_context_lifts_a_relevant_memory_above_a_more_important_one():
    """What the context weight is for, once it can actually fire."""
    ranker = RecallRanker()
    ranked = ranker.rank(
        [
            _cand("globally-important", importance=0.9),
            _cand("relevant-to-now", importance=0.5, project="life_graph"),
        ],
        current_context={"project": "life_graph"},
    )
    scores = {c["id"]: c["final_score"] for c in ranked}
    assert scores["relevant-to-now"] >= scores["globally-important"], (
        "a memory from the project in hand should not rank below an unrelated "
        "one merely because the unrelated one is globally important"
    )


# ── reporting behaviour ───────────────────────────────────────────────


def test_reports_once_per_process_then_falls_to_debug(caplog):
    ranker = RecallRanker()
    rows = [_cand("A", importance=0.9), _cand("B", importance=0.2)]

    with caplog.at_level(logging.INFO, logger="life_graph.scoring.ranking"):
        ranker.rank([dict(r) for r in rows], current_context={"project": "p"})
        first = [r for r in caplog.records if r.levelno == logging.INFO]
        ranker.rank([dict(r) for r in rows], current_context={"project": "p"})
        second = [r for r in caplog.records if r.levelno == logging.INFO]

    assert len(first) == 1, "the condition should be reported"
    assert len(second) == 1, "repeat recalls must not repeat the line"


def test_report_names_the_signals_and_the_wasted_weight(caplog):
    with caplog.at_level(logging.INFO, logger="life_graph.scoring.ranking"):
        RecallRanker().rank(
            [_cand("A", importance=0.9), _cand("B", importance=0.2)],
            current_context={"project": "life_graph"},
        )
    # getMessage() already applies the record args; formatting again raises.
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "semantic" in text
    assert "context" in text
    assert "%" in text


def test_ranking_never_fails_on_an_inert_signal():
    """Reporting is diagnostic; recall must still return results."""
    ranked = RecallRanker().rank(
        [_cand("A"), _cand("B"), _cand("C")], current_context={"project": "p"}
    )
    assert len(ranked) == 3
    assert all("final_score" in c for c in ranked)
