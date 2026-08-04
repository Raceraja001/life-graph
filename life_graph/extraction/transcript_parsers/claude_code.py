# life_graph/extraction/transcript_parsers/claude_code.py
"""Parser for Claude Code session transcripts (``~/.claude/projects/**/*.jsonl``).

Each line is a JSON object with a top-level ``type``. Only genuine, external,
non-sidechain ``user`` turns yield a Turn; tool results, harness-injected
system-reminders, assistant turns, and bookkeeping lines are dropped.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from life_graph.extraction.transcript_parsers.base import Turn

if TYPE_CHECKING:
    from collections.abc import Iterable


class ClaudeCodeParser:
    tool = "claude-code"

    def parse(self, lines: Iterable[str]) -> list[Turn]:
        turns: list[Turn] = []
        for raw in lines:
            try:
                obj = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(obj, dict) or obj.get("type") != "user":
                continue
            if obj.get("isSidechain"):
                continue
            if obj.get("userType") not in (None, "external"):
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            text = self._text(msg.get("content")).strip()
            if not text or self._harness_only(text):
                continue
            turns.append(Turn(role="user", text=text, ts=obj.get("timestamp")))
        return turns

    @staticmethod
    def _text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            return "\n".join(parts)
        return ""

    @staticmethod
    def _harness_only(text: str) -> bool:
        """True when the whole turn is a harness wrapper, not real user text."""
        t = text.strip()
        return (
            t.startswith("<system-reminder>") and t.endswith("</system-reminder>")
        ) or t.startswith("<local-command-")
