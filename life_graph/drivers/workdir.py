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
