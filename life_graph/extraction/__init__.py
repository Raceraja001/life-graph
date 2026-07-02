"""Life Graph extraction pipeline — public API.

Exports the core classes for multi-tier fact extraction:
  - ExtractionPipeline: orchestrator
  - RuleBasedExtractor: Tier 1 regex
  - SpacyExtractor: Tier 2 NLP
  - LLMExtractor: Tier 3 LLM fallback
  - ExtractedFact: common result dataclass
"""

from life_graph.extraction.llm import LLMExtractor
from life_graph.extraction.nlp import SpacyExtractor
from life_graph.extraction.pipeline import ExtractionPipeline, ExtractionResult
from life_graph.extraction.rules import ExtractedFact, RuleBasedExtractor

__all__ = [
    "ExtractionPipeline",
    "ExtractionResult",
    "RuleBasedExtractor",
    "SpacyExtractor",
    "LLMExtractor",
    "ExtractedFact",
]
