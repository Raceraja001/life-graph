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


def _user_message(text: str, *, schema_in_prompt: bool) -> str:
    """The extraction request. The schema is pasted in only when the runtime is
    not enforcing it — with constrained decoding it is redundant, and it is
    exactly what small models copy back instead of answering."""
    message = f"Extract facts from the following text:\n\n---\n{text}\n---\n\n"
    if schema_in_prompt:
        return (
            message
            + f"Respond with JSON matching this schema:\n{json.dumps(_EXTRACTION_SCHEMA, indent=2)}"
        )
    return message + 'Respond with JSON only: {"facts": [...]}.'


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
        lm_client: Any = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._lm_client = lm_client

        # Cumulative cost tracking
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.call_count: int = 0

    async def extract(self, text: str) -> list[ExtractedFact]:
        """Call the LLM to extract facts from *text*.

        Uses LM Studio (local) when configured, otherwise falls back
        to LiteLLM (cloud).

        Args:
            text: Raw input text.

        Returns:
            Extracted facts with LLM-assigned confidence.
        """
        from life_graph.config import settings

        if settings.use_local_llm and self._lm_client is not None:
            return await self._extract_local(text)
        return await self._extract_cloud(text)

    async def _local_chat(self, text: str, *, structured: bool) -> str:
        """One local extraction request, constrained (json_schema) or not."""
        from life_graph.config import settings

        response_format: dict[str, Any] = (
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "extracted_facts",
                    "schema": _EXTRACTION_SCHEMA,
                    "strict": True,
                },
            }
            if structured
            else {"type": "json_object"}
        )
        return await self._lm_client.chat(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _user_message(text, schema_in_prompt=not structured)},
            ],
            model=settings.lm_extraction_model,
            temperature=0.1,
            max_tokens=self._max_tokens,
            response_format=response_format,
        )

    async def _extract_local(self, text: str) -> list[ExtractedFact]:
        """Extract facts using a local model (LM Studio / Ollama).

        With ``settings.lm_structured_output`` (the default) the schema is sent
        as a ``json_schema`` response format, so the runtime constrains decoding
        to it. The previous request — ``json_object`` plus the schema pasted into
        the prompt — let small models answer with the *schema itself*: measured
        on qwen3:4b, 2 of 8 extractions were usable, 8 of 8 with constrained
        decoding. Each failure was silent, because an empty result makes the
        pipeline fall back to the regex tier. A runtime that rejects
        ``json_schema`` gets one retry in the old mode.
        """
        from life_graph.config import settings

        raw_content = ""
        try:
            if settings.lm_structured_output:
                raw_content = await self._local_chat(text, structured=True)
                if not raw_content:
                    logger.warning(
                        "Local runtime returned nothing for a json_schema request; "
                        "retrying with json_object (set LIFE_GRAPH_LM_STRUCTURED_OUTPUT=false "
                        "if this runtime does not support structured output)"
                    )
            if not raw_content:
                raw_content = await self._local_chat(text, structured=False)
        except Exception:
            logger.exception("Local LLM extraction failed")
            return []

        self.call_count += 1

        if not raw_content:
            return []

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            logger.warning("Local LLM returned invalid JSON: %.200s", raw_content)
            return []

        # No default: a missing key (the schema-echo case) must not read as an
        # empty-but-valid {"facts": []}, which is a legitimate "nothing to keep".
        raw_facts = data.get("facts") if isinstance(data, dict) else None
        if not isinstance(raw_facts, list):
            # Typically the model echoed the schema back instead of answering.
            # Say so: returning [] here otherwise looks like "nothing to extract".
            logger.warning("Local LLM output has no 'facts' list: %.200s", raw_content)
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
                    source_text=text[:500],
                )
            )

        return facts

    async def _extract_cloud(self, text: str) -> list[ExtractedFact]:
        """Extract facts using cloud LLM via LiteLLM (original path)."""
        from life_graph.api.dependencies import get_resilient_llm

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
            response = await get_resilient_llm().acompletion(
                messages=messages,
                model=self._model,
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
