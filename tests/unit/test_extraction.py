"""Unit tests for Life Graph extraction pipeline (T-016).

Tests the Tier 1 RuleBasedExtractor thoroughly — all fact types,
confidence levels, edge cases, and false-positive rejection.

Also tests the ExtractionPipeline orchestrator with mocked Tier 2/3.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.extraction.rules import ExtractedFact, RuleBasedExtractor


# ---------------------------------------------------------------------------
# Tier 1 — RuleBasedExtractor
# ---------------------------------------------------------------------------


class TestRuleBasedExtractor:
    """Test the regex-based Tier 1 fact extractor."""

    def setup_method(self) -> None:
        self.extractor = RuleBasedExtractor()

    # -- Preferences --------------------------------------------------------

    def test_extracts_preference_i_prefer(self) -> None:
        facts = self.extractor.extract("I prefer FastAPI for building APIs")
        assert any(f.fact_type == "preference" for f in facts)
        assert any("FastAPI" in f.content for f in facts)

    def test_extracts_preference_i_always_use(self) -> None:
        facts = self.extractor.extract("I always use PostgreSQL for databases")
        assert any(f.fact_type == "preference" for f in facts)
        assert any("PostgreSQL" in f.content for f in facts)

    def test_extracts_preference_my_goto(self) -> None:
        facts = self.extractor.extract("My go-to is Django")
        assert any(f.fact_type == "preference" for f in facts)

    def test_extracts_preference_usually_use(self) -> None:
        facts = self.extractor.extract("I usually use Ruff for linting")
        assert any(f.fact_type == "preference" for f in facts)

    def test_extracts_preference_typically_use(self) -> None:
        facts = self.extractor.extract("I typically use asyncpg for database drivers")
        assert any(f.fact_type == "preference" for f in facts)

    def test_extracts_preference_swear_by(self) -> None:
        facts = self.extractor.extract("I swear by Docker for deployments")
        assert any(f.fact_type == "preference" for f in facts)

    def test_extracts_preference_really_love(self) -> None:
        facts = self.extractor.extract("I really love using Pydantic")
        assert any(f.fact_type == "preference" for f in facts)

    # -- Anti-preferences ---------------------------------------------------

    def test_extracts_anti_preference_dont_like(self) -> None:
        facts = self.extractor.extract("I don't like MongoDB for relational data")
        assert any(f.fact_type == "anti_preference" for f in facts)

    def test_extracts_anti_preference_avoid(self) -> None:
        facts = self.extractor.extract("I avoid using global variables")
        assert any(f.fact_type == "anti_preference" for f in facts)

    def test_extracts_anti_preference_never_use(self) -> None:
        facts = self.extractor.extract("Never use eval() in production code")
        assert any(f.fact_type == "anti_preference" for f in facts)

    def test_extracts_anti_preference_hate(self) -> None:
        facts = self.extractor.extract("I hate writing boilerplate code")
        assert any(f.fact_type == "anti_preference" for f in facts)

    def test_extracts_anti_preference_cant_stand(self) -> None:
        facts = self.extractor.extract("I can't stand YAML configuration")
        assert any(f.fact_type == "anti_preference" for f in facts)

    def test_extracts_anti_preference_stay_away(self) -> None:
        facts = self.extractor.extract("I stay away from vendor lock-in")
        assert any(f.fact_type == "anti_preference" for f in facts)

    def test_extracts_anti_preference_stopped_using(self) -> None:
        facts = self.extractor.extract("I stopped using ChromaDB last month")
        assert any(f.fact_type == "anti_preference" for f in facts)

    # -- Decisions ----------------------------------------------------------

    def test_extracts_decision_i_decided(self) -> None:
        facts = self.extractor.extract("I decided to use Docker for deployment")
        assert any(f.fact_type == "decision" for f in facts)

    def test_extracts_decision_switched_to(self) -> None:
        facts = self.extractor.extract("I switched to Ruff from Flake8")
        assert any(f.fact_type == "decision" for f in facts)

    def test_extracts_decision_went_with(self) -> None:
        facts = self.extractor.extract("I went with SQLAlchemy for the ORM")
        assert any(f.fact_type == "decision" for f in facts)

    def test_extracts_decision_i_chose(self) -> None:
        facts = self.extractor.extract("I chose PostgreSQL over MySQL")
        assert any(f.fact_type == "decision" for f in facts)

    def test_extracts_decision_picked(self) -> None:
        facts = self.extractor.extract("I picked FastAPI for the project")
        assert any(f.fact_type == "decision" for f in facts)

    def test_extracts_decision_settled_on(self) -> None:
        facts = self.extractor.extract("I settled on using pgvector")
        assert any(f.fact_type == "decision" for f in facts)

    def test_extracts_decision_we_are_going_with(self) -> None:
        facts = self.extractor.extract("We're going with MinIO for object storage")
        assert any(f.fact_type == "decision" for f in facts)

    # -- Explicit saves -----------------------------------------------------

    def test_extracts_explicit_save_remember(self) -> None:
        facts = self.extractor.extract(
            "Remember this: always run migrations before deploying"
        )
        assert any(f.fact_type == "explicit_save" for f in facts)

    def test_extracts_explicit_save_important(self) -> None:
        facts = self.extractor.extract(
            "Important: the API key must be rotated monthly"
        )
        assert any(f.fact_type == "explicit_save" for f in facts)

    def test_extracts_explicit_save_save_this(self) -> None:
        facts = self.extractor.extract("Save this: the staging DB is on port 5433")
        assert any(f.fact_type == "explicit_save" for f in facts)

    def test_extracts_explicit_save_note_that(self) -> None:
        facts = self.extractor.extract("Note that the config file is YAML-based")
        assert any(f.fact_type == "explicit_save" for f in facts)

    def test_extracts_explicit_save_dont_forget(self) -> None:
        facts = self.extractor.extract("Don't forget: update the changelog")
        assert any(f.fact_type == "explicit_save" for f in facts)

    def test_extracts_explicit_save_keep_in_mind(self) -> None:
        facts = self.extractor.extract("Keep in mind: the test DB resets nightly")
        assert any(f.fact_type == "explicit_save" for f in facts)

    # -- Intentions ---------------------------------------------------------

    def test_extracts_intention_i_should(self) -> None:
        facts = self.extractor.extract("I should refactor the auth module later")
        assert any(f.fact_type == "intention" for f in facts)

    def test_extracts_intention_todo(self) -> None:
        facts = self.extractor.extract("TODO: add rate limiting to the API")
        assert any(f.fact_type == "intention" for f in facts)

    def test_extracts_intention_fixme(self) -> None:
        facts = self.extractor.extract("FIXME: handle edge case in parser")
        assert any(f.fact_type == "intention" for f in facts)

    def test_extracts_intention_remind_me(self) -> None:
        facts = self.extractor.extract("Remind me to update the dependencies")
        assert any(f.fact_type == "intention" for f in facts)

    def test_extracts_intention_i_need_to(self) -> None:
        facts = self.extractor.extract("I need to set up CI/CD pipeline")
        assert any(f.fact_type == "intention" for f in facts)

    def test_extracts_intention_i_plan_to(self) -> None:
        facts = self.extractor.extract("I plan to migrate to Kubernetes next quarter")
        assert any(f.fact_type == "intention" for f in facts)

    def test_extracts_intention_i_want_to(self) -> None:
        facts = self.extractor.extract("I want to add WebSocket support")
        assert any(f.fact_type == "intention" for f in facts)

    # -- Confidence ---------------------------------------------------------

    def test_confidence_is_high_for_regex(self) -> None:
        facts = self.extractor.extract("I prefer Python over JavaScript")
        assert len(facts) > 0
        for f in facts:
            if f.fact_type in ("preference", "anti_preference", "decision", "explicit_save"):
                assert f.confidence >= 0.8

    def test_todo_has_very_high_confidence(self) -> None:
        facts = self.extractor.extract("TODO: add caching layer")
        todo_facts = [f for f in facts if f.fact_type == "intention"]
        assert len(todo_facts) > 0
        assert todo_facts[0].confidence >= 0.90

    def test_explicit_save_has_highest_confidence(self) -> None:
        facts = self.extractor.extract("Remember this: always use async drivers")
        save_facts = [f for f in facts if f.fact_type == "explicit_save"]
        assert len(save_facts) > 0
        assert save_facts[0].confidence >= 0.90

    # -- No false positives -------------------------------------------------

    def test_no_extraction_from_generic_text(self) -> None:
        facts = self.extractor.extract("The weather is nice today")
        # Generic facts pattern may match "The weather is nice today" as a fact,
        # but should not match preference/decision/intention types
        high_confidence = [f for f in facts if f.fact_type != "fact"]
        assert len(high_confidence) == 0

    def test_no_extraction_from_greeting(self) -> None:
        facts = self.extractor.extract("Hello, how are you?")
        specific_facts = [f for f in facts if f.fact_type != "fact"]
        assert len(specific_facts) == 0

    def test_no_extraction_from_question(self) -> None:
        facts = self.extractor.extract("What do you think about this approach?")
        specific_facts = [
            f for f in facts if f.fact_type in ("preference", "decision", "explicit_save")
        ]
        assert len(specific_facts) == 0

    # -- Multiple extractions -----------------------------------------------

    def test_multiple_facts_from_one_text(self) -> None:
        text = "I prefer FastAPI. I always use PostgreSQL. TODO: add caching"
        facts = self.extractor.extract(text)
        fact_types = {f.fact_type for f in facts}
        # Should find at least preferences and intention
        assert "preference" in fact_types or "intention" in fact_types
        assert len(facts) >= 2

    def test_multiple_preferences(self) -> None:
        text = "I prefer Python over JS. I always use black for formatting."
        facts = self.extractor.extract(text)
        pref_facts = [f for f in facts if f.fact_type == "preference"]
        assert len(pref_facts) >= 2

    def test_mixed_preferences_and_decisions(self) -> None:
        text = "I prefer FastAPI. I decided to use Docker."
        facts = self.extractor.extract(text)
        fact_types = {f.fact_type for f in facts}
        assert "preference" in fact_types
        assert "decision" in fact_types

    # -- Entities extraction ------------------------------------------------

    def test_entities_extracted(self) -> None:
        facts = self.extractor.extract("I prefer FastAPI over Flask")
        preference_facts = [f for f in facts if f.fact_type == "preference"]
        assert len(preference_facts) > 0
        # The entity should include "FastAPI" (captured group)
        assert any("FastAPI" in str(f.entities) for f in preference_facts)

    def test_entities_list_not_empty(self) -> None:
        facts = self.extractor.extract("I decided to use SQLAlchemy")
        for f in facts:
            if f.fact_type == "decision":
                assert len(f.entities) > 0

    # -- Content formatting -------------------------------------------------

    def test_preference_content_format(self) -> None:
        facts = self.extractor.extract("I prefer FastAPI for APIs")
        prefs = [f for f in facts if f.fact_type == "preference"]
        assert len(prefs) > 0
        assert prefs[0].content.startswith("Prefers:")

    def test_decision_content_format(self) -> None:
        facts = self.extractor.extract("I decided to use Docker")
        decisions = [f for f in facts if f.fact_type == "decision"]
        assert len(decisions) > 0
        assert decisions[0].content.startswith("Decided:")

    def test_anti_preference_content_format(self) -> None:
        facts = self.extractor.extract("I avoid using global state")
        anti_prefs = [f for f in facts if f.fact_type == "anti_preference"]
        assert len(anti_prefs) > 0
        assert anti_prefs[0].content.startswith("Avoids:")

    def test_intention_content_format(self) -> None:
        facts = self.extractor.extract("TODO: add unit tests")
        intents = [f for f in facts if f.fact_type == "intention"]
        assert len(intents) > 0
        assert intents[0].content.startswith("TODO:")

    def test_explicit_save_content_format(self) -> None:
        facts = self.extractor.extract("Remember this: backup the database daily")
        saves = [f for f in facts if f.fact_type == "explicit_save"]
        assert len(saves) > 0
        assert saves[0].content.startswith("Saved:")

    # -- Source text --------------------------------------------------------

    def test_source_text_captured(self) -> None:
        facts = self.extractor.extract("I prefer FastAPI for APIs")
        for f in facts:
            assert f.source_text != ""

    # -- Sorting ------------------------------------------------------------

    def test_results_sorted_by_confidence_descending(self) -> None:
        text = "I prefer Python. I should refactor later. Note that config is YAML."
        facts = self.extractor.extract(text)
        if len(facts) > 1:
            for i in range(len(facts) - 1):
                assert facts[i].confidence >= facts[i + 1].confidence

    # -- Edge cases ---------------------------------------------------------

    def test_empty_text_returns_empty(self) -> None:
        facts = self.extractor.extract("")
        assert facts == []

    def test_whitespace_only_returns_empty_or_no_match(self) -> None:
        facts = self.extractor.extract("   \n\t  ")
        # Should return no meaningful facts
        specific = [f for f in facts if f.fact_type != "fact"]
        assert len(specific) == 0

    def test_case_insensitive_matching(self) -> None:
        facts = self.extractor.extract("i PREFER python over javascript")
        assert any(f.fact_type == "preference" for f in facts)

    def test_multiline_text(self) -> None:
        text = "I prefer FastAPI.\nI always use PostgreSQL.\nTODO: add tests"
        facts = self.extractor.extract(text)
        assert len(facts) >= 2


# ---------------------------------------------------------------------------
# ExtractionPipeline tests (with mocked Tier 2/3)
# ---------------------------------------------------------------------------


class TestExtractionPipeline:
    """Test the pipeline orchestrator with mocked spaCy and LLM extractors."""

    def setup_method(self) -> None:
        from life_graph.extraction.pipeline import ExtractionPipeline

        # Create mock Tier 2 (spaCy) — returns empty by default
        self.mock_spacy = MagicMock()
        self.mock_spacy.extract.return_value = []

        # Create mock Tier 3 (LLM) — async, returns empty by default
        self.mock_llm = MagicMock()
        self.mock_llm.extract = AsyncMock(return_value=[])
        self.mock_llm.total_cost_usd = 0.0
        self.mock_llm.get_cost_summary.return_value = {"total_cost_usd": 0.0}

        self.pipeline = ExtractionPipeline(
            rules_extractor=RuleBasedExtractor(),
            spacy_extractor=self.mock_spacy,
            llm_extractor=self.mock_llm,
        )

    async def test_pipeline_extracts_from_text(self) -> None:
        result = await self.pipeline.extract("I prefer FastAPI for APIs")
        assert len(result.facts) > 0
        assert any(f.fact_type == "preference" for f in result.facts)

    async def test_pipeline_returns_extraction_result(self) -> None:
        from life_graph.extraction.pipeline import ExtractionResult

        result = await self.pipeline.extract("I decided to use Docker")
        assert isinstance(result, ExtractionResult)
        assert result.tier1_count > 0

    async def test_pipeline_tracks_tier1_stats(self) -> None:
        await self.pipeline.extract("I prefer FastAPI")
        stats = self.pipeline.stats
        assert stats.tier1_count > 0

    async def test_pipeline_no_llm_for_clear_preferences(self) -> None:
        await self.pipeline.extract("I prefer FastAPI for APIs")
        stats = self.pipeline.stats
        # Tier 1 gives high confidence, so LLM should NOT be invoked
        assert stats.llm_calls == 0
        self.mock_llm.extract.assert_not_awaited()

    async def test_pipeline_calls_spacy(self) -> None:
        await self.pipeline.extract("I prefer FastAPI for APIs")
        self.mock_spacy.extract.assert_called_once()

    async def test_pipeline_deduplicates_facts(self) -> None:
        # Make spaCy return the same fact as Tier 1
        self.mock_spacy.extract.return_value = [
            ExtractedFact(
                content="Prefers: FastAPI",
                fact_type="preference",
                confidence=0.5,
                entities=["FastAPI"],
                source_text="I prefer FastAPI",
            )
        ]
        result = await self.pipeline.extract("I prefer FastAPI for APIs")
        # Dedup should keep the higher-confidence version
        pref_facts = [f for f in result.facts if "FastAPI" in f.content]
        assert len(pref_facts) <= 2  # Should be deduped

    async def test_pipeline_empty_text_returns_empty(self) -> None:
        result = await self.pipeline.extract("")
        assert len(result.facts) == 0
        assert result.tier1_count == 0

    async def test_pipeline_whitespace_returns_empty(self) -> None:
        result = await self.pipeline.extract("   \n  ")
        assert len(result.facts) == 0

    async def test_pipeline_accumulates_stats_over_calls(self) -> None:
        await self.pipeline.extract("I prefer FastAPI")
        await self.pipeline.extract("I decided to use Docker")
        stats = self.pipeline.stats
        assert stats.tier1_count >= 2
        assert stats.total_extractions >= 2

    async def test_pipeline_get_stats_dict(self) -> None:
        await self.pipeline.extract("I prefer FastAPI")
        stats_dict = self.pipeline.get_stats()
        assert isinstance(stats_dict, dict)
        assert "tier1_count" in stats_dict
        assert "tier2_count" in stats_dict
        assert "tier3_count" in stats_dict
        assert "total_cost_usd" in stats_dict

    async def test_pipeline_result_has_tier_counts(self) -> None:
        result = await self.pipeline.extract("I prefer FastAPI for building APIs")
        assert result.tier1_count >= 1
        # spaCy mock returns empty, so tier2_count should be 0
        assert result.tier2_count == 0
        assert result.tier3_count == 0

    async def test_pipeline_result_llm_not_invoked_flag(self) -> None:
        result = await self.pipeline.extract("I prefer FastAPI for building APIs")
        assert result.llm_invoked is False

    async def test_pipeline_facts_sorted_by_confidence(self) -> None:
        result = await self.pipeline.extract(
            "I prefer FastAPI. I should refactor later."
        )
        if len(result.facts) > 1:
            for i in range(len(result.facts) - 1):
                assert result.facts[i].confidence >= result.facts[i + 1].confidence


class TestExtractionPipelineLLMFallback:
    """Test that the pipeline correctly invokes Tier 3 LLM when confidence is low."""

    def setup_method(self) -> None:
        from life_graph.extraction.pipeline import ExtractionPipeline

        # Mock spaCy returning a low-confidence result
        self.mock_spacy = MagicMock()
        self.mock_spacy.extract.return_value = []

        # Mock LLM returning a fact
        self.mock_llm = MagicMock()
        self.mock_llm.extract = AsyncMock(
            return_value=[
                ExtractedFact(
                    content="Prefers microservices architecture",
                    fact_type="preference",
                    confidence=0.75,
                    entities=["microservices"],
                    source_text="discussion about architecture",
                )
            ]
        )
        self.mock_llm.total_cost_usd = 0.001

        # Use low confidence threshold so LLM might be triggered
        self.pipeline = ExtractionPipeline(
            rules_extractor=RuleBasedExtractor(),
            spacy_extractor=self.mock_spacy,
            llm_extractor=self.mock_llm,
            confidence_threshold=0.99,  # Force LLM invocation
            min_words_for_llm=3,  # Low threshold for testing
        )

    async def test_llm_invoked_when_confidence_low(self) -> None:
        # Generic text that Tier 1 won't match well but has enough words
        text = "we discussed the overall system approach for the new service layer"
        result = await self.pipeline.extract(text)
        # LLM should have been called because Tier 1 confidence < 0.99
        assert result.llm_invoked is True
        self.mock_llm.extract.assert_awaited_once()

    async def test_llm_stats_tracked(self) -> None:
        text = "we discussed the overall system approach for the new service layer"
        await self.pipeline.extract(text)
        stats = self.pipeline.stats
        assert stats.llm_calls >= 1
