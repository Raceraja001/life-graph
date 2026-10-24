"""What a Jarvis run saved itself, so the capture extractor does not save it again.

On the phone app (``capture_saved_by_tool_surfaces``) the owner's message is
captured (api/jarvis.py ``_capture``) just before Jarvis's run for it starts,
and the two learn from the same words: Jarvis with ``memory_save``, the
capture extractor with its own facts. Dropping only the extractor's
``explicit_save`` facts (#139) was not enough either way. The extractor often
labels "remember that my bike service is due on 3 November" a plain ``fact``,
so a reworded copy still landed pending next to Jarvis's save (2026-10-24);
and when Jarvis did not call ``memory_save`` at all, the request was dropped
and nothing was saved.

So each capture is settled by what its run actually saved:

* :func:`run_saves` finds the run — a top-level ``AgentTask`` of the capture's
  tenant (and conversation, when the capture knows it), created around the
  capture, whose owner message is the captured text — waits a bounded time for
  it to finish, and returns what ``memory_save`` stored in it (tagged
  ``properties.task_id``). ``None`` means it is not finished yet: the caller
  leaves the capture ``received`` and the capture sweep retries it later
  (workers/capture_sweep.py, after 15 minutes), when it is settled with
  whatever the run saved by then. A capture with no run to be found is
  settled as "nothing saved".
* :func:`drop_saved` drops extracted facts close in meaning to one of those
  memories (cosine >= :data:`SIMILAR`). If the run saved nothing, every fact
  is kept, ``explicit_save`` included, and the memory manager's existing rule
  makes that one active at once.

Nothing here logs memory or message content.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.storage.database import async_session

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from life_graph.extraction.rules import ExtractedFact

logger = logging.getLogger(__name__)

#: Cosine similarity at which an extracted fact counts as the run's own save.
SIMILAR = 0.85
#: Run states after which nothing more is saved (api/jarvis.py ``_TERMINAL``).
TERMINAL = frozenset({"completed", "failed", "timeout", "cancelled"})
#: How far before and after the capture its run may have been created. The run
#: is spawned right after the capture; the slack covers clock skew.
BEFORE = timedelta(seconds=30)
AFTER = timedelta(minutes=5)
#: Younger than this, a capture whose run has not finished waits for the sweep
#: (which only picks captures over 15 minutes old). Older — that is, the sweep
#: itself — it is settled with what the run saved so far.
DEFER_WITHIN = timedelta(minutes=10)
#: Seconds between looks while waiting for the run.
POLL_SECONDS = 2.0
#: Leading characters of a shared capture looked for in the run's message.
_SHARED_PROBE = 200


@dataclass(frozen=True)
class SavedMemory:
    id: uuid.UUID
    content: str
    embedding: list[float] | None


def _captured_at(capture_evt: Any) -> datetime:
    at = getattr(capture_evt, "created_at", None) or getattr(capture_evt, "occurred_at", None)
    return at if isinstance(at, datetime) else datetime.now(UTC)


def _conversation_of(capture_evt: Any) -> uuid.UUID | None:
    properties = getattr(capture_evt, "properties", None) or {}
    try:
        return uuid.UUID(str(properties["conversation_id"]))
    except (KeyError, TypeError, ValueError):
        return None


def is_run_for(task_input: dict[str, Any] | None, capture_evt: Any) -> bool:
    """Whether a run with *task_input* was started from this capture's words."""
    inp = task_input or {}
    content = " ".join(str(getattr(capture_evt, "content", "") or "").split())
    if not content:
        return False
    properties = getattr(capture_evt, "properties", None) or {}
    if properties.get("input") == "shared":
        # Shared text goes to the run inside a fence after the owner's message
        # (core/trust.py with_shared); the capture holds it alone.
        message = " ".join(str(inp.get("message") or "").split())
        return content[:_SHARED_PROBE] in message
    owner = " ".join(str(inp.get("owner_message", inp.get("message")) or "").split())
    # _capture keeps the first 8,000 characters.
    return bool(owner) and owner[: len(content)] == content


