# 05: Memory recall, more relative time phrases

| | |
|---|---|
| Theme | C. Memory recall |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
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

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_time_window_relative.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_time_window_relative.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_time_window_relative.py =====
from datetime import date

import pytest

from life_graph.services.episodes import time_window

SAT = date(2026, 10, 24)
SUN = date(2026, 10, 25)
MON = date(2026, 10, 26)


@pytest.mark.parametrize(
    ("question", "window"),
    [
        ("what did I do this month", (date(2026, 10, 1), SAT)),
        ("what happened 2 weeks ago", (date(2026, 10, 5), date(2026, 10, 11))),
        ("three weeks ago", (date(2026, 9, 28), date(2026, 10, 4))),
        ("a week ago", (date(2026, 10, 12), date(2026, 10, 18))),
        ("what did we discuss in the past 3 days", (date(2026, 10, 22), SAT)),
        ("last 7 days", (date(2026, 10, 18), SAT)),
        ("over the past week", (date(2026, 10, 18), SAT)),
        ("two days ago", (date(2026, 10, 22), date(2026, 10, 22))),
        ("100 days ago", (date(2026, 7, 16), date(2026, 7, 16))),
        ("what did I do last weekend", (date(2026, 10, 17), date(2026, 10, 18))),
        ("anything from last year", (date(2025, 1, 1), date(2025, 12, 31))),
        ("all of this year", (date(2026, 1, 1), SAT)),
        ("what's planned in 2 weeks", None),
    ],
)
def test_relative_windows(question, window):
    assert time_window(question, SAT) == window


@pytest.mark.parametrize(
    ("today", "window"),
    [
        (SAT, (date(2026, 10, 17), date(2026, 10, 18))),
        (SUN, (date(2026, 10, 17), date(2026, 10, 18))),
        (MON, (date(2026, 10, 24), date(2026, 10, 25))),
    ],
)
def test_last_weekend_from_each_day(today, window):
    assert time_window("last weekend", today) == window
===== end of tests/unit/test_time_window_relative.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_time_window_relative.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/episodes.py (time_window) that makes those cases pass. Read the code first.
Weeks start on Monday, as now. Ranges are inclusive (start, end) dates. Keep every existing rule and add the new ones, checked in this order:
1. "day before yesterday", then "yesterday" (existing).
2. NEW "past N days" / "last N days" -> (today - (N - 1) days, today).
3. NEW "past week" -> (today - 6 days, today).
4. "N days ago" (existing), now with N as 1-3 digits or a word: a, one, two, three, four, five, six, seven, eight, nine, ten. Put the words in a module-level dict and one shared number pattern.
5. NEW "N weeks ago" (same N forms; "a week ago" is N=1): start = today - (today.weekday() + 7*N) days, end = start + 6 days.
6. NEW "last weekend": start = today - (today.weekday() + 2) days, end = start + 1 day. Before "last week".
7. "last week", "this week", "last month" (existing).
8. NEW "this month" -> (first day of this month, today).
9. NEW "last year" -> (1 Jan, 31 Dec of last year); NEW "this year" -> (1 Jan this year, today).
10. "today" / "this morning", then the weekday names (existing, unchanged).
"in 2 weeks" (no "ago") stays None.

STEP 4. Run run_tests with paths ["tests/unit/test_time_window_relative.py", "tests/unit/test_episodes_and_validity.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_time_window_relative.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what time_window did before, in your words>
Change: <what you changed in time_window (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_time_window_relative.py or tests/unit/test_episodes_and_validity.py shows it does not>

Files you may touch:
- life_graph/services/episodes.py (time_window and module-level helpers next to it)
- tests/unit/test_time_window_relative.py (new; created in STEP 1)

Do NOT:
- change episodes_between, write_day, summarize or anything that touches the database;
- change life_graph/services/memory_retrieval.py;
- parse explicit dates such as "21 October" (a separate task does that);
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: Relative phrases (this month, N weeks ago, past/last N days, past week, word numbers, 3-digit days ago, last/this year) give the stated inclusive ranges — test: tests/unit/test_time_window_relative.py::test_relative_windows
AC-2: "last weekend" is last week's Saturday and Sunday on any day of the week — test: tests/unit/test_time_window_relative.py::test_last_weekend_from_each_day
AC-3: The existing phrases give the same windows as before — test: tests/unit/test_episodes_and_validity.py::test_time_window
**Design:** A small word-number map and a shared number pattern; new regex rules inserted into time_window in the stated order, each returning early.
**Tasks:**
1. Create tests/unit/test_time_window_relative.py exactly as given, then add the word-number helper and the new rules to time_window until it and test_time_window pass (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->

## Reviewer notes

- The weekday fallback ("what's on my calendar this friday" gives *last* Friday) is a
  separate, known limit: time_window serves recall of the past. It is left alone on purpose.
