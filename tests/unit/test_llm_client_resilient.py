"""LMStudioClient cloud path now delegates to ResilientLLM."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import life_graph.services.llm_client as lc
from life_graph.services.llm_client import LMStudioClient
from life_graph.services.resilient_llm import ResilientLLMExhausted


@pytest.mark.asyncio
async def test_cloud_chat_uses_resilient(monkeypatch):
    monkeypatch.setattr(lc.settings, "use_hybrid_llm", True, raising=False)
    monkeypatch.setattr(lc.settings, "openrouter_api_key", "k", raising=False)
    resilient = AsyncMock()
    resilient.chat = AsyncMock(return_value="cloud-answer")
    monkeypatch.setattr(lc, "get_resilient_llm", lambda: resilient)
    out = await LMStudioClient().chat([{"role": "user", "content": "q"}])
    assert out == "cloud-answer"
    resilient.chat.assert_awaited()


@pytest.mark.asyncio
async def test_falls_back_to_local_on_exhaustion(monkeypatch):
    monkeypatch.setattr(lc.settings, "use_hybrid_llm", True, raising=False)
    monkeypatch.setattr(lc.settings, "openrouter_api_key", "k", raising=False)
    resilient = AsyncMock()
    resilient.chat = AsyncMock(side_effect=ResilientLLMExhausted("x"))
    monkeypatch.setattr(lc, "get_resilient_llm", lambda: resilient)
    client = LMStudioClient()
    client._local_chat = AsyncMock(return_value="local-answer")  # type: ignore[method-assign]
    out = await client.chat([{"role": "user", "content": "q"}])
    assert out == "local-answer"
