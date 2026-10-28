# tests for local_model in services.lead

# Import the function under test
# Helper to patch settings temporarily
from life_graph.config import settings
from life_graph.services.lead import local_model

# Monkeypatch settings attributes


def set_setting(attr, value):
    original = getattr(settings, attr)
    setattr(settings, attr, value)
    return original


# Test when lead_local_model is set


def test_local_model_prefers_lead_local_model(monkeypatch):
    # Ensure lead_local_model is set
    monkeypatch.setattr(settings, "lead_local_model", "my_local_model")
    # Also make agent_llm_model local to see that lead_local_model takes precedence
    monkeypatch.setattr(settings, "agent_llm_model", "ollama_chat/qwen3:14b")
    assert local_model() == "my_local_model"


# Test when lead_local_model empty and agent_llm_model is local


def test_local_model_uses_agent_llm_model_when_local(monkeypatch):
    monkeypatch.setattr(settings, "lead_local_model", "")
    # set agent_llm_model to a local prefix
    monkeypatch.setattr(settings, "agent_llm_model", "ollama_chat/qwen3:14b")
    assert local_model() == "ollama_chat/qwen3:14b"


# Test fallback when neither is local


def test_local_model_fallback(monkeypatch):
    monkeypatch.setattr(settings, "lead_local_model", "")
    # set agent_llm_model to a non-local prefix
    monkeypatch.setattr(settings, "agent_llm_model", "gemini/gemini-3.6-flash")
    assert local_model() == "ollama_chat/qwen3:14b"


# Edge case: settings lead_local_model set to empty string and agent_llm_model None


def test_local_model_none_agent(monkeypatch):
    monkeypatch.setattr(settings, "lead_local_model", "")
    monkeypatch.setattr(settings, "agent_llm_model", None)
    assert local_model() == "ollama_chat/qwen3:14b"
