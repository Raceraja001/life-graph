"""Invoices: draft, number, render, track and chase what clients owe.

Phase H of docs/specs/assistant-capabilities.md, for the commercial side of
the user's work.

- **Numbering** is per tenant and per year (``INV-2026-0001``); a unique
  index backs it, and a clash from two drafts created at once retries with
  the next number.
- **Totals** are computed here with ``Decimal`` and stored, so an invoice that
  has been sent never changes because a rule changed later.
- **Lifecycle:** draft → sent → paid, or void from draft or sent. Only a
  draft can be edited.
- **Sending is a stub.** ``mark_sent`` records the date and returns the email
  as a draft (subject and body) for the user to send from their own mailbox.
  No mail is sent from here: an invoice email goes out under the user's name
  and is theirs to send. Wiring a sender is a separate decision.
- **Overdue:** the daily sweep raises a reminder for each sent invoice past
  its due date, at most once every ``REMIND_EVERY_DAYS``, with the chaser
  email drafted.
"""

from __future__ import annotations

import html
import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from life_graph.config import settings
from life_graph.models.assistant import Invoice

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

STATUSES = ("draft", "sent", "paid", "void")
REMIND_EVERY_DAYS = 7
CENT = Decimal("0.01")


class InvoiceError(ValueError):
    """The request breaks an invoice rule; the message says which."""


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except Exception as exc:  # noqa: BLE001
        raise InvoiceError(f"not an amount: {value!r}") from exc


def clean_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        raise InvoiceError("an invoice needs at least one line item")
    out = []
    for i, item in enumerate(items, start=1):
        desc = str(item.get("description") or "").strip()
        if not desc:
            raise InvoiceError(f"line {i} has no description")
        qty = Decimal(str(item.get("quantity", 1)))
        price = _money(item.get("unit_price", 0))
        if qty <= 0 or price < 0:
            raise InvoiceError(f"line {i}: quantity must be positive and price not negative")
        out.append(
            {
                "description": desc[:300],
                "quantity": float(qty),
                "unit_price": float(price),
                "amount": float(_money(qty * price)),
            }
        )
    return out


def totals(items: list[dict[str, Any]], tax_rate: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = sum((_money(i["amount"]) for i in items), Decimal(0))
    tax = _money(subtotal * tax_rate / 100)
    return subtotal, tax, subtotal + tax


async def _next_number(session: AsyncSession, tenant_id: str, year: int, bump: int = 0) -> str:
    prefix = f"INV-{year}-"
    taken = (
        await session.execute(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.tenant_id == tenant_id, Invoice.number.like(f"{prefix}%"))
        )
    ).scalar_one()
    return f"{prefix}{taken + 1 + bump:04d}"


async def create(
    session: AsyncSession,
    tenant_id: str,
    *,
    client_name: str,
    items: list[dict[str, Any]],
    today: date,
    client_email: str | None = None,
    client_details: str | None = None,
    currency: str = "INR",
    tax_rate: float = 0,
    due_days: int = 15,
    notes: str | None = None,
) -> Invoice:
    if not client_name.strip():
        raise InvoiceError("client_name is required")
    rate = Decimal(str(tax_rate))
    if not (0 <= rate <= 100):
        raise InvoiceError("tax_rate is a percentage between 0 and 100")
    lines = clean_items(items)
    subtotal, tax, total = totals(lines, rate)
    for bump in range(5):
        number = await _next_number(session, tenant_id, today.year, bump)
        invoice = Invoice(
            tenant_id=tenant_id,
            number=number,
            client_name=client_name.strip()[:200],
            client_email=(client_email or "").strip() or None,
            client_details=client_details,
            currency=currency.upper()[:3],
            items=lines,
            tax_rate=rate,
            subtotal=subtotal,
            tax=tax,
            total=total,
            status="draft",
            issued_on=today,
            due_on=today + timedelta(days=max(0, int(due_days))),
            notes=notes,
        )
        try:
            async with session.begin_nested():
                session.add(invoice)
                await session.flush()
            return invoice
        except IntegrityError:
            continue  # another draft took the number; try the next
    raise InvoiceError("could not allocate an invoice number")


