"""Extraction's cloud path fails over via ResilientLLM instead of hard-failing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import life_graph.extraction.llm as ex
from life_graph.services.llm.resilient import local_only


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
    resilient.local_only = local_only  # the real gate (D25)

    monkeypatch.setattr("life_graph.api.dependencies.get_resilient_llm", lambda: resilient)

    # A local model: since D25 a cloud model here is skipped, never called.
    extractor = ex.LLMExtractor(model="ollama_chat/qwen3:14b")
    facts = await extractor._extract_cloud("some text")

    resilient.acompletion.assert_awaited()
    assert resilient.acompletion.call_args.kwargs["model"] == "ollama_chat/qwen3:14b"
    assert facts == []
