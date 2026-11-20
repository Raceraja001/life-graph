"""The live session log of a dev task (work order Stage 4).

Writers anywhere in the run — the runner, the dispatcher's stages, the
claude_code driver as its CLI streams, the task runtime, the verifier chain —
call :func:`emit`. It never blocks and never fails the caller: events go onto
one in-process queue, and a single consumer writes them in order, in batches,
to ``dev_task_events`` with a per-task ``seq``. Readers ask for "everything
after N" (:func:`read_events`), optionally waiting for new ones
(:func:`wait_for_events`, the long-poll the dashboard uses), so a viewer that
drops and reconnects resumes exactly where it was.

Every event's text is redacted (services/redaction.py) and capped before it is
stored; a task keeps at most ``MAX_EVENTS_PER_TASK`` events, then one
``truncated`` marker. Readers are tenant-checked by the API, never here.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from life_graph.services.redaction import redact

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 4000
MAX_DATA_CHARS = 8000
MAX_EVENTS_PER_TASK = 5000
TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "timeout", "merged", "closed", "landed"}
)

_queue: asyncio.Queue | None = None
_consumer: asyncio.Task | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
# Tasks already at the cap (in this process): one marker, then silence.
_capped: set[str] = set()


def configure(session_factory: async_sessionmaker[AsyncSession] | None) -> None:
    """Point the writer at a session factory (tests use their own)."""
    global _session_factory
    _session_factory = session_factory


def _sf() -> async_sessionmaker[AsyncSession]:
    if _session_factory is not None:
        return _session_factory
    from life_graph.storage.database import async_session

    return async_session


def _clean_data(data: dict | None) -> dict:
    if not data:
        return {}
    try:
        raw = json.dumps(data, default=str)
    except (TypeError, ValueError):
        return {"unserializable": True}
    raw = redact(raw).replace("\\u0000", "")
    if len(raw) > MAX_DATA_CHARS:
        return {"truncated": True, "original_chars": len(raw)}
    try:
        return json.loads(raw)
    except ValueError:
        return {"redaction_broke_json": True}


def emit(
    tenant_id: str | None,
    task_id: Any,
    kind: str,
    content: str = "",
    *,
    data: dict | None = None,
    source: str = "runner",
) -> None:
    """Queue one event for *task_id*. Never raises, never blocks."""
    global _queue, _consumer
    if not tenant_id or not task_id:
        return
    try:
        tid = str(uuid.UUID(str(task_id)))
    except ValueError:
        return  # throwaway dispatch ids (the test endpoint) have no row
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _queue is None or _consumer is None or _consumer.done() or _consumer.get_loop() is not loop:
        _queue = asyncio.Queue()
        _consumer = loop.create_task(_consume(_queue), name="dev-task-events")
    raw = str(content or "")
    # Truncate first (bounded work on the event loop), then redact; NUL cannot
    # be stored by Postgres in text or jsonb.
    body = redact(raw[: MAX_CONTENT_CHARS * 2]).replace("\x00", "")
    event = {
        "tenant_id": str(tenant_id),
        "task_id": tid,
        "kind": str(kind)[:32],
        "source": str(source)[:32],
        "content": body[:MAX_CONTENT_CHARS],
        "data": {
            **_clean_data(data),
            **({"original_chars": len(raw)} if len(raw) > MAX_CONTENT_CHARS else {}),
        },
    }
    _queue.put_nowait(event)


async def flush(timeout: float = 10.0) -> None:
    """Wait until everything emitted so far is written (end of a run, tests)."""
    if _queue is None:
        return
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(_queue.join(), timeout=timeout)


async def _consume(queue: asyncio.Queue) -> None:
    while True:
        batch = [await queue.get()]
        # Whatever else is already waiting goes in the same transaction.
        while not queue.empty() and len(batch) < 200:
            batch.append(queue.get_nowait())
        try:
            await _write(batch)
        except Exception:
            logger.warning("Could not write %d dev task event(s)", len(batch), exc_info=True)
        finally:
            for _ in batch:
                queue.task_done()


_INSERT = text(
    """
    INSERT INTO dev_task_events (tenant_id, task_id, seq, kind, source, content, data)
    SELECT :tenant_id, CAST(:task_id AS uuid),
           coalesce(max(seq), 0) + 1, :kind, :source, :content, CAST(:data AS jsonb)
    FROM dev_task_events WHERE task_id = CAST(:task_id AS uuid)
    RETURNING seq
    """
)


async def _write(batch: list[dict]) -> None:
    # One consumer per process writes in order; the unique (task_id, seq)
    # constraint catches another process writing the same task at the same
    # moment (the API recording a cancel request while the worker streams),
    # and that one event is retried with the next number.
    async with _sf()() as session:
        for event in batch:
            tid = event["task_id"]
            if tid in _capped:
                continue
            params = {**event, "data": json.dumps(event["data"])}
            seq = await _insert_one(session, params)
            if seq >= MAX_EVENTS_PER_TASK:
                _capped.add(tid)
                marker = {
                    **params,
                    "kind": "truncated",
                    "source": "events",
                    "content": f"event log capped at {MAX_EVENTS_PER_TASK} events",
                    "data": "{}",
                }
                await _insert_one(session, marker)
        await session.commit()


async def _insert_one(session, params: dict) -> int:
    """Insert one event; 0 when it was dropped. Never raises.

    One event that cannot be stored (no task row, a value Postgres rejects)
    is skipped on its own savepoint -- it must not take the rest of the batch
    with it.
    """
    for attempt in range(3):
        try:
            async with session.begin_nested():
                return (await session.execute(_INSERT, params)).scalar_one()
        except Exception as exc:  # best-effort: a dropped event row never fails the run
            if "uq_dev_task_events_task_seq" in str(exc) and attempt < 2:
                continue
            if "foreign key" not in str(exc).lower():
                logger.warning("Dropped a dev task event: %s", str(exc)[:200])
            return 0
    return 0


async def read_events(
    session: AsyncSession, tenant_id: str, task_id: str, *, after: int = 0, limit: int = 200
) -> list[dict]:
    rows = await session.execute(
        text(
            "SELECT seq, kind, source, content, data, created_at FROM dev_task_events"
            " WHERE tenant_id = :tenant AND task_id = CAST(:task AS uuid) AND seq > :after"
            " ORDER BY seq LIMIT :limit"
        ),
        {"tenant": tenant_id, "task": task_id, "after": int(after), "limit": int(limit)},
    )
    return [
        {
            "seq": r.seq,
            "kind": r.kind,
            "source": r.source,
            "content": r.content,
            "data": r.data or {},
            "at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def task_status(session: AsyncSession, tenant_id: str, task_id: str) -> str | None:
    row = (
        await session.execute(
            text(
                "SELECT status FROM agent_tasks WHERE id = CAST(:task AS uuid)"
                " AND tenant_id = :tenant"
            ),
            {"task": task_id, "tenant": tenant_id},
        )
    ).first()
    return row[0] if row else None


async def wait_for_events(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    task_id: str,
    *,
    after: int = 0,
    limit: int = 200,
    wait: float = 0.0,
    poll: float = 0.5,
) -> tuple[list[dict], str | None]:
    """Events after *after*, waiting up to *wait* seconds for the first new one.

    Returns ``(events, status)``. Stops waiting as soon as the task is in a
    terminal status (nothing more will come). The writer may be in another
    process, so this polls the table (an index lookup), not a local signal.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, wait)
    while True:
        async with session_factory() as session:
            events = await read_events(session, tenant_id, task_id, after=after, limit=limit)
            status = await task_status(session, tenant_id, task_id)
        if events or status is None or status in TERMINAL_STATUSES or loop.time() >= deadline:
            return events, status
        await asyncio.sleep(poll)


async def expire(session_factory: async_sessionmaker[AsyncSession], days: int) -> int:
    """Delete events older than *days* (maintenance; all tenants)."""
    async with session_factory() as session:
        res = await session.execute(
            text(
                "DELETE FROM dev_task_events WHERE created_at < now() - make_interval(days => :d)"
            ),
            {"d": int(days)},
        )
        await session.commit()
        return res.rowcount or 0
