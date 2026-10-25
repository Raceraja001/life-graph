"""The phone's Today screen in one call (life-graph-android docs/PLAN-v4.md, S1).

``GET /jarvis/today`` (api/jarvis.py) reads each source on its own here, then
:func:`assemble` builds the screen from what came back. A source that fails
is ``None``: its part of the screen is null or empty, and the rest still
shows. The failure is logged at debug level by source name and exception
type only: the rows are the owner's mail, bills and memories.

The phone is the owner's own screen, like the dashboard, so connector items
use the LOCAL rendering (connectors/exposure.py): amounts and titles shown,
``local_only`` accounts included.

Insights are fixed rules, no model: a bill due tomorrow (with "Mark paid",
``POST /jarvis/bills/{item_id}/paid``), a document expiring within
INSIGHT_DOC_DAYS, a contact's birthday tomorrow.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

DUE_DAYS = 7  # "Due this week": documents and to-dos due within this many days
INSIGHT_DOC_DAYS = 7
MAX_INSIGHTS = 5
MAX_LEARNT_PENDING = 3
MAX_LEARNT_KEPT = 2
LEARNT_KEPT_HOURS = 48  # "Jarvis learnt" shows memories kept this recently
MAX_MAIL_WAITING = 100
MAX_BRIEF_HEADINGS = 6
BILL_KINDS = ("bill", "renewal")


async def _read(name: str, fn: Callable[[], Awaitable[Any]]) -> Any:
    """``await fn()``, or None when it fails: one broken source never fails the screen."""
    try:
        return await fn()
    except Exception as exc:  # noqa: BLE001 - every failure is this section's null
        logger.debug("today: %s unavailable (%s)", name, type(exc).__name__)
        return None


# ── Sources: one query (or service call) each, tenant-scoped ────────────────


async def _events(tenant_id: str, today: date) -> list[dict[str, Any]]:
    from life_graph.connectors import store
    from life_graph.connectors.exposure import view_items
    from life_graph.connectors.locality import LOCAL
    from life_graph.connectors.tools import day_bounds
    from life_graph.storage.database import async_session

    start, end = day_bounds(today)
    async with async_session() as session:
        rows = await store.events_between(session, tenant_id, start, end)
    return view_items(rows, LOCAL)["items"]


async def _bills(tenant_id: str, today: date) -> list[dict[str, Any]]:
    from life_graph.connectors.bills import bills_due
    from life_graph.connectors.exposure import view_bills
    from life_graph.connectors.locality import LOCAL
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = await bills_due(session, tenant_id, today)
    return view_bills(rows, LOCAL)["items"]


async def _documents(tenant_id: str, today: date) -> list[dict[str, Any]]:
    from life_graph.services import documents
    from life_graph.storage.database import async_session

    async with async_session() as session:
        docs = await documents.expiring(session, tenant_id, today, within_days=DUE_DAYS)
    return [documents.to_dict(d, today) for d in docs]


async def _todos(tenant_id: str) -> list[dict[str, Any]]:
    from life_graph.connectors import store
    from life_graph.connectors.exposure import view_items
    from life_graph.connectors.locality import LOCAL
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = await store.task_items(session, tenant_id)
    return view_items(rows, LOCAL)["items"]


async def _birthdays_tomorrow(tenant_id: str, today: date) -> list[dict[str, Any]]:
    from life_graph.connectors import store
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = await store.birthdays_between(session, tenant_id, today + timedelta(days=1), 1)
    return [{"id": r["id"], "name": r.get("title") or ""} for r in rows if r.get("title")]


async def _count(model_query) -> int:
    from life_graph.storage.database import async_session

    async with async_session() as session:
        return int(await session.scalar(model_query) or 0)


def _approvals_query(tenant_id: str):
    from life_graph.models.db import Approval

    return (
        select(func.count())
        .select_from(Approval)
        .where(Approval.tenant_id == tenant_id, Approval.status == "pending")
    )


def _to_review_query(tenant_id: str):
    from life_graph.models.db import Memory

    return (
        select(func.count())
        .select_from(Memory)
        .where(Memory.tenant_id == tenant_id, Memory.status == "pending")
    )


def _reminders_query(tenant_id: str, today: date):
    """Pending timed reminders for the rest of the owner's day (and any missed today)."""
    from life_graph.connectors.tools import day_bounds
    from life_graph.models.db import Intention

    start, end = day_bounds(today)
    return (
        select(func.count())
        .select_from(Intention)
        .where(
            Intention.tenant_id == tenant_id,
            Intention.trigger_type == "time",
            Intention.status == "pending",
            Intention.trigger_time >= start,
            Intention.trigger_time < end,
        )
    )


