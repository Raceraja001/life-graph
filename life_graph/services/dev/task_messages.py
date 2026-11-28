"""Steering messages: the owner's notes to a queued or running dev task.

docs/specs/agent-drivers.md, "Steering messages (2026-11-28)". Headless coding
CLIs take no input mid-run, so a message is delivered at the next turn
boundary (the dispatcher's steering turn, drivers/steering.py) or, for a task
that has not started yet, appended to its instruction when it starts.

No table: the messages live in ``agent_tasks.properties.steer_messages``, a
list of ``{id, text, at, delivered_at, via, undelivered_reason}``. Every write
takes the task row's lock (``SELECT ... FOR UPDATE``) and rewrites the list in
that transaction, so two writers never lose each other's messages.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from life_graph.core.redaction import redact_secrets
from life_graph.models.db import AgentTask
from life_graph.services.dev import task_events

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

PROP = "steer_messages"
MAX_TEXT_CHARS = 4000
MAX_PENDING = 10
#: Delivered messages beyond this many are dropped, oldest first.
MAX_STORED = 100
_OPEN = frozenset({"queued", "running"})
_DEV_KIND = "dev_task"

CLAIM_START = "--- MESSAGES FROM THE OWNER (sent after this task was queued) ---"
CLAIM_END = "--- END OF THE OWNER'S MESSAGES ---"


class MessageError(Exception):
    """A message was refused; ``code`` names why, ``http_status`` for the API."""

    def __init__(self, code: str, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _pk(task_id: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(task_id))
    except ValueError:
        return None


def _messages(task: AgentTask) -> list[dict]:
    raw = (task.properties or {}).get(PROP)
    return [dict(m) for m in raw if isinstance(m, dict)] if isinstance(raw, list) else []


def pending(messages: list[dict]) -> list[dict]:
    """The messages not delivered yet, oldest first."""
    return [m for m in messages if not m.get("delivered_at")]


def public(message: dict) -> dict:
    """A message as ``GET .../messages`` shows it."""
    out = {
        "id": message.get("id"),
        "text": message.get("text") or "",
        "at": message.get("at"),
        "delivered_at": message.get("delivered_at"),
    }
    if message.get("via"):
        out["via"] = message["via"]
    if message.get("undelivered_reason") and not message.get("delivered_at"):
        out["undelivered_reason"] = message["undelivered_reason"]
    return out


def clean_text(text: str | None) -> str:
    """Trimmed and redacted, or a :class:`MessageError` (422)."""
    text = (text or "").strip()
    if not text:
        raise MessageError("empty", "The message is empty", 422)
    if len(text) > MAX_TEXT_CHARS:
        raise MessageError("too_long", f"A message is at most {MAX_TEXT_CHARS} characters", 422)
    return redact_secrets(text)


async def _locked(session: Any, tenant_id: str, pk: uuid.UUID) -> AgentTask | None:
    task = await session.get(AgentTask, pk, with_for_update=True)
    if (
        not isinstance(task, AgentTask)
        or task.tenant_id != tenant_id
        or (task.properties or {}).get("kind") != _DEV_KIND
    ):
        return None
    return task


def _store(task: AgentTask, messages: list[dict]) -> None:
    done = [m for m in messages if m.get("delivered_at")]
    drop = {id(m) for m in done[: max(0, len(messages) - MAX_STORED)]}
    props = dict(task.properties or {})
    props[PROP] = [m for m in messages if id(m) not in drop]
    task.properties = props


async def queue_message(
    session_factory: Callable[[], Any], tenant_id: str, task_id: str, text: str
) -> dict[str, Any]:
    """Queue *text* for *task_id*; ``{queued: <undelivered count>, id}``.

    Raises :class:`MessageError`: ``empty`` / ``too_long`` 422, ``not_found``
    404, ``not_running`` 409 (not queued or running), ``too_many`` 409.
    """
    clean = clean_text(text)
    pk = _pk(task_id)
    if pk is None:
        raise MessageError("not_found", "Dev task not found", 404)
    async with session_factory() as session:
        task = await _locked(session, tenant_id, pk)
        if task is None:
            raise MessageError("not_found", "Dev task not found", 404)
        if task.status not in _OPEN:
            raise MessageError(
                "not_running", f"Dev task is {task.status}; messages reach queued or running tasks"
            )
        messages = _messages(task)
        waiting = pending(messages)
        if len(waiting) >= MAX_PENDING:
            raise MessageError(
                "too_many", f"{MAX_PENDING} messages are already waiting to be delivered"
            )
        message = {"id": str(uuid.uuid4()), "text": clean, "at": _now(), "delivered_at": None}
        messages.append(message)
        _store(task, messages)
        status = task.status
        await session.commit()
    count = len(waiting) + 1
    task_events.emit(
        tenant_id, str(pk), "steer", f"owner message queued ({count} waiting)",
        data={"state": "queued", "ids": [message["id"]], "pending": count, "task_status": status},
        source="api",
    )  # fmt: skip
    return {"queued": count, "id": message["id"]}


async def list_messages(
    session_factory: Callable[[], Any], tenant_id: str, task_id: str
) -> list[dict] | None:
    """Every message of *task_id*, oldest first; None for no such dev task."""
    pk = _pk(task_id)
    if pk is None:
        return None
    async with session_factory() as session:
        task = await session.get(AgentTask, pk)
        if (
            not isinstance(task, AgentTask)
            or task.tenant_id != tenant_id
            or (task.properties or {}).get("kind") != _DEV_KIND
        ):
            return None
        return [public(m) for m in _messages(task)]


async def read_pending(
    session_factory: Callable[[], Any], tenant_id: str, task_id: Any
) -> list[dict]:
    """The undelivered messages of *task_id*. Never raises: [] on any failure
    (a throwaway dispatch id, no database in a test)."""
    pk = _pk(task_id)
    if pk is None:
        return []
    try:
        async with session_factory() as session:
            task = await session.get(AgentTask, pk)
            if not isinstance(task, AgentTask) or task.tenant_id != tenant_id:
                return []
            return pending(_messages(task))
    except Exception:
        logger.debug("Could not read the messages of task %s", task_id, exc_info=True)
        return []


async def settle(
    session_factory: Callable[[], Any],
    tenant_id: str,
    task_id: Any,
    ids: list[str],
    *,
    via: str,
    reason: str | None = None,
) -> bool:
    """Mark *ids* delivered (``via`` = instruction / turn / continue), or, with
    *reason*, note why they are still undelivered. Best-effort: False when the
    write failed."""
    pk = _pk(task_id)
    if pk is None or not ids:
        return False
    wanted = set(ids)
    try:
        async with session_factory() as session:
            task = await _locked(session, tenant_id, pk)
            if task is None:
                return False
            messages = _messages(task)
            now = _now()
            for m in messages:
                if m.get("id") not in wanted or m.get("delivered_at"):
                    continue
                if reason is None:
                    m["delivered_at"], m["via"] = now, via
                    m.pop("undelivered_reason", None)
                else:
                    m["undelivered_reason"] = reason[:300]
            _store(task, messages)
            await session.commit()
            return True
    except Exception:
        logger.warning("Could not record the messages of task %s", task_id, exc_info=True)
        return False


def _numbered(messages: list[dict]) -> str:
    return "\n".join(f"{i}. {m.get('text') or ''}" for i, m in enumerate(messages, 1))


def claim_block(messages: list[dict]) -> str:
    """The block appended to a task's instruction when it starts."""
    return f"\n\n{CLAIM_START}\n{_numbered(messages)}\n{CLAIM_END}"


def steer_text(messages: list[dict]) -> str:
    """The prompt of a steering turn."""
    return (
        "The owner sent these messages while you were working on this task:\n\n"
        f"{_numbered(messages)}\n\n"
        "Your changes so far are in this working tree; build on them, do not start over. "
        "Take the messages into account, finish the task, then stop."
    )