async def get(session: AsyncSession, tenant_id: str, invoice_id) -> Invoice | None:
    return (
        await session.execute(
            select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.id == invoice_id)
        )
    ).scalar_one_or_none()


async def list_all(
    session: AsyncSession, tenant_id: str, status: str | None = None
) -> list[Invoice]:
    stmt = select(Invoice).where(Invoice.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(Invoice.status == status)
    return list((await session.execute(stmt.order_by(Invoice.issued_on.desc()))).scalars().all())


def edit(invoice: Invoice, changes: dict[str, Any]) -> Invoice:
    if invoice.status != "draft":
        raise InvoiceError(
            f"a {invoice.status} invoice cannot be edited; void it and issue a new one"
        )
    if "items" in changes or "tax_rate" in changes:
        lines = clean_items(changes.get("items", invoice.items))
        rate = Decimal(str(changes.get("tax_rate", invoice.tax_rate)))
        invoice.items = lines
        invoice.tax_rate = rate
        invoice.subtotal, invoice.tax, invoice.total = totals(lines, rate)
    for key in ("client_name", "client_email", "client_details", "notes", "due_on"):
        if key in changes and changes[key] is not None:
            setattr(invoice, key, changes[key])
    return invoice


def _amount(inv: Invoice) -> str:
    symbol = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get(inv.currency, inv.currency + " ")
    return f"{symbol}{inv.total:,.2f}"


def email_draft(
    inv: Invoice, *, reminder: bool = False, today: date | None = None
) -> dict[str, str]:
    """The email to send with (or to chase) an invoice; the user sends it."""
    seller = settings.invoice_seller_name or "us"
    first = inv.client_name.split()[0] if inv.client_name else ""
    if reminder:
        days = ((today or date.today()) - inv.due_on).days
        subject = f"Reminder: invoice {inv.number} ({_amount(inv)}) was due {inv.due_on:%d %b %Y}"
        body = (
            f"Hi {first},\n\nA gentle reminder that invoice {inv.number} for {_amount(inv)}"
            f" was due on {inv.due_on:%d %b %Y} ({days} day{'s' if days != 1 else ''} ago)."
            " If it has already been paid, please ignore this and thank you; otherwise"
            " could you let me know when to expect payment?\n\n"
            f"Thanks,\n{seller}"
        )
    else:
        subject = f"Invoice {inv.number} from {seller} — {_amount(inv)} due {inv.due_on:%d %b %Y}"
        body = (
            f"Hi {first},\n\nPlease find invoice {inv.number} for {_amount(inv)} attached,"
            f" due on {inv.due_on:%d %b %Y}.\n\nThanks,\n{seller}"
        )
    return {"to": inv.client_email or "", "subject": subject, "body": body}


def mark_sent(inv: Invoice, today: date) -> dict[str, str]:
    if inv.status != "draft":
        raise InvoiceError(f"only a draft can be sent; this one is {inv.status}")
    inv.status, inv.sent_on = "sent", today
    return email_draft(inv)


def mark_paid(inv: Invoice, paid_on: date) -> None:
    if inv.status not in ("sent", "draft"):
        raise InvoiceError(f"a {inv.status} invoice cannot be marked paid")
    inv.status, inv.paid_on = "paid", paid_on


def void(inv: Invoice) -> None:
    if inv.status == "paid":
        raise InvoiceError("a paid invoice cannot be voided")
    inv.status = "void"


def overdue_reminder_due(inv: Invoice, today: date) -> bool:
    if inv.status != "sent" or inv.due_on >= today:
        return False
    return inv.last_reminded_on is None or (today - inv.last_reminded_on).days >= REMIND_EVERY_DAYS


async def sweep_overdue(session_factory, tenant_id: str, today: date, notifications) -> int:
    sent = 0
    async with session_factory() as session:
        rows = await list_all(session, tenant_id, status="sent")
        for inv in rows:
            if not overdue_reminder_due(inv, today):
                continue
            draft = email_draft(inv, reminder=True, today=today)
            await notifications.create(
                tenant_id,
                f"Invoice {inv.number} to {inv.client_name} is {(today - inv.due_on).days} days overdue",
                body=f"Drafted reminder:\n\nSubject: {draft['subject']}\n\n{draft['body']}",
                priority="info",
                source_type="invoice",
                source_id=str(inv.id),
                metadata={"kind": "invoice_overdue", "invoice_id": str(inv.id), "email": draft},
                deliver_at_brief=True,
            )
            inv.last_reminded_on = today
            sent += 1
        await session.commit()
    return sent


async def overdue_count(session: AsyncSession, tenant_id: str, today: date) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.tenant_id == tenant_id, Invoice.status == "sent", Invoice.due_on < today)
        )
    ).scalar_one()


