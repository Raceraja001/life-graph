# 06: Memory recall, explicit dates

| | |
|---|---|
| Theme | C. Memory recall |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
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

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_time_window_dates.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_time_window_dates.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_time_window_dates.py =====
from datetime import date

import pytest

from life_graph.services.episodes import time_window

SAT = date(2026, 10, 24)


@pytest.mark.parametrize(
    ("question", "day"),
    [
        ("what did I do on 2026-10-21", date(2026, 10, 21)),
        ("notes from 21/10/2026", date(2026, 10, 21)),
        ("notes from 21-10-26", date(2026, 10, 21)),
        ("what did I do on 21/10", date(2026, 10, 21)),
        ("what happened on 21 October", date(2026, 10, 21)),
        ("on 21st Oct", date(2026, 10, 21)),
        ("on October 21", date(2026, 10, 21)),
        ("Oct 21st meeting", date(2026, 10, 21)),
        ("on 30 December", date(2025, 12, 30)),
        ("on 24 Oct", SAT),
        ("on 5 March 2025", date(2025, 3, 5)),
        ("October 21, 2025", date(2025, 10, 21)),
    ],
)
def test_explicit_dates(question, day):
    assert time_window(question, SAT) == (day, day)


@pytest.mark.parametrize(
    ("question", "window"),
    [
        ("on 31/02", None),
        ("1/2 cup of rice", None),
        ("meet at 10:30", None),
        ("release v2.1 notes", None),
        ("what may I have missed yesterday", (date(2026, 10, 23), date(2026, 10, 23))),
    ],
)
def test_not_dates(question, window):
    assert time_window(question, SAT) == window
===== end of tests/unit/test_time_window_dates.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_time_window_dates.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/episodes.py (time_window) that makes those cases pass. Read the code first.
Add explicit_date(q, today) -> date | None | False: False when the question names no date, None when it names an impossible one, else the date. Call it FIRST in time_window: a date d -> return (d, d); None -> return None; False -> carry on with the existing rules.
Forms, tried in this order (case-insensitive; months as full names or 3-letter forms, plus "sept"):
1. ISO: 2026-10-21.
2. Day-first with a year: 21/10/2026, 21-10-2026, 21/10/26 (a 2-digit year is 20YY).
3. Day-first without a year, ONLY right after "on ": "on 21/10". Without "on", "1/2 cup" is not a date.
4. Day then month: "21 October", "21st Oct", "21 of October", optionally a year: "5 March 2025".
5. Month then day: "October 21", "Oct 21st", optionally a year: "October 21, 2025".
With no year, use the most recent such date not after today ("30 December" on 2026-10-24 is 2025-12-30). An impossible date (31/02) returns None. "may" is a month only with a day number right next to it. Times (10:30) and versions (v2.1) are not dates; "." is not a separator. Build dates with datetime.date inside try/except ValueError. Module-level helpers (a month map, the patterns) next to time_window are fine.

STEP 4. Run run_tests with paths ["tests/unit/test_time_window_dates.py", "tests/unit/test_time_window_relative.py", "tests/unit/test_episodes_and_validity.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_time_window_dates.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what time_window did before, in your words>
Change: <what you changed in time_window (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_time_window_dates.py or tests/unit/test_time_window_relative.py shows it does not>

Files you may touch:
- life_graph/services/episodes.py (time_window, a new explicit_date helper and module-level helpers next to them)
- tests/unit/test_time_window_dates.py (new; created in STEP 1)

Do NOT:
- change the relative rules, episodes_between, write_day or summarize;
- import dateutil or anything new: re, datetime and calendar only;
- read dates month-first (10/21 is not 21 October);
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: ISO, day-first numeric and month-name dates give a one-day window, with the most recent past year when none is given — test: tests/unit/test_time_window_dates.py::test_explicit_dates
AC-2: Fractions, times, versions, impossible dates and "may" as a verb are not dates — test: tests/unit/test_time_window_dates.py::test_not_dates
AC-3: Relative phrases still work — test: tests/unit/test_time_window_relative.py::test_relative_windows
AC-4: The original phrases still work — test: tests/unit/test_episodes_and_validity.py::test_time_window
**Design:** One explicit_date helper with a False/None/date result, tried before the relative rules; a month-name map; a most-recent-past rule when the year is missing.
**Tasks:**
1. Create tests/unit/test_time_window_dates.py exactly as given, then add explicit_date and call it first in time_window until it and the relative and original window tests pass (AC-1, AC-2, AC-3, AC-4)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->

## Reviewer notes

- `explicit_date` returns three kinds of value (False, None or a date). Check that the tests
  cover each branch: a False result falls through to the old rules ("yesterday").
