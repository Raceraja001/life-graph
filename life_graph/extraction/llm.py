"""Tier 3: LLM-based fact extraction via LiteLLM.

Only invoked when Tier 1 + Tier 2 confidence is below threshold.
Uses structured JSON output to extract facts, tracks token costs.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from life_graph.extraction.rules import ExtractedFact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON schema the LLM must follow
# ---------------------------------------------------------------------------

_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Concise statement of the extracted fact.",
                    },
                    "fact_type": {
                        "type": "string",
                        "enum": [
                            "preference",
                            "anti_preference",
                            "decision",
                            "explicit_save",
                            "intention",
                            "fact",
                        ],
                        "description": "Category of the fact.",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence 0.0-1.0 that this is a genuine fact.",
                    },
                    "entities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key entities or subjects mentioned.",
                    },
                },
                "required": ["content", "fact_type", "confidence", "entities"],
            },
        }
    },
    "required": ["facts"],
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a fact-extraction engine for a personal memory system.
Given a block of text from a developer conversation, extract ALL
meaningful facts that are worth remembering long-term.

Categories:
- preference: Things the user prefers or favours.
- anti_preference: Things the user dislikes or avoids.
- decision: Choices or decisions the user has made.
- explicit_save: Information the user explicitly asked to remember.
- intention: Things the user plans or wants to do later.
- fact: Objective facts, relationships, or technical details.

Rules:
1. Be precise — only extract genuine, specific facts.
2. Ignore filler, greetings, and generic statements.
3. Each fact should be a single, self-contained statement.
4. Confidence should reflect how clearly the text conveys the fact.
5. Return valid JSON matching the provided schema.
"""


class LLMExtractor:
    """Tier 3 extractor using LLM via LiteLLM.

    Only called when lower tiers produce insufficient confidence.
    Tracks cumulative cost for budget enforcement.

    Args:
        model: LiteLLM model identifier (e.g. ``gemini/gemini-2.0-flash``).
        max_tokens: Maximum response tokens.
    """

    def __init__(
        self,
        model: str = "gemini/gemini-2.0-flash",
        max_tokens: int = 1024,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens

        # Cumulative cost tracking
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.call_count: int = 0

    async def extract(self, text: str) -> list[ExtractedFact]:
        """Call the LLM to extract facts from *text*.

        Args:
            text: Raw input text.

        Returns:
            Extracted facts with LLM-assigned confidence.
        """
        import litellm

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Extract facts from the following text:\n\n"
                    f"---\n{text}\n---\n\n"
                    f"Respond with JSON matching this schema:\n"
                    f"{json.dumps(_EXTRACTION_SCHEMA, indent=2)}"
                ),
            },
        ]

        try:
            response = await litellm.acompletion(
                model=self._model,
                messages=messages,
                max_tokens=self._max_tokens,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except Exception:
            logger.exception("LLM extraction call failed for model '%s'", self._model)
            return []

        # Track costs
        self.call_count += 1
        usage = getattr(response, "usage", None)
        if usage:
            self.total_prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.total_completion_tokens += getattr(usage, "completion_tokens", 0) or 0

        cost = getattr(response, "_hidden_params", {}).get("response_cost", 0.0)
        if cost:
            self.total_cost_usd += float(cost)

        return self._parse_response(response, text)

    @staticmethod
    def _parse_response(response: Any, source_text: str) -> list[ExtractedFact]:
        """Parse the LLM JSON response into ExtractedFact objects."""
        raw_content = response.choices[0].message.content
        if not raw_content:
            return []

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON: %.200s", raw_content)
            return []

        raw_facts = data.get("facts", [])
        if not isinstance(raw_facts, list):
            return []

        facts: list[ExtractedFact] = []
        for item in raw_facts:
            if not isinstance(item, dict):
                continue
            content = item.get("content", "").strip()
            if not content:
                continue

            fact_type = item.get("fact_type", "fact")
            confidence = _clamp(float(item.get("confidence", 0.5)), 0.0, 1.0)
            entities = item.get("entities", [])
            if not isinstance(entities, list):
                entities = []
            entities = [str(e) for e in entities if e]

            facts.append(
                ExtractedFact(
                    content=content,
                    fact_type=fact_type,
                    confidence=confidence,
                    entities=entities,
                    source_text=source_text[:500],
                )
            )

        return facts

    def get_cost_summary(self) -> dict[str, Any]:
        """Return a summary of LLM usage and costs."""
        return {
            "model": self._model,
            "call_count": self.call_count,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
        }


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp *value* between *lo* and *hi*."""
    return max(lo, min(hi, value))
