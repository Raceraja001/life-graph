"""Claude Code session transcripts (``~/.claude/projects/**/*.jsonl``).

One file per session, one JSON object per line. The records that matter:

* ``{"type": "user", "message": {"role": "user", "content": "..."}}`` — a prompt,
  or, when ``content`` is a list of ``tool_result`` blocks, the output of the
  tools the previous assistant turn called.
* ``{"type": "assistant", "message": {"content": [{"type": "text"|"thinking"|
  "tool_use", ...}]}}`` — the reply, its reasoning, and the tool calls.

A tool result arrives twice: once as the block the model sees (``content``,
``is_error``) and once as the raw payload under the record's ``toolUseResult``
(``stdout``/``stderr``/``interrupted`` for shell tools, ``structuredPatch`` for
edits). Both are read — the block carries the error flag, the payload carries
the exit status and the diff.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from life_graph.watchers.agent_transcripts.adapters.base import (
    KIND_ASSISTANT,
    KIND_TOOL_CALL,
    KIND_TOOL_RESULT,
    KIND_USER,
    BaseTranscriptAdapter,
    first_text,
    snippet,
)

#: Context the client injects into the conversation as if the user had typed
#: it — reminders, hook output, command echoes. It is not the ask, and a turn
#: made only of it is not a turn: dropping it keeps the tool work attached to
#: the prompt that actually caused it.
INJECTED_RE = re.compile(
    r"<(system-reminder|command-name|command-message|command-args|local-command-stdout"
    r"|local-command-stderr|user-prompt-submit-hook)>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)


def user_text(content: Any) -> str:
    """The user's own words in *content*, with injected context removed."""
    return INJECTED_RE.sub("", first_text(content)).strip()


class ClaudeCodeAdapter(BaseTranscriptAdapter):
    """Reads Claude Code's per-session JSONL transcripts."""

    agent_type = "claude_code"
    home_globs = (".claude/projects/**/*.jsonl",)
    relative_globs = ("**/*.jsonl",)

    def canonical_events(self, raw_events: list[dict]) -> list[dict]:
        """Canonical events for Claude Code records (see the module docstring)."""
        out: list[dict] = []
        for record in raw_events:
            if not isinstance(record, dict):
                continue
            kind = record.get("type")
            if kind == "user":
                out.extend(self._from_user(record))
            elif kind == "assistant":
                out.extend(self._from_assistant(record))
            # Everything else — queue-operation, attachment, system, cost-state —
            # is client bookkeeping. The prompt it sometimes carries is already
            # in the matching "user" record, so reading it would double the turn.
        return out

    # ── Record kinds ──────────────────────────────────────────

    def _meta(self, record: dict) -> dict[str, Any]:
        """Session, project and timestamp, carried on every event of a record."""
        cwd = record.get("cwd")
        return {
            "ts": record.get("timestamp"),
            "session_id": record.get("sessionId") or record.get("session_id"),
            "project": Path(cwd).name if isinstance(cwd, str) and cwd else None,
            "cwd": cwd if isinstance(cwd, str) else None,
            "git_branch": record.get("gitBranch"),
        }

    def _from_user(self, record: dict) -> list[dict]:
        """A prompt, or the tool results of the turn before it."""
        meta = self._meta(record)
        content = (record.get("message") or {}).get("content")
        events: list[dict] = []

        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    events.append(self._tool_result(block, record.get("toolUseResult"), meta))
            text = user_text([b for b in content if isinstance(b, dict)])
            if text:
                events.append({"kind": KIND_USER, "text": text, **meta})
            return events

        text = user_text(content)
        if text:
            events.append({"kind": KIND_USER, "text": text, **meta})
        return events

    def _from_assistant(self, record: dict) -> list[dict]:
        """Assistant text, its thinking, and each tool it called."""
        meta = self._meta(record)
        content = (record.get("message") or {}).get("content")
        if isinstance(content, str):
            text = content.strip()
            return (
                [{"kind": KIND_ASSISTANT, "text": text, "is_thought": False, **meta}]
                if text
                else []
            )

        events: list[dict] = []
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                text = str(block.get("text", "")).strip()
                if text:
                    events.append(
                        {"kind": KIND_ASSISTANT, "text": text, "is_thought": False, **meta}
                    )
            elif btype == "thinking":
                thought = str(block.get("thinking", "")).strip()
                if thought:
                    events.append(
                        {"kind": KIND_ASSISTANT, "text": thought, "is_thought": True, **meta}
                    )
            elif btype == "tool_use":
                events.append(
                    {
                        "kind": KIND_TOOL_CALL,
                        "tool_name": str(block.get("name") or "unknown"),
                        "command": self.command_of(block.get("name") or "", block.get("input")),
                        "tool_id": block.get("id"),
                        **meta,
                    }
                )
        return events

    def _tool_result(self, block: dict, payload: Any, meta: dict) -> dict:
        """One ``tool_result`` block plus the raw ``toolUseResult`` beside it."""
        output = first_text(block.get("content"))
        exit_code = self.exit_code_of(payload)
        stderr = ""
        if isinstance(payload, dict):
            stderr = str(payload.get("stderr") or "").strip()
            if not output:
                output = first_text(payload.get("stdout")) or self._edit_summary(payload)
            if payload.get("interrupted"):
                stderr = f"{stderr}\n[interrupted]".strip()

        is_error = bool(block.get("is_error")) or (exit_code is not None and exit_code != 0)
        if isinstance(payload, dict) and payload.get("interrupted"):
            is_error = True

        combined = "\n".join(p for p in (output, stderr and f"stderr: {stderr}") if p)
        return {
            "kind": KIND_TOOL_RESULT,
            "tool_id": block.get("tool_use_id") or block.get("toolUseId"),
            "output": snippet(combined),
            "is_error": is_error,
            "exit_code": exit_code,
            **meta,
        }

    @staticmethod
    def _edit_summary(payload: dict) -> str:
        """What a file-edit result says when it has no stdout: the file it wrote."""
        kind = payload.get("type")
        path = payload.get("filePath") or payload.get("file_path")
        if kind and path:
            patch = payload.get("structuredPatch")
            hunks = f", {len(patch)} hunk(s)" if isinstance(patch, list) and patch else ""
            return f"{kind} {path}{hunks}"
        return ""