async def _find_run(capture_evt: Any, tenant_id: str) -> Any | None:
    from life_graph.models.db import AgentTask

    at = _captured_at(capture_evt)
    query = select(AgentTask).where(
        AgentTask.tenant_id == tenant_id,
        AgentTask.parent_task_id.is_(None),
        AgentTask.created_at >= at - BEFORE,
        AgentTask.created_at <= at + AFTER,
    )
    if (conversation := _conversation_of(capture_evt)) is not None:
        query = query.where(AgentTask.session_id == conversation)
    async with async_session() as session:
        rows = (
            (await session.execute(query.order_by(AgentTask.created_at).limit(20))).scalars().all()
        )
    return next((t for t in rows if is_run_for(t.input, capture_evt)), None)


async def _saved_in(task_id: uuid.UUID, tenant_id: str) -> list[SavedMemory]:
    """What memory_save stored in this run and was not since taken back."""
    from life_graph.models.db import Memory

    async with async_session() as session:
        rows = (
            await session.execute(
                select(Memory.id, Memory.content, Memory.embedding).where(
                    Memory.tenant_id == tenant_id,
                    Memory.properties["task_id"].astext == str(task_id),
                    Memory.status.in_(("active", "pending")),
                )
            )
        ).all()
    return [
        SavedMemory(id=r[0], content=r[1], embedding=list(r[2]) if r[2] is not None else None)
        for r in rows
    ]


async def run_saves(
    capture_evt: Any, tenant_id: str, *, wait_seconds: float
) -> list[SavedMemory] | None:
    """What the capture's Jarvis run saved; ``None`` while it should wait for the sweep.

    Waits up to *wait_seconds* for the run to appear and finish. Runs on the
    event bus, off the request path; it holds no DB connection while waiting.
    """
    deferrable = datetime.now(UTC) - _captured_at(capture_evt) < DEFER_WITHIN
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, wait_seconds)
    run = None
    while True:
        run = await _find_run(capture_evt, tenant_id)
        if run is not None and run.status in TERMINAL:
            break
        if loop.time() >= deadline:
            break
        await asyncio.sleep(POLL_SECONDS)
    if run is None or run.status not in TERMINAL:
        if deferrable:
            logger.debug(
                "Capture %s: its Jarvis run is not finished (%s); left for the sweep",
                getattr(capture_evt, "id", None),
                run.status if run is not None else "not found",
            )
            return None
        if run is None:
            return []
    return await _saved_in(run.id, tenant_id)


def _same_words(a: str, b: str) -> bool:
    return " ".join(a.lower().split()).rstrip(".") == " ".join(b.lower().split()).rstrip(".")


async def drop_saved(
    facts: list[ExtractedFact],
    saved: list[SavedMemory],
    embed: Callable[[str], Awaitable[list[float] | None]],
) -> list[ExtractedFact]:
    """*facts* without those the run already saved (close in meaning to one of *saved*).

    A fact that cannot be compared (no embedding) is kept, unless it is an
    ``explicit_save``: the run did save what was asked, and that is the
    extractor's most likely copy of it.
    """
    if not saved or not facts:
        return list(facts)
    from life_graph.services.recall import _cosine

    vectors = [s.embedding or await embed(s.content) for s in saved]
    kept: list[ExtractedFact] = []
    for fact in facts:
        if any(_same_words(fact.content, s.content) for s in saved):
            continue
        vector = await embed(fact.content)
        if not vector or not any(vectors):
            if fact.fact_type != "explicit_save":
                kept.append(fact)
            continue
        scores = [_cosine(vector, v) for v in vectors if v]
        if any(s is not None and s >= SIMILAR for s in scores):
            continue
        kept.append(fact)
    return kept
