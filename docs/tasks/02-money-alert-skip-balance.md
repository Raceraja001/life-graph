# 02: Bank alerts, the amount is not the balance

| | |
|---|---|
| Theme | A. Money |
| Engine | `code-fixer-local`, `spec_first=True` |
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

Read first:
- life_graph/services/money.py: parse_alert, _SMS_AMOUNT, _SMS_DEBIT, _SMS_CREDIT, _SMS_ACCOUNT.
- tests/unit/test_assistant_money.py::test_bank_alerts and tests/unit/test_money_alert_not_transactions.py (both must keep passing unchanged).

Change (life_graph/services/money.py):
1. The amount is the first _SMS_AMOUNT match that is NOT introduced by a balance or limit word. A match is introduced by one when the up-to-25 characters before it end with "bal", "balance", "limit" or "lmt" as a whole word, optionally followed by spaces, ".", ":", "-", "is" or "of". Examples: "Avl Bal Rs", "Avl Bal: INR", "balance is Rs", "credit limit is Rs", "Avl Lmt Rs".
2. If every amount in the message is a balance or limit, return None.
3. In _SMS_CREDIT, the word "credit" must not count when it is followed by "card" or "limit" (use a negative lookahead: credit(?!\s+(?:card|limit))). "credited" still counts.

Cases (copy exactly; NOW = datetime(2026, 10, 24, 9, 0, tzinfo=UTC); each parsed case asserts (amount, direction, account_last4, occurred_on)):
- "Avl Bal Rs 10,000.00 in A/c XX1234. Rs 500.00 debited on 12-10-26 to VPA zomato@ybl." -> (Decimal("500.00"), "debit", "1234", date(2026, 10, 12))
- "Bal Rs 100.00. Rs 2,000 credited to A/c XX5678 on 01-10-26." -> (Decimal("2000"), "credit", "5678", date(2026, 10, 1))
- "A/c XX1234 debited for Rs 450.00; Avl Bal: INR 9,550.00" -> (Decimal("450.00"), "debit", "1234", NOW.date())
- "Your available credit limit is Rs 50,000. Rs 1,299 spent at AMAZON on 2026-10-10." -> (Decimal("1299"), "debit", None, date(2026, 10, 10))
- "Rs 2,000 credited to your Credit Card ending 4321 on 01-10-26." -> (Decimal("2000"), "credit", "4321", date(2026, 10, 1))
- "You have spent Rs 1,299 on your Credit Card ending 4321 at AMAZON on 2026-10-10." -> (Decimal("1299"), "debit", "4321", date(2026, 10, 10))
parse_alert(text, NOW) is None for:
- "Avl Bal INR 9,550.00 in A/c XX1234 as of 12-10-26."
- "Your A/c XX1234 balance is Rs 3,000 after the last debit."

Files you may touch:
- life_graph/services/money.py (parse_alert, _SMS_CREDIT, and one new module-level pattern)
- tests/unit/test_money_alert_amount.py (new)

Do NOT:
- change parse_amount, parse_day, merchant_from or the CSV import;
- edit any existing test file;
- remove the existing OTP check or the not-a-transaction checks added before this task;
- add a database, a mock or a new dependency.

## Spec
**Requirements:**
AC-1: The amount is the first one not introduced by a balance or limit word — test: tests/unit/test_money_alert_amount.py::test_balance_amount_is_not_the_transaction
AC-2: A message whose only amounts are balances or limits is not a transaction — test: tests/unit/test_money_alert_amount.py::test_balance_only_messages_are_not_transactions
AC-3: "credit card" and "credit limit" do not make a spend a credit — test: tests/unit/test_money_alert_amount.py::test_credit_card_and_credit_limit_are_not_credits
AC-4: Existing alert parsing is unchanged — test: tests/unit/test_assistant_money.py::test_bank_alerts
**Design:** Loop over _SMS_AMOUNT.finditer and skip matches whose preceding text ends with a balance/limit word; tighten _SMS_CREDIT with a lookahead.
**Tasks:**
1. Pick the first non-balance amount in parse_alert and return None when there is none, with tests (AC-1, AC-2, AC-4)
2. Add the card/limit lookahead to _SMS_CREDIT, with tests (AC-3, AC-4)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->

## Reviewer notes

- The 25-character look-back must be anchored at the end (`$`). A loose `search` would skip
  "Rs 500 debited. Avl bal Rs 9,500" style amounts that come *before* the balance.
