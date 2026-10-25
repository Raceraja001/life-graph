# 02: Bank alerts, the amount is not the balance

| | |
|---|---|
| Theme | A. Money |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
| Depends on | **01 merged** (same function) |
| Review | gates |
| Size | ~15 lines in `money.py`, one new test file |

## Why

`parse_alert` takes the **first** rupee amount in the SMS. Some banks put the balance or the
card limit first, so the balance is recorded as the spend. "Credit" in "credit limit" also
counts as a credit word, so a card spend after a limit line is recorded as money in.

Reproduced on 6459f6b:

```
"Avl Bal Rs 10,000.00 in A/c XX1234. Rs 500.00 debited on 12-10-26 to VPA zomato@ybl."
    -> debit 10000.00   (should be 500.00)
"Your available credit limit is Rs 50,000. Rs 1,299 spent at AMAZON on 2026-10-10."
    -> credit 50000     (should be debit 1299)
```

## Instruction

<!-- instruction:start -->
Bank alerts: parse_alert must not take the balance or limit as the transaction amount

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_money_alert_amount.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_money_alert_amount.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_money_alert_amount.py =====
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from life_graph.services.money import parse_alert

NOW = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)


def fields(text):
    txn = parse_alert(text, NOW)
    assert txn is not None
    return (txn.amount, txn.direction, txn.account_last4, txn.occurred_on)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Avl Bal Rs 10,000.00 in A/c XX1234. Rs 500.00 debited on 12-10-26 to VPA zomato@ybl.",
            (Decimal("500.00"), "debit", "1234", date(2026, 10, 12)),
        ),
        (
            "Bal Rs 100.00. Rs 2,000 credited to A/c XX5678 on 01-10-26.",
            (Decimal("2000"), "credit", "5678", date(2026, 10, 1)),
        ),
        (
            "A/c XX1234 debited for Rs 450.00; Avl Bal: INR 9,550.00",
            (Decimal("450.00"), "debit", "1234", NOW.date()),
        ),
    ],
)
def test_balance_amount_is_not_the_transaction(text, expected):
    assert fields(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Avl Bal INR 9,550.00 in A/c XX1234 as of 12-10-26.",
        "Your A/c XX1234 balance is Rs 3,000 after the last debit.",
    ],
)
def test_balance_only_messages_are_not_transactions(text):
    assert parse_alert(text, NOW) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Your available credit limit is Rs 50,000. Rs 1,299 spent at AMAZON on 2026-10-10.",
            (Decimal("1299"), "debit", None, date(2026, 10, 10)),
        ),
        (
            "Rs 2,000 credited to your Credit Card ending 4321 on 01-10-26.",
            (Decimal("2000"), "credit", "4321", date(2026, 10, 1)),
        ),
        (
            "You have spent Rs 1,299 on your Credit Card ending 4321 at AMAZON on 2026-10-10.",
            (Decimal("1299"), "debit", "4321", date(2026, 10, 10)),
        ),
    ],
)
def test_credit_card_and_credit_limit_are_not_credits(text, expected):
    assert fields(text) == expected
===== end of tests/unit/test_money_alert_amount.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_money_alert_amount.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/money.py (parse_alert) that makes those cases pass. Read the code first.
1. The amount is the first _SMS_AMOUNT match that is NOT introduced by a balance or limit word: the up-to-25 characters before the match end with "bal", "balance", "limit" or "lmt" as a whole word, then optionally spaces, ".", ":", "-", "is" or "of" ("Avl Bal Rs", "Avl Bal: INR", "balance is Rs", "credit limit is Rs", "Avl Lmt Rs"). Add one module-level pattern for it, anchored at the end, for example r"\b(?:bal|balance|limit|lmt)\b[\s.:\-]*(?:(?:is|of)\s*)?$" (re.I), searched in body[max(0, m.start() - 25):m.start()].
2. If every amount in the message is a balance or limit, return None.
3. In _SMS_CREDIT, "credit" must not count when "card" or "limit" follows: credit(?!\s+(?:card|limit)). "credited" still counts.
Keep the OTP check and the not-a-transaction checks that are already in parse_alert.

STEP 4. Run run_tests with paths ["tests/unit/test_money_alert_amount.py", "tests/unit/test_assistant_money.py", "tests/unit/test_money_alert_not_transactions.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_money_alert_amount.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what parse_alert did before, in your words>
Change: <what you changed in parse_alert (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_money_alert_amount.py or tests/unit/test_assistant_money.py shows it does not>

Files you may touch:
- life_graph/services/money.py (parse_alert)
- tests/unit/test_money_alert_amount.py (new; created in STEP 1)

Do NOT:
- change parse_amount, parse_day, merchant_from or the CSV import;
- remove the OTP check or the not-a-transaction checks added before this task;
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: The amount is the first one not introduced by a balance or limit word — test: tests/unit/test_money_alert_amount.py::test_balance_amount_is_not_the_transaction
AC-2: A message whose only amounts are balances or limits is not a transaction — test: tests/unit/test_money_alert_amount.py::test_balance_only_messages_are_not_transactions
AC-3: "credit card" and "credit limit" do not make a spend a credit — test: tests/unit/test_money_alert_amount.py::test_credit_card_and_credit_limit_are_not_credits
AC-4: Existing alert parsing is unchanged — test: tests/unit/test_assistant_money.py::test_bank_alerts
**Design:** Loop over _SMS_AMOUNT.finditer and skip matches whose preceding text ends with a balance/limit word; tighten _SMS_CREDIT with a lookahead.
**Tasks:**
1. Create tests/unit/test_money_alert_amount.py exactly as given, then make parse_alert pick the first non-balance amount, return None when there is none, and add the card/limit lookahead to _SMS_CREDIT, until it and the existing alert tests pass (AC-1, AC-2, AC-3, AC-4)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->

## Reviewer notes

- The 25-character look-back must be anchored at the end (`$`). A loose `search` would skip
  "Rs 500 debited. Avl bal Rs 9,500" style amounts that come *before* the balance.
