# life_graph/extraction/transcript_extract.py
"""Conversation-aware fact extraction for external AI-tool transcripts.

Replaces the note-tuned rules/spaCy tiers for transcripts: chunks the cleaned
dialogue and makes one free-model LLM call per chunk to emit categorized,
standalone facts in the user's voice — decisions, preferences, project/domain
facts, and open tasks — while excluding code and AI-process meta.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from life_graph.extraction.rules import ExtractedFact

if TYPE_CHECKING:
    from life_graph.extraction.transcript_parsers.base import Turn

logger = logging.getLogger(__name__)

_MAX_CHARS = 10_000
_OVERLAP = 2

# LLM "category" -> existing ExtractedFact.fact_type value.
_CATEGORY_TO_FACT_TYPE = {
    "decision": "decision",
    "preference": "preference",
    "fact": "fact",
    "task": "intention",
}

_SYSTEM_PROMPT = """You extract durable personal-knowledge facts from a developer's \
conversation with an AI coding assistant.
The user's turns are labelled `USER:`; assistant turns (`ASSISTANT:`) are context \
only — never extract facts from them.
Emit ONLY things worth remembering long-term, in the user's voice:
1. decisions the user made
2. preferences they expressed
3. concrete project or domain facts
4. open tasks / TODOs they raised
Do NOT emit: code, commands, file paths, shell output, error text, or anything about \
the AI-assistant process itself (skills, plans, reviews, tool mechanics).
Each fact is one standalone sentence understandable without the conversation.
Respond with JSON: {"facts": [{"content": "...", "category": "decision|preference|fact|task"}]}.
If there is nothing durable, return {"facts": []}."""


def _line(turn: Turn) -> str:
    return f"{turn['role'].upper()}: {turn['text']}"


def _chunk(
    turns: list[Turn], max_chars: int = _MAX_CHARS, overlap: int = _OVERLAP
) -> list[list[Turn]]:
    """Greedily pack turns into ~max_chars windows, carrying `overlap` trailing turns forward."""
    chunks: list[list[Turn]] = []
    cur: list[Turn] = []
    size = 0
    for t in turns:
        length = len(_line(t))
        if cur and size + length > max_chars:
            chunks.append(cur)
            cur = cur[-overlap:] if overlap else []
            size = sum(len(_line(x)) for x in cur)
        cur.append(t)
        size += length
    if cur:
        chunks.append(cur)
    return chunks


def _parse_facts(raw: str) -> list[ExtractedFact]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    out: list[ExtractedFact] = []
    for item in data.get("facts", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        category = str(item.get("category", "fact")).lower()
        out.append(
            ExtractedFact(
                content=content,
                fact_type=_CATEGORY_TO_FACT_TYPE.get(category, "fact"),
                confidence=0.7,
                entities=[],
                source_text=content,
            )
        )
    return out


async def extract_transcript_facts(turns: list[Turn], *, resilient_llm) -> list[ExtractedFact]:
    """Extract categorized facts from a cleaned dialogue via the free-model LLM."""
    facts: list[ExtractedFact] = []
    for chunk in _chunk(turns):
        if not any(t["role"] == "user" for t in chunk):
            continue  # context-only window — nothing to extract, skip the call
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(_line(t) for t in chunk)},
        ]
        try:
            raw = await resilient_llm.chat(
                messages,
                tier="cheap",
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
        except Exception:  # noqa: BLE001 - a failed chunk must not sink the session
            logger.warning("Transcript extraction chunk failed", exc_info=True)
            continue
        facts.extend(_parse_facts(raw))
    return facts
