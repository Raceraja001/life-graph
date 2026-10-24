# 01: Bank alerts, skip messages that are not a transaction

| | |
|---|---|
| Theme | A. Money |
| Engine | `code-fixer-local`, `spec_first=True` |
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

Read first:
- life_graph/services/money.py: parse_alert, and the _SMS_* patterns just above it.
- tests/unit/test_assistant_money.py: test_bank_alerts and test_non_transactions_are_ignored (these must keep passing unchanged).

Change (life_graph/services/money.py, parse_alert only):
Right after the existing OTP check, return None when the message is one of these. Add each as a module-level compiled regex next to the other _SMS_* patterns, case-insensitive:
1. Future or possible money movement: "will be", "shall be", "to be", "can be" or "may be", followed by one of debited, credited, deducted, charged, refunded, reversed (also "auto-debited"). Also "due on", "due by", "due date", "is due", "are due", "scheduled", "upcoming", "reminder".
2. Promotions: "pre-approved" or "preapproved", "apply now", "eligible for", "limited period", "click", "T&C", "up to" or "upto".
3. Declined or failed: "declined", "failed", "unsuccessful", "rejected". The exception: the message also says the money came back ("credited", "refunded" or "reversed") and rule 1 did not match. A refund for a failed payment is a real credit.

Cases (copy them exactly into a parametrized test; NOW = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)):
parse_alert(text, NOW) is None for each of:
- "Your SIP of Rs 5,000 will be debited on 05-11-2026 from A/c XX1234."
- "Rs 2,000 to be debited on 01-11-26 towards your e-mandate for LIC. Ensure sufficient balance."
- "Credit card bill of Rs 12,340 is due on 05-11-2026. Min due Rs 620."
- "Pre-approved personal loan of Rs 5,00,000 can be credited instantly. Apply now!"
- "Get cashback of up to Rs 150 when you pay with UPI. T&C apply."
- "Purchase of Rs 1,200 at AMAZON on your card ending 4321 was declined."
- "Txn of INR 300 failed at SWIGGY. Amount will be refunded if debited."
- "Your payment of Rs 650 to AIRTEL was unsuccessful."
Still parsed, with exactly these (amount, direction, account_last4, occurred_on):
- "Refund of Rs 300 for failed txn at SWIGGY has been credited to A/c XX1234 on 22-10-26." -> (Decimal("300"), "credit", "1234", date(2026, 10, 22))
- "Rs 799 debited from A/c XX1234 for Netflix autopay on 20-10-26." -> (Decimal("799"), "debit", "1234", date(2026, 10, 20))

Files you may touch:
- life_graph/services/money.py (parse_alert and new module-level patterns only)
- tests/unit/test_money_alert_not_transactions.py (new)

Do NOT:
- change parse_amount, parse_day, merchant_from, categorise or any other function;
- edit tests/unit/test_assistant_money.py or any other existing test;
- assert only "is None" / "is not None" for the parsed cases: assert all four fields;
- add a database, a mock or a new dependency (this is pure string logic).

## Spec
**Requirements:**
AC-1: Scheduled, due and possible debits/credits are not transactions — test: tests/unit/test_money_alert_not_transactions.py::test_scheduled_and_due_alerts_are_not_transactions
AC-2: Declined and failed payments are not transactions, unless the money is said to have come back — test: tests/unit/test_money_alert_not_transactions.py::test_declined_and_failed_alerts_are_not_transactions
AC-3: Offers and promotions are not transactions — test: tests/unit/test_money_alert_not_transactions.py::test_offers_are_not_transactions
AC-4: Real alerts, including a refund after a failure, still parse with exact fields — test: tests/unit/test_money_alert_not_transactions.py::test_real_alerts_still_parse
AC-5: The existing alert tests still pass unchanged — test: tests/unit/test_assistant_money.py::test_bank_alerts
**Design:** Three compiled patterns (future, promo, failed) plus a came-back pattern, checked in parse_alert after the OTP check and before the direction is worked out.
**Tasks:**
1. Add the patterns and the early returns to parse_alert, and write tests/unit/test_money_alert_not_transactions.py with the cases above (AC-1, AC-2, AC-3, AC-4, AC-5)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->

## Reviewer notes

- Check that rule 3's exception does not let "will be refunded" through. Rule 1 must win.
- If a merchant name itself contains "click" or "upto", the alert is skipped. That is
  acceptable for now; say so in the PR if the engine notices it.
