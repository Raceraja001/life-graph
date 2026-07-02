"""Extraction pipeline orchestrator.

Coordinates the three extraction tiers:
  1. Tier 1 — Rule-based regex (always runs, cheapest)
  2. Tier 2 — spaCy NLP (always runs, local model)
  3. Tier 3 — LLM fallback (only when confidence < threshold)

Deduplicates results, tracks per-tier statistics, and returns
a consolidated list sorted by confidence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from life_graph.extraction.llm import LLMExtractor
from life_graph.extraction.nlp import SpacyExtractor
from life_graph.extraction.rules import ExtractedFact, RuleBasedExtractor

logger = logging.getLogger(__name__)

_LLM_CONFIDENCE_THRESHOLD: float = 0.5
_MIN_WORDS_FOR_LLM: int = 20


@dataclass
class PipelineStats:
    """Running statistics for the extraction pipeline."""

    tier1_count: int = 0
    tier2_count: int = 0
    tier3_count: int = 0
    total_extractions: int = 0
    total_cost_usd: float = 0.0
    llm_calls: int = 0

    def as_dict(self) -> dict[str, Any]:
        """Serialise stats for logging or API responses."""
        return {
            "tier1_count": self.tier1_count,
            "tier2_count": self.tier2_count,
            "tier3_count": self.tier3_count,
            "total_extractions": self.total_extractions,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "llm_calls": self.llm_calls,
        }


@dataclass
class ExtractionResult:
    """Container for pipeline output."""

    facts: list[ExtractedFact] = field(default_factory=list)
    tier1_count: int = 0
    tier2_count: int = 0
    tier3_count: int = 0
    llm_invoked: bool = False


class ExtractionPipeline:
    """Orchestrates multi-tier fact extraction.

    Args:
        rules_extractor: Tier 1 regex extractor.
        spacy_extractor: Tier 2 spaCy NLP extractor.
        llm_extractor: Tier 3 LLM fallback extractor.
        confidence_threshold: Max-confidence below which Tier 3 is invoked.
        min_words_for_llm: Minimum word count before considering LLM.
    """

    def __init__(
        self,
        rules_extractor: RuleBasedExtractor | None = None,
        spacy_extractor: SpacyExtractor | None = None,
        llm_extractor: LLMExtractor | None = None,
        *,
        confidence_threshold: float = _LLM_CONFIDENCE_THRESHOLD,
        min_words_for_llm: int = _MIN_WORDS_FOR_LLM,
    ) -> None:
        self._rules = rules_extractor or RuleBasedExtractor()
        self._spacy = spacy_extractor or SpacyExtractor()
        self._llm = llm_extractor or LLMExtractor()
        self._confidence_threshold = confidence_threshold
        self._min_words_for_llm = min_words_for_llm
        self.stats = PipelineStats()

    async def extract(self, text: str) -> ExtractionResult:
        """Run the full extraction pipeline on *text*.

        Steps:
            1. Always run Tier 1 (rules).
            2. Always run Tier 2 (spaCy).
            3. Merge and deduplicate.
            4. If max confidence < threshold and text is long enough,
               invoke Tier 3 (LLM).
            5. Return consolidated results sorted by confidence.

        Args:
            text: Raw input text to extract facts from.

        Returns:
            ExtractionResult with deduplicated facts and tier counts.
        """
        text = text.strip()
        if not text:
            return ExtractionResult()

        # Tier 1 — regex
        tier1_facts = self._rules.extract(text)
        logger.debug("Tier 1 extracted %d facts", len(tier1_facts))

        # Tier 2 — spaCy
        tier2_facts = self._spacy.extract(text)
        logger.debug("Tier 2 extracted %d facts", len(tier2_facts))

        # Merge and deduplicate (Tier 1 + 2)
        merged = _deduplicate(tier1_facts + tier2_facts)

        # Determine if Tier 3 is needed
        max_confidence = max((f.confidence for f in merged), default=0.0)
        word_count = len(text.split())
        llm_invoked = False
        tier3_facts: list[ExtractedFact] = []

        if max_confidence < self._confidence_threshold and word_count >= self._min_words_for_llm:
            logger.info(
                "Max confidence %.2f < %.2f — invoking Tier 3 LLM (%d words)",
                max_confidence,
                self._confidence_threshold,
                word_count,
            )
            tier3_facts = await self._llm.extract(text)
            llm_invoked = True
            logger.debug("Tier 3 extracted %d facts", len(tier3_facts))
            merged = _deduplicate(merged + tier3_facts)

        # Sort by confidence descending
        merged.sort(key=lambda f: f.confidence, reverse=True)

        # Update running stats
        result = ExtractionResult(
            facts=merged,
            tier1_count=len(tier1_facts),
            tier2_count=len(tier2_facts),
            tier3_count=len(tier3_facts),
            llm_invoked=llm_invoked,
        )
        self._update_stats(result)

        return result

    def _update_stats(self, result: ExtractionResult) -> None:
        """Accumulate pipeline statistics."""
        self.stats.tier1_count += result.tier1_count
        self.stats.tier2_count += result.tier2_count
        self.stats.tier3_count += result.tier3_count
        self.stats.total_extractions += len(result.facts)
        if result.llm_invoked:
            self.stats.llm_calls += 1
            self.stats.total_cost_usd = self._llm.total_cost_usd

    def get_stats(self) -> dict[str, Any]:
        """Return cumulative pipeline statistics."""
        return self.stats.as_dict()

    def get_llm_cost_summary(self) -> dict[str, Any]:
        """Return detailed LLM cost breakdown."""
        return self._llm.get_cost_summary()


def _deduplicate(facts: list[ExtractedFact]) -> list[ExtractedFact]:
    """Remove duplicate facts, keeping the highest-confidence version.

    Two facts are considered duplicates when their normalised content
    strings match.  When a duplicate is found, the version with higher
    confidence wins.  If confidence is equal, the first occurrence wins.
    """
    best: dict[str, ExtractedFact] = {}

    for fact in facts:
        key = _normalise_key(fact.content)
        existing = best.get(key)
        if existing is None or fact.confidence > existing.confidence:
            best[key] = fact

    return list(best.values())


def _normalise_key(content: str) -> str:
    """Create a stable dedup key from content."""
    return content.strip().lower()
