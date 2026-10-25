"""Buttons on the phone's notifications (life-graph-android docs/PLAN-v3.md).

``GET /jarvis/notifications`` gives each notification a ``kind`` and the
``actions`` it offers; ``POST /jarvis/notifications/{id}/action`` performs one
(api/jarvis.py). What a notification is comes from what wrote it:

* services/due_notifications.py rows (``source_type="due_item"``) name the
  item in their metadata (``item``, ``item_id``): bill, task, document,
  reminder. Rows written before ``item_id`` was stored are "other", without
  buttons: there is nothing for a button to find.
* the daily brief (services/brief.py, ``source_type="brief"``): "Listen".

An action is taken once: it is recorded in the notification's metadata
(``action``), and a second tap gets "Already done." Listen is the exception:
it only opens the app, so it changes nothing and may be tapped again.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

ITEM_KINDS = ("bill", "task", "document", "reminder")
SNOOZE_DAY_HOUR = 9  # "Tomorrow" means 09:00 tomorrow, in the owner's day

#: Per kind, the buttons in the order the phone shows them (at most 3).
ACTIONS: dict[str, list[tuple[str, str]]] = {
    "bill": [("paid", "Paid"), ("snooze_1d", "Tomorrow")],
    "reminder": [("done", "Done"), ("snooze_1h", "In 1 hour"), ("snooze_1d", "Tomorrow")],
    "task": [("snooze_1d", "Tomorrow")],
    "document": [],
    "brief": [("listen", "Listen")],
    "other": [],
}
LISTEN_RESULT = "Open Jarvis to listen."
ALREADY_DONE = "Already done."
NOT_OFFERED = "That button isn't offered for this notification."


class ActionRefusedError(Exception):
    """The action cannot be taken; the message is a sentence for the owner (409)."""


class ActionNotFoundError(Exception):
    """What the notification points at is gone (404)."""


def utcnow() -> datetime:
    """The action endpoint's clock (a seam for tests that run the due job at a set time)."""
    return datetime.now(UTC)


def kind_of(source_type: str | None, meta: dict[str, Any] | None) -> str:
    from life_graph.services.due_notifications import SOURCE_TYPE

    meta = meta or {}
    if source_type == "brief":
        return "brief"
    if source_type == SOURCE_TYPE and meta.get("item") in ITEM_KINDS and meta.get("item_id"):
        return meta["item"]
    return "other"


def taken(meta: dict[str, Any] | None) -> bool:
    return bool((meta or {}).get("action"))


def actions_for(kind: str, meta: dict[str, Any] | None) -> list[dict[str, str]]:
    """The buttons to show; none once an action has been taken (bar Listen)."""
    if kind != "brief" and taken(meta):
        return []
    return [{"id": a, "label": label} for a, label in ACTIONS.get(kind, [])]


def offered(kind: str, action: str) -> bool:
    return any(a == action for a, _ in ACTIONS.get(kind, []))


def snooze_until(action: str, now: datetime, tz: Any) -> datetime:
    """When a snoozed item comes back: an hour from now, or 09:00 tomorrow."""
    if action == "snooze_1h":
        return (now + timedelta(hours=1)).astimezone(tz)
    tomorrow = now.astimezone(tz).date() + timedelta(days=1)
    return datetime.combine(tomorrow, time(SNOOZE_DAY_HOUR, 0), tzinfo=tz)


def result_for(action: str, *, at: datetime | None, now: datetime, tz: Any) -> str:
    """The plain sentence the phone shows in place of the notification."""
    from life_graph.services.reminders import say_when

    if action == "paid":
        return "Marked paid."
    if action == "done":
        return "Done."
    if action == "listen":
        return LISTEN_RESULT
    if at is not None:
        return f"I'll remind you {say_when(at, now, tz)}."
    return "Done."


async def perform(
    session: AsyncSession, tenant_id: str, notification: Any, action: str, now: datetime, tz: Any
) -> str:
    """Take *action* on *notification* (already this tenant's, locked by the caller).

    Returns the result sentence; raises ActionRefusedError (409) or ActionNotFoundError
    (404). The caller commits.
    """
    meta = dict(notification.extra_metadata or {})
    kind = kind_of(notification.source_type, meta)
    if not offered(kind, action):
        raise ActionRefusedError(NOT_OFFERED)
    if action == "listen":
        return LISTEN_RESULT
    if taken(meta):
        raise ActionRefusedError(ALREADY_DONE)
    at = None
    if action == "paid":
        await _paid(session, tenant_id, meta["item_id"], now)
    elif kind == "reminder":
        at = await _reminder(session, tenant_id, meta["item_id"], action, now, tz)
    else:  # snooze_1d on a bill or to-do
        from life_graph.services.due_notifications import snooze_metadata

        at = snooze_until(action, now, tz)
        meta = snooze_metadata(meta, at, notification.id)
    meta["action"] = {"id": action, "at": now.astimezone(UTC).isoformat()}
    notification.extra_metadata = meta  # a new dict, so the JSONB change is saved
    notification.is_read = True
    return result_for(action, at=at, now=now, tz=tz)


async def _paid(session: AsyncSession, tenant_id: str, item_id: str, now: datetime) -> None:
    from life_graph.connectors.bills import mark_paid

    if await mark_paid(session, tenant_id, item_id, now) is None:
        raise ActionNotFoundError("That bill is gone.")


async def _reminder(
    session: AsyncSession, tenant_id: str, item_id: str, action: str, now: datetime, tz: Any
) -> datetime | None:
    """Done, or a new time for the reminder. Returns the new time when snoozed."""
    from sqlalchemy import select

    from life_graph.models.db import Intention

    try:
        ident = uuid.UUID(str(item_id))
    except ValueError:
        raise ActionNotFoundError("That reminder is gone.") from None
    row = (
        await session.execute(
            select(Intention)
            .where(Intention.tenant_id == tenant_id, Intention.id == ident)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise ActionNotFoundError("That reminder is gone.")
    if row.status == "completed":
        raise ActionRefusedError(ALREADY_DONE)
    if row.status != "pending":
        raise ActionRefusedError("That reminder was cancelled.")
    if action == "done":
        row.status, row.completed_at = "completed", now
        return None
    at = snooze_until(action, now, tz)
    # A new time is a new dedup key (due_notifications.reminder_items): it is
    # posted again when that time comes.
    row.trigger_time = at
    return at
