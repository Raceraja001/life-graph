# 01: Bank alerts, skip messages that are not a transaction

| | |
|---|---|
| Theme | A. Money |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
| Depends on | none |
| Review | gates |
| Size | ~20 lines in `money.py`, one new test file |

## Why

`services/money.py::parse_alert` turns a bank SMS into a transaction. On 6459f6b it records
messages that are not transactions: a scheduled SIP debit, a declined card purchase, a failed
UPI payment and a pre-approved loan offer all come back as real debits or credits. These go
straight into the money check-in (Job 5) and the budgets.

Reproduced (today 2026-10-24):

```
"Your SIP of Rs 5,000 will be debited on 05-11-2026 from A/c XX1234."   -> debit 5000
"Purchase of Rs 1,200 at AMAZON on your card ending 4321 was declined." -> debit 1200
"Pre-approved personal loan of Rs 5,00,000 can be credited instantly. Apply now!" -> credit 500000
"Txn of INR 300 failed at SWIGGY. Amount will be refunded if debited."  -> credit 300
```

## Instruction

<!-- instruction:start -->
Bank alerts: make parse_alert ignore messages that are not a completed transaction

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_money_alert_not_transactions.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_money_alert_not_transactions.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_money_alert_not_transactions.py =====
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from life_graph.services.money import parse_alert

NOW = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "text",
    [
        "Your SIP of Rs 5,000 will be debited on 05-11-2026 from A/c XX1234.",
        "Rs 2,000 to be debited on 01-11-26 towards your e-mandate for LIC. Ensure sufficient balance.",
        "Credit card bill of Rs 12,340 is due on 05-11-2026. Min due Rs 620.",
    ],
)
def test_scheduled_and_due_alerts_are_not_transactions(text):
    assert parse_alert(text, NOW) is None


@pytest.mark.parametrize(
    "text",
    [
        "Purchase of Rs 1,200 at AMAZON on your card ending 4321 was declined.",
        "Txn of INR 300 failed at SWIGGY. Amount will be refunded if debited.",
        "Your payment of Rs 650 to AIRTEL was unsuccessful.",
    ],
)
def test_declined_and_failed_alerts_are_not_transactions(text):
    assert parse_alert(text, NOW) is None


@pytest.mark.parametrize(
    "text",
    [
        "Pre-approved personal loan of Rs 5,00,000 can be credited instantly. Apply now!",
        "Get cashback of up to Rs 150 when you pay with UPI. T&C apply.",
    ],
)
def test_offers_are_not_transactions(text):
    assert parse_alert(text, NOW) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Refund of Rs 300 for failed txn at SWIGGY has been credited to A/c XX1234 on 22-10-26.",
            (Decimal("300"), "credit", "1234", date(2026, 10, 22)),
        ),
        (
            "Rs 799 debited from A/c XX1234 for Netflix autopay on 20-10-26.",
            (Decimal("799"), "debit", "1234", date(2026, 10, 20)),
        ),
    ],
)
def test_real_alerts_still_parse(text, expected):
    txn = parse_alert(text, NOW)
    assert txn is not None
    assert (txn.amount, txn.direction, txn.account_last4, txn.occurred_on) == expected
===== end of tests/unit/test_money_alert_not_transactions.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_money_alert_not_transactions.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/money.py (parse_alert) that makes those cases pass. Read the code first.
Add module-level compiled patterns next to the other _SMS_* patterns (case-insensitive), and in parse_alert, right after the existing OTP check, return None when:
1. the money only will or may move: "will be", "shall be", "to be", "can be" or "may be" followed by debited, credited, deducted, charged, refunded or reversed (also "auto-debited"); or "due on", "due by", "due date", "is due", "are due", "scheduled", "upcoming", "reminder". This pattern works: r"\b(?:(?:will|shall|to|can|may)\s+be\s+(?:auto-)?(?:debited|credited|deducted|charged|refunded|reversed)|due\s+(?:on|by|date)|(?:is|are)\s+due|scheduled|upcoming|reminder)\b"
2. it is a promotion: "pre-approved" or "preapproved", "apply now", "eligible for", "limited period", "click", "T&C", "up to" or "upto";
3. it declined or failed ("declined", "failed", "unsuccessful", "rejected"), unless it also says "credited", "refunded" or "reversed": a refund after a failure is a real credit. Rule 1 is checked first, so "will be refunded" is still skipped.

STEP 4. Run run_tests with paths ["tests/unit/test_money_alert_not_transactions.py", "tests/unit/test_assistant_money.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_money_alert_not_transactions.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what parse_alert did before, in your words>
Change: <what you changed in parse_alert (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_money_alert_not_transactions.py or tests/unit/test_assistant_money.py shows it does not>

Files you may touch:
- life_graph/services/money.py (parse_alert)
- tests/unit/test_money_alert_not_transactions.py (new; created in STEP 1)

Do NOT:
- change parse_amount, parse_day, merchant_from, categorise or any function other than parse_alert;
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: Scheduled, due and possible debits/credits are not transactions — test: tests/unit/test_money_alert_not_transactions.py::test_scheduled_and_due_alerts_are_not_transactions
AC-2: Declined and failed payments are not transactions, unless the money is said to have come back — test: tests/unit/test_money_alert_not_transactions.py::test_declined_and_failed_alerts_are_not_transactions
AC-3: Offers and promotions are not transactions — test: tests/unit/test_money_alert_not_transactions.py::test_offers_are_not_transactions
AC-4: Real alerts, including a refund after a failure, still parse with exact fields — test: tests/unit/test_money_alert_not_transactions.py::test_real_alerts_still_parse
AC-5: The existing alert tests still pass unchanged — test: tests/unit/test_assistant_money.py::test_bank_alerts
**Design:** Three compiled patterns (future, promo, failed) plus a came-back pattern, checked in parse_alert after the OTP check and before the direction is worked out.
**Tasks:**
1. Create tests/unit/test_money_alert_not_transactions.py exactly as given, then add the patterns and early returns to parse_alert until it and the existing alert tests pass (AC-1, AC-2, AC-3, AC-4, AC-5)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->

## Reviewer notes

- Check that rule 3's exception does not let "will be refunded" through. Rule 1 must win.
- If a merchant name itself contains "click" or "upto", the alert is skipped. That is
  acceptable for now; say so in the PR if the engine notices it.
