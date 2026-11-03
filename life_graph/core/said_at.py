"""When the owner said what is being processed, for a capture delivered late.

The Claude Code hook queues captures while the API is down and sends them later;
on 2026-11-02 2,844 arrived at once, the oldest from 13 Oct. Each capture keeps
its own time (``occurred_at``, #219), but extraction told the model "Today is"
the delivery day and memories were dated on arrival, so an old "I live in
Madurai" would read as newer than "we moved to Coimbatore" and replace it.

The capture processor sets :data:`said_at` for a late capture only; extraction
(extraction/llm.py) and storage (core/memory_manager.py) read it. Unset means
now, which is every capture that arrives on time.
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import UTC, datetime, timedelta

#: Older than this on arrival is late: an ordinary capture takes seconds.
LATE = timedelta(minutes=10)

said_at: ContextVar[datetime | None] = ContextVar("said_at", default=None)


def late(at: datetime | None) -> datetime | None:
    """*at* when a capture from then is arriving late, else None."""
    if at is None:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return at if datetime.now(UTC) - at > LATE else None
