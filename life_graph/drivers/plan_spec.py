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


# Phase 4b (docs/specs/agent-drivers.md): a plan task may declare the files it
# will change, so tasks that touch different files can run at once. Asked for
# only when the owner turned parallel plans on (driver_team_max_parallel > 1).
_FILES_RULE = (
    "- End each task with the files it will change, as paths or globs relative "
    'to the repository root, e.g. "Files: life_graph/api/x.py, tests/unit/test_x.py" '
    'or "Files: src/ui/**". Tasks that touch different files run in parallel.\n'
    '- Optionally add how hard a task is, "Tier: cheap", "Tier: balanced" or '
    '"Tier: best" (best only for the hardest task); leave it out when unsure.\n'
)


def plan_only_prefix(with_files: bool = False) -> str:
    """The plan-only prompt prefix; *with_files* adds the ``Files:`` rule."""
    if not with_files:
        return _PLAN_ONLY_PREFIX
    marker = "- Keep tasks few:"
    return _PLAN_ONLY_PREFIX.replace(marker, _FILES_RULE + marker, 1)


# "Files: a.py, src/**" (or "Scope:"), up to the end of the line. A "(AC-1)"
# after it is not a path.
_FILES_RE = re.compile(r"(?:^|(?<=[\s(*_]))(?:files?|scope)\s*:\s*\**\s*([^\n]*)", re.IGNORECASE)
_SCOPE_TOKEN_RE = re.compile(r"^[\w.*?/\-\[\]{}@+~]+$")
_NOT_A_PATH = frozenset({"and", "or", "none", "n/a", "etc", "-"})
_MAX_SCOPE_ENTRIES = 50
_AGENT_TIER_KEY_RE = re.compile(r"(?:^|(?<=[\s(*_]))(?:agent|persona|tier)\s*:", re.IGNORECASE)


def parse_task_files(item: str | None) -> list[str]:
    """The file scope a plan task declares (``Files: a.py, src/**``), or ``[]``.

    Several ``Files:`` segments are joined. Backticks, quotes and trailing
    punctuation are dropped; acceptance-criterion ids (``AC-1``) and words
    that are not paths are ignored. ``[]`` means "no scope declared", which
    the scheduler treats as overlapping every other task.
    """
    if not item:
        return []
    out: list[str] = []
    for match in _FILES_RE.finditer(item):
        text = match.group(1)
        # "Files: a.py Tier: best" -- the Agent:/Tier: that follow are not paths.
        tail = _AGENT_TIER_KEY_RE.search(text)
        if tail:
            text = text[: tail.start()]
        cut = re.search(r"\s\(", text)
        if cut:
            text = text[: cut.start()]
        for raw in re.split(r"[,\s;]+", text):
            token = raw.strip("`'\"").rstrip(".:)")
            if (
                not token
                or token.lower() in _NOT_A_PATH
                or re.fullmatch(r"AC-\d+", token, re.IGNORECASE)
                or not _SCOPE_TOKEN_RE.match(token)
            ):
                continue
            if token not in out:
                out.append(token[:300])
    return out[:_MAX_SCOPE_ENTRIES]


# Team upgrades (2026-11-28, docs/specs/agent-drivers.md "Team upgrades"): a
# plan task may also ask for who does it -- "Agent: <persona name>" and/or
# "Tier: cheap|balanced|best" -- next to its "Files:". Parsed here as text;
# services/dev/teams.py validates them (an unknown value is a warning on the
# team, never a failed plan).
TIERS = ("cheap", "balanced", "best")
_AGENT_RE = re.compile(
    r"(?:^|(?<=[\s(*_]))(?:agent|persona)\s*:\s*\**\s*[`'\"]?([A-Za-z0-9][\w.\-]{0,99})",
    re.IGNORECASE,
)
_TIER_RE = re.compile(
    r"(?:^|(?<=[\s(*_]))tier\s*:\s*\**\s*[`'\"]?([A-Za-z][\w\-]{0,39})", re.IGNORECASE
)


def parse_task_agent(item: str | None) -> str | None:
    """The persona a plan task asks for (``Agent: code-fixer``), or None.

    The first ``Agent:`` (or ``Persona:``) wins; trailing punctuation is
    dropped. Whether that persona exists is the caller's question.
    """
    match = _AGENT_RE.search(item or "")
    if not match:
        return None
    return match.group(1).rstrip(".-") or None


def parse_task_tier(item: str | None) -> str | None:
    """The tier a plan task asks for (``Tier: best``), lower-cased, or None.

    Returned as written (lower-cased) even when it is not one of
    :data:`TIERS`, so the caller can warn about it.
    """
    match = _TIER_RE.search(item or "")
    return match.group(1).lower() if match else None
