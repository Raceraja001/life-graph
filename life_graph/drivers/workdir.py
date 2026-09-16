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
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from life_graph.drivers.base import ContextPacket

logger = logging.getLogger(__name__)


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
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "worktree",
            "add",
            "--detach",
            str(worktree),
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
