# life_graph/extraction/transcript_parsers/__init__.py
"""Registry of transcript parsers keyed by tool name."""

from __future__ import annotations

from life_graph.extraction.transcript_parsers.base import TranscriptParser, Turn
from life_graph.extraction.transcript_parsers.claude_code import ClaudeCodeParser

PARSERS: dict[str, TranscriptParser] = {
    "claude-code": ClaudeCodeParser(),
}

__all__ = ["PARSERS", "TranscriptParser", "Turn"]
