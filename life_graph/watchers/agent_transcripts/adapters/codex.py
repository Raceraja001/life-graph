"""Codex CLI and OpenClaw session logs.

Codex writes ``~/.codex/sessions/<date>/rollout-*.jsonl``; OpenClaw keeps the
same shape under ``~/.openclaw/**/sessions/``. Records follow the OpenAI
Responses item vocabulary, often wrapped one level deep:

    {"type": "session_meta", "payload": {"id": "...", "cwd": "..."}}
    {"type": "response_item", "payload": {"type": "message", "role": "user",
                                          "content": [{"type": "input_text", "text": "..."}]}}
    {"type": "response_item", "payload": {"type": "function_call", "name": "shell",
                                          "arguments": "{\\"command\\": [\\"bash\\", \\"-lc\\", \\"pytest\\"]}"}}
    {"type": "response_item", "payload": {"type": "function_call_output",
                                          "call_id": "...", "output": "{...}"}}

``arguments`` and ``output`` are JSON *strings*, and a command is argv rather
than a shell line; both are decoded here so the rest of the pipeline sees the
same canonical events as every other agent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from life_graph.watchers.agent_transcripts.adapters.base import (
    KIND_ASSISTANT,
    KIND_TOOL_CALL,
    KIND_TOOL_RESULT,
    KIND_USER,
    BaseTranscriptAdapter,
    first_text,
    pick,
    snippet,
)


def _maybe_json(value: Any) -> Any:
    """*value* decoded if it is a JSON object or array in a string, else as-is."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except ValueError:
        return value


class CodexAdapter(BaseTranscriptAdapter):
    """Reads Codex / OpenClaw session JSONL logs."""

    agent_type = "codex"
    home_globs = (
        ".codex/sessions/**/*.jsonl",
        ".openclaw/**/sessions/*.jsonl",
    )
    relative_globs = (
        "**/sessions/**/*.jsonl",
        "**/rollout-*.jsonl",
    )

    def canonical_events(self, raw_events: list[dict]) -> list[dict]:
        """Canonical events for Codex items (see the module docstring)."""
        out: list[dict] = []
        session: dict[str, Any] = {"ts": None, "session_id": None, "project": None}

        for record in raw_events:
            if not isinstance(record, dict):
                continue
            outer = str(pick(record, "type", default="") or "").lower()
            item = record.get("payload") if isinstance(record.get("payload"), dict) else record

            if outer in ("session_meta", "session", "meta"):
                cwd = pick(item, "cwd", "workspace", "project")
                session = {
                    "ts": pick(record, "timestamp", "ts") or pick(item, "timestamp", "ts"),
                    "session_id": pick(item, "id", "session_id", "sessionId"),
                    "project": Path(cwd).name if isinstance(cwd, str) and cwd else None,
                }
                continue

            meta = {
                **session,
                "ts": pick(record, "timestamp", "ts") or pick(item, "timestamp") or session["ts"],
            }
            itype = str(pick(item, "type", "kind", default="") or "").lower()
            role = str(pick(item, "role", default="") or "").lower()
            text = self._text_of(item)

            if itype in ("function_call", "tool_call", "local_shell_call", "custom_tool_call"):
                out.append(self._call(item, meta))
            elif itype in (
                "function_call_output",
                "tool_result",
                "local_shell_call_output",
                "custom_tool_call_output",
            ):
                out.append(self._result(item, meta))
            elif role in ("user", "human") and text:
                out.append({"kind": KIND_USER, "text": text, **meta})
            elif role in ("assistant", "model") and text:
                out.append({"kind": KIND_ASSISTANT, "text": text, "is_thought": False, **meta})
            elif itype == "reasoning":
                # Reasoning summaries are blocks typed "summary_text".
                summary = self._text_of({"content": pick(item, "summary", "content")}) or text
                if summary:
                    out.append(
                        {"kind": KIND_ASSISTANT, "text": summary, "is_thought": True, **meta}
                    )
        return out

    # ── Items ─────────────────────────────────────────────────

    @staticmethod
    def _text_of(item: dict) -> str:
        """The text of a message item: ``content`` blocks, or a plain string."""
        content = pick(item, "content", "text", "message")
        if isinstance(content, list):
            parts = [
                str(block.get("text", "")).strip()
                for block in content
                if isinstance(block, dict) and str(block.get("type", "")).endswith("text")
            ]
            joined = "\n".join(p for p in parts if p).strip()
            if joined:
                return joined
        return first_text(content)

    def _call(self, item: dict, meta: dict) -> dict:
        """A ``function_call`` item; ``arguments`` is a JSON string."""
        name = str(pick(item, "name", "tool_name", "action", default="shell"))
        args = _maybe_json(pick(item, "arguments", "args", "input", "action"))
        return {
            "kind": KIND_TOOL_CALL,
            "tool_name": name,
            "command": self.command_of(name, args),
            "tool_id": pick(item, "call_id", "callId", "id"),
            **meta,
        }

    def _result(self, item: dict, meta: dict) -> dict:
        """A ``function_call_output`` item; ``output`` is often a JSON string."""
        payload = _maybe_json(pick(item, "output", "result", "content"))
        body = payload if isinstance(payload, dict) else {}
        text = (
            first_text(pick(body, "output", "stdout", "content", "text"))
            if body
            else first_text(payload) or snippet(payload)
        )
        error = first_text(pick(body, "error", "stderr") if body else pick(item, "error", "stderr"))
        metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        exit_code = (
            self.exit_code_of(metadata) or self.exit_code_of(body) or self.exit_code_of(item)
        )
        is_error = (
            bool(error)
            or bool(pick(item, "is_error", "isError") or pick(body, "is_error", "isError"))
            or (exit_code is not None and exit_code != 0)
        )
        combined = "\n".join(part for part in (text, error) if part)
        return {
            "kind": KIND_TOOL_RESULT,
            "tool_id": pick(item, "call_id", "callId", "id"),
            "output": snippet(combined),
            "is_error": is_error,
            "exit_code": exit_code,
            **meta,
        }
