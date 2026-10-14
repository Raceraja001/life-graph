"""Documents vault: what the user owns and when it runs out.

Phase B of docs/specs/assistant-capabilities.md. A document arrives as text
(typed, or OCR from a Telegram photo captioned ``/doc``); the local model
names its kind, title, issuer and holder and copies the date *words*, and plain
code turns the words into dates (connectors/bills.parse_due — the model never
does date arithmetic). The expiry date is looked for twice: in the model's
words and, independently, next to an expiry keyword in the text itself, so a
document still gets a reminder when the model misses the date.

Privacy:
- only the last four characters of a document number are stored;
- the OCR text itself is not stored here (the capture spine already holds it
  as a memory, under its own review);
- the brief, which leaves the machine, names the kind and the date only.

Reminders go out once per threshold (60, 30, 7 and 1 days before, then once
when expired) through the notification engine; far-off ones wait for the
daily brief, near ones are delivered at once.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.config import settings
from life_graph.connectors.bills import parse_due
from life_graph.models.assistant import Document

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

KINDS = (
    "passport",
    "driving_licence",
    "id_card",
    "vehicle_registration",
    "insurance",
    "warranty",
    "contract",
    "certificate",
    "subscription",
    "receipt",
    "other",
)
THRESHOLDS = (60, 30, 7, 1)
EXPIRED = "expired"
MAX_INPUT_CHARS = 6000

_SYSTEM = (
    "You read the text of one document the user owns (OCR from a photo, or typed)"
    " and fill in fields. Copy what the document says; never invent. Fields:\n"
    f'- "kind": one of {", ".join(KINDS)}.\n'
    '- "title": a short name for it, under 8 words ("Indian passport", "Car insurance'
    ' — HDFC Ergo", "Samsung TV warranty").\n'
    '- "issuer": who issued it, or "".\n'
    '- "holder": whose document it is, or "".\n'
    '- "number": the document, policy or serial number exactly as written, or "".\n'
    '- "issued": the issue or start date words exactly as written, or "".\n'
    '- "expires": the expiry, valid-until, renewal or end date words exactly as'
    ' written, or "".'
)
_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "document_fields",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": list(KINDS)},
                "title": {"type": "string"},
                "issuer": {"type": "string"},
                "holder": {"type": "string"},
                "number": {"type": "string"},
                "issued": {"type": "string"},
                "expires": {"type": "string"},
            },
            "required": ["kind", "title", "issuer", "holder", "number", "issued", "expires"],
            "additionalProperties": False,
        },
    },
}

_EXPIRY_KEYWORD = re.compile(
    r"(date\s+of\s+expiry|expiry\s+date|expiry|expires?\s*(?:on)?|valid\s+(?:till|until|upto|up\s+to|thru|through)"
    r"|renewal\s+(?:date|due)|policy\s+(?:end|expiry)|end\s+date|warranty\s+(?:till|until|ends?))",
    re.I,
)
_ISSUE_KEYWORD = re.compile(
    r"(date\s+of\s+issue|issue\s+date|issued\s*(?:on)?|start\s+date|policy\s+start|purchase\s+date|valid\s+from)",
    re.I,
)
_KIND_WORDS = (
    ("passport", "passport"),
    ("driving licence", "driving_licence"),
    ("driving license", "driving_licence"),
    ("insurance", "insurance"),
    ("policy", "insurance"),
    ("warranty", "warranty"),
    ("registration certificate", "vehicle_registration"),
    ("aadhaar", "id_card"),
    ("pan card", "id_card"),
    ("voter", "id_card"),
    ("agreement", "contract"),
    ("contract", "contract"),
    ("subscription", "subscription"),
    ("certificate", "certificate"),
    ("receipt", "receipt"),
    ("invoice", "receipt"),
)


def last4(number: str | None) -> str | None:
    """The last four letters or digits of a number; nothing more is stored."""
    chars = re.sub(r"[^0-9A-Za-z]", "", number or "")
    return chars[-4:].upper() if len(chars) >= 4 else None


def _dated(words: str | None, now: datetime) -> date | None:
    try:
        return parse_due(words, now) if words else None
    except Exception:  # noqa: BLE001 — a bad date is just no date
        return None


def date_after_keyword(text: str, keyword: re.Pattern[str], now: datetime) -> date | None:
    """The first date written within 40 characters after a keyword."""
    for m in keyword.finditer(text or ""):
        window = text[m.end() : m.end() + 40]
        found = _dated(window, now)
        if found:
            return found
    return None


def guess_kind(text: str) -> str:
    low = (text or "").lower()
    return next((kind for word, kind in _KIND_WORDS if word in low), "other")


def fields_from(text: str, model: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    """Merge the model's fields with what plain code finds in the text."""
    model = model or {}
    kind = model.get("kind") if model.get("kind") in KINDS else guess_kind(text)
    if kind == "other":
        kind = guess_kind(text)
    expires = _dated(model.get("expires"), now) or date_after_keyword(text, _EXPIRY_KEYWORD, now)
    issued = _dated(model.get("issued"), now) or date_after_keyword(text, _ISSUE_KEYWORD, now)
    if issued and expires and issued > expires:
        issued, expires = expires, issued
    if expires is None and issued is not None:
        # "covered for 2 years from the date of purchase": no date written, but
        # a duration from the issue date is (qwen3 left these blank).
        expires = expiry_from_duration(text, issued)
    number = str(model.get("number") or "")
    title = scrub(str(model.get("title") or "").strip(), number)[:200]
    if not title:
        first = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
        title = scrub(first, number)[:80] or kind.replace("_", " ").title()
    return {
        "kind": kind,
        "title": title,
        "issuer": (scrub(str(model.get("issuer") or "").strip(), number)[:200] or None),
        "holder": (scrub(str(model.get("holder") or "").strip(), number)[:120] or None),
        "number_last4": last4(number),
        "issued_on": issued,
        "expires_on": expires,
    }


