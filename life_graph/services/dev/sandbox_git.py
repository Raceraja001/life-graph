"""Read-only git metadata for a task runtime container.

A dispatch's worktree is a linked ``git worktree``: its ``.git`` is a one-line
file, ``gitdir: <origin>/.git/worktrees/<name>``, an absolute HOST path. The
task runtime mounts only the worktree (at ``/work``), so inside the container
that pointer led nowhere and every ``git`` command failed ("not a git
repository"), seen on a live team run 2026-11-28.

What git needs to read a linked worktree is a small part of the common dir.
:func:`worktree_layout` finds it, and the task runtime mounts each piece
read-only at its own absolute path, so both the worktree's ``gitdir:`` pointer
and the worktree dir's ``commondir`` (``../..``) resolve unchanged:

- ``<common>/objects``, ``<common>/refs``, ``<common>/packed-refs``,
  ``<common>/HEAD``, and ``<common>/info`` / ``<common>/reftable`` if present;
- ``<common>/worktrees/<name>`` (this worktree's HEAD and index);
- ``<common>/config`` -- NOT the real one, which may carry tokens in remote
  URLs, credential helpers, includes, ``core.fsmonitor``/``core.hooksPath``
  commands. :func:`synthesize_config` writes a minimal one instead: the
  repository format version, ``bare = false`` and the extensions git needs to
  read the repository (``objectformat``, ``refstorage``). Nothing else.

Never mounted: the real config, ``hooks/``, ``logs/``, ``modules/``,
``lfs/``, other worktrees' dirs, anything else in the common dir. Everything
is read-only, so writes (``git add``, ``commit``, the index lock) fail inside
the container; Life Graph commits the worktree on the host.

The validator (``sandbox._git_bind_violations``) does not trust the binds a
spec lists: it derives the layout again from the workspace bind's own
``.git`` file with :func:`worktree_layout`, and re-parses the staged config
with :func:`config_violations`.

Pure ``pathlib`` (plus one ``git config`` read): imported by ``sandbox``.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

CONFIG_NAME = "config"
# Common-dir entries mounted when present (the worktree's own dir is added
# separately). Files and directories alike; each read-only.
COMMON_ENTRIES = ("objects", "refs", "packed-refs", "HEAD", "info", "reftable")
# Required for a usable repository.
_REQUIRED = ("objects", "refs", "HEAD")

# What the synthesized config may say, section -> key -> allowed values.
_ALLOWED_CONFIG: dict[str, dict[str, frozenset[str]]] = {
    "core": {
        "repositoryformatversion": frozenset({"0", "1"}),
        "bare": frozenset({"false"}),
    },
    "extensions": {
        "objectformat": frozenset({"sha1", "sha256"}),
        "refstorage": frozenset({"files", "reftable"}),
    },
}
_MAX_CONFIG_BYTES = 1024
_SECTION = re.compile(r"^\[([a-z]+)\]$")
_ENTRY = re.compile(r"^\t([a-z]+) = ([a-z0-9]+)$")


class GitLayoutError(ValueError):
    """The workspace is not a linked worktree whose metadata can be mounted safely."""


@dataclass(frozen=True)
class GitLayout:
    """Where one linked worktree's git metadata lives on the host (all resolved)."""

    worktree: Path
    gitdir: Path  # <common>/worktrees/<name>
    common: Path
    # Host paths mounted read-only at the same path (gitdir included).
    paths: tuple[Path, ...]

    @property
    def config_target(self) -> str:
        return str(self.common / CONFIG_NAME)


def _pointed_gitdir(dot_git: Path) -> Path:
    """The canonical directory a linked worktree's ``.git`` file points to."""
    if dot_git.is_symlink() or not dot_git.is_file():
        raise GitLayoutError(f"{dot_git} is not a linked worktree's .git file")
    try:
        content = dot_git.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise GitLayoutError(f"{dot_git} is unreadable: {exc}") from exc
    if not content.startswith("gitdir:") or "\n" in content:
        raise GitLayoutError(f"{dot_git} is not a single gitdir: line")
    raw = Path(content.removeprefix("gitdir:").strip())
    if not raw.is_absolute():
        raise GitLayoutError(f"{dot_git} points to a relative gitdir")
    gitdir = raw.resolve()
    if str(gitdir) != str(raw) or gitdir.is_symlink() or not gitdir.is_dir():
        raise GitLayoutError(f"gitdir {raw} is not a canonical existing directory")
    return gitdir


