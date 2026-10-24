"""Plan and spec text: the prompt prefixes a spec-first or plan-only dispatch
adds, and the parsers that read the ``## Spec`` and ``**Tasks:**`` sections
back out of a driver's output. Pure text handling, no I/O (split out of
dispatcher.py, 2026-10-25)."""

from __future__ import annotations

import re

# spec_first: ask the driver to write its plan before touching anything,
# spec-driven-development style (requirements → design → tasks), in the
# same call rather than a separate pre-pass — no extra driver cost, no new
# pause-for-approval architecture, most of the benefit (a reviewable plan,
# a forcing function against misreading the instruction) for one-file's
# worth of code.
_SPEC_HEADINGS = (
    "## Spec\n"
    "**Requirements:** the acceptance criteria this change must satisfy, one "
    "per line, each with an id and the pytest test that will prove it, "
    "exactly like:\n"
    "AC-1: <what must be true> — test: tests/unit/test_example.py::test_name\n"
    "**Design:** the approach, in a sentence or two.\n"
    "**Tasks:** a numbered list of the concrete steps you will take. End each "
    'task with the criteria it satisfies, e.g. "1. Add the parser (AC-1)". A '
    "task that cites a criterion also writes or updates that criterion's test.\n\n"
)
_SPEC_FIRST_PREFIX = (
    "Before changing anything, write a short spec as the FIRST part of "
    "your response, using exactly these headings:\n"
    + _SPEC_HEADINGS
    + "Then implement it. Keep the spec to a few lines total — it's a plan, "
    "not documentation.\n\n---\n\n"
)
# A plan task's spec is the whole job. Reusing _SPEC_FIRST_PREFIX ("...Then
# implement it.") had a claude_code plan run write the full feature, which
# no_diff_in_plan then rightly rejected.
_PLAN_ONLY_PREFIX = (
    "This is a PLAN-ONLY task for human review: do NOT create, edit or delete "
    "any file. Read the code as much as you need to plan well, then reply with "
    "a spec using exactly these headings, and nothing else:\n"
    + _SPEC_HEADINGS
    + "Rules for the Tasks list:\n"
    "- Every task changes something (code, tests or docs). No task that only "
    "runs checks: lint and tests run automatically after every task, and a "
    "check-only task is dropped.\n"
    "- When a change makes a generated file stale (an inventory or state doc, "
    "a lockfile, generated types), regenerate it inside that same task.\n"
    "- Keep tasks few: each one is a separate run, review and merge.\n\n"
    "Stop after the spec. The tasks run later, one at a time, after this plan "
    "is approved.\n\n---\n\n"
)
# Plan tasks keep only the tools that read. Anything mapping to a write or a
# shell (file_write, code_edit, run_command, and the git_* tools, which the
# claude_code driver maps to a full Bash) is dropped for the plan stage.
_PLAN_READ_TOOLS = frozenset(
    {
        "file_read",
        "code_read",
        "code_search",
        "code_list",
        "web_search",
        "browse_web",
        "memory_search",
    }
)
_SPEC_SECTION_RE = re.compile(r"##\s*Spec\b(.*?)(?:\n##\s|\Z)", re.DOTALL | re.IGNORECASE)


def _extract_spec(output: str | None) -> str | None:
    """Pull the ``## Spec`` section out of a driver's narrative output, if any."""
    if not output:
        return None
    match = _SPEC_SECTION_RE.search(output)
    return match.group(1).strip() or None if match else None


_TASKS_SECTION_RE = re.compile(r"\*\*Tasks:?\*\*\s*(.*)", re.DOTALL | re.IGNORECASE)
# A candidate list marker: "3." or "3)" at the start or after whitespace, then
# whitespace. Only the next expected number counts (see _parse_tasks), so a
# "(default 5, max 20)" inside task 1 is text, not task 20.
_TASK_MARKER_RE = re.compile(r"(?:^|(?<=\s))(\d+)[.)](?=\s)")
_PLAN_SPEC_MAX_CHARS = 50_000
_BOLD_HEADING_RE = re.compile(r"\*\*[A-Za-z][\w -]*:?\*\*")


def _parse_tasks(spec_text: str | None) -> list[str]:
    """Pull the numbered task list out of a spec's ``**Tasks:**`` section.

    Tolerates both inline ("1. x 2. y") and multi-line numbering — the
    model's own formatting varies and neither is wrong. Returns ``[]`` when
    no numbered list is found, so callers fall back to a single combined
    dispatch rather than fanning out on a guess.
    """
    if not spec_text:
        return []
    section = _TASKS_SECTION_RE.search(spec_text)
    if not section:
        return []
    block = section.group(1)
    # Stop at the next bold heading, if the model added one after Tasks.
    block = _BOLD_HEADING_RE.split(block)[0]
    starts = []
    for marker in _TASK_MARKER_RE.finditer(block):
        if int(marker.group(1)) == len(starts) + 1:
            starts.append(marker)
    items = []
    for i, marker in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(block)
        text = block[marker.end() : end].strip()
        if text:
            items.append(text)
    return items
