"""Phase C: statement and alert parsing, categories, budget alerts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from life_graph.services import money

NOW = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)

HDFC_CSV = """HDFC BANK Ltd.  Statement of accounts
Account No : XXXXXXXX1234
,,,,,,
Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/10/26,UPI-SWIGGY-swiggy@icici-ICIC0001-123456,0000123456,01/10/26,450.00,,10550.00
02/10/26,SALARY OCT 2026 ACME PVT LTD,0000999,02/10/26,,85000.00,95550.00
05/10/26,POS 1234XXXX AMAZON PAY INDIA,0000222,05/10/26,"2,499.00",,93051.00
,,,,,,
Statement Summary :-,,,,,,
"""

SBI_CSV = """Txn Date;Description;Amount;Dr/Cr
12 Oct 2026;ATM WDL CHENNAI;2000.00;DR
13 Oct 2026;NEFT REFUND MERCHANT;150.50;CR
"""


def test_hdfc_style_statement():
    txns, problems = money.parse_csv(HDFC_CSV, NOW)
    assert problems == []
    assert [(t.occurred_on, t.amount, t.direction) for t in txns] == [
        (date(2026, 10, 1), Decimal("450.00"), "debit"),
        (date(2026, 10, 2), Decimal("85000.00"), "credit"),
        (date(2026, 10, 5), Decimal("2499.00"), "debit"),
    ]
    assert [t.merchant for t in txns] == [
        "SWIGGY",
        "SALARY OCT 2026 ACME PVT LTD",
        "AMAZON PAY INDIA",
    ]


def test_amount_and_dr_cr_columns():
    txns, _ = money.parse_csv(SBI_CSV, NOW)
    assert [(t.amount, t.direction) for t in txns] == [
        (Decimal("2000.00"), "debit"),
        (Decimal("150.50"), "credit"),
    ]


def test_a_file_without_a_header_is_reported():
    txns, problems = money.parse_csv("hello,world\n1,2\n", NOW)
    assert txns == [] and problems


@pytest.mark.parametrize(
    ("text", "amount", "direction", "last4", "merchant_has", "day"),
    [
        (
            "Rs.250.00 debited from A/c XX1234 on 12-10-26 to VPA swiggy@icici UPI Ref 628512345678.",
            "250.00",
            "debit",
            "1234",
            "swiggy",
            date(2026, 10, 12),
        ),
        (
            "INR 85,000.00 credited to your A/c no. XXXXXX5678 on 01-Oct-26 by NEFT from ACME PVT LTD. Avl Bal INR 95,550.00",
            "85000.00",
            "credit",
            "5678",
            None,
            date(2026, 10, 1),
        ),
        (
            "You have spent Rs 1,299 on your Credit Card ending 4321 at AMAZON on 2026-10-10.",
            "1299",
            "debit",
            "4321",
            "AMAZON",
            date(2026, 10, 10),
        ),
    ],
)
def test_bank_alerts(text, amount, direction, last4, merchant_has, day):
    txn = money.parse_alert(text, NOW)
    assert txn is not None
    assert txn.amount == Decimal(amount) and txn.direction == direction
    assert txn.account_last4 == last4 and txn.occurred_on == day
    if merchant_has:
        assert merchant_has.lower() in (txn.merchant or "").lower()


@pytest.mark.parametrize(
    "text",
    [
        "Your OTP for a transaction of Rs 500 is 482913. Do not share.",
        "Hi, are we meeting at 5?",
        "Get Rs 500 cashback on your next order!",
    ],
)
def test_non_transactions_are_ignored(text):
    assert money.parse_alert(text, NOW) is None


def test_user_rules_beat_builtin_keywords():
    t = money.Txn(
        date(2026, 10, 1), Decimal(10), "debit", "UPI/AMAZON PRIME", merchant="AMAZON PRIME"
    )
    assert money.categorise(t, []) == ("shopping", "rule")
    assert money.categorise(t, [("amazon prime", "subscriptions")]) == ("subscriptions", "user")
    salary = money.Txn(
        date(2026, 10, 1), Decimal(10), "credit", "SALARY OCT", merchant="SALARY OCT"
    )
    assert money.categorise(salary, [])[0] == "income"
    odd = money.Txn(date(2026, 10, 1), Decimal(10), "debit", "XYZ TRADERS", merchant="XYZ TRADERS")
    assert money.categorise(odd, [])[0] == "uncategorised"


def test_dedup_hash_is_stable_and_tenant_specific():
    t = money.Txn(date(2026, 10, 1), Decimal("450.00"), "debit", "UPI  SWIGGY")
    same = money.Txn(date(2026, 10, 1), Decimal("450"), "debit", "upi swiggy")
    assert t.dedup_hash("a") == same.dedup_hash("a") != t.dedup_hash("b")


def test_budget_alert_levels():
    assert money.due_alert(None, []) is None
    assert money.due_alert(50, []) is None
    assert money.due_alert(85, []) == 80
    assert money.due_alert(85, [80]) is None
    assert money.due_alert(130, []) == 100
    assert money.due_alert(130, [80, 100]) is None


def test_brief_and_cloud_views_carry_no_amounts():
    s = {
        "month": "2026-10",
        "total_spent": 5000.0,
        "income": 85000.0,
        "categories": [
            {"category": "food", "spent": 4500.0, "budget": 5000.0, "percent_of_budget": 90},
            {"category": "fuel", "spent": 500.0, "budget": None, "percent_of_budget": None},
        ],
    }
    assert money.brief_line(s) == "Budgets this month: food 90%"
    cloud = money.cloud_view(s)
    assert "4500" not in str(cloud) and "85000" not in str(cloud)


def test_month_bounds():
    assert money.month_bounds("2026-12", date(2026, 1, 1)) == (
        date(2026, 12, 1),
        date(2027, 1, 1),
        "2026-12",
    )
    with pytest.raises(ValueError):
        money.month_bounds("2026-13", date(2026, 1, 1))


@pytest.mark.asyncio
async def test_model_categories_must_be_from_the_list():
    class LM:
        async def chat_local_only(self, **_kw):
            return '{"categories": ["food", "bogus"]}'

    assert await money.categorise_with_model(["a", "b"], client=LM()) == ["food", None]

    class Broken:
        async def chat_local_only(self, **_kw):
            return '{"categories": ["food"]}'  # wrong length

    assert await money.categorise_with_model(["a", "b"], client=Broken()) == [None, None]
