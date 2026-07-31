"""Extraction's cloud path fails over via ResilientLLM instead of hard-failing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import life_graph.extraction.llm as ex


@pytest.mark.asyncio
async def test_extract_cloud_uses_resilient(monkeypatch):
    # A response whose JSON content yields zero facts is fine; we assert the
    # resilient wrapper is what gets called (not litellm directly).
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"facts": []}'))],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        _hidden_params={},
    )
    resilient = AsyncMock()
    resilient.acompletion = AsyncMock(return_value=resp)

    monkeypatch.setattr(
        "life_graph.api.dependencies.get_resilient_llm", lambda: resilient
    )

    extractor = ex.LLMExtractor(model="gemini/gemini-2.0-flash")
    facts = await extractor._extract_cloud("some text")

    resilient.acompletion.assert_awaited()
    assert resilient.acompletion.call_args.kwargs["model"] == "gemini/gemini-2.0-flash"
    assert facts == []
