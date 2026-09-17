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
        },
        "required": ["path"],
    },
)
async def code_read(path: str, start_line: int = 1) -> str:
    try:
        p = _resolve(path, "code_read")
        if not p.is_file():
            return json.dumps({"error": f"Not a file: {path}"})
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start_line))
        out: list[str] = []
        used = 0
        n = start
        while n <= len(lines):
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
                "next_start_line": n if n <= len(lines) else None,
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
        "Edit a file by replacing one exact snippet. `old` must appear exactly once "
        "(include enough surrounding lines to make it unique; copy whitespace exactly, "
        "without the line-number prefixes code_read shows). To create a new file, "
        "pass an empty `old` and the whole file as `new`."
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
                "description": "Exact text to replace; empty to create a new file.",
            },
            "new": {"type": "string", "description": "Replacement text."},
        },
        "required": ["path", "old", "new"],
    },
)
async def code_edit(path: str, old: str, new: str) -> str:
    if len(new) > MAX_EDIT_CHARS:
        return json.dumps(
            {"error": f"Replacement too large ({len(new)} chars, max {MAX_EDIT_CHARS})"}
        )
    try:
        p = _resolve(path, "code_edit")
        check_writable(p, tool_name="code_edit")
        if old == "":
            if p.exists():
                return json.dumps({"error": "File exists; pass the text to replace as `old`."})
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(new, encoding="utf-8")
            return json.dumps({"created": str(p), "lines": new.count("\n") + 1})
        if not p.is_file():
            return json.dumps({"error": f"Not a file: {path}"})
        text = p.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            hint = (
                "not found — re-read the file and copy the text exactly"
                if count == 0
                else f"found {count} times — include more surrounding lines"
            )
            return json.dumps({"error": f"`old` {hint}"})
        at_line = text[: text.index(old)].count("\n") + 1
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        return json.dumps({"edited": str(p), "at_line": at_line})
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
