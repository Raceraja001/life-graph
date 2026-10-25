"""The phone's contacts and mail waiting (life-graph-android docs/PLAN-v4.md, S2).

``GET /jarvis/contacts?q=`` and ``GET /jarvis/mail/waiting`` (api/jarvis.py)
read the connector store as the dashboard does (connectors/tools.py
contact_lookup and email_waiting), rendered LOCAL: the phone is the owner's
own screen. What it is sent leaves this machine, so a ``local_only``
account is treated as on the Today screen: its mail passes ``phone_rows``
(when, never who or what), and its contacts are left out, since a contact
without its name is nothing to show. A failed read is an empty list, logged
at debug level by exception type only.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

MAX_CONTACTS = 100
MAX_SEARCH = 30
MAX_WAITING = 50
#: "+91 98765 43210 (mobile)" as the contacts plugin stores it: the number alone.
_PHONE_KIND = re.compile(r"\s*\([^)]*\)\s*$")


def _first_phone(phones: list[Any] | None) -> str | None:
    for p in phones or []:
        number = _PHONE_KIND.sub("", str(p)).strip()
        if number:
            return number
    return None


def contact_row(c: dict[str, Any]) -> dict[str, Any]:
    emails = c.get("emails") or []
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "phone": _first_phone(c.get("phones")),
        "email": emails[0] if emails else None,
    }


async def contacts(tenant_id: str, query: str = "") -> list[dict[str, Any]]:
    """Contacts matching every word of *query*, or the list by name when it is blank."""
    from life_graph.connectors import store
    from life_graph.connectors.exposure import EXPOSURE_LOCAL_ONLY, view_items
    from life_graph.connectors.locality import LOCAL
    from life_graph.storage.database import async_session

    query = " ".join((query or "").split())
    try:
        async with async_session() as session:
            if any(len(t) > 1 for t in query.split()):
                rows = await store.search_contacts(session, tenant_id, query, limit=MAX_SEARCH)
            else:
                rows = await store.list_contacts(session, tenant_id, limit=MAX_CONTACTS)
    except Exception as exc:  # noqa: BLE001 - an empty list, never a 500
        logger.debug("contacts unavailable (%s)", type(exc).__name__)
        return []
    rows = [r for r in rows if r.get("account_exposure") != EXPOSURE_LOCAL_ONLY]
    return [contact_row(c) for c in view_items(rows, LOCAL)["items"]]


def mail_row(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": m.get("id"),
        "from": m.get("sender_name") or m.get("sender_addr") or "Someone",
        "subject": m.get("subject") or "(no subject)",
        "received_at": m.get("date"),
        "needs_reply": bool(m.get("needs_reply")),
    }


async def mail_waiting(tenant_id: str, now: datetime | None = None) -> list[dict[str, Any]]:
    """Mail waiting on the owner's reply, the longest wait first (store.waiting_on_me)."""
    from life_graph.connectors import store
    from life_graph.connectors.exposure import EXPOSURE_LOCAL_ONLY, phone_rows, view_items
    from life_graph.connectors.locality import LOCAL
    from life_graph.storage.database import async_session

    now = now or datetime.now(UTC)
    try:
        async with async_session() as session:
            rows = await store.waiting_on_me(session, tenant_id, now, limit=MAX_WAITING)
            addrs = {r["sender_addr"] for r in rows if r.get("sender_addr")}
            people = await store.people_by_address(session, tenant_id, addrs)
    except Exception as exc:  # noqa: BLE001 - an empty list, never a 500
        logger.debug("mail waiting unavailable (%s)", type(exc).__name__)
        return []
    # A local_only account's contact lends no name to other accounts' mail.
    people = {a: c for a, c in people.items() if c.get("account_exposure") != EXPOSURE_LOCAL_ONLY}
    return [mail_row(m) for m in view_items(phone_rows(rows), LOCAL, people)["items"]]
