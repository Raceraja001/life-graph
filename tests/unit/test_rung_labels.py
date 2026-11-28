"""Labels found on the third live team run: a CLI driver's rung borrowed the persona's
LiteLLM model, and team notes lacked the worker index/author the cockpit reads."""

from __future__ import annotations

from life_graph.config import settings
from life_graph.drivers import escalation


def test_cli_drivers_never_take_the_persona_model():
    for name in ("claude_code", "codex", "gemini", "opencode"):
        assert escalation.run_model(name, "ollama_chat/gpt-oss:20b") is None


def test_litellm_drivers_use_the_persona_model_or_the_local_default():
    assert (
        escalation.run_model("local", "ollama_chat/qwen3-coder:30b")
        == "ollama_chat/qwen3-coder:30b"
    )
    assert escalation.run_model("local", None) == settings.agent_llm_model
    assert escalation.run_model("cloud", "gemini/gemini-3.6-flash") == "gemini/gemini-3.6-flash"
    assert escalation.run_model("cloud", None) is None


def test_a_claude_code_run_stands_on_its_driver_rung():
    ladder = [
        escalation.Rung("local", "ollama_chat/qwen3:14b"),
        escalation.Rung("local", "ollama_chat/qwen3-coder:30b"),
        escalation.Rung("claude_code", None),
    ]
    model = escalation.run_model("claude_code", "ollama_chat/gpt-oss:20b")
    assert escalation.position(ladder, "claude_code", model) == 2
