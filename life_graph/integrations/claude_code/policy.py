"""Client-side volume control for tool-exhaust captures.

This is a faithful port of the in-process policy in
:mod:`life_graph.services.tool_observation` (``DAILY_CAP``,
``LOW_SIGNAL_SAMPLE_RATE``, ``is_low_signal``, ``should_store`` and the
``tool:… status:… …ms args:…`` content format), moved to the *client* side so a
throttled event never becomes an HTTP request at all.

That matters here specifically: the default plan allows 60 requests/minute and
``event_bus.emit`` is awaited in-request, so an unsampled hook on every tool
call would exhaust the quota within seconds of normal agent work.

The server-side hook can count today's rows with a ``SELECT COUNT(*)``. A hook
is a fresh process per event, several of which run in parallel, so the counter
is kept in a small JSON file guarded by an advisory file lock.
"""

from __future__ import annotations

import json
import os
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from life_graph.core.redaction import summarize_args

try:  # POSIX advisory locking; absent on Windows.
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]


def is_low_signal(observation: dict[str, Any]) -> bool:
    """Low-signal = succeeded and not tied to a project (routine noise).

    Mirrors ``ToolObservationHook.is_low_signal``. A Claude Code hook has no
    kernel project id, so successful tool calls are always low-signal and are
    therefore the ones the daily cap throttles.
    """
    return observation.get("exit_status") == "ok" and not observation.get("project_id")


def should_store(
    count_today: int,
    low_signal: bool,
    *,
    daily_cap: int,
    sample_rate: float,
    rng=random.random,
) -> bool:
    """Decide whether to send, applying the daily cap to noise only.

    High-signal observations (errors, timeouts, project-scoped) always send.
    Low-signal ones send until ``daily_cap``, then at ``sample_rate``.
    Mirrors ``ToolObservationHook.should_store``.
    """
    if not low_signal:
        return True
    if count_today < daily_cap:
        return True
    return rng() < sample_rate


def format_observation(observation: dict[str, Any]) -> str:
    """Render an observation into the spine's tool-exhaust content format.

    Byte-identical in shape to ``ToolObservationHook.__call__`` so tool exhaust
    from Claude Code and from the in-process registry are indistinguishable
    downstream.
    """
    return (
        f"tool:{observation.get('tool')} "
        f"status:{observation.get('exit_status')} "
        f"{observation.get('duration_ms', 0)}ms "
        f"args:{observation.get('args_summary', '')}"
    )


def build_observation(
    *,
    tool_name: str,
    tool_input: Any,
    exit_status: str,
    duration_ms: int = 0,
    project_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble an observation dict with redacted, summarized args.

    ``summarize_args`` is the backend's own redactor/truncator — reused rather
    than reimplemented so a credential in a tool argument is scrubbed by
    exactly the same rules on both paths.
    """
    observation: dict[str, Any] = {
        "tool": tool_name,
        "exit_status": exit_status,
        "duration_ms": duration_ms,
        "args_summary": summarize_args(tool_input),
        "project_id": project_id,
    }
    if extra:
        observation.update(extra)
    return observation


class DailyCounter:
    """Cross-process, UTC-day-scoped counter of sent tool-exhaust captures.

    Each hook invocation is a separate process and hooks for one event run in
    parallel, so ``check_and_increment`` does read → decide → write inside a
    single advisory-locked open of the state file.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _ensure_parent(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def current(self) -> int:
        """Today's count, or 0 if the file is missing, stale or corrupt."""
        try:
            data = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return 0
        if data.get("date") != self._today():
            return 0
        try:
            return int(data.get("count", 0))
        except (TypeError, ValueError):
            return 0

    def check_and_increment(
        self,
        *,
        low_signal: bool,
        daily_cap: int,
        sample_rate: float,
        rng=random.random,
    ) -> bool:
        """Apply the sampling policy and, if storing, book the slot.

        Returns True when the caller should send. Any I/O failure fails *open*
        (send) rather than silently dropping the developer's data — a broken
        counter file must not become a silent capture outage.
        """
        try:
            self._ensure_parent()
            with open(self._path, "a+", encoding="utf-8") as fh:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                fh.seek(0)
                raw = fh.read()
                today = self._today()
                try:
                    data = json.loads(raw) if raw.strip() else {}
                except ValueError:
                    data = {}
                count = int(data.get("count", 0)) if data.get("date") == today else 0

                store = should_store(
                    count,
                    low_signal,
                    daily_cap=daily_cap,
                    sample_rate=sample_rate,
                    rng=rng,
                )
                if store:
                    fh.seek(0)
                    fh.truncate()
                    fh.write(json.dumps({"date": today, "count": count + 1}))
                    fh.flush()
                    os.fsync(fh.fileno())
                return store
        except OSError:
            return True
