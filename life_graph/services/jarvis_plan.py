"""The phone's Plan screen: the next days, one row each (life-graph-android docs/PLAN-v4.md, S2).

``GET /jarvis/plan?days=N`` (api/jarvis.py) reads each source on its own here,
as the Today screen does (services/jarvis_today.py), then :func:`assemble`
puts every item on its day in the owner's time zone. A source that fails is
``None`` and only its kind is empty; the failure is logged at debug level by
source name and exception type only.

Sources: calendar events (the connector store, as ``/connectors/today``),
bills and renewals from mail (connectors/bills.bills_due), documents
expiring, Jarvis's timed reminders (Intention rows with a time trigger) and
Google Tasks with a due date. Connector rows pass ``phone_rows`` first: a
``local_only`` account's items show when and what kind only.

bills_due looks a week ahead for bills and two weeks for renewals, so a
longer plan shows no bill further out than that.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

MIN_DAYS = 1
MAX_DAYS = 31
DEFAULT_DAYS = 7
MAX_EVENTS = 500
MAX_REMINDERS = 300
BILL_KINDS = ("bill", "renewal")


async def _read(name: str, fn: Callable[[], Awaitable[Any]]) -> Any:
    """``await fn()``, or None when it fails: one broken source never fails the plan."""
    try:
        return await fn()
    except Exception as exc:  # noqa: BLE001 - every failure is this kind's empty list
        logger.debug("plan: %s unavailable (%s)", name, type(exc).__name__)
        return None


# ── Sources: one query (or service call) each, tenant-scoped ────────────────


async def _events(tenant_id: str, first: date, days: int) -> list[dict[str, Any]]:
    from life_graph.connectors import store
    from life_graph.connectors.exposure import phone_rows, view_items
    from life_graph.connectors.locality import LOCAL
    from life_graph.connectors.tools import day_bounds
    from life_graph.storage.database import async_session

    start, end = day_bounds(first, days)
    async with async_session() as session:
        rows = await store.events_between(session, tenant_id, start, end, limit=MAX_EVENTS)
    return view_items(phone_rows(rows), LOCAL)["items"]


async def _bills(tenant_id: str, today: date) -> list[dict[str, Any]]:
    from life_graph.connectors.bills import bills_due
    from life_graph.connectors.exposure import phone_rows, view_bills
    from life_graph.connectors.locality import LOCAL
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = await bills_due(session, tenant_id, today)
    return view_bills(phone_rows(rows), LOCAL)["items"]


async def _documents(tenant_id: str, today: date, days: int) -> list[dict[str, Any]]:
    from life_graph.services import documents
    from life_graph.storage.database import async_session

    async with async_session() as session:
        docs = await documents.expiring(session, tenant_id, today, within_days=days)
    return [documents.to_dict(d, today) for d in docs]


def _reminders_query(tenant_id: str, first: date, days: int):
    """Pending timed reminders inside the plan's days."""
    from life_graph.connectors.tools import day_bounds
    from life_graph.models.db import Intention

    start, end = day_bounds(first, days)
    return (
        select(Intention)
        .where(
            Intention.tenant_id == tenant_id,
            Intention.trigger_type == "time",
            Intention.status == "pending",
            Intention.trigger_time >= start,
            Intention.trigger_time < end,
        )
        .order_by(Intention.trigger_time)
        .limit(MAX_REMINDERS)
    )


async def _reminders(tenant_id: str, first: date, days: int) -> list[dict[str, Any]]:
    from life_graph.connectors.tools import user_tz
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = (await session.execute(_reminders_query(tenant_id, first, days))).scalars().all()
    tz = user_tz()
    return [
        {"id": str(it.id), "text": it.content, "at": it.trigger_time.astimezone(tz).isoformat()}
        for it in rows
        if it.trigger_time is not None
    ]


async def _tasks(tenant_id: str) -> list[dict[str, Any]]:
    from life_graph.connectors import store
    from life_graph.connectors.exposure import phone_rows, view_items
    from life_graph.connectors.locality import LOCAL
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = await store.task_items(session, tenant_id)
    return view_items(phone_rows(rows), LOCAL)["items"]


async def collect(tenant_id: str, today: date, days: int) -> dict[str, Any]:
    """Every source, each read on its own; a failed one is None."""
    return {
        "events": await _read("events", lambda: _events(tenant_id, today, days)),
        "bills": await _read("bills", lambda: _bills(tenant_id, today)),
        "documents": await _read("documents", lambda: _documents(tenant_id, today, days)),
        "reminders": await _read("reminders", lambda: _reminders(tenant_id, today, days)),
        "tasks": await _read("tasks", lambda: _tasks(tenant_id)),
    }


