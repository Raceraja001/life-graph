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

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DepsMount:
    """One read-only bind: a directory inside a finished env → a path under the container's ``/work``."""

    source: Path  # absolute host path inside a published (ready) env directory
    target: str  # container path, always ``/work/<workspace>/node_modules`` (or ``/work/node_modules``)


@dataclass(frozen=True)
class DepsPlan:
    """What a container needs to see a project's prepared dependencies."""

    toolchain: str  # "bun" (only value today)
    env_key: str  # content hash of the manifests + setup + base image
    mounts: tuple[DepsMount, ...]
    path_prepend: tuple[str, ...] = ()  # e.g. ("/work/node_modules/.bin",)
    env: dict[str, str] = field(default_factory=dict)  # extra container env (cache dirs, never secrets)
    # Host directories (relative to the worktree) that were created as empty mountpoints. They are
    # git-ignored by construction; listed so callers can explain/clean them.
    mountpoints: tuple[str, ...] = ()


class DepsUnavailableError(RuntimeError):
    """The dependency environment could not be prepared (setup failed, not ready, refused manifests).

    Callers treat it like ``SandboxUnavailableError``: a check that needs it is *inconclusive*, never a
    pass; the agent runs without project tools and says so.
    """


async def deps_mounts(ctx: dict, worktree: Path) -> DepsPlan | None:
    """Prepare (or reuse) the project's dependency env and return the mount plan.

    ``ctx`` is the project context packet (``sandbox_toolchain``, ``sandbox_setup``,
    ``sandbox_setup_allow`` …). Returns ``None`` when the project isn't on a toolchain this module
    serves (today: anything but ``"bun"``). Raises :class:`DepsUnavailableError` when it should serve
    the project but can't. Implemented by the sandbox side (W1).
    """
    raise NotImplementedError  # W1 replaces this
