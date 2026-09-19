"""Bills and renewals found in mail (docs/specs/bills-from-mail.md).

The local summariser copies what a bill email says — the payee, the amount and
the due-date words — and this module turns those words into data with plain
code: day-first Indian dates (``25-09-2026``), month names, amounts in rupees.
The model never does date arithmetic (asked to, qwen3 got "by Friday" wrong).

A bill lives on its email row as ``flags.bill``; nothing here needs a table of
its own. A later "payment received" email from the same payee closes it.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.connectors.base import DIR_INBOUND, KIND_EMAIL
from life_graph.connectors.models import ConnectorAccount, ConnectorItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

KINDS = ("bill", "renewal", "payment_done")
OPEN_STATES = ("open", "reminded")
PAID_MATCH_DAYS = 45
OVERDUE_DAYS = 7  # overdue bills are listed this long
BILL_AHEAD_DAYS = 7
RENEWAL_AHEAD_DAYS = 14
# A due date in the email may be in the past (an overdue reminder); one further
# back than this without a year is taken to mean next year.
PAST_TOLERANCE_DAYS = 60

_MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ]
    )
    for m in names
}
_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_NUMERIC = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b")
_DAY_MON = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?[\s\-/.,]*(?:of\s+)?{_MON}\b\.?[\s\-/.,]*(\d{{4}})?"
)
_MON_DAY = re.compile(rf"\b{_MON}\.?[\s\-/.]*(\d{{1,2}})(?:st|nd|rd|th)?\b,?\s*(\d{{4}})?")

_CURRENCIES = (
    (re.compile(r"₹|\brs\.?|\binr\b", re.I), "INR"),
    (re.compile(r"\$|\busd\b", re.I), "USD"),
    (re.compile(r"€|\beur\b", re.I), "EUR"),
    (re.compile(r"£|\bgbp\b", re.I), "GBP"),
)
_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)")
_SYMBOL = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}

# Words that say what kind of thing a payee is, not who it is.
_GENERIC = frozenset(
    [
        "bill",
        "bills",
        "payment",
        "payments",
        "statement",
        "account",
        "ltd",
        "limited",
        "pvt",
        "private",
        "services",
        "service",
        "india",
        "the",
        "your",
        "of",
        "for",
        "due",
        "renewal",
        "card",
        "credit",
        "debit",
        "bank",
        "electricity",
        "broadband",
        "mobile",
        "postpaid",
        "prepaid",
        "insurance",
        "policy",
        "premium",
        "subscription",
        "domain",
        "co",
        "inc",
        "company",
        "plan",
        "a",
        "an",
        "and",
        "online",
        "auto",
        "emi",
        "loan",
        "fees",
        "fee",
    ]
)


def _year(y: str | None) -> int | None:
    if not y:
        return None
    n = int(y)
    return 2000 + n if n < 100 else n


def _anchor(day: int, month: int, year: int | None, received: date) -> date | None:
    try:
        if year:
            return date(year, month, day)
        d = date(received.year, month, day)
    except ValueError:
        return None
    if d < received - timedelta(days=PAST_TOLERANCE_DAYS):
        try:
            d = date(received.year + 1, month, day)
        except ValueError:
            return None
    return d


def parse_due(words: str | None, received: datetime) -> date | None:
    """The date in ``words`` (as the email wrote it), anchored to when it arrived."""
    text = (words or "").strip().lower()
    if not text:
        return None
    base = received.date()
    if m := _ISO.search(text):
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    if m := _NUMERIC.search(text):
        # Day first: Indian bills write 05-10-2026 for 5 October.
        return _anchor(int(m[1]), int(m[2]), _year(m[3]), base)
    if m := _DAY_MON.search(text):
        return _anchor(int(m[1]), _MONTHS[m[2][:3]], _year(m[3]), base)
    if m := _MON_DAY.search(text):
        return _anchor(int(m[2]), _MONTHS[m[1][:3]], _year(m[3]), base)
    from life_graph.services.prediction_detection import parse_horizon

    parsed = parse_horizon(text, received)
    return parsed.date() if parsed else None


def parse_amount(words: str | None) -> tuple[float | None, str | None]:
    """``"Rs. 2,345.00"`` → (2345.0, "INR"). The currency defaults to INR."""
    text = (words or "").strip()
    m = _NUMBER.search(text)
    if not m:
        return None, None
    try:
        amount = float(m[1].replace(",", ""))
    except ValueError:
        return None, None
    currency = next((code for rx, code in _CURRENCIES if rx.search(text)), "INR")
    return amount, currency


def format_amount(amount: float | None, currency: str | None) -> str:
    if amount is None:
        return ""
    return f"{_SYMBOL.get(currency or '', (currency or '') + ' ')}{amount:,.2f}"


def payee_key(payee: str | None) -> frozenset[str]:
    """The identifying words of a payee: "HDFC Bank credit card" → {"hdfc"}."""
    words = re.findall(r"[a-z0-9][a-z0-9.&-]*", (payee or "").lower())
    return frozenset(w.strip(".") for w in words if w.strip(".") not in _GENERIC and len(w) > 1)


def same_payee(a: str | None, b: str | None) -> bool:
    ka, kb = payee_key(a), payee_key(b)
    return bool(ka and kb and ka & kb)


# Scam signs in a "bill" that the local model may miss (it did, in testing): link
# shorteners, threats of disconnection within hours, call-an-officer numbers,
# and throwaway top-level domains.
_SCAM_TEXT = re.compile(
    r"(?i)(\b(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|is\.gd|cutt\.ly|rb\.gy|shorturl\.at)/"
    r"|disconnect(?:ed|ion)?\s+(?:tonight|today|within\s+\d+\s+hours?)"
    r"|\bcall\s+(?:our|the)\s+(?:electricity\s+)?officer\b)"
)
_SCAM_TLDS = frozenset(
    [
        "xyz",
        "top",
        "click",
        "link",
        "live",
        "icu",
        "buzz",
        "rest",
        "cfd",
        "sbs",
        "gq",
        "tk",
        "ml",
        "cf",
        "ga",
        "work",
        "support",
    ]
)


def looks_like_scam(sender_addr: str | None, text: str | None) -> bool:
    """Deterministic scam signs for a bill, independent of the model's opinion.

    A free-mail sender alone is not one: landlords and tutors send real bills
    from Gmail.
    """
    if _SCAM_TEXT.search(text or ""):
        return True
    domain = (sender_addr or "").rsplit("@", 1)[-1].lower()
    if not domain or "." not in domain:
        return False
    return domain.rsplit(".", 1)[-1] in _SCAM_TLDS


# "LIC of India policy no. [redacted]" → "LIC of India": the payee is a name, and
# numbers identifying the user's account never belong in it.
_PAYEE_REF = re.compile(
    r"(?i)[\s,-]*\b(?:policy|account|a/c|acct|card|consumer|customer|loan|member|folio)\s*"
    r"(?:(?:no\.?|number|id|ending(?:\s+in)?)\s*[:#]?\s*[\w/-]*|[:#]?\s*[\w/-]*\d[\w/-]*)\s*$"
)


def clean_payee(payee: str | None) -> str:
    text = " ".join((payee or "").replace("[redacted]", " ").split())
    text = _PAYEE_REF.sub("", text).strip(" ,-:#")
    words = text.split()
    return " ".join(words[:6])[:80]


def from_fields(
    *,
    kind: str | None,
    payee: str | None,
    amount: str | None,
    due: str | None,
    autopay: bool,
    received: datetime,
) -> dict[str, Any] | None:
    """The ``flags.bill`` value for one email, or None when it is not a bill."""
    if kind not in KINDS:
        return None
    payee = clean_payee(payee)
    if not payee:
        return None
    value, currency = parse_amount(amount)
    due_date = parse_due(due, received) if kind != "payment_done" else None
    return {
        "kind": kind,
        "payee": payee,
        "amount": value,
        "currency": currency if value is not None else None,
        "due": due_date.isoformat() if due_date else None,
        "autopay": bool(autopay),
        "state": "confirmation" if kind == "payment_done" else "open",
    }


def merge_state(new: dict[str, Any] | None, old: dict[str, Any] | None) -> dict[str, Any] | None:
    """A re-read of the same email keeps what the user already did with the bill."""
    if new and old and old.get("state") not in (None, "open", "confirmation"):
        return {**new, "state": old["state"]}
    return new


async def close_paid(
    session: AsyncSession, tenant_id: str, payee: str, paid_at: datetime
) -> str | None:
    """Mark the newest open bill from ``payee`` (issued in the last 45 days) paid.

    Returns the id of the bill closed, if any.
    """
    rows = (
        await session.execute(
            select(ConnectorItem)
            .where(
                ConnectorItem.tenant_id == tenant_id,
                ConnectorItem.kind == KIND_EMAIL,
                ConnectorItem.flags["bill"]["kind"].astext == "bill",
                ConnectorItem.flags["bill"]["state"].astext.in_(OPEN_STATES),
                ConnectorItem.occurred_at >= paid_at - timedelta(days=PAID_MATCH_DAYS),
                ConnectorItem.occurred_at <= paid_at,
            )
            .order_by(ConnectorItem.occurred_at.desc())
        )
    ).scalars()
    for item in rows:
        bill = (item.flags or {}).get("bill") or {}
        if same_payee(bill.get("payee"), payee):
            item.flags = {
                **(item.flags or {}),
                "bill": {**bill, "state": "paid", "paid_at": paid_at.isoformat()},
            }
            return str(item.id)
    return None


async def paid_since(
    session: AsyncSession, tenant_id: str, payee: str, issued_at: datetime
) -> datetime | None:
    """When a confirmation from ``payee`` arrived after a bill issued at ``issued_at``.

    New mail is summarised newest first, so a confirmation can be read before
    the bill it pays; the bill then checks for it here.
    """
    rows = (
        await session.execute(
            select(ConnectorItem.flags, ConnectorItem.occurred_at).where(
                ConnectorItem.tenant_id == tenant_id,
                ConnectorItem.kind == KIND_EMAIL,
                ConnectorItem.flags["bill"]["kind"].astext == "payment_done",
                ConnectorItem.occurred_at > issued_at,
                ConnectorItem.occurred_at <= issued_at + timedelta(days=PAID_MATCH_DAYS),
            )
        )
    ).all()
    for flags, occurred in rows:
        if same_payee(((flags or {}).get("bill") or {}).get("payee"), payee):
            return occurred
    return None


async def bills_due(session: AsyncSession, tenant_id: str, today: date) -> list[dict[str, Any]]:
    """Open bills overdue (up to a week) or due within a week, and renewals within two.

    Several emails about the same bill (a statement and two reminders) come
    back as one row: the newest email, with ``email_count`` counting them.
    """
    from life_graph.connectors.store import _as_dict

    lo = (today - timedelta(days=OVERDUE_DAYS)).isoformat()
    hi = (today + timedelta(days=RENEWAL_AHEAD_DAYS)).isoformat()
    due = ConnectorItem.flags["bill"]["due"].astext
    rows = (
        await session.execute(
            select(ConnectorItem, ConnectorAccount)
            .join(ConnectorAccount, ConnectorAccount.id == ConnectorItem.account_id)
            .where(
                ConnectorItem.tenant_id == tenant_id,
                ConnectorAccount.enabled.is_(True),
                ConnectorItem.kind == KIND_EMAIL,
                ConnectorItem.direction == DIR_INBOUND,
                ConnectorItem.flags["bill"]["kind"].astext.in_(["bill", "renewal"]),
                ConnectorItem.flags["bill"]["state"].astext.in_(OPEN_STATES),
                due.is_not(None),
                due >= lo,
                due <= hi,
            )
            .order_by(ConnectorItem.occurred_at.desc())
        )
    ).all()
    groups: dict[tuple, dict[str, Any]] = {}
    for item, account in rows:
        row = _as_dict(item, account)
        bill = row["flags"]["bill"]
        d = date.fromisoformat(bill["due"])
        if bill["kind"] == "bill":
            if d > today + timedelta(days=BILL_AHEAD_DAYS):
                continue
            if bill.get("autopay") and d < today:
                continue  # autopay: past due means paid
        elif d < today:
            continue  # a renewal date that has passed is done
        key = (tuple(sorted(payee_key(bill["payee"]))) or (bill["payee"].lower(),), bill["due"])
        if key in groups:
            groups[key]["email_count"] += 1
            continue
        row["bill"] = bill
        row["email_count"] = 1
        groups[key] = row
    return sorted(groups.values(), key=lambda r: (r["bill"]["due"], r["bill"]["payee"]))
