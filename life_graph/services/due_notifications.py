"""The owner's own due items, written as notifications for the phone.

The phone app polls ``GET /api/v1/jarvis/notifications`` and posts each new
row as an Android notification. This module writes one row per item per lead
time for:

- bills and renewals found in mail (connectors/bills.bills_due): overdue, due
  today, due tomorrow;
- to-dos from Google Tasks (connectors/store.task_items): the same three;
- documents (services/documents.py): 30, 7 and 1 days before expiry;
- timed reminders (``Intention`` with ``trigger_type="time"``) once their
  time has come. Until now those only surfaced when a session started.

Each row carries a ``dedup_key`` in its metadata (``bill:<payee>:<due>:today``)
and is written only when no row with that key exists, so the job can run as
often as it likes. Documents also share ``Document.reminders_sent`` with the
daily sweep (services/documents.sweep_reminders), so the two never post the
same threshold twice.

Nothing is sent from here: no Telegram, no web push. Rows are written already
marked delivered, so the next daily brief does not re-post them with "due
tomorrow" wording a day late; the brief lists bills and tasks itself.

Items from a ``local_only`` account are announced without payee, amount or
title (a phone notification leaves the machine).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.connectors.bills import format_amount, payee_key
from life_graph.connectors.exposure import EXPOSURE_LOCAL_ONLY
from life_graph.models.db import Intention, Notification

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SOURCE_TYPE = "due_item"
OVERDUE = "overdue"
TODAY = "today"
TOMORROW = "tomorrow"
OVERDUE_DAYS = 7  # an item overdue longer than this was dealt with or abandoned
DOC_LEADS = (30, 7, 1)  # days before a document expires
REMINDER_LOOKBACK = timedelta(days=1)  # a reminder missed by longer is stale
MAX_PER_RUN = 20  # per tenant; the rest wait for the next run
# Hours of the owner's day (user_timezone) in which due items are posted.
# "Tomorrow" waits for the evening, when it is useful; timed reminders are
# posted whenever their time comes, since the owner chose it.
MORNING_HOUR = 8
EVENING_HOUR = 18
NIGHT_HOUR = 22


@dataclass
class DueItem:
    kind: str  # bill | task | document | reminder
    key: str
    lead: str
    title: str
    body: str
    priority: str
    source_id: str | None = None
    due: str | None = None
    document: Any = None  # the Document whose reminders_sent records this lead


def dedup_key(kind: str, ident: str, when: str, lead: str) -> str:
    return f"{kind}:{ident}:{when}:{lead}"


def day_lead(due: date, today: date) -> str | None:
    """overdue / today / tomorrow for a due date, or None when not yet (or long past)."""
    days = (due - today).days
    if days < -OVERDUE_DAYS or days > 1:
        return None
    if days < 0:
        return OVERDUE
    return TODAY if days == 0 else TOMORROW


def document_lead(expires_on: date, today: date, sent: list | None) -> str | None:
    """The nearest of 30/7/1 days already reached and not yet notified.

    A document filed 5 days before expiry gets the 7-day notice, not three.
    Expired documents are the daily sweep's ("expired"), not this one's.
    """
    days = (expires_on - today).days
    if days < 0 or days > max(DOC_LEADS):
        return None
    lead = str(min(t for t in DOC_LEADS if days <= t))
    return None if lead in {str(s) for s in (sent or [])} else lead


def lead_open(lead: str, hour: int) -> bool:
    """Whether an item of this lead may be posted at this hour of the owner's day."""
    if not MORNING_HOUR <= hour < NIGHT_HOUR:
        return False
    return hour >= EVENING_HOUR if lead == TOMORROW else True


def priority_for(days: int, *, autopay: bool = False) -> str:
    """Due today or overdue is important; anything later, or on autopay, is info."""
    return "important" if days <= 0 and not autopay else "info"


def short_amount(amount: float | None, currency: str | None) -> str:
    """``₹1,240`` for a whole amount, ``₹1,240.50`` otherwise."""
    text = format_amount(amount, currency)
    return text.removesuffix(".00")


def _when(lead: str) -> str:
    return {OVERDUE: "overdue", TODAY: "due today", TOMORROW: "due tomorrow"}[lead]


def bill_text(bill: dict[str, Any], lead: str, *, private: bool = False) -> tuple[str, str]:
    """Title and body for one bill or renewal."""
    renewal = bill.get("kind") == "renewal"
    if private:
        noun = "A renewal" if renewal else "A bill"
        return f"{noun} is {_when(lead)}", "Details on the dashboard."
    payee = bill.get("payee") or "A payee"
    amount = short_amount(bill.get("amount"), bill.get("currency"))
    if renewal:
        title = f"{payee} renews {lead}" if lead != OVERDUE else f"{payee} renewal overdue"
        body = f"{amount} to renew with {payee}." if amount else f"Renewal with {payee}."
    else:
        title = f"{payee} bill {_when(lead)}"
        body = f"{amount} to {payee}." if amount else f"Pay {payee}."
    if lead == OVERDUE and bill.get("due"):
        body += f" It was due {date.fromisoformat(bill['due']):%a %d %b}."
    if bill.get("autopay"):
        body += " Autopay is on."
    return title, body


