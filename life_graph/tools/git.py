"""Git tool — read-only repository inspection via the git CLI.

Provides the agent with git status, log, diff and branch. All operations run
via subprocess to avoid heavy git library dependencies.

These tools act on the host exactly like ``file_read``, so they sit behind
the same controls in :mod:`life_graph.tools._guards`: the tenant gate, and
``repo_path`` confined to the allowed roots. Two git-specific holes are
closed here as well:

* **Option injection.** A model-supplied ``target`` beginning with ``-`` is
  parsed by git as an option — ``--output=<file>`` turns ``git diff`` into an
  arbitrary file write. Such targets are rejected, and ``--end-of-options``
  stops git reading any later argument as a flag.
* **Repo-config execution.** A repository's own config can make read-only
  commands run programs (``core.fsmonitor`` on status, external diff and
  textconv drivers on diff). Those are disabled per invocation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

from life_graph.tools._guards import ToolDeniedError, check_tenant, resolve_in_roots
from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

COMMAND_TIMEOUT = 15
MAX_LOG_COUNT = 200

# Neutralise repo-config keys that execute programs during read-only commands.
_HARDENING = ["-c", "core.fsmonitor=false", "-c", "core.pager=cat"]


def _resolve_repo(repo_path: str, tool_name: str) -> str:
    """Apply the host-tool guards and return the resolved repository path."""
    check_tenant(tool_name)
    resolved = resolve_in_roots(repo_path, tool_name=tool_name)
    if not resolved.is_dir():
        raise ToolDeniedError(f"Not a directory: {repo_path}")
    return str(resolved)


async def _run_git(args: list[str], cwd: str) -> dict:
    """Run a git command and return structured result."""
    cmd = ["git", *_HARDENING, *args]
    logger.info("Running: %s (cwd=%s)", " ".join(cmd), cwd)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=COMMAND_TIMEOUT,
        )
        return {
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace").strip(),
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
        }
    except TimeoutError:
        return {"error": f"Git command timed out after {COMMAND_TIMEOUT}s"}
    except Exception as exc:
        return {"error": f"Git command failed: {exc}"}


async def _guarded(tool_name: str, repo_path: str, args: list[str]) -> str:
    try:
        cwd = _resolve_repo(repo_path, tool_name)
    except ToolDeniedError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(await _run_git(args, cwd))


@tool(
    name="git_status",
    description=(
        "Get the current git status of a repository. Shows modified, staged, and untracked files."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Absolute path to the git repository.",
            },
        },
        "required": ["repo_path"],
    },
)
async def git_status(repo_path: str) -> str:
    """Get git status of a repository."""
    return await _guarded("git_status", repo_path, ["status", "--porcelain", "--branch"])


@tool(
    name="git_log",
    description=(
        "Get recent git commit history. Returns commit hash, author, date, "
        "and message for the last N commits."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Absolute path to the git repository.",
            },
            "count": {
                "type": "integer",
                "description": f"Number of recent commits to show. Default 10, max {MAX_LOG_COUNT}.",
            },
        },
        "required": ["repo_path"],
    },
)
async def git_log(repo_path: str, count: int = 10) -> str:
    """Get recent git log."""
    try:
        n = max(1, min(int(count), MAX_LOG_COUNT))
    except (TypeError, ValueError):
        return json.dumps({"error": f"count must be an integer, got {count!r}"})
    return await _guarded(
        "git_log", repo_path, ["log", f"-{n}", "--oneline", "--decorate", "--graph"]
    )


@tool(
    name="git_diff",
    description=(
        "Show changes in the working directory or between commits. "
        "Without arguments, shows unstaged changes."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Absolute path to the git repository.",
            },
            "target": {
                "type": "string",
                "description": "Diff target: a file path, 'staged' for staged changes, "
                "or a commit hash/range like 'HEAD~3..HEAD'. Default: unstaged changes.",
            },
        },
        "required": ["repo_path"],
    },
)
async def git_diff(repo_path: str, target: str | None = None) -> str:
    """Show git diff."""
    args = ["diff", "--stat", "--no-ext-diff", "--no-textconv"]
    if target == "staged":
        args.append("--cached")
    elif target:
        if target.lstrip().startswith("-"):
            return json.dumps({"error": "target must be a path or revision, not an option"})
        args += ["--end-of-options", target]
    return await _guarded("git_diff", repo_path, args)


@tool(
    name="git_branch",
    description="List branches or get current branch name.",
    parameters_schema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Absolute path to the git repository.",
            },
        },
        "required": ["repo_path"],
    },
)
async def git_branch(repo_path: str) -> str:
    """List git branches."""
    return await _guarded("git_branch", repo_path, ["branch", "-a", "--sort=-committerdate"])
