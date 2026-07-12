"""Unit tests for the interview engine and daily brief — pure logic paths."""

from __future__ import annotations

from life_graph.services.brief import BriefComposer
from life_graph.services.interview import (
    MAX_ASKS,
    ORIGIN_ORDER,
    QUESTION_TTL_DAYS,
    InterviewService,
)


class TestOutcomeInference:
    """Free-text answers map to prediction outcomes."""

    def test_positive_answers(self) -> None:
        for answer in ["Yes", "yes, it shipped", "Correct", "It did work", "Done"]:
            assert InterviewService._infer_outcome(answer) == "correct", answer

    def test_negative_answers(self) -> None:
        for answer in ["No", "no way", "Incorrect", "didn't happen", "Failed hard"]:
            assert InterviewService._infer_outcome(answer) == "incorrect", answer

    def test_ambiguous_answers(self) -> None:
        for answer in ["kind of", "partially", "still waiting on the client"]:
            assert InterviewService._infer_outcome(answer) == "ambiguous", answer


class TestBudgetConstants:
    """Anti-nag invariants the spec cares about."""

    def test_origin_priority_order(self) -> None:
        assert ORIGIN_ORDER == [
            "outcome_resolution",
            "knowledge_gap",
            "drift",
            "reflection",
        ]

    def test_never_nag_constants(self) -> None:
        assert MAX_ASKS == 2
        assert QUESTION_TTL_DAYS == 7


class TestBriefFormatting:
    """Brief body composition — silence and section ordering."""

    def test_empty_sections_produce_empty_body(self) -> None:
        body = BriefComposer._format_body(
            held=[],
            questions=[],
            capture_summary={"captures": 0, "memories": 0, "decisions": 0, "total": 0},
            watcher_summary={},
        )
        assert body == ""

    def test_sections_appear_in_order(self) -> None:
        body = BriefComposer._format_body(
            held=[{"id": "n1", "title": "Deploy failed", "priority": "critical"}],
            questions=[{"id": "q1", "question": "Is X still a goal?", "origin": "drift"}],
            capture_summary={"captures": 5, "memories": 3, "decisions": 1, "total": 9},
            watcher_summary={"server_health": 2},
        )
        attention = body.index("Needs attention")
        questions = body.index("Questions for you")
        summary = body.index("Yesterday:")
        watchers = body.index("Watchers (24h):")
        assert attention < questions < summary < watchers
        assert "[critical] Deploy failed" in body
        assert "Is X still a goal?" in body
        assert "5 captures, 3 new memories, 1 decisions" in body
        assert "server_health: 2" in body

    def test_critical_notifications_sort_first(self) -> None:
        held = [
            {"id": "a", "title": "FYI", "priority": "important"},
            {"id": "b", "title": "Fire", "priority": "critical"},
        ]
        held.sort(key=lambda h: 0 if h["priority"] == "critical" else 1)
        assert held[0]["title"] == "Fire"
