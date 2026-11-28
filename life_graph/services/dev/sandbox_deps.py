"""Per-project dependency mounts for the sandbox (Bun/Node toolchain).

Decision record: race-app docs/research/2026-11-28-bun-sandbox/04-decision.md. A project on
``sandbox_toolchain: "bun"`` gets its dependencies installed into a host-side cache from its manifests
only (``bun install --frozen-lockfile --ignore-scripts`` behind the egress proxy), then each workspace's
``node_modules`` is bind-mounted **read-only** at the same relative path under ``/work`` — for the
verifiers and for the coding agent alike. Bun's isolated-linker symlinks are relative, so the identical
layout keeps them valid.

This module is the contract between the two halves of the work:

* the sandbox side (services/dev/sandbox.py + this module's implementation) builds and caches the
  environment, pre-creates the git-ignored mountpoints and returns a :class:`DepsPlan`;
* the agent side (drivers/claude_code.py and the container runtime) only consumes a :class:`DepsPlan`.

Storage stays behind :func:`deps_mounts` so a different store (e.g. Docker ``type=image`` mounts) can
replace host directories later without touching either consumer.
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from life_graph.services.dev import sandbox, sandbox_bun

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class DepsMount:
    """One read-only bind: a directory inside a finished env → a path under the container's ``/work``."""

    source: Path  # absolute host path inside a published (ready) env directory
    target: (
        str  # container path, always ``/work/<workspace>/node_modules`` (or ``/work/node_modules``)
    )


@dataclass(frozen=True)
class DepsPlan:
    """What a container needs to see a project's prepared dependencies."""

    toolchain: str  # "bun" (only value today)
    env_key: str  # content hash of the manifests + setup + base image
    mounts: tuple[DepsMount, ...]
    path_prepend: tuple[str, ...] = ()  # e.g. ("/work/node_modules/.bin",)
    env: dict[str, str] = field(
        default_factory=dict
    )  # extra container env (cache dirs, never secrets)
    # Host directories (relative to the worktree) that were created as empty mountpoints. They are
    # git-ignored by construction; listed so callers can explain/clean them.
    mountpoints: tuple[str, ...] = ()


class DepsUnavailableError(sandbox.SandboxUnavailableError, RuntimeError):
    """The dependency environment could not be prepared (setup failed, not ready, refused manifests).

    Callers treat it like ``SandboxUnavailableError``: a check that needs it is *inconclusive*, never a
    pass; the agent runs without project tools and says so. (It *is* one, so every verifier's
    existing ``except SandboxUnavailableError`` already makes it inconclusive.)
    """


WORK_BIN = f"{sandbox.WORK}/node_modules/.bin"
_HARDENED_GIT = ("git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null")


def _git_ignores(worktree: Path, rel: str) -> bool:
    """Whether git ignores directory *rel* (exit 0). Not ignored, tracked, or any git
    error is ``False``: a mountpoint git would see is refused, fail-closed."""
    try:
        proc = subprocess.run(
            [*_HARDENED_GIT, "check-ignore", "-q", "--", f"{rel}/"],
            cwd=str(worktree),
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _make_mountpoint(worktree: Path, rel: str) -> None:
    """``mkdir -p`` one git-ignored mountpoint, refusing symlinks anywhere on its path.

    Docker cannot create a mountpoint inside a read-only bind (experiment 2b), so the
    verifier's ``/work/<ws>/node_modules`` must exist before the container starts.
    """
    base = worktree.resolve()
    target = worktree / rel
    parent = target.parent
    if not parent.is_dir() or parent.resolve() != (base / rel).parent:
        raise DepsUnavailableError(f"mountpoint {rel!r}: its directory is missing or a symlink")
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise DepsUnavailableError(f"mountpoint {rel!r} exists and is not a plain directory")
    target.mkdir(exist_ok=True)
    if target.is_symlink() or target.resolve() != base / rel:
        raise DepsUnavailableError(f"mountpoint {rel!r} does not resolve inside the worktree")


async def plan_for_env(env: Path, worktree: Path, workspaces: tuple[str, ...]) -> DepsPlan:
    """The mount plan for a finished Bun env: one read-only mount per ``node_modules``.

    Refuses (:class:`DepsUnavailableError`) when git does not ignore a mountpoint: the
    empty directory would otherwise show up in the agent's diff (or hide a tracked one).
    """
    rels = sandbox_bun.node_modules_dirs(env, workspaces)
    if "node_modules" not in rels:
        raise DepsUnavailableError(f"bun env {env.name} has no root node_modules")
    for rel in rels:
        if not await asyncio.to_thread(_git_ignores, worktree, rel):
            raise DepsUnavailableError(
                f"{rel}/ is not ignored by git in this project: refusing to create the"
                " dependency mountpoint there (add node_modules/ to .gitignore)"
            )
    for rel in rels:
        _make_mountpoint(worktree, rel)
    mounts = tuple(DepsMount(source=env / rel, target=f"{sandbox.WORK}/{rel}") for rel in rels)
    return DepsPlan(
        toolchain="bun",
        env_key=env.name,
        mounts=mounts,
        path_prepend=(WORK_BIN,),
        env=dict(sandbox.BUN_ENV),
        mountpoints=rels,
    )


async def deps_mounts(ctx: dict, worktree: Path) -> DepsPlan | None:
    """Prepare (or reuse) the project's dependency env and return the mount plan.

    ``ctx`` is the project context packet (``sandbox_toolchain``, ``sandbox_setup``,
    ``sandbox_setup_allow`` …). Returns ``None`` when the project isn't on a toolchain this module
    serves (today: anything but ``"bun"``). Raises :class:`DepsUnavailableError` when it should serve
    the project but can't.

    For ``"bun"``: :func:`sandbox.prepare_bun_env` (manifests-only install behind the
    egress proxy, ready check, atomic publish), then :func:`plan_for_env` (git-ignore
    guard, pre-created mountpoints, one read-only mount per workspace ``node_modules``).
    """
    if not sandbox.bun_toolchain(ctx):
        return None
    try:
        env = await sandbox.prepare_bun_env(
            worktree, ctx.get("sandbox_setup"), allow=ctx.get("sandbox_setup_allow")
        )
        workspaces = sandbox_bun.expand_workspaces(worktree)
    except DepsUnavailableError:
        raise
    except sandbox.SandboxUnavailableError as exc:
        raise DepsUnavailableError(str(exc)) from exc
    return await plan_for_env(env, worktree, workspaces)
