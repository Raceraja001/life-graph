"""Antigravity (Gemini) brain transcripts (``~/.gemini/antigravity/brain/**/transcript.jsonl``).

Antigravity logs a session as a list of *steps* rather than chat messages. Each
step names its kind — ``USER_INPUT``, ``PLANNER_RESPONSE``, a tool step — and
tool activity hangs off the step that caused it (``tool_calls``, with outputs
either inline on the call or in a following tool step).

Field names here are read permissively: the brain format is internal to the
product and has renamed ``text``/``content``/``message`` between releases. An
unrecognised step contributes nothing instead of failing the harvest.
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

#: Step kinds that carry something the user said.
USER_STEPS = {"USER_INPUT", "USER_MESSAGE", "USER_REQUEST", "USER_TURN"}

#: Step kinds that carry something the agent said — plans, answers, the wrap-up.
ASSISTANT_STEPS = {
    "PLANNER_RESPONSE",
    "AGENT_RESPONSE",
    "ASSISTANT_RESPONSE",
    "FINAL_RESPONSE",
    "RESOLUTION",
    "SUMMARY",
    "THOUGHT",
}

#: Step kinds that are a tool's output on their own.
RESULT_STEPS = {"TOOL_OUTPUT", "TOOL_RESULT", "TOOL_RESPONSE", "COMMAND_OUTPUT"}

#: Step kinds that are a tool invocation on their own.
CALL_STEPS = {"TOOL_CALL", "TOOL_USE", "COMMAND", "ACTION"}


class AntigravityAdapter(BaseTranscriptAdapter):
    """Reads Antigravity's per-session ``transcript.jsonl`` step logs."""

    agent_type = "antigravity"
    home_globs = (".gemini/antigravity/brain/**/transcript.jsonl",)
    relative_globs = ("**/transcript.jsonl",)

    def canonical_events(self, raw_events: list[dict]) -> list[dict]:
        """Canonical events for Antigravity steps (see the module docstring)."""
        out: list[dict] = []
        for record in raw_events:
            if not isinstance(record, dict):
                continue
            step = record.get("payload") if isinstance(record.get("payload"), dict) else record
            kind = str(
                pick(step, "step_type", "stepType", "type", "kind", default="") or ""
            ).upper()
            meta = self._meta(record, step)
            text = first_text(pick(step, "text", "content", "message", "prompt", "response"))

            if kind in USER_STEPS:
                if text:
                    out.append({"kind": KIND_USER, "text": text, **meta})
            elif kind in ASSISTANT_STEPS:
                if text:
                    out.append(
                        {
                            "kind": KIND_ASSISTANT,
                            "text": text,
                            "is_thought": kind == "THOUGHT",
                            **meta,
                        }
                    )
            elif kind in RESULT_STEPS:
                out.append(self._result(step, meta))
            elif kind in CALL_STEPS:
                out.extend(self._calls([step], meta))
                continue

            # Tool activity attached to any step, whatever its kind.
            out.extend(self._calls(pick(step, "tool_calls", "toolCalls", default=[]), meta))
            for payload in (
                pick(step, "tool_outputs", "toolOutputs", "tool_results", default=[]) or []
            ):
                if isinstance(payload, dict):
                    out.append(self._result(payload, meta))
        return out

    # ── Steps ─────────────────────────────────────────────────

    @staticmethod
    def _meta(record: dict, step: dict) -> dict[str, Any]:
        return {
            "ts": pick(record, "timestamp", "ts", "created_at") or pick(step, "timestamp", "ts"),
            "session_id": pick(record, "session_id", "sessionId", "trajectory_id")
            or pick(step, "session_id", "sessionId"),
            "project": pick(record, "workspace", "project", "cwd")
            or pick(step, "workspace", "project"),
        }

    def _calls(self, calls: Any, meta: dict) -> list[dict]:
        """``tool_calls`` entries, plus any output carried inline on them."""
        events: list[dict] = []
        for call in calls if isinstance(calls, list) else []:
            if not isinstance(call, dict):
                continue
            name = str(pick(call, "name", "tool_name", "toolName", "tool", default="unknown"))
            args = pick(call, "args", "arguments", "input", "parameters", "params")
            events.append(
                {
                    "kind": KIND_TOOL_CALL,
                    "tool_name": name,
                    "command": self.command_of(name, args),
                    "tool_id": pick(call, "id", "call_id", "tool_call_id"),
                    **meta,
                }
            )
            inline = pick(call, "output", "result", "tool_output", "response")
            if inline is not None:
                events.append(self._result(call, meta))
        return events

    def _result(self, payload: dict, meta: dict) -> dict:
        """A tool output step, or the output carried on a call."""
        output = pick(payload, "output", "result", "tool_output", "stdout", "response", "content")
        error = pick(payload, "error", "stderr", "error_message")
        exit_code = self.exit_code_of(payload)
        is_error = (
            bool(error)
            or bool(payload.get("is_error"))
            or (exit_code is not None and exit_code != 0)
        )
        combined = "\n".join(
            part for part in (first_text(output) or snippet(output), first_text(error)) if part
        )
        return {
            "kind": KIND_TOOL_RESULT,
            "tool_id": pick(payload, "id", "call_id", "tool_call_id"),
            "output": snippet(combined),
            "is_error": is_error,
            "exit_code": exit_code,
            **meta,
        }
