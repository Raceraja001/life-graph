# tests/unit/test_claude_code_parser.py
"""Unit tests for the Claude Code JSONL transcript parser."""

from __future__ import annotations

from pathlib import Path

from life_graph.extraction.transcript_parsers import PARSERS
from life_graph.extraction.transcript_parsers.claude_code import ClaudeCodeParser

FIXTURE = Path(__file__).parent.parent / "fixtures" / "claude_code_sample.jsonl"


def _lines() -> list[str]:
    return FIXTURE.read_text(encoding="utf-8").splitlines()


def test_registered_under_claude_code_key():
    assert isinstance(PARSERS["claude-code"], ClaudeCodeParser)
    assert PARSERS["claude-code"].tool == "claude-code"


def test_extracts_only_genuine_user_prompt():
    turns = ClaudeCodeParser().parse(_lines())
    assert len(turns) == 1
    assert turns[0]["role"] == "user"
    assert "OpenRouter" in turns[0]["text"]
    assert turns[0]["ts"] == "2026-08-01T10:00:00Z"


def test_drops_tool_results_sidechains_reminders_assistant_and_attachments():
    texts = [t["text"] for t in ClaudeCodeParser().parse(_lines())]
    joined = "\n".join(texts)
    assert "file contents here" not in joined  # tool_result dropped
    assert "subagent side thread" not in joined  # isSidechain dropped
    assert "ambient context" not in joined  # system-reminder-only dropped
    assert "Got it" not in joined  # assistant dropped


def test_ignores_malformed_lines():
    turns = ClaudeCodeParser().parse(["not json", "", '{"type":"user"}'])
    assert turns == []
