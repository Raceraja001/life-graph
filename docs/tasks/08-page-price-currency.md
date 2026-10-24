# 08: Page monitors, the price is the currency-marked number

| | |
|---|---|
| Theme | A. Money |
| Engine | `code-fixer-local`, `spec_first=True` |
| Depends on | none |
| Review | gates |
| Size | ~15 lines in `page_monitors.py`, one new test file |

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

Read first:
- life_graph/services/page_monitors.py: _PRICE and parse_price (lines 175-192), and evaluate (its only caller).
- tests/unit/test_assistant_monitors.py::test_parse_price (must keep passing unchanged).

Change (life_graph/services/page_monitors.py, _PRICE and parse_price only):
1. Capture the currency marker in its own group (₹, Rs, Rs., INR, $, USD, €, £; case-insensitive, as now).
2. Return the FIRST positive number that has a currency marker in front of it.
3. If no number has a marker, return the first positive number that is not:
   - followed by "%" (spaces allowed), by "/" and a digit, by "out of", or by "star"/"stars";
   - preceded by "/" or "out of" (the "5" in "4.2/5").
4. Otherwise return None, as now.
When there are several marked prices ("MRP ₹1,999 Deal ₹1,499"), the first marked one wins. Choosing between them is out of scope.

Cases (copy exactly). parse_price(text) ==:
- "Save 20%! Now ₹1,299" -> Decimal("1299")
- "4.5 out of 5 stars ₹999" -> Decimal("999")
- "Only 3 left! $49.99" -> Decimal("49.99")
- "Rs. 2,499 (was Rs 3,000)" -> Decimal("2499")
- "MRP ₹1,999 Deal ₹1,499" -> Decimal("1999")
- "62999.00" -> Decimal("62999.00")
- "4 stars, 1,299" -> Decimal("1299")
- "₹ 1,24,999" -> Decimal("124999")
- "20% off" -> None
- "Rated 4.2/5" -> None
- "no price" -> None
- "" -> None
- None -> None

Files you may touch:
- life_graph/services/page_monitors.py (_PRICE and parse_price only)
- tests/unit/test_parse_price_currency.py (new)

Do NOT:
- change evaluate, select_text, parse_selector or anything that fetches pages;
- edit tests/unit/test_assistant_monitors.py or any other existing test;
- add a dependency.

## Spec
**Requirements:**
AC-1: A currency-marked number wins over any earlier unmarked number — test: tests/unit/test_parse_price_currency.py::test_currency_marked_price_wins
AC-2: Percentages and ratings are never a price; with no marked number the first other number is — test: tests/unit/test_parse_price_currency.py::test_percentages_and_ratings_are_not_prices
AC-3: Existing price parsing is unchanged — test: tests/unit/test_assistant_monitors.py::test_parse_price
**Design:** One pass over _PRICE matches: return at the first marked number, and remember the first acceptable unmarked one as the fallback.
**Tasks:**
1. Rework parse_price as described and add tests/unit/test_parse_price_currency.py with the cases above (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->

## Reviewer notes

- Run the whole `tests/unit/test_assistant_monitors.py` file too. Its `evaluate` tests feed
  real page markup through `parse_price`.
