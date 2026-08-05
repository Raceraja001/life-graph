# tests/unit/test_transcript_extract.py
"""Unit tests for the conversation-aware transcript extractor (LLM mocked)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.extraction.transcript_extract import _chunk, extract_transcript_facts


def _t(role, text):
    return {"role": role, "text": text, "ts": None}


@pytest.mark.asyncio
async def test_extracts_categorized_facts():
    llm = MagicMock()
    llm.chat = AsyncMock(
        return_value=json.dumps(
            {
                "facts": [
                    {"content": "User prefers OpenRouter free models.", "category": "preference"},
                    {"content": "Client wants TPV in Cashfree and Razorpay.", "category": "fact"},
                ]
            }
        )
    )
    turns = [_t("assistant", "which models?"), _t("user", "use openrouter free models")]
    facts = await extract_transcript_facts(turns, resilient_llm=llm)
    assert [f.content for f in facts] == [
        "User prefers OpenRouter free models.",
        "Client wants TPV in Cashfree and Razorpay.",
    ]
    assert facts[0].fact_type == "preference"
    assert facts[1].fact_type == "fact"


@pytest.mark.asyncio
async def test_all_assistant_chunk_makes_no_llm_call():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=json.dumps({"facts": []}))
    facts = await extract_transcript_facts([_t("assistant", "context only")], resilient_llm=llm)
    assert facts == []
    llm.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_chunk_failure_is_swallowed():
    llm = MagicMock()
    llm.chat = AsyncMock(side_effect=RuntimeError("all models exhausted"))
    facts = await extract_transcript_facts([_t("user", "hi")], resilient_llm=llm)
    assert facts == []  # no crash


@pytest.mark.asyncio
async def test_malformed_json_yields_no_facts():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value="not json at all")
    facts = await extract_transcript_facts([_t("user", "hi")], resilient_llm=llm)
    assert facts == []


def test_chunk_packs_to_budget_with_overlap():
    turns = [_t("user", "x" * 40) for _ in range(10)]
    chunks = _chunk(turns, max_chars=100, overlap=1)
    assert len(chunks) > 1
    # consecutive chunks share the 1-turn overlap (last of chunk N == first of N+1)
    assert chunks[0][-1] == chunks[1][0]
