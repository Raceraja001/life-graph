"""Bun workspaces for the verifier sandbox: which manifests, which ``node_modules``.

Pure filesystem helpers for :func:`sandbox.prepare_bun_env` and
:func:`sandbox_deps.deps_mounts` (decision record: race-app
``docs/research/2026-11-28-bun-sandbox/04-decision.md``).

Bun's isolated linker gives every workspace its own ``node_modules`` (relative
links into the root ``node_modules/.bun`` store), so one ``/node_modules``
mount, as the Node toolchain uses, does not fit. Instead the setup installs
from the manifests only -- root ``package.json``, the lockfile and every
workspace's ``package.json``, at their relative paths -- and each resulting
``node_modules`` is mounted read-only at the same path under ``/work``.

Everything read here is agent-edited (the worktree), so it is treated as
hostile: workspace globs that leave the repository, symlinked directories or
manifests, and absurd counts are refused (:class:`SandboxUnavailableError`,
which every caller turns into *inconclusive*). A wrong expansion would be a
missing mount, so it fails closed with a message rather than guessing.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path, PurePosixPath

from life_graph.services.dev.sandbox import SandboxUnavailableError

ROOT_MANIFEST = "package.json"
LOCKFILES: tuple[str, ...] = ("bun.lock", "bun.lockb")
NODE_MODULES = "node_modules"
MAX_WORKSPACES = 200
_MAX_MANIFEST_BYTES = 5 * 1024 * 1024
_DEP_MAPS = ("dependencies", "devDependencies", "optionalDependencies")
# A glob segment may hold these characters and nothing else (no "..", no "~",
# no "$", no backslash): enough for "apps/*", "packages/**", "tools/cli-*".
_SEGMENT = re.compile(r"^[A-Za-z0-9._@*?\[\]+-]+$")


class BunWorkspaceError(SandboxUnavailableError):
    """The root ``package.json``'s workspaces could not be expanded safely."""


def regular_file(workdir: Path, rel: str) -> bool:
    """*rel* is a regular file inside *workdir*, reached through no symlink."""
    f = workdir / rel
    try:
        return f.is_file() and not f.is_symlink() and f.resolve() == workdir.resolve() / rel
    except (OSError, RuntimeError):
        return False


def read_json(workdir: Path, rel: str) -> dict:
    """A manifest as a dict; refuses symlinks, oversized files and non-JSON."""
    if not regular_file(workdir, rel):
        raise BunWorkspaceError(f"bun toolchain: {rel} is missing, a symlink or not a file")
    f = workdir / rel
    if f.stat().st_size > _MAX_MANIFEST_BYTES:
        raise BunWorkspaceError(f"bun toolchain: {rel} is too large to read")
    try:
        data = json.loads(f.read_text(errors="replace"))
    except ValueError as exc:
        raise BunWorkspaceError(f"bun toolchain: {rel} does not parse as JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise BunWorkspaceError(f"bun toolchain: {rel} is not a JSON object")
    return data


def workspace_patterns(pkg: dict) -> list[str]:
    """The ``workspaces`` globs of a root ``package.json``: an array or ``{packages: [...]}``."""
    raw = pkg.get("workspaces")
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = raw.get("packages", [])
    if not isinstance(raw, list) or not all(isinstance(p, str) for p in raw):
        raise BunWorkspaceError(
            "bun toolchain: package.json 'workspaces' must be a list of globs"
            " (or {packages: [...]})"
        )
    return raw


def _clean_pattern(pattern: str) -> str:
    """A workspace glob relative to the repo root, or :class:`BunWorkspaceError`."""
    p = pattern.strip()
    if p.startswith("./"):
        p = p[2:]
    p = p.rstrip("/")
    parts = p.split("/") if p else []
    if (
        not parts
        or p.startswith("/")
        or any(part in ("", ".", "..") or not _SEGMENT.match(part) for part in parts)
        or "!" in p
    ):
        raise BunWorkspaceError(
            f"bun toolchain: workspace glob {pattern!r} is not a plain path inside the repository"
        )
    return p


def expand_workspaces(workdir: Path) -> tuple[str, ...]:
    """Every workspace directory (relative POSIX path, sorted), from the root globs.

    A match counts when it is a real directory inside the repository (no
    symlinked component), outside any ``node_modules`` or dot-directory, with
    a regular ``package.json``. A leading ``!`` excludes matches, as in Bun.

    Raises:
        BunWorkspaceError: a glob escapes the repository or is not a plain
            path, a matched directory is reached through a symlink, or there
            are more than :data:`MAX_WORKSPACES`.
    """
    base = workdir.resolve()
    pkg = read_json(workdir, ROOT_MANIFEST)
    include: set[str] = set()
    exclude: set[str] = set()
    for raw in workspace_patterns(pkg):
        negated = raw.strip().startswith("!")
        pattern = _clean_pattern(raw.strip()[1:] if negated else raw)
        for match in workdir.glob(pattern):
            rel = match.relative_to(workdir).as_posix()
            parts = PurePosixPath(rel).parts
            if any(part == NODE_MODULES or part.startswith(".") for part in parts):
                continue
            if not match.is_dir():
                continue
            if match.is_symlink() or match.resolve() != base / rel:
                raise BunWorkspaceError(
                    f"bun toolchain: workspace {rel!r} is reached through a symlink"
                )
            if not regular_file(workdir, f"{rel}/{ROOT_MANIFEST}"):
                continue
            (exclude if negated else include).add(rel)
            if len(include) > MAX_WORKSPACES:
                raise BunWorkspaceError(
                    f"bun toolchain: more than {MAX_WORKSPACES} workspaces match"
                )
    return tuple(sorted(include - exclude))


def manifests(workdir: Path, workspaces: tuple[str, ...]) -> tuple[str, ...]:
    """What decides the install: root manifest, lockfiles, each workspace's manifest."""
    return (ROOT_MANIFEST, *LOCKFILES, *(f"{ws}/{ROOT_MANIFEST}" for ws in workspaces))


def copy_manifests(workdir: Path, names: tuple[str, ...], dest: Path) -> None:
    """Copy the manifests that exist into *dest*, keeping their relative paths.

    Done on the host so the setup container needs no view of the worktree at
    all: it sees only these files. Symlinks are never followed.
    """
    for rel in names:
        if not regular_file(workdir, rel):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workdir / rel, target, follow_symlinks=False)