_LONG_ID = re.compile(r"\b(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]{6,}\b")
_DURATION = re.compile(
    r"\b(\d{1,2}|one|two|three|four|five|ten)[\s-]*(years?|yrs?|months?)\b"
    r"(?=[^.\n]{0,60}\b(warranty|guarantee|cover|covered|valid|validity|from|term|period)\b)"
    r"|\b(warranty|guarantee|cover(?:ed)?|valid(?:ity)?|term|period)\b[^.\n]{0,40}?\b"
    r"(\d{1,2}|one|two|three|four|five|ten)[\s-]*(years?|yrs?|months?)\b",
    re.I,
)
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10}


def scrub(value: str, number: str = "") -> str:
    """Drop the document number, and any long token with digits, from free text.

    The model put the full passport number in the title ("Indian passport —
    Z1234567"), which defeats keeping only the last four characters.
    """
    out = value
    if len(number.strip()) >= 4:
        out = out.replace(number.strip(), "")
    out = _LONG_ID.sub("", out)
    out = re.sub(r"\s*[—–-]\s*$", "", re.sub(r"\s{2,}", " ", out)).strip(" ,;:—–-")
    return out


def expiry_from_duration(text: str, start: date) -> date | None:
    m = _DURATION.search(text or "")
    if not m:
        return None
    count_raw, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(5), m.group(6))
    count = _WORDS.get(count_raw.lower()) if not count_raw.isdigit() else int(count_raw)
    if not count:
        return None
    months = count * 12 if unit.lower().startswith("y") else count
    year, month = divmod(start.month - 1 + months, 12)
    import calendar

    day = min(start.day, calendar.monthrange(start.year + year, month + 1)[1])
    # Cover ends the day before the anniversary.
    return date(start.year + year, month + 1, day) - timedelta(days=1)


async def extract(text: str, *, client=None, now: datetime | None = None) -> dict[str, Any]:
    """Fields for one document's text, on the local model only; never raises."""
    now = now or datetime.now(UTC)
    if client is None:
        from life_graph.api.dependencies import get_lm_client

        client = get_lm_client()
    data = None
    try:
        raw = await client.chat_local_only(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": (text or "")[:MAX_INPUT_CHARS]},
            ],
            model=settings.lm_extraction_model or None,
            temperature=0.1,
            max_tokens=400,
            response_format=_SCHEMA,
        )
        data = json.loads(raw) if raw else None
    except Exception:
        logger.warning("Local document extraction failed", exc_info=True)
    return fields_from(text, data if isinstance(data, dict) else None, now)


