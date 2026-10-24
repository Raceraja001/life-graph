# 05: Memory recall, more relative time phrases

| | |
|---|---|
| Theme | C. Memory recall |
| Engine | `code-fixer-local`, `spec_first=True` |
| Depends on | none |
| Review | gates |
| Size | ~30 lines in `episodes.py`, one new test file |

## Why

`services/episodes.py::time_window` turns "what did I do yesterday?" into a date range, so
memory retrieval (`memory_retrieval.py`) can fetch that period's day summaries directly. On
6459f6b these common phrasings return `None`, and the question falls back to plain search over
every day:

```
"this month", "2 weeks ago", "a week ago", "past 3 days", "last 7 days",
"two days ago", "100 days ago", "last weekend", "last year"   -> None
```

## Instruction

<!-- instruction:start -->
Memory recall: time_window must understand more relative time phrases

Read first:
- life_graph/services/episodes.py: _WEEKDAYS and time_window (lines 273-306).
- tests/unit/test_episodes_and_validity.py::test_time_window (must keep passing unchanged).

Change (life_graph/services/episodes.py, time_window only, plus module-level helpers it uses):
Weeks start on Monday, as they already do. All ranges are inclusive (start, end) dates. Keep every existing rule. Add the rules below, checked in this order relative to the existing ones:
1. "day before yesterday" (existing), then "yesterday" (existing).
2. NEW "past N days" / "last N days" -> (today - (N - 1) days, today).
3. NEW "past week" -> (today - 6 days, today).
4. "N days ago" (existing), now with N as 1-3 digits OR a word: a, one, two, three, four, five, six, seven, eight, nine, ten.
5. NEW "N weeks ago" (same N forms; "a week ago" is N=1) -> the Monday-Sunday week N weeks before the current week: start = today - (today.weekday() + 7*N) days, end = start + 6 days.
6. NEW "last weekend" -> Saturday and Sunday of last week: start = today - (today.weekday() + 2) days, end = start + 1 day. Check it BEFORE "last week".
7. "last week", "this week", "last month" (existing).
8. NEW "this month" -> (first day of this month, today).
9. NEW "last year" -> (1 Jan of last year, 31 Dec of last year). NEW "this year" -> (1 Jan this year, today).
10. "today" / "this morning", then the weekday names (existing, unchanged).
"in 2 weeks" (future, no "ago") stays None.

Cases (copy exactly; SAT = date(2026, 10, 24), a Saturday; SUN = date(2026, 10, 25); MON = date(2026, 10, 26)):
time_window(q, SAT) ==
- "what did I do this month" -> (date(2026, 10, 1), SAT)
- "what happened 2 weeks ago" -> (date(2026, 10, 5), date(2026, 10, 11))
- "three weeks ago" -> (date(2026, 9, 28), date(2026, 10, 4))
- "a week ago" -> (date(2026, 10, 12), date(2026, 10, 18))
- "what did we discuss in the past 3 days" -> (date(2026, 10, 22), SAT)
- "last 7 days" -> (date(2026, 10, 18), SAT)
- "over the past week" -> (date(2026, 10, 18), SAT)
- "two days ago" -> (date(2026, 10, 22), date(2026, 10, 22))
- "100 days ago" -> (date(2026, 7, 16), date(2026, 7, 16))
- "what did I do last weekend" -> (date(2026, 10, 17), date(2026, 10, 18))
- "anything from last year" -> (date(2025, 1, 1), date(2025, 12, 31))
- "all of this year" -> (date(2026, 1, 1), SAT)
- "what's planned in 2 weeks" -> None
time_window("last weekend", SUN) == (date(2026, 10, 17), date(2026, 10, 18))
time_window("last weekend", MON) == (date(2026, 10, 24), date(2026, 10, 25))

Files you may touch:
- life_graph/services/episodes.py (time_window and new module-level constants/helpers next to it)
- tests/unit/test_time_window_relative.py (new)

Do NOT:
- change episodes_between, write_day, summarize or anything that touches the database;
- change life_graph/services/memory_retrieval.py;
- edit tests/unit/test_episodes_and_validity.py or any other existing test;
- parse explicit dates such as "21 October" or "2026-10-21" (a separate task does that).

## Spec
**Requirements:**
AC-1: Relative phrases (this month, N weeks ago, past/last N days, past week, word numbers, 3-digit days ago, last/this year) give the stated inclusive ranges — test: tests/unit/test_time_window_relative.py::test_relative_windows
AC-2: "last weekend" is last week's Saturday and Sunday on any day of the week — test: tests/unit/test_time_window_relative.py::test_last_weekend_from_each_day
AC-3: The existing phrases give the same windows as before — test: tests/unit/test_episodes_and_validity.py::test_time_window
**Design:** A small word-number map and a shared number pattern; new regex rules inserted into time_window in the stated order, each returning early.
**Tasks:**
1. Add the word-number helper and the new rules to time_window, and write tests/unit/test_time_window_relative.py with every case above (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->

## Reviewer notes

- The weekday fallback ("what's on my calendar this friday" gives *last* Friday) is a
  separate, known limit: time_window serves recall of the past. It is left alone on purpose.
