"""Shared workdir resolution — a real project's path, or an isolated git
worktree off it, for drivers/dispatch code that needs a real filesystem
location.

Extracted from ``ClaudeCodeDriver`` (its original, sole consumer) so
``TaskDispatcher.dispatch_task`` can resolve the SAME directory for both the
driver dispatch call and the verifier chain that inspects its output — a
verifier chain given a different workdir than the one the driver actually
wrote to would verify nothing.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from life_graph.drivers.base import ContextPacket

logger = logging.getLogger(__name__)


_BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")


async def _pinned_start(project: Path, base_branch: str | None) -> str | None:
    """The ref a worktree starts from when the project pins a base branch.

    ``origin/<base>`` after a fetch, so a task is built on what is on GitHub,
    not on whatever branch the local checkout happens to be on (switching
    branches mid-plan used to change the base under a running plan). Falls
    back to the local ``<base>`` when the fetch fails (offline, no remote);
    None (= the checkout's HEAD, the old behaviour) when nothing is pinned.
    """
    if not base_branch or not _BRANCH_NAME_RE.match(base_branch) or base_branch.startswith("-"):
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "fetch",
            "--quiet",
            "origin",
            f"{base_branch}:refs/remotes/origin/{base_branch}",
            cwd=str(project),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await asyncio.wait_for(proc.communicate(), timeout=60)
    except (OSError, TimeoutError) as exc:
        logger.warning("Could not fetch base %s (%s) — using the local branch", base_branch, exc)
        return base_branch
    if proc.returncode != 0:
        logger.warning(
            "Could not fetch base %s (%s) — using the local branch",
            base_branch,
            err.decode(errors="replace").strip()[:200],
        )
        return base_branch
    return f"origin/{base_branch}"


async def resolve_workdir(packet: ContextPacket, fallback: Path) -> tuple[Path, Path | None]:
    """Pick the execution directory for a dispatch.

    Returns ``(cwd, worktree)`` where ``worktree`` is non-``None`` only when
    an isolated git worktree was created (and must be removed after the
    dispatch via :func:`remove_worktree`).

    - No real, existing directory at ``packet.project_context["path"]`` →
      ``(fallback, None)``.
    - A real path, but ``packet.project_context["isolation"]`` is falsy →
      ``(that path, None)`` — operate directly on it.
    - A real path AND ``isolation`` truthy → create a throwaway
      ``git worktree`` off it under ``fallback`` and return that.
    - Worktree creation fails — ``git worktree add`` returned non-zero
      (e.g. not a git repo), or ``git`` is not installed at all →
      ``(fallback, None)``, logged as a warning. Isolation was ASKED
      FOR and could not be delivered, so the dispatch must NOT silently
      degrade onto the real, live checkout; it degrades onto the inert
      scratch dir instead, exactly as if no project were registered.
      Never raises.
    """
    project_path = packet.project_context.get("path")
    if not project_path or not Path(project_path).is_dir():
        return fallback, None

    project = Path(project_path)
    if not packet.project_context.get("isolation"):
        return project, None

    worktree = fallback / f"wt_{uuid.uuid4().hex[:8]}"
    start = await _pinned_start(project, packet.project_context.get("base_branch"))
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "worktree",
            "add",
            "--detach",
            str(worktree),
            *([start] if start else []),
            cwd=str(project),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
    except Exception as exc:
        # `git` missing from PATH (FileNotFoundError — the shipped runtime
        # image had no git until this was found), permission errors, etc.
        # create_subprocess_exec raises BEFORE there is a proc to inspect.
        logger.warning("Worktree isolation could not run git (%s) — using scratch dir", exc)
        return fallback, None
    if proc.returncode != 0:
        logger.warning(
            "Worktree isolation failed (%s) — using scratch dir",
            err.decode(errors="replace").strip()[:200],
        )
        return fallback, None
    return worktree, worktree


def worktree_intact(worktree: Path, origin: str | Path) -> bool:
    """Whether *worktree*'s ``.git`` is still the link ``git worktree add`` wrote.

    A linked worktree's ``.git`` is a one-line file pointing into
    ``<origin>/.git/worktrees/``. A driver with write access to the worktree
    can replace it with a directory of its own — whose config then governs
    every host-side git command run there afterwards.
    """
    git = Path(worktree) / ".git"
    try:
        if git.is_symlink() or not git.is_file():
            return False
        content = git.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not content.startswith("gitdir:") or "\n" in content:
        return False
    try:
        target = Path(content.removeprefix("gitdir:").strip()).resolve()
        expected = (Path(origin) / ".git" / "worktrees").resolve()
    except (OSError, RuntimeError):
        return False
    return expected in target.parents


# Bounds the walk: an agent can create files faster than we want to stat them.
# High enough for a JS worktree after `npm install`; past it, fail closed.
_SYMLINK_SCAN_LIMIT = 1_000_000


def _unchanged_tracked_links(base: Path) -> set[str]:
    """Symlinks committed at HEAD and not changed in the worktree.

    Those are the project's own (the owner committed them), not the agent's.
    Only called once the worktree's .git link is known intact, so these git
    commands read the origin's own repository config. Any git failure
    (timeout, no commits yet) returns an empty set: every escaping link is
    then counted -- fail closed.
    """
    import subprocess

    def git(*args: str) -> str | None:
        try:
            res = subprocess.run(
                ["git", "-C", str(base), *args], capture_output=True, text=True, timeout=30
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return res.stdout if res.returncode == 0 else None

    listed = git("ls-files", "-s", "-z")
    changed_out = git("diff", "--name-only", "-z", "HEAD")
    if listed is None or changed_out is None:
        return set()
    tracked = {
        entry.split("\t", 1)[1]
        for entry in listed.split("\0")
        if entry.startswith("120000 ") and "\t" in entry
    }
    changed = {p for p in changed_out.split("\0") if p}
    return tracked - changed


def escaping_symlinks(worktree: Path, limit: int = 20, *, git_aware: bool = False) -> list[str]:
    """Symlinks in *worktree* whose target lies outside it (relative paths).

    The worktree is the agent's. A link it plants -- ``notes.txt ->
    ~/.ssh/id_rsa`` -- is read by host-side code that trusts the worktree:
    verifiers reading changed files, the PR description and review models
    reading the diff, the landing commit. The agent's own container cannot see
    the host; the host-side reader can, so one link would carry a host file
    out. A link that stays inside the worktree is fine (repos use them).
    Dangling links count when their target would be outside. The walk skips
    ``.git`` and stops after ``limit`` findings. With ``git_aware`` (only for a
    worktree whose .git link is intact), links committed at HEAD and left
    unchanged are not counted: the agent did not make them.
    """
    try:
        base = Path(worktree).resolve()
    except (TypeError, OSError):
        return []
    # The project's own links are known BEFORE the walk, so they never take
    # a place under `limit` (20 committed links used to hide the agent's).
    own = _unchanged_tracked_links(base) if git_aware else set()
    found: list[str] = []
    seen = 0
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        # Only the worktree's own top-level .git dir is git's business (and
        # worktree_intact checks it). A ".git" anywhere else, or one that is a
        # symlink, is checked like any other entry.
        if Path(dirpath) == base and ".git" in dirnames and not (base / ".git").is_symlink():
            dirnames.remove(".git")
        for name in [*dirnames, *filenames]:
            seen += 1
            if seen > _SYMLINK_SCAN_LIMIT:
                found.append("(scan limit reached: too many files to check)")
                return found
            path = Path(dirpath) / name
            if not path.is_symlink():
                continue
            try:
                target = Path(os.path.realpath(path))
            except OSError:
                target = None
            if target is None or (target != base and base not in target.parents):
                rel = str(path.relative_to(base))
                if rel in own:
                    continue
                found.append(rel)
                if len(found) >= limit:
                    return found
    return found


async def diff_against_head(workdir: Path) -> str:
    """Unified diff of every change (tracked, modified, untracked) since HEAD.

    Stages everything first (``git add -A``) so new files show up — a plain
    ``git diff HEAD`` only covers already-tracked files. This runs BEFORE
    :func:`preserve_verified_work`, which re-stages (a harmless no-op) and
    commits; staging here changes nothing about what eventually lands.

    Same hardened git invocation as landing: this also runs on the host,
    against a worktree the driver controls. Never raises — a diff that
    could not be computed is reported as empty, not a dispatch failure.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "add",
            "-A",
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode != 0:
            return ""

        proc = await asyncio.create_subprocess_exec(
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "diff",
            "--cached",
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _err = await proc.communicate()
        if proc.returncode != 0:
            return ""
        return out.decode(errors="replace")
    except Exception as exc:
        logger.warning("Could not compute diff for review: %s", exc)
        return ""


async def preserve_verified_work(
    worktree: Path,
    repo_path: str | Path,
    task_id: str,
    summary: str | None = None,
) -> str | None:
    """Commit a verified dispatch onto a branch so cleanup cannot discard it.

    ``resolve_workdir`` creates the worktree with ``--detach``, so any commit
    made inside it is unreferenced and ``remove_worktree`` takes the work with
    it. The dispatcher ran the verifier chain, proved the change good, and
    then deleted it -- reporting success while landing nothing.

    This commits the worktree's changes and points a branch at them. The
    branch lives in the shared object store, so it survives the worktree
    being removed and is visible from the origin checkout. Nothing is merged,
    nothing is pushed, and the default branch is never touched: the result is
    a reviewable branch, which is what an approval step needs to act on.

    Returns the branch name, or ``None`` when there was nothing to commit or
    git refused. Never raises -- landing is best-effort and must not turn a
    verified dispatch into a failed one.
    """
    branch = f"lg/task-{str(task_id)[:8]}"
    message = summary or f"Verified change from Life Graph task {task_id}"
    # Keep the subject to one line; the driver's summary can be a paragraph.
    subject = message.strip().splitlines()[0][:72] if message.strip() else message

    async def _git(*args: str, cwd: Path | str) -> tuple[int, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                # The worktree holds driver-written content and shares the
                # origin's .git, so hooks and fsmonitor here could be agent-
                # planted — and this runs on the host, outside any driver
                # scoping. The verifier chain is the gate, not commit hooks.
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "core.fsmonitor=false",
                *args,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await proc.communicate()
        except Exception as exc:  # git absent, permissions, ...
            logger.warning("Landing could not run git %s (%s)", args[:2], exc)
            return 1, str(exc)
        return proc.returncode, (out + err).decode(errors="replace").strip()

    code, _ = await _git("add", "-A", cwd=worktree)
    if code != 0:
        return None

    # Nothing staged means the driver changed no files; that is not a failure.
    code, _ = await _git("diff", "--cached", "--quiet", cwd=worktree)
    if code == 0:
        logger.info("Task %s produced no file changes — nothing to land", task_id)
        return None

    code, out = await _git(
        "-c",
        "user.email=life-graph@localhost",
        "-c",
        "user.name=Life Graph",
        "commit",
        "--no-verify",
        "-m",
        subject,
        cwd=worktree,
    )
    if code != 0:
        logger.warning("Landing could not commit task %s: %s", task_id, out[:200])
        return None

    # Name the commit from the ORIGIN repo: the worktree is detached, so a
    # branch created here is what keeps the commit reachable after removal.
    code, out = await _git("branch", "--force", branch, "HEAD", cwd=worktree)
    if code != 0:
        logger.warning("Landing could not create branch %s: %s", branch, out[:200])
        return None

    logger.info("Task %s landed on branch %s", task_id, branch)
    return branch


async def remove_worktree(
    packet: ContextPacket, worktree: Path, repo_path: str | Path | None = None
) -> None:
    """Remove a worktree created by :func:`resolve_workdir`. Best-effort.

    ``repo_path`` overrides where ``git worktree remove`` is run from. Pass
    it when the caller has since rewritten ``packet.project_context["path"]``
    to point at the worktree itself (``TaskDispatcher.dispatch_task`` does,
    to keep a downstream driver's own ``resolve_workdir`` idempotent) — git
    refuses to delete a worktree while the cwd is inside it.

    Never raises — including when ``git`` is not installed at all.
    """
    project_path = str(repo_path) if repo_path else packet.project_context.get("path")
    if not project_path:
        return
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "worktree",
            "remove",
            "--force",
            str(worktree),
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    except Exception as exc:
        logger.warning("Worktree cleanup could not run git (%s) — leaving %s", exc, worktree)
