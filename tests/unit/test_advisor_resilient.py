"""Advisor opinions route through ResilientLLM instead of calling litellm directly."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.services.multi_model_advisor import MultiModelAdvisor
from life_graph.services.resilient_llm import ResilientLLMExhaustedError


def _make_advisor() -> MultiModelAdvisor:
    # _query_model never touches the session factory, so a dummy is fine.
    return MultiModelAdvisor(session_factory=None, openrouter_api_key="test-key")


@pytest.mark.asyncio
async def test_query_model_uses_resilient_with_diversity(monkeypatch):
    """A successful opinion routes through resilient.acompletion with the opinion's
    model as primary, and forwards the advisor's per-instance api_key/api_base."""
    resp = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"recommendation": "use X", "pros": ["a"], "cons": [], '
                    '"confidence": 0.8, "reasoning": "because"}'
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    resilient = AsyncMock()
    resilient.acompletion = AsyncMock(return_value=resp)
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_resilient_llm", lambda: resilient
    )

    advisor = _make_advisor()
    result = await advisor._query_model(
        "openrouter/deepseek/deepseek-chat", "Should I use Postgres?", []
    )

    resilient.acompletion.assert_awaited_once()
    call_kwargs = resilient.acompletion.call_args.kwargs
    assert call_kwargs["model"] == "openrouter/deepseek/deepseek-chat"
    assert call_kwargs["api_key"] == "test-key"
    assert call_kwargs["api_base"] == advisor._api_base
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert call_kwargs["temperature"] == 0.3
    assert isinstance(call_kwargs["messages"], list)

    assert result.status == "completed"
    assert result.recommendation == "use X"


@pytest.mark.asyncio
async def test_query_model_falls_back_when_resilient_exhausted(monkeypatch):
    """When resilient.acompletion raises ResilientLLMExhaustedError, the advisor degrades
    to its normal fabricated fallback ModelResponse instead of raising."""
    resilient = AsyncMock()
    resilient.acompletion = AsyncMock(side_effect=ResilientLLMExhaustedError("all models down"))
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_resilient_llm", lambda: resilient
    )

    advisor = _make_advisor()
    result = await advisor._query_model(
        "openrouter/openai/gpt-4o-mini", "Should I use Postgres?", []
    )

    resilient.acompletion.assert_awaited_once()
    assert result.status == "timeout"
    assert result.model == "openrouter/openai/gpt-4o-mini"
    assert result.recommendation == ""
    assert result.confidence == 0.0
