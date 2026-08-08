"""Regression test: agent LLM model defaults must not point at Gemini model
ids blocked for new API keys (gemini-2.5-flash and gemini-2.0-flash both
return 404 as of 2026-08-08, ahead of Google's Oct 16, 2026 shutdown)."""

from __future__ import annotations

from life_graph.agents.orchestrator import AgentOrchestrator
from life_graph.config import Settings


def test_agent_llm_model_default_is_current():
    assert Settings().agent_llm_model == "gemini/gemini-3.6-flash"


def test_agent_fallback_model_default_is_current():
    assert Settings().agent_fallback_model == "gemini/gemini-3.5-flash-lite"


def test_orchestrator_fallback_model_class_default_is_current():
    orch = AgentOrchestrator()
    assert orch.FALLBACK_MODEL == "gemini/gemini-3.5-flash-lite"
