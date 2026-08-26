"""Build the session context fingerprint that proactive recall ranks against.

``RecallEngine`` feeds the raw dict to ``ContextBuilder.build``, which reads
``project``, ``module``, ``tools``, ``files_open``/``files``, ``git_branch`` and
``topics``. A Claude Code hook can fill ``project`` and ``git_branch`` cheaply
from ``cwd``; anything requiring the transcript is deliberately skipped, since
this runs on the critical path of session startup.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

#: The git call is bounded hard — session startup must not wait on a slow or
#: network-backed repository.
GIT_TIMEOUT_SECONDS = 0.5


def git_branch(cwd: str | Path) -> str | None:
    """Current branch name, or None if this is not a git worktree.

    Reads ``.git/HEAD`` directly first (a file read, no process spawn) and only
    shells out to ``git`` for the worktree/submodule cases where ``.git`` is a
    file pointing elsewhere.
    """
    path = Path(cwd)
    for parent in [path, *path.parents]:
        head = parent / ".git" / "HEAD"
        try:
            if head.is_file():
                ref = head.read_text(encoding="utf-8", errors="replace").strip()
                if ref.startswith("ref: refs/heads/"):
                    return ref.removeprefix("ref: refs/heads/")
                return ref[:12] or None  # detached HEAD
        except OSError:
            return None
        if (parent / ".git").is_file():
            break
    return _git_branch_subprocess(path)


def _git_branch_subprocess(path: Path) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    branch = out.stdout.strip()
    return branch or None


def project_name(cwd: str | Path) -> str:
    """Project identifier — the working directory's basename."""
    return Path(cwd).name or str(cwd)


def build_session_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Assemble the recall context dict from a SessionStart hook payload."""
    cwd = payload.get("cwd") or os.getcwd()
    context: dict[str, Any] = {
        "project": project_name(cwd),
        "tools": ["claude_code"],
        "topics": [],
    }
    branch = git_branch(cwd)
    if branch:
        context["git_branch"] = branch
    return context