def declared_deps(pkg: dict) -> set[str]:
    """Package names a manifest depends on (not counting ``workspace:`` links)."""
    names: set[str] = set()
    for field in _DEP_MAPS:
        deps = pkg.get(field)
        if isinstance(deps, dict):
            names.update(n for n, spec in deps.items() if not str(spec).startswith("workspace:"))
    return names


def has_deps(pkg: dict) -> bool:
    """Whether Bun gives this workspace a ``node_modules`` (any dependency at all)."""
    return any(isinstance(pkg.get(f), dict) and pkg.get(f) for f in _DEP_MAPS)


def node_modules_dirs(env: Path, workspaces: tuple[str, ...]) -> tuple[str, ...]:
    """The ``node_modules`` directories a finished env holds, root first.

    Only real directories (no symlink) at exactly ``{ws}/node_modules``.
    """
    out = []
    for ws in ("", *workspaces):
        rel = f"{ws}/{NODE_MODULES}" if ws else NODE_MODULES
        d = env / rel
        if d.is_dir() and not d.is_symlink() and d.resolve() == env.resolve() / rel:
            out.append(rel)
    return tuple(out)


def ready_problems(env: Path, workspaces: tuple[str, ...], bun_version: str | None) -> list[str]:
    """Why an installed env must not be published (empty = ready).

    The E2B-style ready check: Bun ran (``bun --version`` printed a version),
    the root ``node_modules`` exists, and every workspace that declares
    dependencies can resolve them -- its own ``node_modules`` (isolated
    linker), or each declared package hoisted into the root one.
    """
    bad: list[str] = []
    if not bun_version or not re.match(r"^\d+\.\d+\.\d+", bun_version):
        bad.append("bun --version did not print a version")
    present = set(node_modules_dirs(env, workspaces))
    if NODE_MODULES not in present:
        bad.append("no root node_modules was installed")
        return bad
    for ws in workspaces:
        try:
            pkg = json.loads((env / ws / ROOT_MANIFEST).read_text())
        except (OSError, ValueError):
            bad.append(f"{ws}/{ROOT_MANIFEST} is missing from the env")
            continue
        if not isinstance(pkg, dict) or not has_deps(pkg) or f"{ws}/{NODE_MODULES}" in present:
            continue
        missing = [n for n in sorted(declared_deps(pkg)) if not (env / NODE_MODULES / n).exists()]
        if missing:
            bad.append(f"{ws}/{NODE_MODULES} was not installed (missing {', '.join(missing[:3])})")
    return bad
