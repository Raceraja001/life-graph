"""Canonical events → :class:`NormalizedSessionSlice`, one per user turn.

A transcript is a flat stream; the unit worth remembering is a *turn*: what the
user asked, the tools that ran because of it, whether anything broke, and how
it ended. The normalizer cuts the stream at each user prompt and folds
everything until the next one into a single slice.

The two flags on a slice are what the distiller filters on later:

* ``has_errors`` — a tool exited non-zero, reported an error, or printed
  something that reads like a traceback.
* ``has_fixes`` — after that error, something changed the world (an edit, a
  successful command) or the agent wrote a closing message. An error with no
  fix is a session that was abandoned, and there is no procedure to learn
  from it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from life_graph.watchers.agent_transcripts.adapters.base import (
    KIND_ASSISTANT,
    KIND_TOOL_CALL,
    KIND_TOOL_RESULT,
    KIND_USER,
    BaseTranscriptAdapter,
)

#: Output that means a failure even when the exit status says nothing. Tool
#: wrappers routinely return 0 while printing a Python traceback or a
#: compiler's error line, so the text is read as well as the status.
ERROR_PATTERNS = re.compile(
    r"\b("
    r"traceback \(most recent call last\)"
    r"|[a-z_]*error:"
    r"|[a-z_]*(?:error|exception)\b"
    r"|fatal"
    r"|command not found"
    r"|no such file or directory"
    r"|permission denied"
    r"|segmentation fault"
    r"|assertionerror"
    r"|failed to"
    r"|\d+ failed"
    r"|cannot find module"
    r"|modulenotfounderror"
    r"|undefined reference"
    r")",
    re.IGNORECASE,
)

#: Tools that change something. Used for ``has_fixes`` and by the distiller's
#: read-only gate. Matched case-insensitively against a prefix of the name, so
#: ``Edit``, ``FileEdit``, ``str_replace_editor`` and ``edit_file`` all count.
MUTATING_TOOL_HINTS = (
    "bash",
    "shell",
    "terminal",
    "command",
    "run",
    "exec",
    "edit",
    "write",
    "patch",
    "apply",
    "create",
    "replace",
    "notebook",
    "git",
    "install",
    "mkdir",
    "move",
    "delete",
)

#: How much of a prompt is kept. Agent prompts can be whole specifications;
#: the distiller only needs the ask.
PROMPT_CHARS = 2000

#: How much of a closing message is kept.
RESOLUTION_CHARS = 1500


def _is_mutating(tool_name: str) -> bool:
    """True when *tool_name* looks like a tool that changes state."""
    name = (tool_name or "").lower()
    return any(hint in name for hint in MUTATING_TOOL_HINTS)


def _looks_like_error(text: str) -> bool:
    """True when *text* reads like a failure, whatever the exit status said."""
    return bool(text) and bool(ERROR_PATTERNS.search(text))


def _parse_ts(value: Any) -> datetime | None:
    """An ISO 8601 (or epoch) timestamp as an aware datetime; None if unreadable."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else f"{text[:limit]}… [truncated]"


