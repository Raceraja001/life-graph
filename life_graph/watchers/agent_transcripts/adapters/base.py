"""The transcript adapter contract: find files, read new bytes, canonicalise.

Every coding agent writes its session log in its own JSONL dialect. An adapter
knows exactly three things about its agent:

1. **where** the transcripts live (:meth:`find_transcript_files`),
2. **how to read only the new bytes** (:meth:`parse_incremental`, shared — the
   format is JSONL for all of them),
3. **what its records mean** (:meth:`canonical_events`, the only per-agent part).

Canonicalising in the adapter and grouping in the normalizer is what keeps a new
agent to one small file: the normalizer never learns a vendor's field names.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── The canonical event vocabulary ───────────────────────────────────────
# Adapters emit dicts with a "kind" from this set. Anything else is ignored
# by the normalizer, so an adapter may carry extra keys for its own use.
KIND_USER = "user"
KIND_ASSISTANT = "assistant"
KIND_TOOL_CALL = "tool_call"
KIND_TOOL_RESULT = "tool_result"

#: How much of a tool's output is kept in a normalized slice.
OUTPUT_SNIPPET_CHARS = 1200


def snippet(text: Any, limit: int = OUTPUT_SNIPPET_CHARS) -> str:
    """*text* as a string, clipped to *limit* characters with the tail marked.

    Tool output is unbounded (a full test run, a 10k-line file) while the
    useful signal — the command, the error, the last lines — is small. The
    head is kept because that is where a traceback's exception line and a
    compiler's first error appear.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = json.dumps(text, default=str)
        except (TypeError, ValueError):  # pragma: no cover - json is forgiving
            text = str(text)
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… [+{len(text) - limit} chars]"


