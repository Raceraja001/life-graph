"""Circuit breaker for automatic starts, per source (``intake:<id>``) or job (``schedule:<id>``).

A failure whose **normalised** reason (times, ids, hashes, paths and numbers
replaced by placeholders) equals the previous one counts up; a different
reason starts the count at 1; a success resets it. At the threshold (default
3) the key **trips**: automatic starts for it stop, and a notice goes out
("Automation paused: <label> — <reason>"). It stays tripped until the owner
resets it, or a manual start of that source/job succeeds. The breaker never
stops manual work and never starts anything. Each task's outcome is counted
once (``counted``). With the breaker disabled nothing is recorded and nothing
is tripped.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from life_graph.services.dev.automation.status import failure_reason, finished

if TYPE_CHECKING:
    from datetime import datetime

    from life_graph.services.dev.automation.ports import Notifier, Store
    from life_graph.services.dev.automation.settings import BreakerSettings

logger = logging.getLogger(__name__)

LABEL_MAX = 120
REASON_MAX = 300
COUNTED_MAX = 50

_ISO_TIME = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?\b"
)
_CLOCK = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
# Unix paths (/a/b, ./a, ~/a) and Windows paths (C:\a\b).
_PATH = re.compile(r"(?:[A-Za-z]:\\|~/|\.{0,2}/)[^\s'\"`:,;()]+")
_PREFIXED_ID = re.compile(r"\b[a-z]{1,10}_[A-Za-z0-9]{4,}\b")
_HEX = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,}\b", re.I)
_DIGITS = re.compile(r"\d+")


def intake_key(source_id: str) -> str:
    return f"intake:{source_id}"


def schedule_key(job_id: str) -> str:
    return f"schedule:{job_id}"


def normalise_reason(reason: str | None) -> str:
    """The failure reason with its varying parts replaced, for comparing failures."""
    out = str(reason or "")
    for pattern, repl in (
        (_ISO_TIME, "<time>"),
        (_CLOCK, "<time>"),
        (_UUID, "<id>"),
        (_PATH, "<path>"),
        (_PREFIXED_ID, "<id>"),
        (_HEX, "<id>"),
        (_DIGITS, "#"),
    ):
        out = pattern.sub(repl, out)
    out = " ".join(out.split()) or "Unknown failure"
    return out if len(out) <= REASON_MAX else out[: REASON_MAX - 1] + "…"


@dataclass
class BreakerState:
    key: str
    label: str
    tripped: bool = False
    consecutive_failures: int = 0
    last_reason: str | None = None
    tripped_at: datetime | None = None
    updated_at: datetime | None = None
    counted: list[str] = field(default_factory=list)

    def dump(self) -> dict[str, Any]:
        """The API shape (race-app ``BreakerState``)."""
        return {
            "key": self.key,
            "label": self.label,
            "tripped": self.tripped,
            "consecutiveFailures": self.consecutive_failures,
            "lastReason": self.last_reason,
            "trippedAt": self.tripped_at.isoformat() if self.tripped_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


def _label(text: str | None) -> str:
    return (text or "").strip()[:LABEL_MAX] or "Automation"


def _counted(prev: list[str], task_id: str | None) -> list[str]:
    return [*prev, task_id][-COUNTED_MAX:] if task_id else list(prev)


def apply_failure(
    prev: BreakerState | None,
    key: str,
    label: str,
    reason: str,
    threshold: int,
    now: datetime,
    task_id: str | None = None,
) -> tuple[BreakerState, bool]:
    """The state after one failure, and whether this failure tripped it."""
    normal = normalise_reason(reason)
    same = prev is not None and prev.last_reason == normal and prev.consecutive_failures > 0
    count = prev.consecutive_failures + 1 if same else 1
    was_tripped = bool(prev and prev.tripped)
    tripping = not was_tripped and count >= threshold
    state = BreakerState(
        key=key,
        label=_label(label),
        tripped=was_tripped or tripping,
        consecutive_failures=count,
        last_reason=normal,
        tripped_at=now if tripping else (prev.tripped_at if was_tripped else None),
        updated_at=now,
        counted=_counted(prev.counted if prev else [], task_id),
    )
    return state, tripping


def apply_success(
    prev: BreakerState | None, key: str, label: str, now: datetime, task_id: str | None = None
) -> BreakerState | None:
    """The state after a success (count 0, not tripped); None = nothing to write."""
    if prev is None:
        return None
    if prev.consecutive_failures == 0 and not prev.tripped:
        return replace(prev, counted=_counted(prev.counted, task_id)) if task_id else None
    return BreakerState(
        key=key,
        label=_label(label),
        updated_at=now,
        counted=_counted(prev.counted, task_id),
    )


class Breaker:
    """The breaker of one tenant, over a :class:`Store` and a :class:`Notifier`."""

    def __init__(
        self,
        store: Store,
        notifier: Notifier,
        tenant_id: str,
        settings: BreakerSettings,
        now: datetime,
    ) -> None:
        self._store = store
        self._notifier = notifier
        self._tenant = tenant_id
        self._settings = settings
        self._now = now

    async def is_tripped(self, key: str) -> bool:
        """Automatic starts for *key* must stop (never while the breaker is disabled)."""
        if not self._settings.enabled:
            return False
        state = await self._store.get_breaker(self._tenant, key)
        return bool(state and state.tripped)

    async def record_failure(
        self, key: str, label: str, reason: str, task_id: str | None = None
    ) -> BreakerState | None:
        """Count one failure (each *task_id* once); notify when it trips."""
        if not self._settings.enabled:
            return None
        tripped_now = False

        def update(prev: BreakerState | None) -> BreakerState | None:
            nonlocal tripped_now
            if task_id and prev and task_id in prev.counted:
                return None
            state, tripped_now = apply_failure(
                prev, key, label, reason, self._settings.threshold, self._now, task_id
            )
            return state

        state = await self._store.update_breaker(self._tenant, key, update)
        if tripped_now and state is not None:
            logger.warning(
                "Automation breaker %s tripped after %d failures: %s",
                key,
                state.consecutive_failures,
                state.last_reason,
            )
            await self._notifier.publish(
                self._tenant,
                kind="breaker",
                title=f"Automation paused: {state.label} — {state.last_reason}"[:500],
                body=(
                    f"Automatic starts for {state.label} stopped after "
                    f"{state.consecutive_failures} identical failures: {state.last_reason}. "
                    "Manual starts still work; reset the breaker in Settings → Automation."
                ),
                data={"key": key, "reason": state.last_reason},
            )
        return state

    async def record_success(self, key: str, label: str, task_id: str | None = None) -> None:
        """A success resets the count and un-trips (each *task_id* once)."""
        if not self._settings.enabled:
            return

        def update(prev: BreakerState | None) -> BreakerState | None:
            if task_id and prev and task_id in prev.counted:
                return None
            return apply_success(prev, key, label, self._now, task_id)

        await self._store.update_breaker(self._tenant, key, update)

    async def observe(self, key: str, label: str, view: dict[str, Any] | None) -> None:
        """Feed a task's outcome: failed / needs review → failure, finished → success."""
        if not view:
            return
        reason = failure_reason(view)
        if reason is not None:
            await self.record_failure(key, label, reason, view.get("id"))
        elif finished(view):
            await self.record_success(key, label, view.get("id"))

    async def reset(self, key: str) -> BreakerState | None:
        """Owner reset: count 0, not tripped. None for an unknown key."""
        found: list[BreakerState] = []

        def update(prev: BreakerState | None) -> BreakerState | None:
            if prev is None:
                return None
            state = BreakerState(
                key=key, label=prev.label, updated_at=self._now, counted=prev.counted
            )
            found.append(state)
            return state

        await self._store.update_breaker(self._tenant, key, update)
        return found[0] if found else None