@dataclass
class NormalizedSessionSlice:
    """One user turn of a coding session, agent-agnostic.

    This is the only shape the capture spine and the skill distiller see — the
    vendor's field names stop at the adapter.
    """

    session_id: str
    project_name: str
    agent_type: str
    user_prompt: str
    tool_calls: list[dict] = field(default_factory=list)
    resolution_summary: str = ""
    has_errors: bool = False
    has_fixes: bool = False
    file_path: str = ""
    occurred_at: datetime | None = None

    # ── Derived views ─────────────────────────────────────────

    @property
    def error_calls(self) -> list[dict]:
        """The tool calls that failed."""
        return [c for c in self.tool_calls if c.get("is_error")]

    @property
    def mutating_calls(self) -> list[dict]:
        """The tool calls that changed something (edits, commands, writes)."""
        return [c for c in self.tool_calls if _is_mutating(str(c.get("tool_name", "")))]

    @property
    def tool_names(self) -> list[str]:
        """Tool names in call order, duplicates kept."""
        return [str(c.get("tool_name", "")) for c in self.tool_calls]

    def to_capture_content(self) -> str:
        """A readable markdown rendering for ``CaptureEvent.content``.

        Deterministic: the same slice renders the same text, so the capture
        spine's content-hash dedup recognises a re-read of the same turn.
        """
        when = self.occurred_at.isoformat() if self.occurred_at else "unknown time"
        lines = [
            f"# Coding session turn — {self.project_name} ({self.agent_type})",
            "",
            f"- Session: `{self.session_id}`",
            f"- When: {when}",
            f"- Transcript: `{self.file_path}`",
            f"- Errors encountered: {'yes' if self.has_errors else 'no'}"
            f" · resolved: {'yes' if self.has_fixes else 'no'}",
            "",
            "## Request",
            "",
            self.user_prompt or "_(no prompt text captured)_",
        ]

        if self.tool_calls:
            lines += ["", "## Tool sequence", ""]
            for index, call in enumerate(self.tool_calls, 1):
                status = "ERROR" if call.get("is_error") else "ok"
                code = call.get("exit_code")
                status = f"{status} (exit {code})" if code is not None else status
                lines.append(f"{index}. **{call.get('tool_name', 'unknown')}** [{status}]")
                command = str(call.get("command") or "").strip()
                if command:
                    lines += ["", "   ```", *[f"   {ln}" for ln in command.splitlines()], "   ```"]
                output = str(call.get("output_snippet") or "").strip()
                if output:
                    lines += [f"   > {ln}" for ln in output.splitlines()[:12]]
                lines.append("")

        if self.has_errors:
            lines += ["## Errors encountered", ""]
            for call in self.error_calls:
                output = str(call.get("output_snippet") or "").strip().splitlines()
                head = output[0] if output else "(no output captured)"
                lines.append(f"- `{call.get('tool_name')}`: {head}")
            lines.append("")

        lines += [
            "## Resolution",
            "",
            self.resolution_summary or "_(session ended without a closing summary)_",
        ]
        return "\n".join(lines).strip() + "\n"


