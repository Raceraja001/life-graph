"""Unit tests for Life Graph scoring modules (T-020).

Tests the ImportanceTagger (signal-based importance scoring),
DecayCalculator (forgetting-curve model), and RecallRanker
(multi-signal retrieval ranking with diversity reranking).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from life_graph.scoring.decay import DecayCalculator
from life_graph.scoring.importance import ImportanceTagger
from life_graph.scoring.ranking import RecallRanker, context_similarity


# ---------------------------------------------------------------------------
# ImportanceTagger
# ---------------------------------------------------------------------------


class TestImportanceTagger:
    """Test signal-based importance scoring."""

    def setup_method(self) -> None:
        self.tagger = ImportanceTagger()

    # -- Explicit save signals (highest boost) ------------------------------

    def test_explicit_save_scores_high(self) -> None:
        score, tier = self.tagger.score("Remember this: always use type hints")
        assert score >= 0.8
        assert tier in ("critical", "high")

    def test_save_this_scores_high(self) -> None:
        score, tier = self.tagger.score("Save this: the DB password is in vault")
        assert score >= 0.8

    # -- Failure/bug context ------------------------------------------------

    def test_bug_context_increases_score(self) -> None:
        score, _ = self.tagger.score(
            "This bug crashed production and cost us 3 hours"
        )
        assert score >= 0.7

    def test_error_keyword_increases_score(self) -> None:
        score, _ = self.tagger.score("Encountered a critical error in the pipeline")
        assert score >= 0.7

    def test_crash_keyword_increases_score(self) -> None:
        score, _ = self.tagger.score("The server crash was caused by a memory leak")
        assert score >= 0.7

    # -- Hedging decreases score --------------------------------------------

    def test_hedging_decreases_score(self) -> None:
        score, _ = self.tagger.score(
            "Maybe we could perhaps try this approach"
        )
        assert score < 0.5

    def test_possibly_hedging(self) -> None:
        score, _ = self.tagger.score("This might possibly work for our case")
        assert score < 0.5

    def test_not_sure_hedging(self) -> None:
        score, _ = self.tagger.score("I'm not sure if this is the right path")
        assert score < 0.5

    # -- Questions decrease score -------------------------------------------

    def test_question_decreases_score(self) -> None:
        score, _ = self.tagger.score("Should we use Redis for caching?")
        assert score < 0.5

    def test_question_alone_mild_decrease(self) -> None:
        score_q, _ = self.tagger.score("What do we do next?")
        score_s, _ = self.tagger.score("We do this next.")
        assert score_q < score_s

    # -- Architecture decisions ---------------------------------------------

    def test_architecture_decision_moderate(self) -> None:
        score, _ = self.tagger.score(
            "The architecture pattern uses clean architecture with DDD"
        )
        assert score >= 0.5

    def test_design_keyword_boost(self) -> None:
        score, _ = self.tagger.score("The design of the storage layer")
        assert score >= 0.5

    # -- Cost/financial signals ---------------------------------------------

    def test_cost_keyword_boost(self) -> None:
        score, _ = self.tagger.score(
            "This will cost us $500 more per month in API calls"
        )
        assert score >= 0.6

    # -- Emphasis signals ---------------------------------------------------

    def test_emphasis_always_keyword(self) -> None:
        score, _ = self.tagger.score("You must always validate input data")
        assert score >= 0.7

    def test_emphasis_never_keyword(self) -> None:
        score, _ = self.tagger.score("Never deploy without running tests")
        assert score >= 0.7

    def test_all_caps_word_boost(self) -> None:
        score, _ = self.tagger.score("This is a CRITICAL step in the pipeline")
        assert score >= 0.7

    # -- Neutral text -------------------------------------------------------

    def test_neutral_text_baseline(self) -> None:
        score, tier = self.tagger.score("I worked on the project today")
        assert 0.3 <= score <= 0.6
        assert tier in ("normal", "low")

    def test_generic_statement_near_baseline(self) -> None:
        score, _ = self.tagger.score("The function returns a list of items")
        assert 0.3 <= score <= 0.7

    # -- Critical tier for extreme emphasis ---------------------------------

    def test_critical_tier_for_extreme(self) -> None:
        score, tier = self.tagger.score(
            "CRITICAL: NEVER deploy without running tests, it ALWAYS breaks"
        )
        assert tier == "critical"
        assert score >= 0.85

    def test_multiple_emphasis_stacks(self) -> None:
        # "important" + ALL_CAPS
        score, _ = self.tagger.score(
            "This is important, the PRODUCTION server must be backed up"
        )
        assert score >= 0.7

    # -- Repeated mention context -------------------------------------------

    def test_repeated_mentions_boost(self) -> None:
        score1, _ = self.tagger.score("Use PostgreSQL")
        score2, _ = self.tagger.score(
            "Use PostgreSQL", context={"repeated_count": 5}
        )
        assert score2 > score1

    def test_high_repeat_count_capped(self) -> None:
        # Weight is capped at 0.2 (repeated_count * 0.05, max 0.2)
        score1, _ = self.tagger.score(
            "Use PostgreSQL", context={"repeated_count": 100}
        )
        score2, _ = self.tagger.score(
            "Use PostgreSQL", context={"repeated_count": 4}
        )
        # 100 * 0.05 = capped at 0.2, 4 * 0.05 = 0.2 — both capped
        assert score1 == score2

    def test_zero_repeat_count_no_boost(self) -> None:
        score1, _ = self.tagger.score("Use PostgreSQL")
        score2, _ = self.tagger.score(
            "Use PostgreSQL", context={"repeated_count": 0}
        )
        assert score1 == score2

    # -- Tier mapping -------------------------------------------------------

    def test_tier_low(self) -> None:
        # Hedging + question to push score well below 0.4
        score, tier = self.tagger.score("Maybe we could try something?")
        assert tier == "low"

    def test_tier_normal(self) -> None:
        score, tier = self.tagger.score("I wrote some code today")
        assert tier == "normal"

    # -- Score bounds -------------------------------------------------------

    def test_score_never_exceeds_1(self) -> None:
        # Stack every positive signal
        score, _ = self.tagger.score(
            "CRITICAL: Remember this: always fix the bug in the architecture, "
            "it costs too much and is important!",
            context={"repeated_count": 10},
        )
        assert score <= 1.0

    def test_score_never_below_0(self) -> None:
        # Stack every negative signal
        score, _ = self.tagger.score("Maybe perhaps possibly not sure?")
        assert score >= 0.0

    # -- Detailed scoring ---------------------------------------------------

    def test_score_detailed_returns_signals(self) -> None:
        score, tier, signals = self.tagger.score_detailed(
            "Remember this: always use async drivers"
        )
        assert score >= 0.8
        assert len(signals) > 0
        signal_names = {s.name for s in signals}
        assert "explicit_save" in signal_names


# ---------------------------------------------------------------------------
# DecayCalculator
# ---------------------------------------------------------------------------


class TestDecayCalculator:
    """Test the forgetting-curve decay model."""

    def setup_method(self) -> None:
        self.calc = DecayCalculator()

    # -- Basic decay behaviour ----------------------------------------------

    def test_recent_high_importance_no_decay(self) -> None:
        score = self.calc.calculate(
            importance=0.9, access_count=10, days_since_access=1
        )
        assert score > 0.5

    def test_old_low_importance_decays(self) -> None:
        score = self.calc.calculate(
            importance=0.3, access_count=1, days_since_access=365
        )
        assert score < 0.01

    def test_zero_days_no_decay(self) -> None:
        score = self.calc.calculate(
            importance=1.0, access_count=1, days_since_access=0
        )
        # importance × 1^0.3 × e^0 = 1.0 × 1.0 × 1.0 = 1.0
        assert abs(score - 1.0) < 0.01

    def test_score_decreases_with_time(self) -> None:
        score_recent = self.calc.calculate(
            importance=0.5, access_count=5, days_since_access=1
        )
        score_old = self.calc.calculate(
            importance=0.5, access_count=5, days_since_access=100
        )
        assert score_recent > score_old

    # -- Access count boost -------------------------------------------------

    def test_access_count_helps(self) -> None:
        score_low = self.calc.calculate(
            importance=0.5, access_count=1, days_since_access=30
        )
        score_high = self.calc.calculate(
            importance=0.5, access_count=10, days_since_access=30
        )
        assert score_high > score_low

    def test_access_count_zero_treated_as_one(self) -> None:
        score_zero = self.calc.calculate(
            importance=0.5, access_count=0, days_since_access=10
        )
        score_one = self.calc.calculate(
            importance=0.5, access_count=1, days_since_access=10
        )
        assert score_zero == score_one

    # -- Decay rate ---------------------------------------------------------

    def test_higher_decay_rate_faster_decay(self) -> None:
        score_slow = self.calc.calculate(
            importance=0.5, access_count=5, days_since_access=30, decay_rate=0.05
        )
        score_fast = self.calc.calculate(
            importance=0.5, access_count=5, days_since_access=30, decay_rate=0.2
        )
        assert score_slow > score_fast

    # -- Archival decisions -------------------------------------------------

    def test_should_archive_low_score(self) -> None:
        assert self.calc.should_archive(0.001, "low") is True

    def test_should_not_archive_critical(self) -> None:
        assert self.calc.should_archive(0.001, "critical") is False

    def test_should_not_archive_high_score(self) -> None:
        assert self.calc.should_archive(0.5, "normal") is False

    def test_should_archive_at_threshold(self) -> None:
        # Exactly at threshold — still below
        assert self.calc.should_archive(0.005, "low", threshold=0.01) is True

    def test_should_not_archive_at_threshold(self) -> None:
        assert self.calc.should_archive(0.01, "low", threshold=0.01) is False

    def test_critical_never_archives(self) -> None:
        assert self.calc.should_archive(0.0, "critical") is False

    # -- Batch calculation --------------------------------------------------

    def test_batch_calculate(self) -> None:
        now = datetime.now(timezone.utc)
        memories = [
            {
                "id": "1",
                "importance": 0.9,
                "access_count": 5,
                "last_accessed": now - timedelta(days=7),
                "decay_rate": 0.1,
                "importance_tier": "high",
            },
            {
                "id": "2",
                "importance": 0.2,
                "access_count": 1,
                "last_accessed": now - timedelta(days=365),
                "decay_rate": 0.1,
                "importance_tier": "low",
            },
        ]
        results = self.calc.batch_calculate(memories)
        assert len(results) == 2
        # Each result is (id, decay_score, should_archive)
        assert results[0][0] == "1"
        assert results[1][0] == "2"
        assert results[0][1] > results[1][1]  # Recent high > old low

    def test_batch_calculate_empty(self) -> None:
        results = self.calc.batch_calculate([])
        assert results == []

    def test_batch_calculate_archives_old_memory(self) -> None:
        now = datetime.now(timezone.utc)
        memories = [
            {
                "id": "old",
                "importance": 0.1,
                "access_count": 1,
                "last_accessed": now - timedelta(days=1000),
                "decay_rate": 0.1,
                "importance_tier": "low",
            },
        ]
        results = self.calc.batch_calculate(memories)
        _, score, should_archive = results[0]
        assert should_archive is True
        assert score < 0.01

    def test_batch_calculate_with_float_days(self) -> None:
        memories = [
            {
                "id": "float_days",
                "importance": 0.8,
                "access_count": 3,
                "last_accessed": 7.0,  # Pre-computed days
                "decay_rate": 0.1,
                "importance_tier": "normal",
            },
        ]
        results = self.calc.batch_calculate(memories)
        assert len(results) == 1
        assert results[0][0] == "float_days"
        assert results[0][1] > 0.0

    # -- Edge cases ---------------------------------------------------------

    def test_zero_importance_zero_score(self) -> None:
        score = self.calc.calculate(
            importance=0.0, access_count=10, days_since_access=0
        )
        assert score == 0.0

    def test_score_always_non_negative(self) -> None:
        score = self.calc.calculate(
            importance=0.1, access_count=1, days_since_access=10000
        )
        assert score >= 0.0


# ---------------------------------------------------------------------------
# RecallRanker
# ---------------------------------------------------------------------------


class TestRecallRanker:
    """Test multi-signal retrieval ranking."""

    def setup_method(self) -> None:
        self.ranker = RecallRanker()

    # -- Basic ranking ------------------------------------------------------

    def test_rank_orders_by_score(self) -> None:
        candidates = [
            {
                "content": "low",
                "semantic_score": 0.3,
                "importance": 0.3,
                "access_count": 1,
                "days_since_access": 100.0,
                "trust_score": 0.5,
                "tags": ["a"],
            },
            {
                "content": "high",
                "semantic_score": 0.9,
                "importance": 0.9,
                "access_count": 10,
                "days_since_access": 1.0,
                "trust_score": 0.9,
                "tags": ["b"],
            },
        ]
        ranked = self.ranker.rank(candidates)
        assert ranked[0]["content"] == "high"
        assert ranked[1]["content"] == "low"

    def test_rank_adds_final_score(self) -> None:
        candidates = [
            {
                "content": "test",
                "semantic_score": 0.5,
                "importance": 0.5,
                "access_count": 1,
                "trust_score": 0.5,
            }
        ]
        ranked = self.ranker.rank(candidates)
        assert "final_score" in ranked[0]
        assert ranked[0]["final_score"] > 0

    def test_rank_adds_sub_scores(self) -> None:
        candidates = [
            {
                "content": "test",
                "semantic_score": 0.8,
                "importance": 0.7,
                "access_count": 5,
                "trust_score": 0.6,
            }
        ]
        ranked = self.ranker.rank(candidates)
        sub = ranked[0]["_sub_scores"]
        assert "semantic" in sub
        assert "context" in sub
        assert "importance" in sub
        assert "recency" in sub
        assert "frequency" in sub
        assert "trust" in sub

    def test_rank_empty_candidates(self) -> None:
        ranked = self.ranker.rank([])
        assert ranked == []

    # -- Context similarity -------------------------------------------------

    def test_rank_with_context_boosts_match(self) -> None:
        candidates = [
            {
                "content": "matching",
                "semantic_score": 0.5,
                "importance": 0.5,
                "access_count": 1,
                "trust_score": 0.5,
                "project": "life_graph",
                "module": "storage",
            },
            {
                "content": "non_matching",
                "semantic_score": 0.5,
                "importance": 0.5,
                "access_count": 1,
                "trust_score": 0.5,
                "project": "other_project",
                "module": "other",
            },
        ]
        ranked = self.ranker.rank(
            candidates,
            current_context={"project": "life_graph", "module": "storage"},
        )
        assert ranked[0]["content"] == "matching"

    # -- Reranking ----------------------------------------------------------

    def test_rerank_limits_results(self) -> None:
        candidates = [
            {
                "content": f"mem_{i}",
                "final_score": 1.0 - i * 0.01,
                "tags": [f"tag_{i}"],
                "last_surfaced": None,
            }
            for i in range(20)
        ]
        reranked = self.ranker.rerank(candidates, max_results=5)
        assert len(reranked) <= 5

    def test_rerank_respects_topic_cap(self) -> None:
        # All same topic, max_per_topic=2
        candidates = [
            {
                "content": f"mem_{i}",
                "final_score": 1.0 - i * 0.01,
                "tags": ["same_topic"],
                "last_surfaced": None,
            }
            for i in range(10)
        ]
        reranked = self.ranker.rerank(
            candidates, max_results=10, max_per_topic=2
        )
        assert len(reranked) <= 2

    def test_rerank_cooldown_filters_recent(self) -> None:
        now = datetime.now(timezone.utc)
        candidates = [
            {
                "content": "recently_surfaced",
                "final_score": 0.9,
                "tags": ["a"],
                "last_surfaced": now - timedelta(hours=1),  # Very recent
            },
            {
                "content": "not_surfaced",
                "final_score": 0.8,
                "tags": ["b"],
                "last_surfaced": None,
            },
        ]
        reranked = self.ranker.rerank(
            candidates, max_results=5, cooldown_days=7.0
        )
        # The recently surfaced one should be filtered out
        contents = [c["content"] for c in reranked]
        assert "recently_surfaced" not in contents
        assert "not_surfaced" in contents

    def test_rerank_allows_past_cooldown(self) -> None:
        now = datetime.now(timezone.utc)
        candidates = [
            {
                "content": "old_surfaced",
                "final_score": 0.9,
                "tags": ["a"],
                "last_surfaced": now - timedelta(days=30),  # Long ago
            },
        ]
        reranked = self.ranker.rerank(
            candidates, max_results=5, cooldown_days=7.0
        )
        assert len(reranked) == 1

    def test_rerank_preserves_order(self) -> None:
        candidates = [
            {
                "content": "first",
                "final_score": 0.9,
                "tags": ["a"],
                "last_surfaced": None,
            },
            {
                "content": "second",
                "final_score": 0.7,
                "tags": ["b"],
                "last_surfaced": None,
            },
        ]
        reranked = self.ranker.rerank(candidates, max_results=5)
        assert reranked[0]["content"] == "first"
        assert reranked[1]["content"] == "second"


# ---------------------------------------------------------------------------
# Context similarity helper
# ---------------------------------------------------------------------------


class TestContextSimilarity:
    """Test the context_similarity function directly."""

    def test_perfect_match(self) -> None:
        cand = {
            "project": "life_graph",
            "module": "storage",
            "tools": ["pytest", "ruff"],
            "files": ["db.py", "config.py"],
        }
        ctx = {
            "project": "life_graph",
            "module": "storage",
            "tools": ["pytest", "ruff"],
            "files": ["db.py", "config.py"],
        }
        score = context_similarity(cand, ctx)
        assert score == 1.0

    def test_no_match(self) -> None:
        cand = {
            "project": "other",
            "module": "other",
            "tools": ["maven"],
            "files": ["pom.xml"],
        }
        ctx = {
            "project": "life_graph",
            "module": "storage",
            "tools": ["pytest"],
            "files": ["db.py"],
        }
        score = context_similarity(cand, ctx)
        assert score == 0.0

    def test_partial_match(self) -> None:
        cand = {"project": "life_graph", "module": "api"}
        ctx = {"project": "life_graph", "module": "storage"}
        score = context_similarity(cand, ctx)
        # Project matches (+0.3), module doesn't
        assert abs(score - 0.3) < 0.01

    def test_empty_context(self) -> None:
        cand = {"project": "life_graph"}
        score = context_similarity(cand, {})
        assert score == 0.0

    def test_tools_overlap(self) -> None:
        cand = {"tools": ["pytest", "ruff", "mypy"]}
        ctx = {"tools": ["pytest", "ruff"]}
        score = context_similarity(cand, ctx)
        # overlap = 2, max_size = 3, so 0.2 * (2/3)
        assert score > 0.0