def task_text(task: dict[str, Any], lead: str, *, private: bool = False) -> tuple[str, str]:
    """Title and body for one to-do."""
    if private:
        return f"A to-do is {_when(lead)}", "Details on the dashboard."
    label = {OVERDUE: "Overdue", TODAY: "Due today", TOMORROW: "Due tomorrow"}[lead]
    flags = task.get("flags") or {}
    where = f"on your {flags['list']} list" if flags.get("list") else "on your to-do list"
    if lead == OVERDUE and flags.get("due"):
        body = f"It was due {date.fromisoformat(flags['due'][:10]):%a %d %b}, {where}."
    else:
        body = f"{where[0].upper()}{where[1:]}."
    return f"{label}: {task.get('title') or 'a to-do'}", body


def document_text(title: str, expires_on: date, today: date) -> tuple[str, str]:
    days = (expires_on - today).days
    if days <= 0:
        when = "expires today"
    elif days == 1:
        when = "expires tomorrow"
    else:
        when = f"expires in {days} days"
    return (
        f"{title} {when}",
        f"On {expires_on:%d %b %Y}. Start the renewal now if it needs an appointment or paperwork.",
    )


def reminder_text(content: str, at: datetime, now: datetime, tz: Any) -> tuple[str, str]:
    """The reminder's own words as the title; when it was for as the body."""
    first = next((ln.strip() for ln in (content or "").splitlines() if ln.strip()), "")
    title = first[:120] or "Reminder"
    local, local_now = at.astimezone(tz), now.astimezone(tz)
    when = f"{local:%H:%M}" if local.date() == local_now.date() else f"{local:%a %d %b %H:%M}"
    return title, f"Reminder for {when}."


# ── Finding what is due ──────────────────────────────────────────────


def bill_items(rows: list[dict[str, Any]], today: date, hour: int) -> list[DueItem]:
    """``bills.bills_due`` rows → items. Several emails about one bill are one row."""
    items = []
    for row in rows:
        bill = row.get("bill") or (row.get("flags") or {}).get("bill") or {}
        if not bill.get("due"):
            continue
        due = date.fromisoformat(bill["due"])
        lead = day_lead(due, today)
        if lead is None or not lead_open(lead, hour):
            continue
        ident = "-".join(sorted(payee_key(bill.get("payee")))) or (bill.get("payee") or "").lower()
        title, body = bill_text(
            bill, lead, private=row.get("account_exposure") == EXPOSURE_LOCAL_ONLY
        )
        items.append(
            DueItem(
                kind="bill",
                key=dedup_key("bill", ident, bill["due"], lead),
                lead=lead,
                title=title,
                body=body,
                priority=priority_for((due - today).days, autopay=bool(bill.get("autopay"))),
                source_id=row.get("id"),
                due=bill["due"],
            )
        )
    return items


def task_items(rows: list[dict[str, Any]], today: date, hour: int) -> list[DueItem]:
    """Open top-level to-dos with a due date (``store.task_items`` rows) → items."""
    items = []
    for row in rows:
        flags = row.get("flags") or {}
        if flags.get("status") == "completed" or flags.get("parent") or not flags.get("due"):
            continue
        try:
            due = date.fromisoformat(str(flags["due"])[:10])
        except ValueError:
            continue
        lead = day_lead(due, today)
        if lead is None or not lead_open(lead, hour):
            continue
        title, body = task_text(
            row, lead, private=row.get("account_exposure") == EXPOSURE_LOCAL_ONLY
        )
        items.append(
            DueItem(
                kind="task",
                key=dedup_key("task", row["id"], due.isoformat(), lead),
                lead=lead,
                title=title,
                body=body,
                priority=priority_for((due - today).days),
                source_id=row["id"],
                due=due.isoformat(),
            )
        )
    return items


def document_items(docs: list[Any], today: date, hour: int) -> list[DueItem]:
    items = []
    if not MORNING_HOUR <= hour < NIGHT_HOUR:
        return items
    for doc in docs:
        if doc.expires_on is None:
            continue
        lead = document_lead(doc.expires_on, today, doc.reminders_sent)
        if lead is None:
            continue
        title, body = document_text(doc.title, doc.expires_on, today)
        items.append(
            DueItem(
                kind="document",
                key=dedup_key("document", str(doc.id), doc.expires_on.isoformat(), lead),
                lead=lead,
                title=title,
                body=body,
                priority=priority_for((doc.expires_on - today).days),
                source_id=str(doc.id),
                due=doc.expires_on.isoformat(),
                document=doc,
            )
        )
    return items