# ── Assembly: pure, from whatever the sources gave ──────────────────────────


def _local_day(value: str | None, tz) -> date | None:
    """The owner's date of an ISO timestamp, or of a bare ``YYYY-MM-DD``."""
    if not value:
        return None
    if len(value) == 10:
        return date.fromisoformat(value)
    return datetime.fromisoformat(value).astimezone(tz).date()


def _event_days(e: dict[str, Any], days: list[date], tz) -> list[date]:
    """The plan days an event is on: every day it overlaps, end exclusive.

    An all-day event is stored from local midnight to the next one, so a
    one-day holiday is on one day, not two.
    """
    from life_graph.connectors.tools import day_bounds

    starts = datetime.fromisoformat(e["starts_at"])
    ends = datetime.fromisoformat(e["ends_at"]) if e.get("ends_at") else starts
    on = []
    for d in days:
        lo, hi = day_bounds(d)
        if (starts < hi and ends > lo) or (ends <= starts and lo <= starts < hi):
            on.append(d)
    return on


def _event_row(e: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": e.get("id"),
        "title": e.get("title"),
        "start": e.get("starts_at"),
        "end": e.get("ends_at"),
        "where": e.get("location"),
        "all_day": bool(e.get("all_day")),
        "account": e.get("account"),
    }


def _bill_row(b: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": b.get("id"),
        "kind": b.get("kind"),
        "title": b.get("payee") or "A bill",
        "amount": b.get("amount"),
        "currency": b.get("currency"),
        "autopay": bool(b.get("autopay")),
    }


def _document_row(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": d.get("id"),
        "kind": "document",
        "title": d.get("title") or "A document",
        "amount": None,
        "currency": None,
        "autopay": False,
    }


def _task_row(t: dict[str, Any], due: date) -> dict[str, Any]:
    return {
        "id": t.get("id"),
        "title": t.get("title") or "A to-do",
        "list": t.get("list"),
        "due": due.isoformat(),
    }


def _place(
    name: str, rows: list[dict[str, Any]] | None, put: Callable[[dict[str, Any]], None]
) -> None:
    """Put each row on its day; a malformed row is skipped, the rest still show."""
    for row in rows or []:
        try:
            put(row)
        except (KeyError, TypeError, ValueError) as exc:
            logger.debug("plan: a %s row was skipped (%s)", name, type(exc).__name__)


def assemble(src: dict[str, Any], today: date, days: int, tz) -> dict[str, Any]:
    """``{"days": [...]}``: one row per day from *today*, empty days included."""
    dates = [today + timedelta(days=n) for n in range(days)]
    by_day = {d: {"events": [], "due": [], "reminders": [], "tasks": []} for d in dates}

    def event(e: dict[str, Any]) -> None:
        for d in _event_days(e, dates, tz):
            by_day[d]["events"].append(_event_row(e))

    def bill(b: dict[str, Any]) -> None:
        d = _local_day(b.get("due"), tz)
        if b.get("kind") in BILL_KINDS and d in by_day:
            by_day[d]["due"].append(_bill_row(b))

    def document(doc: dict[str, Any]) -> None:
        d = _local_day(doc.get("expires_on"), tz)
        if d in by_day:
            by_day[d]["due"].append(_document_row(doc))

    def reminder(r: dict[str, Any]) -> None:
        d = _local_day(r.get("at"), tz)
        if d in by_day:
            by_day[d]["reminders"].append(r)

    def task(t: dict[str, Any]) -> None:
        if t.get("done") or t.get("parent") or not t.get("due"):
            return
        # Google keeps a task's due date as midnight UTC: the date is the date.
        d = date.fromisoformat(str(t["due"])[:10])
        if d in by_day:
            by_day[d]["tasks"].append(_task_row(t, d))

    _place("event", src.get("events"), event)
    _place("bill", src.get("bills"), bill)
    _place("document", src.get("documents"), document)
    _place("reminder", src.get("reminders"), reminder)
    _place("task", src.get("tasks"), task)
    return {"days": [{"date": d.isoformat(), **by_day[d]} for d in dates]}


async def plan(tenant_id: str, days: int = DEFAULT_DAYS, now: datetime | None = None) -> dict:
    from life_graph.connectors.tools import user_tz

    tz = user_tz()
    today = (now or datetime.now(UTC)).astimezone(tz).date()
    days = max(MIN_DAYS, min(int(days), MAX_DAYS))
    return assemble(await collect(tenant_id, today, days), today, days, tz)
