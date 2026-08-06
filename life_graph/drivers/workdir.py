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


async def resolve_workdir(
    packet: ContextPacket, fallback: Path
) -> tuple[Path, Path | None]:
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
    - Worktree creation fails (e.g. not a git repo) → falls back to the
      project path directly, logged as a warning. Never raises.
    """
    project_path = packet.project_context.get("path")
    if not project_path or not Path(project_path).is_dir():
        return fallback, None

    project = Path(project_path)
    if not packet.project_context.get("isolation"):
        return project, None

    worktree = fallback / f"wt_{uuid.uuid4().hex[:8]}"
    proc = await asyncio.create_subprocess_exec(
        "git", "worktree", "add", "--detach", str(worktree),
        cwd=str(project),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        logger.warning(
            "Worktree isolation failed (%s) — using project dir directly",
            err.decode(errors="replace").strip()[:200],
        )
        return project, None
    return worktree, worktree


async def remove_worktree(packet: ContextPacket, worktree: Path) -> None:
    """Remove a worktree created by :func:`resolve_workdir`. Best-effort."""
    project_path = packet.project_context.get("path")
    if not project_path:
        return
    proc = await asyncio.create_subprocess_exec(
        "git", "worktree", "remove", "--force", str(worktree),
        cwd=str(project_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
