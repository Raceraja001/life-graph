# 08: Page monitors, the price is the currency-marked number

| | |
|---|---|
| Theme | A. Money |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
| Depends on | none |
| Review | gates |
| Size | ~15 lines in `page_monitors.py`, one new test file |
| Status | Completed once on `code-fixer-opencode` (task 81de2480, 2026-10-25), at `awaiting_pr`. Re-run this spec only if that PR is rejected. |

## Why

A `price_below` page monitor alerts the owner when a product drops under a threshold.
`services/page_monitors.py::parse_price` returns the **first** number in the watched text,
whether or not it is a price. When the selector covers more than the price span, or there is no
selector, a discount or a rating is read as the price, and the alert fires falsely. Reproduced on
6459f6b:

```
"Save 20%! Now ₹1,299"     -> 20
"4.5 out of 5 stars ₹999"  -> 4.5
"Only 3 left! $49.99"      -> 3
```

## Instruction

<!-- instruction:start -->
Page monitors: parse_price must prefer a currency-marked number and never read a percentage or a rating as the price

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_parse_price_currency.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_parse_price_currency.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_parse_price_currency.py =====
from decimal import Decimal

import pytest

from life_graph.services.page_monitors import parse_price


@pytest.mark.parametrize(
    ("text", "price"),
    [
        ("Save 20%! Now ₹1,299", Decimal("1299")),
        ("4.5 out of 5 stars ₹999", Decimal("999")),
        ("Only 3 left! $49.99", Decimal("49.99")),
        ("Rs. 2,499 (was Rs 3,000)", Decimal("2499")),
        ("MRP ₹1,999 Deal ₹1,499", Decimal("1999")),
        ("₹ 1,24,999", Decimal("124999")),
    ],
)
def test_currency_marked_price_wins(text, price):
    assert parse_price(text) == price


@pytest.mark.parametrize(
    ("text", "price"),
    [
        ("62999.00", Decimal("62999.00")),
        ("4 stars, 1,299", Decimal("1299")),
        ("20% off", None),
        ("Rated 4.2/5", None),
        ("no price", None),
        ("", None),
        (None, None),
    ],
)
def test_percentages_and_ratings_are_not_prices(text, price):
    assert parse_price(text) == price
===== end of tests/unit/test_parse_price_currency.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_parse_price_currency.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/page_monitors.py (parse_price) that makes those cases pass. Read the code first.
1. In _PRICE, capture the currency marker in its own group: (₹|rs\.?|inr|\$|usd|€|£)? (case-insensitive, as now). The number becomes group 2.
2. Return the FIRST positive number that has a currency marker in front of it.
3. If no number has a marker, return the first positive number that is not followed by "%" (spaces allowed), by "/" and a digit, by "out of" or by "star"/"stars", and not preceded by "/" or "out of" (the "5" in "4.2/5").
4. Otherwise return None, as now. With several marked prices the first marked one wins.

STEP 4. Run run_tests with paths ["tests/unit/test_parse_price_currency.py", "tests/unit/test_assistant_monitors.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_parse_price_currency.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what parse_price did before, in your words>
Change: <what you changed in parse_price (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_parse_price_currency.py or tests/unit/test_assistant_monitors.py shows it does not>

Files you may touch:
- life_graph/services/page_monitors.py (parse_price)
- tests/unit/test_parse_price_currency.py (new; created in STEP 1)

Do NOT:
- change evaluate, select_text, parse_selector or anything that fetches pages;
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: A currency-marked number wins over any earlier unmarked number — test: tests/unit/test_parse_price_currency.py::test_currency_marked_price_wins
AC-2: Percentages and ratings are never a price; with no marked number the first other number is — test: tests/unit/test_parse_price_currency.py::test_percentages_and_ratings_are_not_prices
AC-3: Existing price parsing is unchanged — test: tests/unit/test_assistant_monitors.py::test_parse_price
**Design:** One pass over _PRICE matches: return at the first marked number, and remember the first acceptable unmarked one as the fallback.
**Tasks:**
1. Create tests/unit/test_parse_price_currency.py exactly as given, then rework _PRICE and parse_price until it and test_parse_price pass (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->

## Reviewer notes

- Run the whole `tests/unit/test_assistant_monitors.py` file too. Its `evaluate` tests feed
  real page markup through `parse_price`.
