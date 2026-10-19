"""Phase H: invoice arithmetic, lifecycle rules, drafts and rendering."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from life_graph.config import settings
from life_graph.models.assistant import Invoice
from life_graph.services import invoices


def test_items_are_cleaned_and_totals_rounded():
    lines = invoices.clean_items(
        [
            {"description": " Design work ", "quantity": 3, "unit_price": 1500},
            {"description": "Hosting", "quantity": 1, "unit_price": "999.995"},
        ]
    )
    assert lines[0] == {
        "description": "Design work",
        "quantity": 3.0,
        "unit_price": 1500.0,
        "amount": 4500.0,
    }
    subtotal, tax, total = invoices.totals(lines, Decimal("18"))
    assert (subtotal, tax, total) == (Decimal("5500.00"), Decimal("990.00"), Decimal("6490.00"))


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{"description": "", "unit_price": 1}],
        [{"description": "x", "quantity": 0, "unit_price": 1}],
    ],
)
def test_bad_items_are_refused(items):
    with pytest.raises(invoices.InvoiceError):
        invoices.clean_items(items)


def _inv(**kw) -> Invoice:
    base = dict(
        tenant_id="t",
        number="INV-2026-0001",
        client_name="Asha Traders",
        client_email="asha@example.com",
        currency="INR",
        items=[{"description": "Work <b>", "quantity": 1, "unit_price": 100.0, "amount": 100.0}],
        tax_rate=Decimal("0"),
        subtotal=Decimal("100"),
        tax=Decimal("0"),
        total=Decimal("100"),
        status="draft",
        issued_on=date(2026, 10, 1),
        due_on=date(2026, 10, 16),
    )
    return Invoice(**{**base, **kw})


def test_lifecycle_rules():
    inv = _inv()
    draft = invoices.mark_sent(inv, date(2026, 10, 2))
    assert inv.status == "sent" and draft["to"] == "asha@example.com"
    with pytest.raises(invoices.InvoiceError):
        invoices.edit(inv, {"notes": "x"})  # only drafts are editable
    with pytest.raises(invoices.InvoiceError):
        invoices.mark_sent(inv, date(2026, 10, 3))
    invoices.mark_paid(inv, date(2026, 10, 10))
    assert inv.status == "paid"
    with pytest.raises(invoices.InvoiceError):
        invoices.void(inv)


def test_editing_a_draft_recomputes_totals():
    inv = _inv()
    invoices.edit(
        inv, {"items": [{"description": "More", "quantity": 2, "unit_price": 250}], "tax_rate": 10}
    )
    assert (inv.subtotal, inv.tax, inv.total) == (
        Decimal("500.00"),
        Decimal("50.00"),
        Decimal("550.00"),
    )


def test_overdue_reminders_are_spaced_a_week_apart():
    inv = _inv(status="sent")
    assert not invoices.overdue_reminder_due(inv, date(2026, 10, 16))  # due today
    assert invoices.overdue_reminder_due(inv, date(2026, 10, 17))
    inv.last_reminded_on = date(2026, 10, 17)
    assert not invoices.overdue_reminder_due(inv, date(2026, 10, 20))
    assert invoices.overdue_reminder_due(inv, date(2026, 10, 24))
    assert not invoices.overdue_reminder_due(_inv(status="paid"), date(2026, 12, 1))


def test_reminder_draft_names_the_invoice_and_days(monkeypatch):
    monkeypatch.setattr(settings, "invoice_seller_name", "Raja Studio")
    d = invoices.email_draft(_inv(status="sent"), reminder=True, today=date(2026, 10, 20))
    assert "INV-2026-0001" in d["subject"] and "₹100.00" in d["subject"]
    assert "4 days ago" in d["body"] and d["body"].endswith("Raja Studio")


def test_rendered_html_escapes_user_text(monkeypatch):
    monkeypatch.setattr(settings, "invoice_seller_name", "Raja <Studio>")
    page = invoices.render_html(_inv(client_name="<script>x</script>"))
    assert "<script>x</script>" not in page and "&lt;script&gt;" in page
    assert "Work &lt;b&gt;" in page and "Raja &lt;Studio&gt;" in page