async def _brief(tenant_id: str) -> dict[str, Any] | None:
    from life_graph.config import settings
    from life_graph.models.db import Notification
    from life_graph.storage.database import async_session

    async with async_session() as session:
        row = (
            (
                await session.execute(
                    select(Notification)
                    .where(Notification.tenant_id == tenant_id, Notification.source_type == "brief")
                    .order_by(Notification.created_at.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
    if row is None:
        return None
    text = row.body or ""
    return {
        "id": str(row.id),
        "summary": brief_summary(text) or (row.title or ""),
        # GET /jarvis/brief/latest speaks it; without a speech server it is text only.
        "has_audio": bool(settings.tts_base_url and text.strip()),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def _money(tenant_id: str, today: date) -> dict[str, Any] | None:
    from life_graph.services import money
    from life_graph.storage.database import async_session

    async with async_session() as session:
        summary = await money.summary(session, tenant_id, None, today)
    return money_card(summary)


async def _mail_waiting(tenant_id: str, now: datetime) -> int:
    from life_graph.connectors import store
    from life_graph.storage.database import async_session

    async with async_session() as session:
        return len(await store.waiting_on_me(session, tenant_id, now, limit=MAX_MAIL_WAITING))


async def _night_run(tenant_id: str) -> dict[str, int]:
    from life_graph.services import night_shift
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rep = await night_shift.report(session, tenant_id)
    return night_run(rep)


async def _down(tenant_id: str) -> list[dict[str, Any]]:
    from life_graph.services import app_health
    from life_graph.storage.database import async_session

    async with async_session() as session:
        apps = await app_health.report(session, tenant_id)
    return [
        {"name": a["project"], "since": a.get("down_since")} for a in apps if a["status"] == "down"
    ]


async def _study_due(tenant_id: str, today: date) -> int:
    from life_graph.services import study
    from life_graph.storage.database import async_session

    async with async_session() as session:
        return int(await study.count_due(session, tenant_id, today))


async def _learnt(tenant_id: str, now: datetime) -> list[dict[str, Any]]:
    """Newest memories waiting for review, then the ones most recently kept."""
    from life_graph.api.jarvis import _source
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as session:
        pending = (
            (
                await session.execute(
                    select(Memory)
                    .where(Memory.tenant_id == tenant_id, Memory.status == "pending")
                    .order_by(Memory.created_at.desc())
                    .limit(MAX_LEARNT_PENDING)
                )
            )
            .scalars()
            .all()
        )
        kept = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.tenant_id == tenant_id,
                        Memory.status == "active",
                        Memory.created_at >= now - timedelta(hours=LEARNT_KEPT_HOURS),
                    )
                    .order_by(Memory.created_at.desc())
                    .limit(MAX_LEARNT_KEPT)
                )
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": str(m.id),
            "content": m.content,
            "source": _source(m),
            "status": m.status,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in [*pending, *kept]
    ]


async def collect(tenant_id: str, now: datetime | None = None) -> dict[str, Any]:
    """Every source, each read on its own; a failed one is None."""
    from life_graph.connectors.tools import user_tz

    now = now or datetime.now(UTC)
    today = now.astimezone(user_tz()).date()
    return {
        "events": await _read("events", lambda: _events(tenant_id, today)),
        "bills": await _read("bills", lambda: _bills(tenant_id, today)),
        "documents": await _read("documents", lambda: _documents(tenant_id, today)),
        "todos": await _read("todos", lambda: _todos(tenant_id)),
        "birthdays": await _read("birthdays", lambda: _birthdays_tomorrow(tenant_id, today)),
        "approvals": await _read("approvals", lambda: _count(_approvals_query(tenant_id))),
        "to_review": await _read("to_review", lambda: _count(_to_review_query(tenant_id))),
        "reminders": await _read("reminders", lambda: _count(_reminders_query(tenant_id, today))),
        "brief": await _read("brief", lambda: _brief(tenant_id)),
        "money": await _read("money", lambda: _money(tenant_id, today)),
        "mail_waiting": await _read("mail_waiting", lambda: _mail_waiting(tenant_id, now)),
        "night_run": await _read("night_run", lambda: _night_run(tenant_id)),
        "down": await _read("down", lambda: _down(tenant_id)),
        "study_due": await _read("study_due", lambda: _study_due(tenant_id, today)),
        "learnt": await _read("learnt", lambda: _learnt(tenant_id, now)),
    }


# ── Assembly: pure, from whatever the sources gave ──────────────────────────


def brief_summary(text: str) -> str:
    """The brief's section headings, ``Bills & renewals · Night shift``."""
    heads = [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]
    return " · ".join(h for h in heads[:MAX_BRIEF_HEADINGS] if h)


def money_card(summary: dict[str, Any]) -> dict[str, Any] | None:
    """Spent this month against the sum of the budgets set; None with nothing recorded."""
    cats = summary.get("categories") or []
    if not cats:
        return None
    budgets = [c["budget"] for c in cats if c.get("budget") is not None]
    return {
        "spent": summary.get("total_spent", 0.0),
        "budget": sum(budgets) if budgets else None,
        "month": summary.get("month"),
    }


def night_run(rep: dict[str, Any]) -> dict[str, int]:
    """Night shift (services/night_shift.py): merged or waiting on the owner passed."""
    passed = len(rep.get("merged") or []) + len(rep.get("waiting") or [])
    return {"passed": passed, "total": passed + len(rep.get("failed") or [])}


def _schedule_row(e: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": e.get("id"),
        "title": e.get("title"),
        "start": e.get("starts_at"),
        "end": e.get("ends_at"),
        "where": e.get("location"),
        "all_day": bool(e.get("all_day")),
    }


def next_event(events: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """The first timed event today that has not ended yet."""
    for e in events:
        if e.get("all_day") or not e.get("starts_at"):
            continue
        ends = datetime.fromisoformat(e.get("ends_at") or e["starts_at"])
        if ends > now:
            return {**_schedule_row(e), "account": e.get("account")}
    return None


def _bill_due_rows(bills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": b.get("id"),
            "kind": b.get("kind"),
            "title": b.get("payee") or "A bill",
            "when": b.get("due"),
            "amount": b.get("amount"),
            "currency": b.get("currency"),
            "autopay": bool(b.get("autopay")),
            "source": "email",
        }
        for b in bills
        if b.get("kind") in BILL_KINDS
    ]


def _document_due_rows(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": d["id"],
            "kind": "document",
            "title": d.get("title") or "A document",
            "when": d.get("expires_on"),
            "amount": None,
            "source": "document",
        }
        for d in docs
        if d.get("days_left") is not None and 0 <= d["days_left"] <= DUE_DAYS
    ]


def _todo_due_rows(todos: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    from life_graph.services.due_notifications import OVERDUE_DAYS

    out = []
    for t in todos:
        if t.get("done") or t.get("parent") or not t.get("due"):
            continue
        try:
            due = date.fromisoformat(str(t["due"])[:10])
        except ValueError:
            continue
        if -OVERDUE_DAYS <= (due - today).days <= DUE_DAYS:
            out.append(
                {
                    "id": t.get("id"),
                    "kind": "task",
                    "title": t.get("title") or "A to-do",
                    "when": due.isoformat(),
                    "amount": None,
                    "source": "tasks",
                }
            )
    return out


def due_rows(src: dict[str, Any], today: date) -> list[dict[str, Any]]:
    """Bills, documents and to-dos due this week, soonest first."""
    rows = [
        *_bill_due_rows(src.get("bills") or []),
        *_document_due_rows(src.get("documents") or []),
        *_todo_due_rows(src.get("todos") or [], today),
    ]
    return sorted(rows, key=lambda r: (r["when"] or "9999", r["title"]))


def insights(src: dict[str, Any], today: date) -> list[dict[str, Any]]:
    """The fixed rules, most urgent first."""
    from life_graph.services.due_notifications import document_text, short_amount

    out: list[dict[str, Any]] = []
    tomorrow = (today + timedelta(days=1)).isoformat()
    for b in src.get("bills") or []:
        if b.get("kind") not in BILL_KINDS or b.get("due") != tomorrow or b.get("autopay"):
            continue
        payee = b.get("payee") or "A bill"
        amount = short_amount(b.get("amount"), b.get("currency"))
        verb = "renews" if b["kind"] == "renewal" else "due"
        out.append(
            {
                "id": f"bill:{b['id']}",
                "kind": "bill",
                "item_id": b["id"],
                "title": f"{payee}{' ' + amount if amount else ''} {verb} tomorrow",
                "body": "Mark it paid once it's done.",
                "actions": [{"id": "paid", "label": "Mark paid"}],
            }
        )
    for d in src.get("documents") or []:
        left = d.get("days_left")
        if left is None or not 0 <= left <= INSIGHT_DOC_DAYS or not d.get("expires_on"):
            continue
        title, body = document_text(
            d.get("title") or "A document", date.fromisoformat(d["expires_on"]), today
        )
        out.append(
            {
                "id": f"document:{d['id']}",
                "kind": "document",
                "item_id": d["id"],
                "title": title,
                "body": body,
                "actions": [],
            }
        )
    for c in src.get("birthdays") or []:
        out.append(
            {
                "id": f"birthday:{c['id']}",
                "kind": "birthday",
                "item_id": c["id"],
                "title": f"{c['name']}'s birthday is tomorrow",
                "body": f"{today + timedelta(days=1):%A %d %B}.",
                "actions": [],
            }
        )
    return out[:MAX_INSIGHTS]


def _part(name: str, fn: Callable[[], Any], default: Any) -> Any:
    """``fn()``, or *default* when a malformed row breaks it: that part only is empty."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        logger.debug("today: %s could not be built (%s)", name, type(exc).__name__)
        return default


def _bills_due_count(bills: list[dict[str, Any]] | None) -> int | None:
    return None if bills is None else sum(1 for b in bills if b.get("kind") in BILL_KINDS)


def assemble(src: dict[str, Any], now: datetime, today: date) -> dict[str, Any]:
    """The Today screen from the sources (None = that source failed)."""
    events = src.get("events")
    approvals = src.get("approvals")
    return {
        "counts": {
            "bills_due": _part("counts", lambda: _bills_due_count(src.get("bills")), None),
            "events_today": None if events is None else len(events),
            "approvals": approvals,
            "to_review": src.get("to_review"),
            "reminders": src.get("reminders"),
        },
        "insights": _part("insights", lambda: insights(src, today), []),
        "next_event": _part("next_event", lambda: next_event(events or [], now), None),
        "brief": src.get("brief"),
        "schedule": _part("schedule", lambda: [_schedule_row(e) for e in events or []], []),
        "due": _part("due", lambda: due_rows(src, today), []),
        "money": src.get("money"),
        "mail_waiting": src.get("mail_waiting"),
        "work": {
            "approvals": approvals,
            "night_run": src.get("night_run"),
            "down": src.get("down") or [],
        },
        "study_due": src.get("study_due"),
        "learnt": src.get("learnt") or [],
    }


async def today_screen(tenant_id: str, now: datetime | None = None) -> dict[str, Any]:
    from life_graph.connectors.tools import user_tz

    now = now or datetime.now(UTC)
    src = await collect(tenant_id, now)
    return assemble(src, now, now.astimezone(user_tz()).date())
