"""Land a verified task branch in a repository with no GitHub remote.

A project whose registry sets ``pr_mode: local`` (a repo kept on this machine
only, such as the Android app) has no pull request to open: approving the
task's ``driver_pr`` approval merges its branch into the local base branch
here instead (services/approvals.py). The same promises as the GitHub path
hold: only the exact commit that was verified is merged, onto the base it was
built from, and nothing is forced.

The merge never touches a working tree with uncommitted changes. If the base
branch is checked out and clean, it is fast-forwarded to the merge commit
(the files update); if it is not checked out, only its ref moves.
"""

from __future__ import annotations

import logging
from typing import Any

from life_graph.services.github_pr import (
    _BRANCH_RE,
    _SHA_RE,
    PullRequestError,
    _git,
    _pr_title,
)

logger = logging.getLogger(__name__)


async def merge_locally(payload: dict[str, Any]) -> dict[str, Any]:
    """Merge the verified task branch into its base branch, locally.

    Returns ``{"merged": True, "merge_commit": sha, "base_branch": name}``.
    An already-merged branch returns the same shape, so a retry is harmless.

    Raises:
        PullRequestError: the branch moved since it was verified, the base is
            gone or no longer contains the commit the task was cut from, the
            change conflicts, or the checked-out base has local changes.
    """
    from life_graph.tools._guards import ToolDeniedError, resolve_in_roots

    branch = payload.get("branch") or ""
    head = payload.get("head_commit") or ""
    base_commit = payload.get("base_commit") or ""
    base = payload.get("base_branch") or ""
    if not _BRANCH_RE.match(branch):
        raise PullRequestError(f"refusing to merge unexpected branch name {branch!r}")
    if not (_SHA_RE.match(head) and _SHA_RE.match(base_commit)):
        raise PullRequestError("approval is missing the verified commit ids")
    if not base:
        raise PullRequestError(
            "the task was cut from a detached HEAD: no base branch to merge into"
        )
    try:
        repo = resolve_in_roots(payload.get("repo_path") or "", tool_name="local merge")
    except ToolDeniedError as exc:
        raise PullRequestError(str(exc)) from exc

    code, current, _ = await _git(repo, "rev-parse", f"refs/heads/{branch}")
    if code != 0:
        raise PullRequestError(f"branch {branch} no longer exists")
    if current != head:
        raise PullRequestError(
            f"branch {branch} moved since it was verified ({head[:8]} → {current[:8]}); "
            "refusing to merge unverified commits"
        )
    code, tip, _ = await _git(repo, "rev-parse", f"refs/heads/{base}")
    if code != 0:
        raise PullRequestError(f"base branch {base!r} does not exist")
    code, _, _ = await _git(repo, "merge-base", "--is-ancestor", head, tip)
    if code == 0:
        return {"merged": True, "merge_commit": tip, "base_branch": base, "existing": True}
    code, _, _ = await _git(repo, "merge-base", "--is-ancestor", base_commit, tip)
    if code != 0:
        raise PullRequestError(
            f"{base!r} no longer contains the commit the task was built on "
            f"({base_commit[:8]}); it was rewritten — re-run the task"
        )

    # Build the merge without touching any working tree.
    code, tree, err = await _git(repo, "merge-tree", "--write-tree", tip, head)
    if code != 0:
        raise PullRequestError(
            f"the change conflicts with {base!r} as it is now: {(tree or err).splitlines()[-1:]}"
        )
    tree = tree.splitlines()[0].strip()
    title = (payload.get("instruction") or f"Life Graph task {payload.get('task_id')}").strip()
    message = f"Merge {branch}: {_pr_title(title.splitlines()[0]) if title else branch}"
    code, merge_commit, err = await _git(
        repo, "commit-tree", tree, "-p", tip, "-p", head, "-m", message
    )
    if code != 0 or not _SHA_RE.match(merge_commit.strip()):
        raise PullRequestError(f"could not create the merge commit: {err[-300:]}")
    merge_commit = merge_commit.strip()

    code, checked_out, _ = await _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    if code == 0 and checked_out == base:
        code, dirty, _ = await _git(repo, "status", "--porcelain", "--untracked-files=no")
        if dirty.strip():
            raise PullRequestError(
                f"{base!r} is checked out with uncommitted changes; commit or stash them, "
                "then approve again"
            )
        code, _, err = await _git(repo, "merge", "--ff-only", "--quiet", merge_commit)
        if code != 0:
            raise PullRequestError(f"could not fast-forward {base!r}: {err[-300:]}")
    else:
        # Compare-and-swap: fails if the base moved since we read it.
        code, _, err = await _git(repo, "update-ref", f"refs/heads/{base}", merge_commit, tip)
        if code != 0:
            raise PullRequestError(f"could not move {base!r}: {err[-300:]}")
    logger.info("Merged %s into %s locally: %s", branch, base, merge_commit[:8])
    return {"merged": True, "merge_commit": merge_commit, "base_branch": base, "existing": False}


async def pr_mode(session: Any, project_id: Any) -> str:
    """The project's ``pr_mode``: "local" or "github" (the default)."""
    import uuid

    from life_graph.models.db import Project

    if not project_id:
        return "github"
    try:
        project = await session.get(Project, uuid.UUID(str(project_id)))
    except (ValueError, TypeError):
        return "github"
    mode = ((project.scan_metadata or {}).get("pr_mode") if project else None) or "github"
    return "local" if str(mode).strip().lower() == "local" else "github"
