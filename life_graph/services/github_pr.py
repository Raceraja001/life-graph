"""Open a GitHub pull request for a verified, approved driver task.

A dispatch that passes verification is committed onto a local ``lg/task-*``
branch (:func:`life_graph.drivers.workdir.preserve_verified_work`). The
dispatcher then files a ``driver_pr`` approval; approving it calls
:func:`open_pull_request`, which pushes that branch and opens a PR with ``gh``.

Nothing is pushed without that approval, and what is pushed is pinned:

* the branch must still point at the commit that was verified (``head_commit``)
  — the push sends that exact commit, not whatever the ref points at now;
* the commit the task started from (``base_commit``) must already be on the
  remote base branch. Otherwise the PR would silently carry the user's own
  unpushed local commits along with the agent's change.

Authentication is ``gh``'s: git is handed ``gh auth git-credential`` for this
push only, so no global git credential config is needed.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import TYPE_CHECKING, Any

from life_graph.config import settings

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_BRANCH_RE = re.compile(r"^lg/task-[0-9a-f-]{1,36}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_TIMEOUT = 120


class PullRequestError(Exception):
    """The PR could not be opened. The message is safe to show the user."""


def _hardened_git(repo: str | Path) -> list[str]:
    gh = settings.driver_gh_bin
    return [
        "git",
        "-C",
        str(repo),
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
        # Reset inherited helpers, then use gh's token for this command only.
        "-c",
        "credential.helper=",
        "-c",
        f"credential.helper=!{gh} auth git-credential",
    ]


async def _run(argv: list[str], cwd: str | Path | None = None) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GH_PROMPT_DISABLED": "1"},
        )
    except FileNotFoundError as exc:
        raise PullRequestError(f"{argv[0]} is not installed") from exc
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        raise PullRequestError(f"{argv[0]} timed out after {_TIMEOUT}s") from None
    return (
        proc.returncode if proc.returncode is not None else -1,
        out.decode(errors="replace").strip(),
        err.decode(errors="replace").strip(),
    )


async def _git(repo: str | Path, *args: str) -> tuple[int, str, str]:
    return await _run([*_hardened_git(repo), *args])


async def describe_landing(repo_path: str | Path, branch: str) -> dict[str, Any]:
    """What a later PR needs to know about a just-landed branch.

    Called right after landing, while the origin checkout is still on the
    branch the task's worktree was cut from.
    """
    info: dict[str, Any] = {}
    code, out, _ = await _git(repo_path, "rev-parse", f"{branch}^{{commit}}")
    if code == 0:
        info["head_commit"] = out
    code, out, _ = await _git(repo_path, "rev-parse", f"{branch}^")
    if code == 0:
        info["base_commit"] = out
    code, out, _ = await _git(repo_path, "symbolic-ref", "--short", "-q", "HEAD")
    if code == 0 and out:
        info["base_branch"] = out
    return info


def _pr_body(payload: dict[str, Any]) -> str:
    checks = payload.get("checks") or []
    lines = [
        payload.get("instruction") or "",
        "",
        "## Agent summary",
        (payload.get("summary") or "(none)")[:3000],
        "",
        "## Verification",
        ("Passed: " + ", ".join(f"`{c}`" for c in checks)) if checks else "No checks ran.",
        "",
        f"Task `{payload.get('task_id')}` · driver `{payload.get('driver')}` · "
        f"opened by Life Graph after human approval.",
    ]
    return "\n".join(lines)


async def open_pull_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Push the task branch and open (or find) its PR. Returns ``{"pr_url"}``.

    Raises:
        PullRequestError: anything that stops the PR; nothing is half-done in a
            way a retry cannot finish (push and create are both idempotent).
    """
    from life_graph.tools._guards import ToolDeniedError, resolve_in_roots

    branch = payload.get("branch") or ""
    head = payload.get("head_commit") or ""
    base_commit = payload.get("base_commit") or ""
    base_branch = payload.get("base_branch") or ""
    if not _BRANCH_RE.match(branch):
        raise PullRequestError(f"refusing to push unexpected branch name {branch!r}")
    if not (_SHA_RE.match(head) and _SHA_RE.match(base_commit)):
        raise PullRequestError("approval is missing the verified commit ids")
    if not base_branch:
        raise PullRequestError(
            "the task was cut from a detached HEAD, so there is no base branch to open a PR against"
        )
    try:
        repo = resolve_in_roots(payload.get("repo_path") or "", tool_name="pull request")
    except ToolDeniedError as exc:
        raise PullRequestError(str(exc)) from exc

    code, current, _ = await _git(repo, "rev-parse", f"refs/heads/{branch}")
    if code != 0:
        raise PullRequestError(f"branch {branch} no longer exists locally")
    if current != head:
        raise PullRequestError(
            f"branch {branch} moved since it was verified ({head[:8]} → {current[:8]}); "
            "refusing to push unverified commits"
        )

    code, _, err = await _git(repo, "fetch", "--quiet", "origin", f"refs/heads/{base_branch}")
    if code != 0:
        raise PullRequestError(
            f"base branch {base_branch!r} is not on origin — push it first ({err[-200:]})"
        )
    code, _, _ = await _git(repo, "merge-base", "--is-ancestor", base_commit, "FETCH_HEAD")
    if code != 0:
        raise PullRequestError(
            f"the task was built on local commits of {base_branch!r} that origin does not "
            "have; push that branch first so the PR contains only the agent's change"
        )

    code, _, err = await _git(repo, "push", "--quiet", "origin", f"{head}:refs/heads/{branch}")
    if code != 0:
        raise PullRequestError(f"git push failed: {err[-400:]}")

    gh = settings.driver_gh_bin
    code, url, _ = await _run([gh, "pr", "view", branch, "--json", "url", "-q", ".url"], cwd=repo)
    if code == 0 and url:
        return {"pr_url": url, "existing": True}

    title = (payload.get("instruction") or f"Life Graph task {payload.get('task_id')}").strip()
    title = title.splitlines()[0][:72] if title else branch
    code, out, err = await _run(
        [
            gh,
            "pr",
            "create",
            "--head",
            branch,
            "--base",
            base_branch,
            "--title",
            title,
            "--body",
            _pr_body(payload),
        ],
        cwd=repo,
    )
    if code != 0:
        raise PullRequestError(f"gh pr create failed: {(err or out)[-400:]}")
    url = out.splitlines()[-1].strip() if out else ""
    logger.info("Opened PR for %s: %s", branch, url)
    return {"pr_url": url, "existing": False}
