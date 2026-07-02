"""Contradiction detection unit tests (T-028).

Tests for the Contradiction dataclass and the rule-based helper
functions (_check_negation_flip, _check_entity_swap, _entities_overlap,
_determine_resolution). No database or embedding service required.
"""

from __future__ import annotations

import pytest

from life_graph.services.contradiction import (
    Contradiction,
    _check_entity_swap,
    _check_negation_flip,
    _determine_resolution,
    _entities_overlap,
)


# ── Contradiction dataclass ───────────────────────────────────────────────


class TestContradictionDataclass:
    """Verify Contradiction fields and construction."""

    def test_create_full_contradiction(self) -> None:
        c = Contradiction(
            existing_memory_id="abc-123",
            existing_content="I prefer Flask",
            new_content="I prefer FastAPI",
            conflict_type="preference_change",
            similarity=0.85,
            resolution="supersede",
            reason="Same preference slot, different value",
        )
        assert c.existing_memory_id == "abc-123"
        assert c.existing_content == "I prefer Flask"
        assert c.new_content == "I prefer FastAPI"
        assert c.conflict_type == "preference_change"
        assert c.similarity == 0.85
        assert c.resolution == "supersede"
        assert c.reason == "Same preference slot, different value"

    def test_contradiction_fields_are_all_accessible(self) -> None:
        c = Contradiction(
            existing_memory_id="x",
            existing_content="old",
            new_content="new",
            conflict_type="negation",
            similarity=0.9,
            resolution="ask_user",
            reason="unclear",
        )
        # Verify every field can be read
        assert all(
            getattr(c, f) is not None
            for f in [
                "existing_memory_id",
                "existing_content",
                "new_content",
                "conflict_type",
                "similarity",
                "resolution",
                "reason",
            ]
        )


# ── Negation flip detection ──────────────────────────────────────────────


class TestNegationFlip:
    """Tests for _check_negation_flip rule-based detection."""

    def test_detects_dont_use_vs_use(self) -> None:
        result = _check_negation_flip(
            "I don't use MongoDB",
            "I always use MongoDB",
        )
        assert result is not None
        conflict_type, reason = result
        assert conflict_type == "negation"
        assert len(reason) > 0

    def test_detects_avoid_vs_use(self) -> None:
        result = _check_negation_flip(
            "avoid global variables",
            "use global variables",
        )
        assert result is not None
        conflict_type, _reason = result
        assert conflict_type == "negation"

    def test_detects_never_vs_always(self) -> None:
        result = _check_negation_flip(
            "never use raw SQL",
            "always use raw SQL",
        )
        assert result is not None
        conflict_type, _reason = result
        assert conflict_type == "negation"

    def test_detects_stopped_using_vs_use(self) -> None:
        result = _check_negation_flip(
            "stopped using Flask",
            "I use Flask",
        )
        assert result is not None
        conflict_type, _reason = result
        assert conflict_type == "preference_change"

    def test_detects_switched_from_vs_use(self) -> None:
        result = _check_negation_flip(
            "switched from SQLite",
            "I use SQLite",
        )
        assert result is not None
        conflict_type, _reason = result
        assert conflict_type == "preference_change"

    def test_no_flip_for_unrelated_content(self) -> None:
        result = _check_negation_flip(
            "I enjoy reading books",
            "The weather is nice today",
        )
        assert result is None

    def test_no_flip_same_polarity(self) -> None:
        result = _check_negation_flip(
            "I prefer PostgreSQL",
            "I use PostgreSQL",
        )
        assert result is None

    def test_direction_2_existing_negative_new_positive(self) -> None:
        """Direction 2: existing has negative, new has positive."""
        result = _check_negation_flip(
            "I always use tabs",
            "I never use tabs",
        )
        assert result is not None
        conflict_type, _reason = result
        assert conflict_type == "negation"

    def test_no_flip_when_entities_differ(self) -> None:
        """Different entities shouldn't trigger a negation flip."""
        result = _check_negation_flip(
            "don't use MongoDB",
            "use PostgreSQL",
        )
        assert result is None


# ── Entity swap detection ─────────────────────────────────────────────────


class TestEntitySwap:
    """Tests for _check_entity_swap preference-verb detection."""

    def test_detects_prefer_swap(self) -> None:
        result = _check_entity_swap(
            "I prefer PostgreSQL",
            "I prefer MongoDB",
        )
        assert result is not None
        assert "PostgreSQL" in result or "MongoDB" in result

    def test_detects_use_swap(self) -> None:
        result = _check_entity_swap(
            "I use FastAPI",
            "I use Django",
        )
        assert result is not None

    def test_no_swap_same_entity(self) -> None:
        result = _check_entity_swap(
            "I prefer PostgreSQL",
            "I prefer PostgreSQL",
        )
        assert result is None

    def test_no_swap_different_verbs(self) -> None:
        """Non-preference verbs shouldn't trigger entity swap."""
        result = _check_entity_swap(
            "The sky is blue",
            "The grass is green",
        )
        assert result is None

    def test_detects_switched_to_swap(self) -> None:
        result = _check_entity_swap(
            "I switched to FastAPI",
            "I prefer Django",
        )
        assert result is not None


# ── Entity overlap helper ─────────────────────────────────────────────────


class TestEntitiesOverlap:
    """Tests for _entities_overlap string matching."""

    def test_exact_match(self) -> None:
        assert _entities_overlap("postgresql", "postgresql") is True

    def test_substring_match(self) -> None:
        assert _entities_overlap("postgres", "postgresql") is True

    def test_word_overlap(self) -> None:
        assert _entities_overlap("raw sql queries", "sql queries") is True

    def test_no_overlap(self) -> None:
        assert _entities_overlap("mongodb", "postgresql") is False

    def test_empty_strings(self) -> None:
        assert _entities_overlap("", "") is True  # exact match of ""


# ── Resolution strategy ──────────────────────────────────────────────────


class TestDetermineResolution:
    """Tests for _determine_resolution logic."""

    def test_negation_supersedes(self) -> None:
        # memory arg needs a mock-like object — use a simple object
        class FakeMemory:
            properties = {}

        assert _determine_resolution("negation", FakeMemory()) == "supersede"

    def test_preference_change_supersedes(self) -> None:
        class FakeMemory:
            properties = {}

        assert _determine_resolution("preference_change", FakeMemory()) == "supersede"

    def test_scope_keeps_both(self) -> None:
        class FakeMemory:
            properties = {}

        assert _determine_resolution("scope", FakeMemory()) == "scope"

    def test_unknown_type_asks_user(self) -> None:
        class FakeMemory:
            properties = {}

        assert _determine_resolution("ambiguous", FakeMemory()) == "ask_user"

    def test_unexpected_type_asks_user(self) -> None:
        class FakeMemory:
            properties = {}

        assert _determine_resolution("something_else", FakeMemory()) == "ask_user"
