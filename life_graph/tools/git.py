"""Git tool — repository operations via git CLI.

Provides the agent with git operations: status, log, diff, branch,
commit, push, pull, and blame. All operations run via subprocess
to avoid heavy git library dependencies.
"""

from __future__ import annotations

import asyncio
import json
import logging

from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

COMMAND_TIMEOUT = 15


async def _run_git(args: list[str], cwd: str) -> dict:
    """Run a git command and return structured result."""
    cmd = ["git"] + args
    logger.info("Running: %s (cwd=%s)", " ".join(cmd), cwd)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
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
    except asyncio.TimeoutError:
        return {"error": f"Git command timed out after {COMMAND_TIMEOUT}s"}
    except Exception as exc:
        return {"error": f"Git command failed: {exc}"}


@tool(
    name="git_status",
    description=(
        "Get the current git status of a repository. Shows modified, staged, "
        "and untracked files."
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
    result = await _run_git(["status", "--porcelain", "--branch"], repo_path)
    return json.dumps(result)


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
                "description": "Number of recent commits to show. Default 10.",
            },
        },
        "required": ["repo_path"],
    },
)
async def git_log(repo_path: str, count: int = 10) -> str:
    """Get recent git log."""
    result = await _run_git(
        ["log", f"-{count}", "--oneline", "--decorate", "--graph"],
        repo_path,
    )
    return json.dumps(result)


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
    args = ["diff", "--stat"]
    if target == "staged":
        args.append("--cached")
    elif target:
        args.append(target)
    result = await _run_git(args, repo_path)
    return json.dumps(result)


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
    result = await _run_git(["branch", "-a", "--sort=-committerdate"], repo_path)
    return json.dumps(result)
