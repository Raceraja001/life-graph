"""Tier 1: Rule-based fact extraction using regex patterns.

Highest confidence tier — regex matches are precise and cheap.
No LLM or model calls needed. Runs on every input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ExtractedFact:
    """A single fact extracted from text by any extraction tier."""

    content: str
    fact_type: str
    confidence: float
    entities: list[str] = field(default_factory=list)
    source_text: str = ""


# ---------------------------------------------------------------------------
# Pattern definitions
# Each tuple: (compiled_regex, fact_type, base_confidence)
# Group 1 in each pattern captures the key entity/phrase.
# ---------------------------------------------------------------------------

_PREFERENCE_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\bi\s+prefer\s+(.+?)(?:\s+(?:over|to|instead)\b|[.,;!?\n]|$)", re.IGNORECASE), "preference", 0.90),
    (re.compile(r"\bi\s+always\s+use\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "preference", 0.90),
    (re.compile(r"\bi\s+like\s+(.+?)\s+better\b", re.IGNORECASE), "preference", 0.85),
    (re.compile(r"\bmy\s+go[- ]?to\s+is\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "preference", 0.90),
    (re.compile(r"\bi\s+(?:really\s+)?love\s+(?:using\s+)?(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "preference", 0.80),
    (re.compile(r"\bi\s+(?:mostly|usually|typically)\s+use\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "preference", 0.85),
    (re.compile(r"\bi\s+(?:swear\s+by|stick\s+with)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "preference", 0.85),
]

_ANTI_PREFERENCE_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\bi\s+(?:don'?t|do\s+not)\s+like\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "anti_preference", 0.90),
    (re.compile(r"\bi\s+avoid\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "anti_preference", 0.90),
    (re.compile(r"\bnever\s+use\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "anti_preference", 0.90),
    (re.compile(r"\bi\s+hate\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "anti_preference", 0.90),
    (re.compile(r"\bi\s+(?:can'?t\s+stand|dislike|despise)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "anti_preference", 0.85),
    (re.compile(r"\bi\s+stay\s+away\s+from\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "anti_preference", 0.85),
    (re.compile(r"\bi\s+stopped\s+using\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "anti_preference", 0.80),
]

_DECISION_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\bi\s+decided\s+to\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "decision", 0.95),
    (re.compile(r"\bi\s+chose\s+(.+?)(?:\s+(?:over|instead)\b|[.,;!?\n]|$)", re.IGNORECASE), "decision", 0.90),
    (re.compile(r"\bi\s+went\s+with\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "decision", 0.90),
    (re.compile(r"\bi\s+switched\s+to\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "decision", 0.90),
    (re.compile(r"\bi\s+(?:picked|selected)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "decision", 0.85),
    (re.compile(r"\bi\s+(?:ended\s+up|settled\s+on)\s+(?:using\s+|with\s+)?(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "decision", 0.85),
    (re.compile(r"\bwe(?:'re|\s+are)\s+going\s+with\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "decision", 0.85),
]

_EXPLICIT_SAVE_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\bremember\s+(?:this|that)\s*[:\-]?\s*(.+?)(?:[.!?\n]|$)", re.IGNORECASE), "explicit_save", 0.95),
    (re.compile(r"\bsave\s+(?:this|that)\s*[:\-]?\s*(.+?)(?:[.!?\n]|$)", re.IGNORECASE), "explicit_save", 0.95),
    (re.compile(r"\bnote\s+that\s+(.+?)(?:[.!?\n]|$)", re.IGNORECASE), "explicit_save", 0.90),
    (re.compile(r"\bimportant\s*:\s*(.+?)(?:[.!?\n]|$)", re.IGNORECASE), "explicit_save", 0.95),
    (re.compile(r"\bdon'?t\s+forget\s*[:\-]?\s*(.+?)(?:[.!?\n]|$)", re.IGNORECASE), "explicit_save", 0.90),
    (re.compile(r"\bkeep\s+in\s+mind\s*[:\-]?\s*(.+?)(?:[.!?\n]|$)", re.IGNORECASE), "explicit_save", 0.85),
]

_INTENTION_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\bi\s+should\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "intention", 0.80),
    (re.compile(r"\bi\s+will\s+(.+?)\s+later\b", re.IGNORECASE), "intention", 0.85),
    (re.compile(r"\bi\s+need\s+to\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "intention", 0.80),
    (re.compile(r"\bremind\s+me\s+to\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "intention", 0.90),
    (re.compile(r"\bTODO\s*:\s*(.+?)(?:\n|$)"), "intention", 0.95),
    (re.compile(r"\bFIXME\s*:\s*(.+?)(?:\n|$)"), "intention", 0.95),
    (re.compile(r"\bi\s+(?:plan|want|intend)\s+to\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "intention", 0.80),
    (re.compile(r"\bi'?ll\s+(?:get\s+to|work\s+on|look\s+into)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "intention", 0.75),
]

_FACT_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\b(\w[\w\s]{0,30}?)\s+(?:is|are)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "fact", 0.60),
    (re.compile(r"\b(\w[\w\s]{0,30}?)\s+uses?\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "fact", 0.65),
    (re.compile(r"\b(\w[\w\s]{0,30}?)\s+depends?\s+on\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "fact", 0.70),
    (re.compile(r"\b(\w[\w\s]{0,30}?)\s+requires?\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "fact", 0.70),
    (re.compile(r"\b(\w[\w\s]{0,30}?)\s+supports?\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE), "fact", 0.65),
]

# All pattern groups in priority order
_ALL_PATTERN_GROUPS: list[list[tuple[re.Pattern[str], str, float]]] = [
    _EXPLICIT_SAVE_PATTERNS,
    _DECISION_PATTERNS,
    _PREFERENCE_PATTERNS,
    _ANTI_PREFERENCE_PATTERNS,
    _INTENTION_PATTERNS,
    _FACT_PATTERNS,
]


def _clean_entity(raw: str) -> str:
    """Strip trailing whitespace and common punctuation from an extracted entity."""
    return raw.strip().rstrip(".,;:!?")


class RuleBasedExtractor:
    """Tier 1 extractor using compiled regex patterns.

    Fast, deterministic, zero-cost extraction. Matches carry high
    confidence because the patterns are specific.
    """

    def extract(self, text: str) -> list[ExtractedFact]:
        """Extract facts from *text* using regex pattern matching.

        Args:
            text: Raw input text to scan.

        Returns:
            Extracted facts sorted by confidence descending.
        """
        facts: list[ExtractedFact] = []
        seen_spans: set[tuple[int, int]] = set()

        for pattern_group in _ALL_PATTERN_GROUPS:
            for pattern, fact_type, confidence in pattern_group:
                for match in pattern.finditer(text):
                    span = match.span()
                    # Avoid overlapping matches — first pattern group wins
                    if any(s[0] <= span[0] < s[1] or s[0] < span[1] <= s[1] for s in seen_spans):
                        continue
                    seen_spans.add(span)

                    groups = match.groups()
                    entities = [_clean_entity(g) for g in groups if g]
                    content = self._build_content(fact_type, entities, match.group(0))

                    facts.append(
                        ExtractedFact(
                            content=content,
                            fact_type=fact_type,
                            confidence=confidence,
                            entities=entities,
                            source_text=match.group(0).strip(),
                        )
                    )

        facts.sort(key=lambda f: f.confidence, reverse=True)
        return facts

    @staticmethod
    def _build_content(fact_type: str, entities: list[str], raw_match: str) -> str:
        """Construct a normalised content string from the match.

        For most types the first entity is the key subject. For facts
        with two groups (X is Y) we join them.
        """
        if not entities:
            return raw_match.strip()

        if fact_type == "fact" and len(entities) >= 2:
            return f"{entities[0]} → {entities[1]}"

        if fact_type == "preference":
            return f"Prefers: {entities[0]}"

        if fact_type == "anti_preference":
            return f"Avoids: {entities[0]}"

        if fact_type == "decision":
            return f"Decided: {entities[0]}"

        if fact_type == "explicit_save":
            return f"Saved: {entities[0]}"

        if fact_type == "intention":
            return f"TODO: {entities[0]}"

        return entities[0]