def reminder_items(intentions: list[Any], now: datetime, tz: Any) -> list[DueItem]:
    items = []
    for it in intentions:
        if it.trigger_time is None:
            continue
        title, body = reminder_text(it.content, it.trigger_time, now, tz)
        at = it.trigger_time.astimezone(UTC).isoformat()
        items.append(
            DueItem(
                kind="reminder",
                key=dedup_key("reminder", str(it.id), at, "now"),
                lead="now",
                title=title,
                body=body,
                priority="important",
                source_id=str(it.id),
                due=at,
            )
        )
    return items


async def _due_reminders(session: AsyncSession, tenant_id: str, now: datetime) -> list[Intention]:
    return list(
        (
            await session.execute(
                select(Intention).where(
                    Intention.tenant_id == tenant_id,
                    Intention.trigger_type == "time",
                    Intention.status == "pending",
                    Intention.trigger_time <= now,
                    Intention.trigger_time >= now - REMINDER_LOOKBACK,
                )
            )
        )
        .scalars()
        .all()
    )


async def collect(session: AsyncSession, tenant_id: str, now: datetime) -> list[DueItem]:
    """Everything due for one tenant at ``now``. A failing kind is logged and skipped."""
    from life_graph.connectors import store
    from life_graph.connectors.bills import bills_due
    from life_graph.connectors.tools import user_tz
    from life_graph.services import documents

    tz = user_tz()
    local = now.astimezone(tz)
    today, hour = local.date(), local.hour
    items: list[DueItem] = []
    try:
        items += reminder_items(await _due_reminders(session, tenant_id, now), now, tz)
    except Exception:
        logger.warning("due notifications: reminders failed for %s", tenant_id, exc_info=True)
        await session.rollback()
    # Documents last: a rollback after a later failure would expire the
    # Document rows whose reminders_sent the write updates.
    sources = (
        ("bills", lambda: bills_due(session, tenant_id, today), bill_items),
        ("tasks", lambda: store.task_items(session, tenant_id), task_items),
        (
            "documents",
            lambda: documents.expiring(session, tenant_id, today, within_days=max(DOC_LEADS)),
            document_items,
        ),
    )
    for name, load, build in sources:
        try:
            items += build(await load(), today, hour)
        except Exception:
            logger.warning("due notifications: %s failed for %s", name, tenant_id, exc_info=True)
            await session.rollback()
    return items


# ── Writing ──────────────────────────────────────────────────────────


async def write_new(
    session: AsyncSession, tenant_id: str, items: list[DueItem], now: datetime
) -> list[str]:
    """Add a notification for each item whose key has none yet. Returns the keys written.

    The caller commits. Important items go first when there are more than
    ``MAX_PER_RUN``.
    """
    if not items:
        return []
    key_col = Notification.extra_metadata["dedup_key"].astext
    existing = set(
        (
            await session.execute(
                select(key_col).where(
                    Notification.tenant_id == tenant_id,
                    Notification.source_type == SOURCE_TYPE,
                    key_col.in_([i.key for i in items]),
                )
            )
        )
        .scalars()
        .all()
    )
    written: list[str] = []
    for item in sorted(items, key=lambda i: i.priority != "important"):
        if item.key in existing or item.key in written:
            continue
        if len(written) >= MAX_PER_RUN:
            break
        session.add(
            Notification(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                priority=item.priority,
                title=item.title[:500],
                body=item.body,
                extra_metadata={
                    "kind": SOURCE_TYPE,
                    "item": item.kind,
                    "lead": item.lead,
                    "due": item.due,
                    "dedup_key": item.key,
                },
                # The phone polls for these; see the module docstring.
                is_delivered=True,
                delivered_at=now,
                source_type=SOURCE_TYPE,
                source_id=_uuid_or_none(item.source_id),
            )
        )
        if item.document is not None:
            doc = item.document
            doc.reminders_sent = sorted({*map(str, doc.reminders_sent or []), item.lead})
        written.append(item.key)
    await session.flush()
    return written


def _uuid_or_none(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


async def run_for_tenant(
    tenant_id: str, now: datetime | None = None, session_factory=None
) -> list[str]:
    """Write one tenant's new due notifications. Returns the dedup keys written."""
    if session_factory is None:
        from life_graph.storage.database import async_session

        session_factory = async_session
    now = now or datetime.now(UTC)
    async with session_factory() as session:
        items = await collect(session, tenant_id, now)
        written = await write_new(session, tenant_id, items, now)
        await session.commit()
    return written
