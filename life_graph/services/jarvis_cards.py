"""Answer cards for the phone's chat (life-graph-android docs/PLAN-v4.md, S2).

When Jarvis looks something up, the app shows what it found as cards under
the answer, each with where it came from in plain words. They are built
here from Jarvis's tool results, so they show exactly what the tool gave
Jarvis, and the answer's text is unchanged:

* ``bills_due`` -> ``bill`` (with "Mark paid", POST /jarvis/bills/{id}/paid,
  unless it is on autopay);
* ``calendar_events`` and ``calendar_next`` -> ``event``;
* ``memory_about`` -> one ``person`` (its id opens GET /jarvis/entities/{id});
* ``app_health`` -> ``app_down``, for each app that is down;
* ``documents_expiring`` -> ``document``;
* ``reminder_set`` -> ``reminder`` (with "Cancel", POST
  /jarvis/reminders/{id}/cancel).

At most MAX_CARDS per tool result. The chat stream's tool results are
redacted and cut at 2,000 characters (services/chat_stream.py), so a result
that is no longer whole JSON is read item by item up to the cut.

A ``local_only`` account's bills and events reach the phone as its Today
screen shows them (connectors/exposure.phone_rows): when, never who, what
or how much. Tool results name the account, not its exposure, so the
caller passes the names of the tenant's local_only accounts; ``None`` (not
known) masks every bill and event.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)

MAX_CARDS = 5
MAX_SUBTITLE = 140
CALENDAR_TOOLS = ("calendar_events", "calendar_next")
CARD_TOOLS = frozenset(
    {
        "bills_due",
        *CALENDAR_TOOLS,
        "memory_about",
        "app_health",
        "documents_expiring",
        "reminder_set",
    }
)
_DECODER = json.JSONDecoder()


# ── Reading a result that may have been cut ─────────────────────────────────


def _parse(result: str) -> dict[str, Any] | None:
    try:
        out = json.loads(result)
    except ValueError:
        return None
    return out if isinstance(out, dict) else None


def salvage_list(text: str, key: str) -> list[dict[str, Any]]:
    """The whole objects of the list under *key* in JSON cut short, in order."""
    found = re.search(r'"' + re.escape(key) + r'"\s*:\s*\[', text)
    if not found:
        return []
    out: list[dict[str, Any]] = []
    pos = found.end()
    while True:
        while pos < len(text) and text[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(text) or text[pos] == "]":
            return out
        try:
            value, pos = _DECODER.raw_decode(text, pos)
        except ValueError:
            return out  # the cut: everything before it is whole
        if isinstance(value, dict):
            out.append(value)


def salvage_value(text: str, key: str) -> Any:
    """One top-level string, number, boolean or list under *key*, if it survived the cut."""
    found = re.search(r'"' + re.escape(key) + r'"\s*:\s*', text)
    if not found:
        return None
    try:
        return _DECODER.raw_decode(text, found.end())[0]
    except ValueError:
        return None


def _payload(result: str, lists: tuple[str, ...], values: tuple[str, ...] = ()) -> dict:
    whole = _parse(result)
    if whole is not None:
        return whole
    out: dict[str, Any] = {key: salvage_list(result, key) for key in lists}
    for key in values:
        out[key] = salvage_value(result, key)
    return out


# ── Plain words ─────────────────────────────────────────────────────────────


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def day_words(value: Any) -> str:
    """``Mon 26 Oct`` for a date or timestamp, on the owner's clock."""
    d = _local(value)
    day = d.date() if d is not None else _date(value)
    return f"{day:%a} {day.day} {day:%b}" if day else ""


def _local(value: Any) -> datetime | None:
    from life_graph.connectors.tools import user_tz

    if not value or len(str(value)) <= 10:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(user_tz())
    except ValueError:
        return None


def _short(text: Any) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= MAX_SUBTITLE else text[: MAX_SUBTITLE - 1].rstrip() + "…"


def card(
    kind: str,
    ident: Any,
    title: str,
    subtitle: str = "",
    *,
    amount: str | None = None,
    when: Any = None,
    actions: list[dict[str, str]] | None = None,
    source: str,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": str(ident) if ident is not None else None,
        "title": title,
        "subtitle": subtitle,
        "amount": amount,
        "when": when,
        "actions": actions or [],
        "source": source,
    }


def _masked(account: Any, local_only: set[str] | None) -> bool:
    return local_only is None or account in local_only


# ── One builder per tool ────────────────────────────────────────────────────


def _bills(result: str, local_only: set[str] | None) -> list[dict[str, Any]]:
    from life_graph.services.due_notifications import short_amount

    out = []
    for b in _payload(result, ("items",)).get("items") or []:
        if b.get("kind") not in ("bill", "renewal"):
            continue
        hide = _masked(b.get("account"), local_only)
        autopay = bool(b.get("autopay"))
        verb = "Renews" if b["kind"] == "renewal" else "Due"
        subtitle = f"{verb} {day_words(b.get('due'))}".strip() + (" · autopay" if autopay else "")
        account = b.get("account")
        out.append(
            card(
                "bill",
                b.get("id"),
                "A bill" if hide else (b.get("payee") or "A bill"),
                subtitle,
                amount=None if hide else (short_amount(b.get("amount"), b.get("currency")) or None),
                when=b.get("due"),
                actions=[] if autopay else [{"id": "paid", "label": "Mark paid"}],
                source=f"email, {account}" if account else "your email",
            )
        )
    return out


