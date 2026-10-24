# 06: Memory recall, explicit dates

| | |
|---|---|
| Theme | C. Memory recall |
| Engine | `code-fixer-local`, `spec_first=True` (OpenCode if it runs out of rounds) |
| Depends on | **05 merged** (same function) |
| Review | gates |
| Size | ~40 lines in `episodes.py`, one new test file |

## Why

After 05, `time_window` handles relative phrases, but a question that names a date ("what did we
decide on 21 October?", "notes from 21/10/2026") still returns `None`, so the day's summary is
not fetched directly. Dates in this codebase are day-first (see `money.parse_day`), as the owner
writes them.

## Instruction

<!-- instruction:start -->
Memory recall: time_window must understand explicit dates (21 October, Oct 21, 21/10, 2026-10-21)

Read first:
- life_graph/services/episodes.py: time_window and the helpers above it.
- tests/unit/test_time_window_relative.py and tests/unit/test_episodes_and_validity.py::test_time_window (must keep passing unchanged).

Change (life_graph/services/episodes.py):
Add a helper, explicit_date(question_lower, today) -> date | None | False. It returns False when the question names no date, None when it names an impossible one, and the date otherwise. Call it FIRST in time_window: if it returns a date d, return (d, d); if it returns None, return None; if it returns False, carry on with the existing rules.
Forms, tried in this order (case-insensitive; months as full names or 3-letter forms, plus "sept"):
1. ISO: 2026-10-21.
2. Day-first with a year: 21/10/2026, 21-10-2026, 21/10/26 (a 2-digit year means 20YY).
3. Day-first without a year, ONLY right after "on ": "on 21/10", "on 21-10". Without "on", "1/2 cup" is not a date.
4. Day then month: "21 October", "21st Oct", "21 of October", optionally followed by a year: "5 March 2025", "21 Oct, 2025".
5. Month then day: "October 21", "Oct 21st", optionally followed by a year: "October 21, 2025".
With no year, use the most recent such date that is not after today: on 2026-10-24, "30 December" is 2025-12-30 and "24 Oct" is 2026-10-24. An impossible date such as 31/02 returns None, for the whole question. Never treat "may" as a month unless a day number is right next to it.
Times (10:30) and versions (v2.1) are not dates. Do not accept "." as a separator.

Cases (copy exactly; SAT = date(2026, 10, 24)). time_window(q, SAT) ==:
- "what did I do on 2026-10-21" -> (date(2026, 10, 21), date(2026, 10, 21))
- "notes from 21/10/2026" -> (date(2026, 10, 21), date(2026, 10, 21))
- "notes from 21-10-26" -> (date(2026, 10, 21), date(2026, 10, 21))
- "what did I do on 21/10" -> (date(2026, 10, 21), date(2026, 10, 21))
- "what happened on 21 October" -> (date(2026, 10, 21), date(2026, 10, 21))
- "on 21st Oct" -> (date(2026, 10, 21), date(2026, 10, 21))
- "on October 21" -> (date(2026, 10, 21), date(2026, 10, 21))
- "Oct 21st meeting" -> (date(2026, 10, 21), date(2026, 10, 21))
- "on 30 December" -> (date(2025, 12, 30), date(2025, 12, 30))
- "on 24 Oct" -> (SAT, SAT)
- "on 5 March 2025" -> (date(2025, 3, 5), date(2025, 3, 5))
- "October 21, 2025" -> (date(2025, 10, 21), date(2025, 10, 21))
- "on 31/02" -> None
- "1/2 cup of rice" -> None
- "meet at 10:30" -> None
- "release v2.1 notes" -> None
- "what may I have missed yesterday" -> (date(2026, 10, 23), date(2026, 10, 23))

Files you may touch:
- life_graph/services/episodes.py (time_window and the new explicit_date helper)
- tests/unit/test_time_window_dates.py (new)

Do NOT:
- change the relative rules added before this task, or episodes_between/write_day/summarize;
- import dateutil or any new dependency; use re, datetime and calendar only;
- edit any existing test file;
- interpret dates month-first (10/21 is not 21 October).

## Spec
**Requirements:**
AC-1: ISO, day-first numeric and month-name dates give a one-day window, with the most recent past year when none is given — test: tests/unit/test_time_window_dates.py::test_explicit_dates
AC-2: Fractions, times, versions, impossible dates and "may" as a verb are not dates — test: tests/unit/test_time_window_dates.py::test_not_dates
AC-3: Relative phrases still work — test: tests/unit/test_time_window_relative.py::test_relative_windows
AC-4: The original phrases still work — test: tests/unit/test_episodes_and_validity.py::test_time_window
**Design:** One explicit_date helper with a False/None/date result, tried before the relative rules; a month-name map; a most-recent-past rule when the year is missing.
**Tasks:**
1. Add explicit_date and call it first in time_window, with tests/unit/test_time_window_dates.py holding every case above (AC-1, AC-2, AC-3, AC-4)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->

## Reviewer notes

- `explicit_date` returns three kinds of value (False, None or a date). Check that the tests
  cover each branch: a False result falls through to the old rules ("yesterday").
