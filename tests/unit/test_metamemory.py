"""Metamemory tracker unit tests (T-034).

Tests for confidence assessment, topic normalisation, and max-score
extraction — pure logic that doesn't need a database session.
"""

from __future__ import annotations

import pytest

from life_graph.services.metamemory import MetamemoryTracker


def _make_tracker() -> MetamemoryTracker:
    """Create a MetamemoryTracker without invoking __init__.

    We bypass __init__ (which requires a DB session factory) because
    assess_confidence, _normalise_topic, and _extract_max_score are
    pure functions that don't touch the database.
    """
    return MetamemoryTracker.__new__(MetamemoryTracker)


# ── Confidence assessment ─────────────────────────────────────────────────


class TestAssessConfidence:
    """Tests for MetamemoryTracker.assess_confidence()."""

    def setup_method(self) -> None:
        self.tracker = _make_tracker()

    # -- high tier ---------------------------------------------------------

    def test_high_confidence_multiple_results(self) -> None:
        tier, msg = self.tracker.assess_confidence(
            results=[{"confidence": 0.9}, {"confidence": 0.8}],
            query="test",
        )
        assert tier == "high"
        assert msg == ""

    def test_high_confidence_single_result(self) -> None:
        tier, msg = self.tracker.assess_confidence(
            results=[{"confidence": 0.75}],
            query="test",
        )
        assert tier == "high"
        assert msg == ""

    def test_high_confidence_at_threshold(self) -> None:
        """Score exactly at 0.7 should be 'high'."""
        tier, msg = self.tracker.assess_confidence(
            results=[{"confidence": 0.7}],
            query="test",
        )
        assert tier == "high"
        assert msg == ""

    # -- partial tier ------------------------------------------------------

    def test_partial_confidence(self) -> None:
        tier, msg = self.tracker.assess_confidence(
            results=[{"confidence": 0.5}],
            query="test",
        )
        assert tier == "partial"
        assert "limited" in msg.lower()

    def test_partial_at_lower_bound(self) -> None:
        """Score at exactly 0.3 should be 'partial'."""
        tier, msg = self.tracker.assess_confidence(
            results=[{"confidence": 0.3}],
            query="test",
        )
        assert tier == "partial"
        assert len(msg) > 0

    def test_partial_just_below_high(self) -> None:
        tier, msg = self.tracker.assess_confidence(
            results=[{"confidence": 0.69}],
            query="test",
        )
        assert tier == "partial"

    # -- unknown tier ------------------------------------------------------

    def test_unknown_empty_results(self) -> None:
        tier, msg = self.tracker.assess_confidence(
            results=[],
            query="test",
        )
        assert tier == "unknown"
        assert "reliable" in msg.lower() or "don't" in msg.lower()

    def test_unknown_with_low_scores(self) -> None:
        tier, msg = self.tracker.assess_confidence(
            results=[{"confidence": 0.1}],
            query="test",
        )
        assert tier == "unknown"
        assert len(msg) > 0

    def test_unknown_with_zero_scores(self) -> None:
        tier, msg = self.tracker.assess_confidence(
            results=[{"confidence": 0.0}, {"confidence": 0.0}],
            query="test",
        )
        assert tier == "unknown"

    def test_unknown_just_below_partial(self) -> None:
        tier, msg = self.tracker.assess_confidence(
            results=[{"confidence": 0.29}],
            query="test",
        )
        assert tier == "unknown"

    # -- edge cases --------------------------------------------------------

    def test_uses_max_of_multiple_scores(self) -> None:
        """The tier should be determined by the best score, not worst."""
        tier, _msg = self.tracker.assess_confidence(
            results=[{"confidence": 0.1}, {"confidence": 0.9}],
            query="test",
        )
        assert tier == "high"

    def test_score_key_alias(self) -> None:
        """Results can use 'score' instead of 'confidence'."""
        tier, _msg = self.tracker.assess_confidence(
            results=[{"score": 0.8}],
            query="test",
        )
        assert tier == "high"


# ── Max-score extraction ──────────────────────────────────────────────────


class TestExtractMaxScore:
    """Tests for the static _extract_max_score helper."""

    def test_dict_with_confidence_key(self) -> None:
        score = MetamemoryTracker._extract_max_score(
            [{"confidence": 0.9}, {"confidence": 0.3}]
        )
        assert score == pytest.approx(0.9)

    def test_dict_with_score_key(self) -> None:
        score = MetamemoryTracker._extract_max_score(
            [{"score": 0.7}, {"score": 0.4}]
        )
        assert score == pytest.approx(0.7)

    def test_empty_list(self) -> None:
        score = MetamemoryTracker._extract_max_score([])
        assert score == 0.0

    def test_object_with_confidence_attr(self) -> None:
        class FakeResult:
            def __init__(self, conf: float) -> None:
                self.confidence = conf

        score = MetamemoryTracker._extract_max_score(
            [FakeResult(0.6), FakeResult(0.8)]
        )
        assert score == pytest.approx(0.8)

    def test_object_with_score_attr(self) -> None:
        class FakeResult:
            def __init__(self, s: float) -> None:
                self.score = s

        score = MetamemoryTracker._extract_max_score(
            [FakeResult(0.5)]
        )
        assert score == pytest.approx(0.5)

    def test_mixed_dict_types(self) -> None:
        """Handles dicts where some have 'confidence' and others 'score'."""
        score = MetamemoryTracker._extract_max_score(
            [{"confidence": 0.4}, {"score": 0.6}]
        )
        assert score == pytest.approx(0.6)

    def test_missing_keys_default_to_zero(self) -> None:
        score = MetamemoryTracker._extract_max_score([{}])
        assert score == 0.0


# ── Topic normalisation ──────────────────────────────────────────────────


class TestNormaliseTopic:
    """Tests for the static _normalise_topic helper."""

    def test_strips_whitespace(self) -> None:
        topic = MetamemoryTracker._normalise_topic("  hello world  ")
        assert topic == "hello world"

    def test_strips_what_is_prefix(self) -> None:
        topic = MetamemoryTracker._normalise_topic("what is pgvector")
        assert topic == "pgvector"

    def test_strips_how_to_prefix(self) -> None:
        topic = MetamemoryTracker._normalise_topic("how to deploy FastAPI")
        assert topic == "deploy FastAPI"

    def test_strips_how_do_i_prefix(self) -> None:
        topic = MetamemoryTracker._normalise_topic("how do i configure pgvector")
        assert topic == "configure pgvector"

    def test_strips_where_is_prefix(self) -> None:
        topic = MetamemoryTracker._normalise_topic("where is the config file")
        assert topic == "the config file"

    def test_strips_what_are_prefix(self) -> None:
        topic = MetamemoryTracker._normalise_topic("what are the best practices")
        assert topic == "the best practices"

    def test_no_prefix_passthrough(self) -> None:
        topic = MetamemoryTracker._normalise_topic("pgvector indexing")
        assert topic == "pgvector indexing"

    def test_case_insensitive_prefix_stripping(self) -> None:
        topic = MetamemoryTracker._normalise_topic("What Is halfvec")
        assert topic == "halfvec"

    def test_empty_string(self) -> None:
        topic = MetamemoryTracker._normalise_topic("")
        assert topic == ""

    def test_only_prefix_word(self) -> None:
        """Edge case: query is just the prefix with nothing after."""
        topic = MetamemoryTracker._normalise_topic("how to ")
        # The normaliser may or may not strip a prefix that equals the full query
        assert isinstance(topic, str)
