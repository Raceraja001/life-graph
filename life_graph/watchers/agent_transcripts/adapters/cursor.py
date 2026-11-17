"""Cursor agent and composer transcripts.

Cursor keeps per-project logs under ``~/.cursor/projects/`` — ``agent-transcripts/``
for agent runs and ``composer/`` for composer threads. Both are JSONL in a
chat shape: a record per message with ``role`` and ``content``, with tool
activity either inline on an assistant message (``toolCalls``/``tool_calls``,
each optionally carrying its own ``result``) or in standalone
``type: "tool_call"`` / ``type: "tool_result"`` records.

The two directories share one adapter because they share that shape; only the
discovery globs differ.
"""

from __future__ import annotations

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


class CursorAdapter(BaseTranscriptAdapter):
    """Reads Cursor's agent-transcript and composer JSONL logs."""

    agent_type = "cursor"
    home_globs = (
        ".cursor/projects/**/agent-transcripts/**/*.jsonl",
        ".cursor/projects/**/composer/**/*.jsonl",
    )
    relative_globs = (
        "**/agent-transcripts/**/*.jsonl",
        "**/composer/**/*.jsonl",
    )

    def canonical_events(self, raw_events: list[dict]) -> list[dict]:
        """Canonical events for Cursor records (see the module docstring)."""
        out: list[dict] = []
        for record in raw_events:
            if not isinstance(record, dict):
                continue
            meta = self._meta(record)
            rtype = str(pick(record, "type", "kind", default="") or "").lower()
            role = str(pick(record, "role", "sender", "author", default="") or "").lower()
            text = first_text(pick(record, "content", "text", "message", "prompt"))

            if rtype in ("tool_call", "toolcall", "tool_use"):
                out.extend(self._calls([record], meta))
                continue
            if rtype in ("tool_result", "toolresult", "tool_output"):
                out.append(self._result(record, meta))
                continue

            if text and role in ("user", "human"):
                out.append({"kind": KIND_USER, "text": text, **meta})
            elif text and role in ("assistant", "ai", "agent", "model"):
                out.append({"kind": KIND_ASSISTANT, "text": text, "is_thought": False, **meta})

            thinking = first_text(pick(record, "thinking", "reasoning"))
            if thinking:
                out.append({"kind": KIND_ASSISTANT, "text": thinking, "is_thought": True, **meta})

            out.extend(self._calls(pick(record, "toolCalls", "tool_calls", default=[]), meta))
            results = pick(record, "toolResults", "tool_results", default=[])
            if isinstance(results, dict):
                results = [results]
            for payload in results or []:
                if isinstance(payload, dict):
                    out.append(self._result(payload, meta))
            single = pick(record, "toolResult", "tool_result")
            if isinstance(single, dict):
                out.append(self._result(single, meta))
        return out

    # ── Records ───────────────────────────────────────────────

    @staticmethod
    def _meta(record: dict) -> dict[str, Any]:
        return {
            "ts": pick(record, "timestamp", "ts", "createdAt", "created_at", "time"),
            "session_id": pick(
                record, "composerId", "composer_id", "sessionId", "session_id", "conversationId"
            ),
            "project": pick(record, "project", "workspace", "workspacePath", "cwd"),
        }

    def _calls(self, calls: Any, meta: dict) -> list[dict]:
        """``toolCalls`` entries, plus the result some of them carry inline."""
        events: list[dict] = []
        for call in calls if isinstance(calls, list) else []:
            if not isinstance(call, dict):
                continue
            name = str(
                pick(call, "name", "tool", "toolName", "tool_name", "function", default="unknown")
            )
            args = pick(call, "arguments", "args", "parameters", "params", "input")
            events.append(
                {
                    "kind": KIND_TOOL_CALL,
                    "tool_name": name,
                    "command": self.command_of(name, args),
                    "tool_id": pick(call, "id", "toolCallId", "tool_call_id", "callId"),
                    **meta,
                }
            )
            if pick(call, "result", "output", "stdout", "error") is not None:
                events.append(self._result(call, meta))
        return events

    def _result(self, payload: dict, meta: dict) -> dict:
        """A tool result, standalone or inline on its call."""
        output = pick(payload, "result", "output", "stdout", "content", "text")
        error = pick(payload, "error", "stderr", "errorMessage", "error_message")
        exit_code = self.exit_code_of(payload)
        is_error = (
            bool(error)
            or bool(pick(payload, "isError", "is_error", "failed"))
            or (exit_code is not None and exit_code != 0)
        )
        combined = "\n".join(
            part for part in (first_text(output) or snippet(output), first_text(error)) if part
        )
        return {
            "kind": KIND_TOOL_RESULT,
            "tool_id": pick(payload, "toolCallId", "tool_call_id", "callId", "id"),
            "output": snippet(combined),
            "is_error": is_error,
            "exit_code": exit_code,
            **meta,
        }