def _clock(value: Any) -> str:
    t = _local(value)
    return f"{t:%H:%M}" if t else ""


def _events(result: str, local_only: set[str] | None) -> list[dict[str, Any]]:
    out = []
    for e in _payload(result, ("items",)).get("items") or []:
        if e.get("kind", "event") != "event":
            continue
        hide = _masked(e.get("account"), local_only)
        start, end = e.get("starts_at"), e.get("ends_at")
        if e.get("all_day"):
            span = "all day"
        else:
            span = "–".join(t for t in (_clock(start), _clock(end)) if t)
        subtitle = ", ".join(p for p in (day_words(start), span) if p)
        if e.get("location") and not hide:
            subtitle += f" · {e['location']}"
        title = e.get("title")
        account = e.get("account")
        out.append(
            card(
                "event",
                e.get("id"),
                "An event" if hide or not title or title == "(no title)" else title,
                _short(subtitle),
                when=start,
                source=f"{account} calendar" if account else "your calendar",
            )
        )
    return out


def _person(result: str) -> list[dict[str, Any]]:
    about = _payload(result, ("memories",), ("name", "known", "id", "also_called"))
    if about.get("known") is not True:
        return []
    names = about.get("also_called") if isinstance(about.get("also_called"), list) else []
    memories = about.get("memories") or []
    newest = memories[0] if memories else {}
    count = len(memories)
    return [
        card(
            "person",
            about.get("id"),
            str(names[0] if names else about.get("name") or "Someone"),
            _short(newest.get("content")),
            when=newest.get("created_at"),
            source="your memories" if not count else f"your memories, {count} noted",
        )
    ]


def _apps_down(result: str) -> list[dict[str, Any]]:
    out = []
    for a in _payload(result, ("apps",)).get("apps") or []:
        if a.get("status") != "down":
            continue
        status = a.get("http_status")
        why = a.get("error") or (f"HTTP {status}" if status else "Not answering")
        out.append(
            card(
                "app_down",
                a.get("project"),
                str(a.get("project") or "An app"),
                _short(f"Down · {why}"),
                when=a.get("down_since"),
                source="uptime check",
            )
        )
    return out


def _documents(result: str) -> list[dict[str, Any]]:
    out = []
    for d in _payload(result, ("documents",)).get("documents") or []:
        left = d.get("days_left")
        if not isinstance(left, int):
            subtitle = ""
        elif left < 0:
            subtitle = "Expired"
        elif left == 0:
            subtitle = "Expires today"
        elif left == 1:
            subtitle = "Expires tomorrow"
        else:
            subtitle = f"Expires in {left} days"
        if d.get("expires_on"):
            subtitle = ", ".join(p for p in (subtitle, day_words(d["expires_on"])) if p)
        out.append(
            card(
                "document",
                d.get("id"),
                str(d.get("title") or "A document"),
                subtitle,
                when=d.get("expires_on"),
                source="your documents",
            )
        )
    return out


def _reminder(result: str) -> list[dict[str, Any]]:
    out = _parse(result)
    if not out or out.get("reminded") is not True or not out.get("id"):
        return []
    return [
        card(
            "reminder",
            out["id"],
            str(out.get("text") or "A reminder"),
            str(out.get("when") or day_words(out.get("at"))),
            when=out.get("at"),
            actions=[{"id": "cancel", "label": "Cancel"}],
            source="a reminder you asked for",
        )
    ]


def cards_for(name: str | None, result: Any, local_only: set[str] | None) -> list[dict[str, Any]]:
    """The cards one tool result makes (at most MAX_CARDS); never raises."""
    if name not in CARD_TOOLS:
        return []
    text = str(result or "")
    try:
        if name == "bills_due":
            out = _bills(text, local_only)
        elif name in CALENDAR_TOOLS:
            out = _events(text, local_only)
        elif name == "memory_about":
            out = _person(text)
        elif name == "app_health":
            out = _apps_down(text)
        elif name == "documents_expiring":
            out = _documents(text)
        else:
            out = _reminder(text)
    except Exception as exc:  # noqa: BLE001 - a card is a nicety: the answer still shows
        logger.debug("cards: %s result unreadable (%s)", name, type(exc).__name__)
        return []
    return out[:MAX_CARDS]


async def local_only_accounts(tenant_id: str) -> set[str] | None:
    """The display names of the tenant's local_only accounts; None if unreadable."""
    from sqlalchemy import select

    from life_graph.connectors.exposure import EXPOSURE_LOCAL_ONLY
    from life_graph.connectors.models import ConnectorAccount
    from life_graph.storage.database import async_session

    try:
        async with async_session() as session:
            rows = (
                await session.execute(
                    select(ConnectorAccount.display_name).where(
                        ConnectorAccount.tenant_id == tenant_id,
                        ConnectorAccount.exposure == EXPOSURE_LOCAL_ONLY,
                    )
                )
            ).scalars()
            return set(rows)
    except Exception as exc:  # noqa: BLE001 - unknown: every bill and event is masked
        logger.debug("cards: accounts unavailable (%s)", type(exc).__name__)
        return None
