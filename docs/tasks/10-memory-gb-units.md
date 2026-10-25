# 10: Tech watch, model sizes in T, M, NxB and E-numbers

| | |
|---|---|
| Theme | D. Research and pipeline |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
| Depends on | none |
| Review | gates |
| Size | ~15 lines in `worker_templates.py`, one new test file |

## Why

The weekly tech watch (Job 10) keeps only open models that fit the 16 GB GPU. When a page does
not state the memory, `services/worker_templates.py::estimated_memory_gb` estimates it from the
parameter count in the title. It only understands "NNB". So a 1-trillion-parameter model has an
unknown size, and unknown is kept, so it is listed as fitting 16 GB. Reproduced on 6459f6b:

```
"Kimi K2 1T"    -> None   (kept as "fits")
"Mixtral 8x7B"  -> None
"Gemma 3n E4B"  -> None
"SmolLM 360M"   -> None
```

## Instruction

<!-- instruction:start -->
Tech watch: estimated_memory_gb must read trillions, millions, NxB mixtures and E-numbers

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_estimated_memory_gb.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_estimated_memory_gb.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_estimated_memory_gb.py =====
from datetime import date

import pytest

from life_graph.services.worker_templates import estimated_memory_gb, validate_finding


@pytest.mark.parametrize(
    ("title", "gb"),
    [
        ("Kimi K2 1T", 600.0),
        ("Kimi K2 1.04T", 624.0),
        ("Mixtral 8x7B", 33.6),
        ("Mixtral 8x22B", 105.6),
        ("Gemma 3n E4B", 2.4),
        ("SmolLM 360M", 0.2),
        ("Qwen3-235B-A22B", 141.0),
        ("Qwen3 30B-A3B", 18.0),
        ("Qwen3-Coder-480B-A35B", 288.0),
        ("gpt-oss-20b", 12.0),
        ("Heron 480B", 288.0),
        ("Phi-4 mini 3.8B", 2.3),
        ("Llama 3.1 8B Instruct", 4.8),
        ("GPT-4 Turbo", None),
        ("no count here", None),
        ("", None),
        (None, None),
    ],
)
def test_estimated_memory_gb(title, gb):
    assert estimated_memory_gb(title) == gb


def finding(title):
    return {"title": title, "source": "https://example.com/k2", "published_on": "2026-10-20"}


def test_validate_finding_uses_the_estimate():
    sources = {"https://example.com/k2"}
    today = date(2026, 10, 24)
    big = finding("Kimi K2 1T open weights")
    assert validate_finding(big, sources, today=today, max_memory_gb=16) is None
    kept = validate_finding(finding("Qwen3 8B update"), sources, today=today, max_memory_gb=16)
    assert kept is not None
    assert kept["title"] == "Qwen3 8B update"
===== end of tests/unit/test_estimated_memory_gb.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_estimated_memory_gb.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/worker_templates.py (estimated_memory_gb) that makes those cases pass. Read the code first.
1. "NxMB" ("8x7B", "8 x 22B") counts as N*M billion. Add one pattern for it, e.g. r"(?<![\w.])(\d+)\s?[xX]\s?(\d+(?:\.\d+)?)\s?[bB]\b", and remove its matches from the text before step 2, so M is not counted again.
2. Change _PARAMS so a single count is a number followed by B (billion), T (trillion = 1000 B) or M (million = 0.001 B), any case, optional space. As now it must not follow a letter, digit or "." directly, except an optional "E"/"e" prefix ("E4B" is 4 B): r"(?<![\w.])[eE]?(\d+(?:\.\d+)?)\s?([bBtTmM])\b".
3. Take the largest count in billions, times _GB_PER_BILLION_Q4, rounded to 1 decimal, as now. None when there is no count.

STEP 4. Run run_tests with paths ["tests/unit/test_estimated_memory_gb.py", "tests/unit/test_workers_and_offers.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_estimated_memory_gb.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what estimated_memory_gb did before, in your words>
Change: <what you changed in estimated_memory_gb (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_estimated_memory_gb.py or tests/unit/test_workers_and_offers.py shows it does not>

Files you may touch:
- life_graph/services/worker_templates.py (estimated_memory_gb)
- tests/unit/test_estimated_memory_gb.py (new; created in STEP 1)

Do NOT:
- change validate_finding, validate_offer, topic_reader or the templates;
- change _GB_PER_BILLION_Q4;
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: Titles with B, T, M, NxB and E-prefixed counts give the stated estimates; titles without a count give None — test: tests/unit/test_estimated_memory_gb.py::test_estimated_memory_gb
AC-2: A trillion-parameter model is dropped from a 16 GB topic, and a small model is kept — test: tests/unit/test_estimated_memory_gb.py::test_validate_finding_uses_the_estimate
AC-3: The existing worker and offer tests still pass — test: tests/unit/test_workers_and_offers.py
**Design:** One pattern for NxMB, one for single counts with a unit; collect counts in billions, take the max.
**Tasks:**
1. Create tests/unit/test_estimated_memory_gb.py exactly as given, then extend the count patterns and estimated_memory_gb until it and the existing worker tests pass (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->

## Reviewer notes

- An 8x7B mixture is really ~47 B, not 56 B. The estimate errs high on purpose, which keeps a
  model from being wrongly listed as fitting.