def first_text(content: Any) -> str:
    """The text of an Anthropic-style ``content`` value: a string, or text blocks."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            str(block.get("text", "")).strip()
            for block in content
            if isinstance(block, dict) and block.get("type") in (None, "text")
        ]
        return "\n".join(p for p in parts if p).strip()
    if isinstance(content, dict):
        return str(content.get("text", "")).strip()
    return ""


def pick(record: Any, *keys: str, default: Any = None) -> Any:
    """The first key of *keys* present and truthy in *record*.

    Transcript dialects name the same thing half a dozen ways
    (``text``/``content``/``message``/``prompt``), and a vendor renames
    them between releases. Reading them all is cheaper than a format
    version check, and an unknown name degrades to a missing field rather
    than a crash.
    """
    if not isinstance(record, dict):
        return default
    for key in keys:
        if key in record and record[key] not in (None, "", [], {}):
            return record[key]
    return default


class BaseTranscriptAdapter:
    """Base class for per-agent transcript readers.

    Subclasses set :attr:`agent_type`, :attr:`home_globs` and
    :attr:`relative_globs`, and implement :meth:`canonical_events`.
    """

    #: Stamped onto every slice and capture this adapter produces.
    agent_type: str = "base"

    #: Glob patterns resolved against the user's home directory.
    home_globs: tuple[str, ...] = ()

    #: Glob patterns resolved against each caller-supplied base directory.
    #: Deliberately narrower than ``**/*.jsonl`` where an agent has a
    #: recognisable layout, so two adapters pointed at one directory do not
    #: both claim the same files.
    relative_globs: tuple[str, ...] = ("**/*.jsonl",)

    # ── Discovery ─────────────────────────────────────────────

    def find_transcript_files(self, base_dirs: list[Path] | None = None) -> list[Path]:
        """Transcript files for this agent, sorted by modification time (oldest first).

        With no *base_dirs* the adapter's own :attr:`home_globs` are used.
        Oldest-first so a run truncated by ``--limit`` makes progress on the
        backlog instead of re-reading the newest file every pass.
        """
        if base_dirs:
            roots = [(Path(d).expanduser(), g) for d in base_dirs for g in self.relative_globs]
        else:
            roots = [(Path.home(), g) for g in self.home_globs]

        found: dict[Path, float] = {}
        for root, pattern in roots:
            if not root.is_dir():
                continue
            try:
                matches = root.glob(pattern)
            except (OSError, ValueError) as exc:  # pragma: no cover - bad pattern
                logger.debug("Glob %s under %s failed: %s", pattern, root, exc)
                continue
            for path in matches:
                try:
                    if not path.is_file():
                        continue
                    found[path.absolute()] = path.stat().st_mtime
                except OSError:
                    continue
        return sorted(found, key=lambda p: (found[p], str(p)))

    # ── Incremental read ──────────────────────────────────────

    def parse_incremental(self, file_path: Path, start_offset: int = 0) -> tuple[list[dict], int]:
        """Parse whole JSONL records from *start_offset*, returning ``(events, new_offset)``.

        The last line of a live transcript is routinely half-written, so the
        read stops at the final newline and *new_offset* points just past it:
        the partial record is left for the next pass rather than being parsed
        from a truncated string. A file shorter than the watermark was rotated
        or rewritten, so it is re-read from the start.
        """
        path = Path(file_path)
        try:
            size = path.stat().st_size
        except OSError as exc:
            logger.debug("Cannot stat %s: %s", path, exc)
            return [], start_offset

        offset = max(int(start_offset), 0)
        if offset > size:
            logger.info(
                "Transcript %s shrank (%d bytes < watermark %d) — re-reading from the start",
                path,
                size,
                offset,
            )
            offset = 0
        if offset == size:
            return [], offset

        try:
            with path.open("rb") as handle:
                handle.seek(offset)
                chunk = handle.read()
        except OSError as exc:
            logger.warning("Cannot read %s: %s", path, exc)
            return [], start_offset

        cut = chunk.rfind(b"\n")
        if cut == -1:
            # Not one complete record yet: hold the offset where it was.
            return [], offset

        events: list[dict] = []
        for line in chunk[: cut + 1].splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line.decode("utf-8", errors="replace"))
            except ValueError:
                logger.debug("Skipping unparseable line in %s", path)
                continue
            if isinstance(record, dict):
                events.append(record)
        return events, offset + cut + 1

    # ── Canonicalisation ──────────────────────────────────────

    def canonical_events(self, raw_events: list[dict]) -> list[dict]:
        """Translate this agent's records into the canonical event vocabulary.

        Returns dicts carrying ``kind`` (one of ``user``, ``assistant``,
        ``tool_call``, ``tool_result``) plus the fields that kind needs:

        * ``user`` / ``assistant`` — ``text``
        * ``tool_call`` — ``tool_name``, ``command``, ``tool_id``
        * ``tool_result`` — ``tool_id``, ``output``, ``is_error``, ``exit_code``

        Every event may also carry ``ts`` (ISO 8601), ``session_id`` and
        ``project``, which the normalizer uses for slice metadata.
        """
        raise NotImplementedError

    # ── Helpers for subclasses ────────────────────────────────

    @staticmethod
    def command_of(tool_name: str, tool_input: Any) -> str:
        """A one-line rendering of a tool's arguments.

        A shell tool's ``command`` is the interesting part; a file tool's is
        the path. Everything else is dumped as compact JSON so no argument is
        silently lost.
        """
        if isinstance(tool_input, str):
            return tool_input.strip()
        if not isinstance(tool_input, dict):
            return snippet(tool_input, 300)

        for key in ("command", "cmd", "script", "shell_command", "query", "pattern"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            # Codex sends a shell command as argv (["bash", "-lc", "pytest"]).
            if isinstance(value, list) and all(isinstance(v, str) for v in value) and value:
                return " ".join(value).strip()

        for key in ("file_path", "path", "filePath", "target_file", "notebook_path"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                edits = tool_input.get("edits")
                suffix = f" ({len(edits)} edits)" if isinstance(edits, list) else ""
                return f"{value.strip()}{suffix}"

        return snippet(tool_input, 300)

    @staticmethod
    def exit_code_of(payload: Any) -> int | None:
        """The exit code in a tool-result payload, under any of its usual names."""
        if not isinstance(payload, dict):
            return None
        for key in ("exit_code", "exitCode", "returncode", "returnCode", "status_code"):
            value = payload.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                return int(value.strip())
        return None
