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


def test_extracts_the_genuine_user_prompt():
    user_turns = [t for t in ClaudeCodeParser().parse(_lines()) if t["role"] == "user"]
    assert len(user_turns) == 1
    assert "OpenRouter" in user_turns[0]["text"]
    assert user_turns[0]["ts"] == "2026-08-01T10:00:00Z"


def test_drops_tool_results_sidechains_reminders_and_attachments():
    texts = [t["text"] for t in ClaudeCodeParser().parse(_lines())]
    joined = "\n".join(texts)
    assert "file contents here" not in joined  # tool_result dropped
    assert "subagent side thread" not in joined  # isSidechain dropped
    assert "ambient context" not in joined  # system-reminder span stripped
    # Assistant turns are now KEPT as short context gists (not dropped).
    assert any("Got it" in t for t in texts)


def test_ignores_malformed_lines():
    turns = ClaudeCodeParser().parse(["not json", "", '{"type":"user"}'])
    assert turns == []


def test_strips_appended_system_reminder_but_keeps_prompt():
    line = (
        '{"type":"user","userType":"external","isSidechain":false,'
        '"message":{"role":"user","content":"Use OpenRouter free models.'
        '\\n<system-reminder>ambient context here</system-reminder>"}}'
    )
    turns = ClaudeCodeParser().parse([line])
    assert len(turns) == 1
    assert "OpenRouter free models" in turns[0]["text"]
    assert "ambient context" not in turns[0]["text"]


def test_drops_skill_body_turn():
    line = (
        '{"type":"user","userType":"external","isSidechain":false,'
        '"message":{"role":"user","content":"Base directory for this skill: '
        '/x/y\\n# Some Skill\\ninstructions..."}}'
    )
    assert ClaudeCodeParser().parse([line]) == []


def test_drops_system_notification_turn():
    line = (
        '{"type":"user","userType":"external","isSidechain":false,'
        '"message":{"role":"user","content":"[SYSTEM NOTIFICATION - NOT USER INPUT]\\n..."}}'
    )
    assert ClaudeCodeParser().parse([line]) == []


def test_emits_assistant_gist_text_only_truncated():
    long_text = "x" * 800
    line = (
        '{"type":"assistant","isSidechain":false,"message":{"role":"assistant",'
        '"content":[{"type":"thinking","thinking":"secret"},'
        '{"type":"text","text":"' + long_text + '"},'
        '{"type":"tool_use","name":"Bash","input":{}}]}}'
    )
    turns = ClaudeCodeParser().parse([line])
    assert len(turns) == 1
    assert turns[0]["role"] == "assistant"
    assert "secret" not in turns[0]["text"]
    assert len(turns[0]["text"]) <= 410  # 400 + " …"
    assert turns[0]["text"].endswith("…")