def to_dict(doc: Document, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(UTC).date()
    return {
        "id": str(doc.id),
        "kind": doc.kind,
        "title": doc.title,
        "issuer": doc.issuer,
        "holder": doc.holder,
        "number_last4": doc.number_last4,
        "issued_on": doc.issued_on.isoformat() if doc.issued_on else None,
        "expires_on": doc.expires_on.isoformat() if doc.expires_on else None,
        "days_left": (doc.expires_on - today).days if doc.expires_on else None,
        "notes": doc.notes,
        "source": doc.source,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


async def create(
    session: AsyncSession, tenant_id: str, fields: dict[str, Any], *, source: str = "api"
) -> Document:
    allowed = {
        "kind",
        "title",
        "issuer",
        "holder",
        "number_last4",
        "issued_on",
        "expires_on",
        "notes",
    }
    values = {k: v for k, v in fields.items() if k in allowed}
    if values.get("kind") not in KINDS:
        values["kind"] = "other"
    doc = Document(tenant_id=tenant_id, source=source, reminders_sent=[], **values)
    session.add(doc)
    await session.flush()
    return doc


async def file_text(
    session: AsyncSession,
    tenant_id: str,
    text: str,
    *,
    source: str = "api",
    overrides: dict[str, Any] | None = None,
    client=None,
) -> Document:
    """Extract and store one document from its text."""
    fields = await extract(text, client=client)
    for key, value in (overrides or {}).items():
        if value not in (None, ""):
            fields[key] = value
    return await create(session, tenant_id, fields, source=source)


async def get(session: AsyncSession, tenant_id: str, doc_id: uuid.UUID) -> Document | None:
    return (
        await session.execute(
            select(Document).where(Document.tenant_id == tenant_id, Document.id == doc_id)
        )
    ).scalar_one_or_none()


async def update(session: AsyncSession, doc: Document, changes: dict[str, Any]) -> Document:
    editable = {"kind", "title", "issuer", "holder", "issued_on", "expires_on", "notes"}
    if "number" in changes:
        doc.number_last4 = last4(changes.pop("number"))
    for key, value in changes.items():
        if key in editable:
            if key == "kind" and value not in KINDS:
                continue
            if key == "expires_on" and value != doc.expires_on:
                doc.reminders_sent = []  # a new date gets its own reminders
            setattr(doc, key, value)
    await session.flush()
    return doc


async def list_all(session: AsyncSession, tenant_id: str) -> list[Document]:
    return list(
        (
            await session.execute(
                select(Document)
                .where(Document.tenant_id == tenant_id)
                .order_by(Document.expires_on.asc().nulls_last(), Document.title)
            )
        )
        .scalars()
        .all()
    )


async def expiring(
    session: AsyncSession, tenant_id: str, today: date, within_days: int = 60
) -> list[Document]:
    """Documents expiring within ``within_days`` (and those expired in the last 30)."""
    from datetime import timedelta

    return list(
        (
            await session.execute(
                select(Document)
                .where(
                    Document.tenant_id == tenant_id,
                    Document.expires_on.is_not(None),
                    Document.expires_on <= today + timedelta(days=within_days),
                    Document.expires_on >= today - timedelta(days=30),
                )
                .order_by(Document.expires_on)
            )
        )
        .scalars()
        .all()
    )


def due_reminder(doc: Document, today: date) -> str | None:
    """The reminder this document needs today, if any: a threshold or 'expired'."""
    if doc.expires_on is None:
        return None
    sent = {str(s) for s in (doc.reminders_sent or [])}
    days = (doc.expires_on - today).days
    if days < 0:
        return EXPIRED if EXPIRED not in sent else None
    crossed = [t for t in THRESHOLDS if days <= t]
    if not crossed:
        return None
    nearest = min(crossed)
    return str(nearest) if str(nearest) not in sent else None


def reminder_text(doc: Document, today: date, key: str) -> tuple[str, str]:
    days = (doc.expires_on - today).days
    when = doc.expires_on.strftime("%d %b %Y")
    if key == EXPIRED:
        return f"{doc.title} expired on {when}", "Renew or replace it, then update the expiry date."
    unit = "day" if days == 1 else "days"
    return (
        f"{doc.title} expires in {days} {unit} ({when})",
        "Start the renewal now if it needs an appointment or paperwork.",
    )


async def sweep_reminders(session_factory, tenant_id: str, today: date, notifications) -> int:
    """Send each document's due reminder once. Returns how many were sent."""
    sent = 0
    async with session_factory() as session:
        docs = await expiring(session, tenant_id, today, within_days=max(THRESHOLDS))
        for doc in docs:
            key = due_reminder(doc, today)
            if key is None:
                continue
            title, body = reminder_text(doc, today, key)
            days = (doc.expires_on - today).days
            await notifications.create(
                tenant_id,
                title,
                body=body,
                priority="important" if days <= 7 else "info",
                source_type="document",
                source_id=str(doc.id),
                metadata={"kind": "document_expiry", "document_id": str(doc.id), "days_left": days},
                deliver_at_brief=days > 7,
            )
            # Every threshold already crossed counts as sent, so a document
            # filed 5 days before expiry gets one reminder, not three.
            crossed = [str(t) for t in THRESHOLDS if days <= t]
            doc.reminders_sent = sorted({*map(str, doc.reminders_sent or []), key, *crossed})
            sent += 1
        await session.commit()
    return sent


def brief_line(docs: list[Document], today: date) -> str | None:
    """One line for the brief: kinds and dates only, never numbers."""
    soon = [d for d in docs if d.expires_on and (d.expires_on - today).days <= 30]
    if not soon:
        return None
    parts = []
    for d in soon[:4]:
        days = (d.expires_on - today).days
        label = d.kind.replace("_", " ")
        parts.append(f"{label} {'expired' if days < 0 else f'in {days}d'}")
    more = f" (+{len(soon) - 4} more)" if len(soon) > 4 else ""
    return "Documents: " + ", ".join(parts) + more
