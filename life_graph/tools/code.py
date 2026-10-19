"""Code tools — read, search and precisely edit a codebase.

``file_read`` / ``file_write`` treat a file as one blob: a read is cut by the
registry's result cap (``MAX_TOOL_RESULT_CHARS``, 4000 chars) mid-JSON, and the
only way to change one line is to rewrite the whole file from memory — which
is how a local model silently drops half a module. These tools are shaped for
coding agents instead:

* ``code_read`` pages through a file by line numbers, each page under the cap,
  and says where the next page starts;
* ``code_edit`` replaces one exact, unique snippet, so an edit either lands
  where intended or fails loudly;
* ``code_search`` / ``code_list`` find things without shelling out.

Same guards as the file tools (:mod:`life_graph.tools._guards`): tenant gate,
root confinement — during a driver run, only the task's worktree — credential
files refused, and no writes into ``.git``. Relative paths resolve against the
task worktree when one is set, so the model need not repeat it.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from life_graph.tools._guards import (
    ToolDeniedError,
    _task_roots,
    check_tenant,
    check_writable,
    resolve_in_roots,
)
from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

PAGE_CHARS = 3200  # keeps a page plus JSON framing under the registry's 4000 cap
MAX_EDIT_CHARS = 50_000
MAX_SEARCH_HITS = 40
MAX_LIST_ENTRIES = 200
MAX_SEARCH_FILE_BYTES = 1_000_000
_SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".next",
        "dist",
        "build",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)


def _resolve(path: str, tool_name: str) -> Path:
    check_tenant(tool_name)
    p = Path(path)
    scoped = _task_roots.get()
    if not p.is_absolute() and scoped:
        p = scoped[0] / p
    return resolve_in_roots(str(p), tool_name=tool_name)


def _err(exc: Exception) -> str:
    return json.dumps({"error": str(exc)})


def _walk(root: Path):
    for entry in sorted(root.iterdir()):
        if entry.is_symlink():
            continue  # never follow links out of the confined tree
        if entry.is_dir():
            if entry.name not in _SKIP_DIRS:
                yield from _walk(entry)
        elif entry.is_file():
            yield entry


@tool(
    name="code_read",
    description=(
        "Read a source file with line numbers, one page at a time. Returns "
        "`next_start_line` when the file continues — call again with it to read on. "
        "Pass `end_line` to stop at a specific line instead of paging to the character "
        "cap (still capped by the same page size if the requested range is large). "
        "Paths may be relative to the project root."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path (relative to project root, or absolute).",
            },
            "start_line": {
                "type": "integer",
                "description": "1-based line to start at. Default 1.",
            },
            "end_line": {
                "type": "integer",
                "description": "1-based line to stop at, inclusive. Default: page to the "
                "character cap. Ignored if smaller than start_line.",
            },
        },
        "required": ["path"],
    },
)
async def code_read(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    try:
        p = _resolve(path, "code_read")
        if not p.is_file():
            return json.dumps({"error": f"Not a file: {path}"})
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start_line))
        stop = (
            min(len(lines), int(end_line)) if end_line is not None and end_line >= start else None
        )
        out: list[str] = []
        used = 0
        n = start
        while n <= len(lines):
            if stop is not None and n > stop:
                break
            row = f"{n}: {lines[n - 1]}"
            if used + len(row) + 1 > PAGE_CHARS and out:
                break
            out.append(row[:PAGE_CHARS])
            used += len(row) + 1
            n += 1
        return json.dumps(
            {
                "path": str(p),
                "total_lines": len(lines),
                "content": "\n".join(out),
                "next_start_line": n if n <= len(lines) and (stop is None or n <= stop) else None,
            }
        )
    except ToolDeniedError as exc:
        return _err(exc)
    except Exception as exc:
        logger.warning("code_read failed for %s: %s", path, exc)
        return _err(exc)


@tool(
    name="code_edit",
    description=(
        "Edit a file by replacing one snippet. `old` should appear exactly once: include"
        " enough surrounding lines to make it unique. Small differences in indentation,"
        " trailing spaces or code_read's line-number prefixes are tolerated. Or replace"
        " whole lines: pass `start_line` and `end_line` (from code_read) with an empty"
        " `old`; end_line = start_line - 1 inserts before start_line without replacing"
        " (start_line = last line + 1 appends). To create a new file, pass an empty `old`"
        " and the whole file as `new`."
        " The reply shows the edited lines."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path (relative to project root, or absolute).",
            },
            "old": {
                "type": "string",
                "description": "Text to replace; empty to create a file or with a line range.",
            },
            "new": {"type": "string", "description": "Replacement text."},
            "start_line": {
                "type": "integer",
                "description": "First line to replace (1-based), with end_line and empty old.",
            },
            "end_line": {"type": "integer", "description": "Last line to replace, inclusive."},
        },
        "required": ["path", "old", "new"],
    },
)
async def code_edit(
    path: str,
    old: str,
    new: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    from life_graph.tools import edit_match

    if len(new) > MAX_EDIT_CHARS:
        return json.dumps(
            {"error": f"Replacement too large ({len(new)} chars, max {MAX_EDIT_CHARS})"}
        )
    try:
        p = _resolve(path, "code_edit")
        check_writable(p, tool_name="code_edit")
        # An empty range (end_line = start_line - 1) inserts before start_line.
        # gpt-oss:20b creates files that way (start_line=1, end_line=0) and
        # appends with start_line=last+1; both were refused, 13 times in one
        # run (task 6f442de2, 2026-10-16).
        inserting = (
            old == ""
            and start_line is not None
            and end_line is not None
            and int(end_line) == int(start_line) - 1
        )
        if inserting and int(start_line) == 1 and not p.exists():
            start_line = end_line = None
        if old == "" and start_line is None:
            if p.exists():
                return json.dumps(
                    {
                        "error": "File exists; pass the text to replace as `old`, or"
                        " start_line/end_line to replace whole lines."
                    }
                )
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(new, encoding="utf-8")
            return json.dumps({"created": str(p), "lines": new.count("\n") + 1})
        if not p.is_file():
            return json.dumps({"error": f"Not a file: {path}"})
        text = p.read_text(encoding="utf-8")

        if old == "":
            # Line-range mode: replace lines start..end with `new`.
            lines = text.split("\n")
            first = int(start_line)
            last = int(end_line) if end_line is not None else first
            if inserting and 1 <= first <= len(lines) + 1:
                if first == len(lines) + 1 and lines[-1] == "":
                    # Appending: go before the empty piece after the final
                    # newline, so the file still ends with one.
                    first, last = len(lines), len(lines) - 1
            elif not (1 <= first <= last <= len(lines)):
                return json.dumps(
                    {"error": f"Line range {first}-{last} is outside the file (1-{len(lines)})"}
                )
            replaced = "\n".join(lines[first - 1 : last])
            lines[first - 1 : last] = new.strip("\n").split("\n") if new.strip("\n") else []
            updated = "\n".join(lines)
            p.write_text(updated, encoding="utf-8")
            start = len("\n".join(lines[: first - 1])) + (1 if first > 1 else 0)
            return json.dumps(
                {
                    "edited": str(p),
                    "at_line": first,
                    "replaced_lines": f"{first}-{last}",
                    "replaced": replaced[:600],
                    "now": edit_match.excerpt(updated, start, len(new.strip("\n"))),
                }
            )

        found = edit_match.locate(text, old, new)
        if isinstance(found, edit_match.Miss):
            if found.reason == "ambiguous":
                return json.dumps(
                    {"error": f"`old` found {found.count} times — include more surrounding lines"}
                )
            near = edit_match.closest(text, old)
            payload = {"error": "`old` not found — copy the text from the file exactly"}
            if near:
                payload["closest_match"] = near
                payload["hint"] = (
                    "The closest lines are shown with their numbers: copy them as `old`"
                    " (without the numbers), or pass start_line/end_line."
                )
            return json.dumps(payload)
        updated = text[: found.start] + found.new + text[found.end :]
        p.write_text(updated, encoding="utf-8")
        result = {
            "edited": str(p),
            "at_line": text[: found.start].count("\n") + 1,
            "now": edit_match.excerpt(updated, found.start, len(found.new)),
        }
        if found.tier != "exact":
            result["matched"] = found.tier  # how loosely `old` had to be matched
        return json.dumps(result)
    except ToolDeniedError as exc:
        return _err(exc)
    except Exception as exc:
        logger.warning("code_edit failed for %s: %s", path, exc)
        return _err(exc)


@tool(
    name="code_search",
    description=(
        "Search file contents under a directory with a regular expression. Returns "
        "matching `path:line: text`. Skips .git, node_modules, virtualenvs and build output."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Python regular expression."},
            "directory": {
                "type": "string",
                "description": "Directory to search. Default: project root.",
            },
            "glob": {
                "type": "string",
                "description": "Only files matching this name glob, e.g. '*.py'.",
            },
        },
        "required": ["pattern"],
    },
)
async def code_search(pattern: str, directory: str = ".", glob: str | None = None) -> str:
    try:
        root = _resolve(directory, "code_search")
        rx = re.compile(pattern)
    except re.error as exc:
        return json.dumps({"error": f"Bad pattern: {exc}"})
    except ToolDeniedError as exc:
        return _err(exc)
    hits: list[str] = []
    try:
        for f in _walk(root):
            if glob and not f.match(glob):
                continue
            if f.stat().st_size > MAX_SEARCH_FILE_BYTES:
                continue
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{f.relative_to(root)}:{i}: {line.strip()[:160]}")
                        if len(hits) >= MAX_SEARCH_HITS:
                            return json.dumps({"matches": hits, "truncated": True})
            except (UnicodeDecodeError, OSError):
                continue
    except OSError as exc:
        return _err(exc)
    return json.dumps({"matches": hits, "truncated": False})


@tool(
    name="code_list",
    description="List files under a directory (recursive), optionally filtered by a name glob like '*.py'.",
    parameters_schema={
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "Directory. Default: project root."},
            "glob": {"type": "string", "description": "Name glob filter."},
        },
    },
)
async def code_list(directory: str = ".", glob: str | None = None) -> str:
    try:
        root = _resolve(directory, "code_list")
        if not root.is_dir():
            return json.dumps({"error": f"Not a directory: {directory}"})
        files = []
        for f in _walk(root):
            if glob and not f.match(glob):
                continue
            files.append(str(f.relative_to(root)))
            if len(files) >= MAX_LIST_ENTRIES:
                return json.dumps({"files": files, "truncated": True})
        return json.dumps({"files": files, "truncated": False})
    except ToolDeniedError as exc:
        return _err(exc)
    except OSError as exc:
        return _err(exc)