def brief_line(overdue: int) -> str | None:
    return f"Invoices: {overdue} overdue" if overdue else None


def to_dict(inv: Invoice) -> dict[str, Any]:
    return {
        "id": str(inv.id),
        "number": inv.number,
        "client_name": inv.client_name,
        "client_email": inv.client_email,
        "client_details": inv.client_details,
        "currency": inv.currency,
        "items": inv.items,
        "tax_rate": float(inv.tax_rate),
        "subtotal": float(inv.subtotal),
        "tax": float(inv.tax),
        "total": float(inv.total),
        "status": inv.status,
        "issued_on": inv.issued_on.isoformat(),
        "due_on": inv.due_on.isoformat(),
        "sent_on": inv.sent_on.isoformat() if inv.sent_on else None,
        "paid_on": inv.paid_on.isoformat() if inv.paid_on else None,
        "notes": inv.notes,
    }


def render_html(inv: Invoice) -> str:
    """A printable, self-contained invoice page (print to PDF from the browser)."""
    e = html.escape
    seller = e(settings.invoice_seller_name or "")
    seller_details = "<br>".join(
        e(x) for x in (settings.invoice_seller_details or "").split("|") if x
    )
    client_details = "<br>".join(e(x) for x in re.split(r"\n|\|", inv.client_details or "") if x)
    rows = "".join(
        f"<tr><td>{e(i['description'])}</td><td class=n>{i['quantity']:g}</td>"
        f"<td class=n>{i['unit_price']:,.2f}</td><td class=n>{i['amount']:,.2f}</td></tr>"
        for i in inv.items
    )
    tax_row = (
        f"<tr><td colspan=3 class=n>Tax ({inv.tax_rate:g}%)</td><td class=n>{inv.tax:,.2f}</td></tr>"
        if inv.tax
        else ""
    )
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Invoice {e(inv.number)}</title>
<style>
body{{font:14px/1.5 system-ui,sans-serif;color:#111;max-width:760px;margin:40px auto;padding:0 16px}}
h1{{font-size:22px;margin:0}} .muted{{color:#555}} table{{width:100%;border-collapse:collapse;margin-top:24px}}
th,td{{padding:8px;border-bottom:1px solid #ddd;text-align:left}} .n{{text-align:right}}
.head{{display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap}} .total td{{font-weight:600}}
@media print{{body{{margin:0}}}}
</style></head><body>
<div class="head"><div><h1>{seller or "Invoice"}</h1><div class="muted">{seller_details}</div></div>
<div><b>Invoice {e(inv.number)}</b><br>Issued {inv.issued_on:%d %b %Y}<br>Due {inv.due_on:%d %b %Y}</div></div>
<p><b>Bill to</b><br>{e(inv.client_name)}<br><span class="muted">{client_details}</span></p>
<table><thead><tr><th>Description</th><th class=n>Qty</th><th class=n>Rate</th><th class=n>Amount ({e(inv.currency)})</th></tr></thead>
<tbody>{rows}
<tr><td colspan=3 class=n>Subtotal</td><td class=n>{inv.subtotal:,.2f}</td></tr>{tax_row}
<tr class="total"><td colspan=3 class=n>Total</td><td class=n>{e(_amount(inv))}</td></tr></tbody></table>
{f"<p class='muted'>{e(inv.notes)}</p>" if inv.notes else ""}
</body></html>"""
