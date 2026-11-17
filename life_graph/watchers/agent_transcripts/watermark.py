"""Incremental read watermarks for coding-agent transcript files.

A session transcript is an append-only JSONL file that its agent keeps writing
to for as long as the session lives. Harvesting it means reading only the bytes
that appeared since last time — re-reading the whole file would re-ingest every
turn on every pass — so one watermark per file records where the reader stopped.

The state lives in a single JSON file outside the repository
(``~/.life-graph/agent_transcripts_state.json`` by default) because it tracks
paths on *this* machine: it is local reader bookkeeping, not tenant data.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Overrides the default state path. Read at construction, not at import.
STATE_PATH_ENV = "LIFE_GRAPH_TRANSCRIPT_STATE_PATH"

DEFAULT_STATE_PATH = Path.home() / ".life-graph" / "agent_transcripts_state.json"

#: A file touched more recently than this is assumed to still be written to.
DEFAULT_SETTLING_SECONDS = 30.0


def _key(file_path: str | Path) -> str:
    """The state key for *file_path* — absolute, so a relative call still matches."""
    return str(Path(file_path).expanduser().absolute())


class WatermarkStore:
    """Per-file ``(byte offset, mtime)`` bookmarks, persisted as one JSON file.

    Usage::

        store = WatermarkStore()
        offset, mtime = store.get_watermark(path)
        events, new_offset = adapter.parse_incremental(path, offset)
        store.update_watermark(path, new_offset, path.stat().st_mtime, session_id)
        store.save()

    Nothing is written to disk until :meth:`save`, so a harvest that fails
    half-way leaves the previous watermarks in place and the same bytes are
    re-read next pass. Re-ingesting a slice is harmless (the capture spine
    dedupes on content hash); losing one is not.
    """

    def __init__(self, state_path: str | Path | None = None):
        if state_path is None:
            state_path = os.environ.get(STATE_PATH_ENV) or DEFAULT_STATE_PATH
        self.state_path = Path(state_path).expanduser()
        self._state: dict[str, dict[str, Any]] = self._load()

    # ── Load / save ───────────────────────────────────────────

    def _load(self) -> dict[str, dict[str, Any]]:
        """Read the state file, treating any unreadable file as empty state.

        A corrupt or truncated state file must not stop the harvest: the cost
        of starting over is re-reading transcripts, which dedupe downstream.
        """
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            logger.warning(
                "Transcript watermark state at %s is unreadable (%s) — starting empty",
                self.state_path,
                exc,
            )
            return {}
        if not isinstance(raw, dict):
            return {}
        return {k: v for k, v in raw.items() if isinstance(v, dict)}

    def save(self) -> Path:
        """Write the state atomically: temp file in the same directory, then rename.

        Same directory so the rename stays on one filesystem (``os.replace``
        across devices is not atomic), and a crash mid-write leaves either the
        old state or the new one — never a half-written file the next run would
        refuse to parse.
        """
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp{os.getpid()}")
        tmp.write_text(json.dumps(self._state, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.state_path)
        return self.state_path

    # ── Watermarks ────────────────────────────────────────────

    def get_watermark(self, file_path: str | Path) -> tuple[int, float]:
        """``(last_byte_offset, last_mtime)`` for *file_path*; ``(0, 0.0)`` if unseen."""
        entry = self._state.get(_key(file_path)) or {}
        try:
            offset = int(entry.get("last_byte_offset", 0) or 0)
        except (TypeError, ValueError):
            offset = 0
        try:
            mtime = float(entry.get("last_mtime", 0.0) or 0.0)
        except (TypeError, ValueError):
            mtime = 0.0
        return max(offset, 0), mtime

    def update_watermark(
        self,
        file_path: str | Path,
        offset: int,
        mtime: float,
        session_id: str,
    ) -> None:
        """Record how far *file_path* has been read. In memory until :meth:`save`."""
        self._state[_key(file_path)] = {
            "last_byte_offset": int(offset),
            "last_mtime": float(mtime),
            "session_id": session_id,
            "last_harvested_at": datetime.now(UTC).isoformat(),
        }

    def session_id(self, file_path: str | Path) -> str | None:
        """The session id last recorded for *file_path*, if any."""
        return (self._state.get(_key(file_path)) or {}).get("session_id")

    def forget(self, file_path: str | Path) -> None:
        """Drop the watermark for *file_path* so it is read from the start again."""
        self._state.pop(_key(file_path), None)

    def entries(self) -> dict[str, dict[str, Any]]:
        """A copy of the whole state, for ``--dry-run`` reporting and tests."""
        return {k: dict(v) for k, v in self._state.items()}

    # ── Settling ──────────────────────────────────────────────

    def is_settled(
        self,
        file_path: str | Path,
        settling_seconds: float = DEFAULT_SETTLING_SECONDS,
    ) -> bool:
        """True when *file_path* looks finished being written for now.

        Unsettled means either the file was modified within the last
        *settling_seconds* — the agent is probably mid-turn, and the tail would
        be read as a partial record — or a sibling lock file
        (``<name>.lock``) says a writer holds it. A missing file is never
        settled: there is nothing to read.
        """
        path = Path(file_path).expanduser()
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return False

        for lock in (path.with_name(path.name + ".lock"), path.with_suffix(".lock")):
            if lock.exists():
                logger.debug("Transcript %s is locked by %s — skipping this pass", path, lock)
                return False

        return (time.time() - mtime) > settling_seconds
