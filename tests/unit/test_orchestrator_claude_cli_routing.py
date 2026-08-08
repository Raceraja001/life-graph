import json

import pytest

from life_graph.agents.orchestrator import AgentOrchestrator
from life_graph.services.claude_cli_reply import ClaudeCliResult


@pytest.mark.asyncio
async def test_claude_cli_model_yields_token_usage_done_only(monkeypatch):
    async def _fake_run_claude_cli(prompt, timeout=60.0):
        return ClaudeCliResult(success=True, text="hi there", error=None, duration_ms=42)

    monkeypatch.setattr(
        "life_graph.agents.orchestrator.run_claude_cli", _fake_run_claude_cli
    )

    orchestrator = AgentOrchestrator(model="claude-cli")
    events = []
    async for chunk in orchestrator.run(messages=[{"role": "user", "content": "hi"}]):
        events.append(json.loads(chunk.removeprefix("data: ").strip()))

    types = [e["type"] for e in events]
    assert types == ["token", "usage", "done"]
    assert events[0]["content"] == "hi there"


@pytest.mark.asyncio
async def test_claude_cli_model_never_calls_resilient_llm(monkeypatch):
    called = {"count": 0}

    def _fake_get_resilient_llm():
        called["count"] += 1
        raise AssertionError("get_resilient_llm should never be called for claude-cli")

    monkeypatch.setattr(
        "life_graph.api.dependencies.get_resilient_llm", _fake_get_resilient_llm
    )

    async def _fake_run_claude_cli(prompt, timeout=60.0):
        return ClaudeCliResult(success=True, text="ok", error=None, duration_ms=1)

    monkeypatch.setattr(
        "life_graph.agents.orchestrator.run_claude_cli", _fake_run_claude_cli
    )

    orchestrator = AgentOrchestrator(model="claude-cli")
    async for _ in orchestrator.run(messages=[{"role": "user", "content": "hi"}]):
        pass

    assert called["count"] == 0


@pytest.mark.asyncio
async def test_claude_cli_failure_yields_partial_error_then_done(monkeypatch):
    async def _fake_run_claude_cli(prompt, timeout=60.0):
        return ClaudeCliResult(success=False, text="", error="claude not found", duration_ms=5)

    monkeypatch.setattr(
        "life_graph.agents.orchestrator.run_claude_cli", _fake_run_claude_cli
    )

    orchestrator = AgentOrchestrator(model="claude-cli")
    events = []
    async for chunk in orchestrator.run(messages=[{"role": "user", "content": "hi"}]):
        events.append(json.loads(chunk.removeprefix("data: ").strip()))

    # Matches the existing ResilientLLMExhausted failure shape exactly
    # (orchestrator.py:297-304): a "partial_error" event with a "message"
    # key, always followed by a terminal "done" — not a bare "error" event.
    types = [e["type"] for e in events]
    assert types == ["partial_error", "done"]
    assert "claude not found" in events[0]["message"]
    assert events[0]["retryable"] is True


@pytest.mark.asyncio
async def test_claude_cli_malformed_message_yields_partial_error_then_done(monkeypatch):
    # A message missing "role" makes the prompt-flattening line raise a bare
    # KeyError (unlike "content", "role" is still accessed via msg['role'] —
    # see test_claude_cli_missing_content_renders_as_empty_not_literal_none
    # for why "content" specifically is now tolerated). This asserts the
    # branch's try/except catches that (and anything else unexpected in the
    # flattening/dispatch step) and reports it through the same graceful
    # partial_error -> done shape as a run_claude_cli() failure, instead of
    # letting the KeyError propagate unhandled out of the async generator.
    async def _fake_run_claude_cli(prompt, timeout=60.0):
        raise AssertionError("run_claude_cli should never be reached for a malformed message")

    monkeypatch.setattr(
        "life_graph.agents.orchestrator.run_claude_cli", _fake_run_claude_cli
    )

    orchestrator = AgentOrchestrator(model="claude-cli")
    events = []
    async for chunk in orchestrator.run(messages=[{"content": "hi"}]):
        events.append(json.loads(chunk.removeprefix("data: ").strip()))

    types = [e["type"] for e in events]
    assert types == ["partial_error", "done"]
    assert "role" in events[0]["message"]
    assert events[0]["retryable"] is True


@pytest.mark.asyncio
async def test_claude_cli_missing_content_renders_as_empty_not_literal_none(monkeypatch):
    # A prior assistant message with content=None (a tool-call turn) must
    # flatten to an empty string, not the literal text "None" — likewise a
    # message missing "content" entirely. Both are tolerated (no exception)
    # and the call proceeds normally.
    captured = {}

    async def _fake_run_claude_cli(prompt, timeout=60.0):
        captured["prompt"] = prompt
        return ClaudeCliResult(success=True, text="ok", error=None, duration_ms=1)

    monkeypatch.setattr(
        "life_graph.agents.orchestrator.run_claude_cli", _fake_run_claude_cli
    )

    orchestrator = AgentOrchestrator(model="claude-cli")
    events = []
    async for chunk in orchestrator.run(
        messages=[
            {"role": "assistant", "content": None},
            {"role": "user"},
            {"role": "user", "content": "hi"},
        ]
    ):
        events.append(json.loads(chunk.removeprefix("data: ").strip()))

    assert events[-1]["type"] == "done"
    assert "None" not in captured["prompt"]
    assert "assistant: \n" in captured["prompt"] or captured["prompt"].startswith("assistant: \n")