class TranscriptNormalizer:
    """Folds an adapter's canonical events into :class:`NormalizedSessionSlice` objects."""

    def normalize(
        self,
        adapter: BaseTranscriptAdapter | str,
        file_path: str | Path,
        raw_events: list[dict],
    ) -> list[NormalizedSessionSlice]:
        """Slices for *raw_events* as parsed from *file_path*.

        *adapter* may be the adapter itself (its ``canonical_events`` is used)
        or an ``agent_type`` string, in which case *raw_events* must already be
        canonical events.
        """
        if isinstance(adapter, str):
            agent_type, events = adapter, list(raw_events)
        else:
            agent_type, events = adapter.agent_type, adapter.canonical_events(raw_events)
        return self.from_canonical(agent_type, file_path, events)

    def from_canonical(
        self,
        agent_type: str,
        file_path: str | Path,
        events: list[dict],
    ) -> list[NormalizedSessionSlice]:
        """Group canonical *events* into one slice per user turn."""
        path = Path(file_path)
        fallback_session = self._fallback_session_id(events, path)
        fallback_project = self._fallback_project(events, path)

        groups = self._group_by_turn(events)
        slices: list[NormalizedSessionSlice] = []
        for group in groups:
            built = self._build_slice(
                agent_type=agent_type,
                path=path,
                group=group,
                fallback_session=fallback_session,
                fallback_project=fallback_project,
            )
            if built is not None:
                slices.append(built)
        return slices

    # ── Grouping ──────────────────────────────────────────────

    @staticmethod
    def _group_by_turn(events: list[dict]) -> list[list[dict]]:
        """Split the stream at each user prompt.

        Tool activity and assistant messages belong to the prompt that caused
        them, so a group runs from one user event up to (not including) the
        next. Events before the first prompt — a resumed session's tail — form
        their own leading group so their work is not lost.
        """
        groups: list[list[dict]] = []
        current: list[dict] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("kind") == KIND_USER and current:
                groups.append(current)
                current = []
            current.append(event)
        if current:
            groups.append(current)
        return groups

    def _build_slice(
        self,
        *,
        agent_type: str,
        path: Path,
        group: list[dict],
        fallback_session: str,
        fallback_project: str,
    ) -> NormalizedSessionSlice | None:
        """One slice from one turn's events, or None when the turn is empty."""
        prompts = [e for e in group if e.get("kind") == KIND_USER]
        calls = [e for e in group if e.get("kind") == KIND_TOOL_CALL]
        results = [e for e in group if e.get("kind") == KIND_TOOL_RESULT]
        assistant = [
            e for e in group if e.get("kind") == KIND_ASSISTANT and not e.get("is_thought")
        ]

        if not (prompts or calls or results or assistant):
            return None

        tool_calls = self._pair(calls, results)
        has_errors = any(c["is_error"] for c in tool_calls)
        session_id = self._first(group, "session_id") or fallback_session
        project = self._first(group, "project") or fallback_project
        resolution = _clip(assistant[-1]["text"], RESOLUTION_CHARS) if assistant else ""

        return NormalizedSessionSlice(
            session_id=str(session_id),
            project_name=str(project),
            agent_type=agent_type,
            user_prompt=_clip(prompts[0].get("text", "") if prompts else "", PROMPT_CHARS),
            tool_calls=tool_calls,
            resolution_summary=resolution,
            has_errors=has_errors,
            has_fixes=self._has_fixes(tool_calls, resolution) if has_errors else False,
            file_path=str(path),
            occurred_at=self._occurred_at(group),
        )

    # ── Pairing ───────────────────────────────────────────────

    @staticmethod
    def _pair(calls: list[dict], results: list[dict]) -> list[dict]:
        """Join each tool call to its result: by ``tool_id``, else in order.

        Positional pairing is the fallback because some agents (and some tools
        inside one agent) omit the id entirely; dropping those results would
        hide exactly the failures worth learning from. A result left over at
        the end belongs to a call made before this byte range — it is kept as
        an unnamed call rather than dropped, because its failure is real.
        """

        def entry(call: dict | None, result: dict | None) -> dict:
            output = str((result or {}).get("output") or "")
            exit_code = (result or {}).get("exit_code")
            is_error = bool((result or {}).get("is_error")) or (
                exit_code is not None and exit_code != 0
            )
            return {
                "tool_name": str((call or {}).get("tool_name") or "unknown"),
                "command": str((call or {}).get("command") or ""),
                "output_snippet": output,
                "is_error": is_error or _looks_like_error(output),
                "exit_code": exit_code,
            }

        by_id = {r["tool_id"]: r for r in results if r.get("tool_id")}
        loose = [r for r in results if not r.get("tool_id")]
        consumed: set[int] = set()
        position = 0

        paired: list[dict] = []
        for call in calls:
            tool_id = call.get("tool_id")
            result = by_id.get(tool_id) if tool_id else None
            if result is None and position < len(loose):
                result, position = loose[position], position + 1
            if result is not None:
                consumed.add(id(result))
            paired.append(entry(call, result))

        paired.extend(entry(None, r) for r in results if id(r) not in consumed)
        return paired

    @staticmethod
    def _has_fixes(tool_calls: list[dict], resolution: str) -> bool:
        """True when something succeeded *after* the last failure.

        "After" matters: a passing test run before the breakage says nothing
        about whether the breakage was understood.
        """
        last_error = max(
            (i for i, c in enumerate(tool_calls) if c.get("is_error")),
            default=-1,
        )
        if last_error < 0:
            return False
        after = tool_calls[last_error + 1 :]
        if any(not c.get("is_error") and _is_mutating(str(c.get("tool_name", ""))) for c in after):
            return True
        return bool(resolution)

    # ── Metadata fallbacks ────────────────────────────────────

    @staticmethod
    def _first(events: list[dict], key: str) -> Any:
        for event in events:
            value = event.get(key)
            if value:
                return value
        return None

    def _fallback_session_id(self, events: list[dict], path: Path) -> str:
        """The first session id anywhere in the file, else the file's stem.

        Only the first record of a Cursor or Codex file names the session, and
        a slice from the middle of the file must still carry it.
        """
        return str(self._first(events, "session_id") or path.stem)

    def _fallback_project(self, events: list[dict], path: Path) -> str:
        """The first project/cwd anywhere in the file, else the directory name.

        Claude Code encodes the project path in the *directory* name
        (``-home-raja-projects-life-graph``), so the leading dashes are turned
        back into a readable last path segment.
        """
        found = self._first(events, "project")
        if found:
            return str(Path(str(found)).name or found)
        parent = path.parent.name
        # Claude Code names the directory after the project's path with the
        # separators replaced by dashes ("-home-raja-projects-life-graph").
        # Which dashes were slashes is unrecoverable, so the label keeps them
        # all; every real record carries ``cwd``, which is read first above,
        # and this only has to be stable and recognisable.
        return parent.strip("-") or "unknown"

    def _occurred_at(self, events: list[dict]) -> datetime | None:
        """The turn's timestamp: the first one its events carry."""
        for event in events:
            parsed = _parse_ts(event.get("ts"))
            if parsed is not None:
                return parsed
        return None