def worktree_layout(worktree: Path) -> GitLayout:
    """The git metadata a container needs to read *worktree*, or why not.

    Raises:
        GitLayoutError: *worktree* is not a linked worktree (no ``.git`` file,
            a ``.git`` directory or symlink, a pointer that is not
            ``<common>/worktrees/<name>``, a worktree dir that does not point
            back), or it uses per-worktree config (``config.worktree``, which
            could hold the same secrets as the real config).
    """
    wt = Path(worktree)
    dot_git = wt / ".git"
    gitdir = _pointed_gitdir(dot_git)
    if gitdir.parent.name != "worktrees":
        raise GitLayoutError(f"gitdir {gitdir} is not <common>/worktrees/<name>")
    common = gitdir.parent.parent
    try:
        commondir = (gitdir / "commondir").read_text(encoding="utf-8").strip()
        back = (gitdir / "gitdir").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise GitLayoutError(f"{gitdir} is missing commondir/gitdir: {exc}") from exc
    if (gitdir / commondir).resolve() != common:
        raise GitLayoutError(f"{gitdir}/commondir does not lead to {common}")
    if Path(back).resolve() != dot_git.resolve():
        raise GitLayoutError(f"{gitdir}/gitdir does not point back to {dot_git}")
    if (gitdir / "config.worktree").exists():
        raise GitLayoutError(f"{gitdir} has a per-worktree config; not mounted")
    for name in _REQUIRED:
        if not (common / name).exists():
            raise GitLayoutError(f"{common} has no {name}")
    paths: list[Path] = []
    for name in COMMON_ENTRIES:
        p = common / name
        if p.is_symlink():
            raise GitLayoutError(f"{p} is a symlink")
        if p.exists():
            paths.append(p)
    paths.append(gitdir)
    return GitLayout(worktree=wt.resolve(), gitdir=gitdir, common=common, paths=tuple(paths))


def _repo_format(common: Path) -> tuple[str, dict[str, str]]:
    """The real config's format version and the extensions we carry over.

    Read with ``git config --file`` (includes are not followed): never with
    the repository's own environment, never anything else.
    """
    try:
        res = subprocess.run(
            [
                "git",
                "config",
                "--file",
                str(common / CONFIG_NAME),
                "--no-includes",
                "--get-regexp",
                r"^(core\.repositoryformatversion|extensions\..*)$",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "0", {}
    version = "0"
    ext: dict[str, str] = {}
    for line in res.stdout.splitlines():
        key, _, value = line.partition(" ")
        key, value = key.lower(), value.strip().lower()
        if key == "core.repositoryformatversion" and value in ("0", "1"):
            version = value
        elif key.startswith("extensions."):
            name = key.removeprefix("extensions.")
            if value in _ALLOWED_CONFIG["extensions"].get(name, frozenset()):
                ext[name] = value
    if ext:
        version = "1"  # extensions are only read under format version 1
    return version, ext


def synthesize_config(common: Path) -> str:
    """A minimal config for *common*: format version, ``bare = false``, read extensions.

    No remotes, credential helpers, includes, hooks paths, fsmonitor, aliases
    or user identity: only what git needs to open the repository.
    """
    version, ext = _repo_format(common)
    lines = ["[core]", f"\trepositoryformatversion = {version}", "\tbare = false"]
    if ext:
        lines.append("[extensions]")
        lines += [f"\t{k} = {v}" for k, v in sorted(ext.items())]
    text = "\n".join(lines) + "\n"
    if bad := config_violations(text):  # never expected: the validator would refuse it
        raise GitLayoutError("; ".join(bad))
    return text


def config_violations(text: str) -> list[str]:
    """Why *text* is not a config :func:`synthesize_config` could have written."""
    if len(text.encode()) > _MAX_CONFIG_BYTES:
        return ["synthesized git config is too large"]
    bad: list[str] = []
    section: str | None = None
    seen: set[tuple[str, str]] = set()
    for n, line in enumerate(text.splitlines(), 1):
        if m := _SECTION.match(line):
            section = m.group(1)
            if section not in _ALLOWED_CONFIG:
                bad.append(f"git config line {n}: section [{section}] is not allowed")
            continue
        m = _ENTRY.match(line)
        if m is None or section is None:
            bad.append(f"git config line {n} is not a plain allowed entry")
            continue
        key, value = m.groups()
        allowed = _ALLOWED_CONFIG.get(section, {})
        if key not in allowed or value not in allowed[key]:
            bad.append(f"git config line {n}: {section}.{key} = {value} is not allowed")
        if (section, key) in seen:
            bad.append(f"git config line {n}: {section}.{key} repeated")
        seen.add((section, key))
    if ("core", "repositoryformatversion") not in seen:
        bad.append("git config has no core.repositoryformatversion")
    return bad
