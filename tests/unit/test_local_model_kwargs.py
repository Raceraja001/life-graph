"""Options that belong only to a locally served model.

Two costs this covers, both measured on qwen3:14b: Ollama evicts a model after
five idle minutes and takes ~4s to load it again, and a thinking model spends
141 tokens reasoning about "hi" before writing 12 of greeting.
"""

import pytest

from life_graph.config import settings
from life_graph.services.resilient_llm import LOCAL_KEEP_ALIVE, _local_model_kwargs


@pytest.mark.parametrize(
    "model",
    ["ollama_chat/qwen3:14b", "ollama/qwen3-coder:30b", "lm_studio/whatever"],
)
def test_a_local_model_is_kept_resident(model):
    assert _local_model_kwargs(model)["keep_alive"] == LOCAL_KEEP_ALIVE


@pytest.mark.parametrize(
    "model",
    [
        "gemini/gemini-3.6-flash",
        "openrouter/deepseek/deepseek-chat",
        # The trap: "openai/" appears INSIDE an OpenRouter id, so matching on it
        # would send a hosted model an option only Ollama understands.
        "openrouter/openai/gpt-oss-20b:free",
        "claude-cli",
    ],
)
def test_a_hosted_model_gets_nothing(model):
    assert _local_model_kwargs(model) == {}


def test_thinking_is_suppressed_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "lm_reasoning_effort", "none")

    extra = _local_model_kwargs("ollama_chat/qwen3:14b")

    # Through extra_body, so an SDK-side enum cannot reject "none".
    assert extra["extra_body"] == {"reasoning_effort": "none"}


def test_nothing_is_sent_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "lm_reasoning_effort", None)

    extra = _local_model_kwargs("ollama_chat/qwen3:14b")

    assert "extra_body" not in extra
    assert extra["keep_alive"] == LOCAL_KEEP_ALIVE
