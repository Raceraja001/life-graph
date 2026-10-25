"""Enforcement for the host-touching agent tools.

``run_command``, ``file_read`` and ``file_write`` act on the real host — the
same machine that holds the operator's SSH keys, cloud credentials and every
other project on disk. Their module docstrings previously described a
"personal tenant only" restriction, but no code implemented it: the only gate
was a persona's ``allowed_tools`` list, and any persona holding the tool held
it unconditionally. This module makes the documented controls real.

Three layers, in decreasing order of how much they can be trusted:

1. **Tenant gate** (a real boundary). Host tools refuse to run for any tenant
   outside ``LIFE_GRAPH_TOOL_PRIVILEGED_TENANTS``. This is the control that
   keeps a customer tenant from reaching the host at all.
2. **Filesystem root confinement** (a real boundary for the file_* tools).
   Paths are fully resolved — symlinks included — and must land inside an
   allowed root, so neither ``../`` nor a symlink planted by an earlier write
   can escape.
3. **Shell command denial** (defence in depth, NOT a boundary). A denylist
   over an arbitrary shell string is trivially bypassable by design —
   variable expansion, encoding, and a hundred spellings of the same command
   defeat it. It is here to catch obvious mistakes, and nothing more. The
   boundary for ``run_command`` is layer 1 plus the master switch; treat
   anything reachable through a shell as reachable.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id, has_tenant_context

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


class ToolDeniedError(Exception):
    """A host tool refused to act. The message is safe to return to the model."""


# Files/directories that stay off-limits even inside an allowed root.
# Reading these is credential theft; writing them is persistence.
_SENSITIVE_DIR_NAMES = frozenset({".ssh", ".aws", ".gnupg", ".kube", ".docker", ".config/gcloud"})
_SENSITIVE_FILE_NAMES = frozenset(
    {
        ".env",
        ".netrc",
        ".htpasswd",
        ".pgpass",
        "id_rsa",
        "id_ed25519",
        "credentials",
        ".credentials.json",  # Claude Code's OAuth token (~/.claude/)
        # Android signing and SDK settings: store and key passwords live here.
        "local.properties",
        "keystore.properties",
    }
)
# Key and keystore files, by extension.
_SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".jks", ".keystore"})
# .env, .env.local, .env.production, .envrc …: all carry secrets, except the
# committed templates that exist to be read.
_ENV_TEMPLATES = frozenset({".env.example", ".env.sample", ".env.template"})

# Writable nowhere, even inside an allowed root: each holds files that run
# code without anyone asking — git hooks and config, Claude Code hooks
# (.claude/settings.json), editor tasks (.vscode/tasks.json, .idea run
# configurations), CI workflows (.github/workflows), and direnv's .envrc,
# which the shell sources on cd. Security review 2026-10-24 (C1b).
_WRITE_PROTECTED_DIRS = frozenset({".git", ".claude", ".vscode", ".github", ".idea"})
_WRITE_PROTECTED_FILES = frozenset({".envrc"})

# Obvious destructive/privilege-escalating shapes. See layer 3 above: this is
# a mistake-catcher, not a security boundary.
_DENY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(sudo|doas|pkexec)\b"), "privilege escalation"),
    (re.compile(r"\bsu\s+(-|root|\w+)"), "privilege escalation"),
    (re.compile(r"\bmkfs(\.\w+)?\b"), "filesystem format"),
    (re.compile(r"\bdd\s+.*\bof=/dev/"), "raw device write"),
    (re.compile(r"\b(shutdown|reboot|halt|poweroff)\b"), "host power control"),
    (re.compile(r":\(\)\s*\{.*\|.*&\s*\}\s*;?\s*:"), "fork bomb"),
    (re.compile(r"\brm\b[^|;&]*\s-[a-zA-Z]*[rf][a-zA-Z]*\s+/\s*($|[;&|])"), "rm -rf /"),
    (re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z|k)?sh\b"), "pipe-to-shell"),
    (re.compile(r"\bchmod\s+(-\w+\s+)*777\s+/\s*($|[;&|])"), "chmod 777 /"),
    (re.compile(r"/etc/(passwd|shadow|sudoers)"), "system credential file"),
    (re.compile(r"\bhistory\s+-c\b|\bunset\s+HISTFILE\b"), "audit-trail tampering"),
)


def check_tenant(tool_name: str) -> None:
    """Raise :class:`ToolDeniedError` unless the calling tenant may use host tools.

    An empty ``tool_privileged_tenants`` disables the check, which is only
    reasonable for a single-tenant personal deployment. With no tenant
    context at all (background jobs, CLI) the call is allowed — those paths
    are already inside the trust boundary.
    """
    allowed = settings.tool_privileged_tenants_list
    if not allowed:
        return
    if not has_tenant_context():
        return
    tenant = get_current_tenant_id()
    if tenant not in allowed:
        logger.warning("%s denied for tenant %r (not privileged)", tool_name, tenant)
        raise ToolDeniedError(
            f"{tool_name} is not available to this tenant. Host tools are "
            f"restricted to the deployment's privileged tenants."
        )


# Per-task confinement. A driver running an agent in one worktree sets this to
# that worktree for the duration of the run: the tools then reach ONLY it —
# not the rest of tool_fs_roots, and not the live checkout the worktree was
# cut from. It also makes a worktree under /tmp reachable at all.
_task_roots: ContextVar[tuple[Path, ...] | None] = ContextVar("tool_task_roots", default=None)


@contextmanager
def confine_to(*paths: str | Path) -> Iterator[None]:
    """Confine host file tools to *paths* within this context (async-safe)."""
    token = _task_roots.set(tuple(Path(p).expanduser().resolve() for p in paths))
    try:
        yield
    finally:
        _task_roots.reset(token)


def _allowed_roots() -> list[Path]:
    scoped = _task_roots.get()
    if scoped is not None:
        return list(scoped)
    roots: list[Path] = []
    for raw in settings.tool_fs_roots_list:
        try:
            roots.append(Path(raw).expanduser().resolve())
        except OSError:  # unreadable/nonexistent root — ignore rather than crash
            logger.warning("tool_fs_roots: skipping unresolvable root %r", raw)
    return roots


def _is_sensitive(resolved: Path) -> str | None:
    # Compared case-folded: the repos live on /mnt/h (drvfs) and NTFS, where
    # ".ENV" or ".AWS/credentials" open the very same file (review 2026-10-25).
    parts = {p.casefold() for p in resolved.parts}
    posix = resolved.as_posix().casefold() + "/"
    for name in _SENSITIVE_DIR_NAMES:
        # ".config/gcloud" is two parts, never one; match it as a path segment.
        if name in parts or ("/" in name and f"/{name}/" in posix):
            return name
    name = resolved.name
    folded = name.casefold()
    if folded in _SENSITIVE_FILE_NAMES:
        return name
    if folded.startswith(".env") and folded not in _ENV_TEMPLATES:
        return name
    if resolved.suffix.lower() in _SENSITIVE_SUFFIXES:
        return name
    return None


def is_sensitive(path: Path) -> bool:
    """True when *path* (already resolved) names credential material."""
    return _is_sensitive(path) is not None


def resolve_in_roots(path: str, *, tool_name: str) -> Path:
    """Resolve *path* and confirm it lands inside an allowed root.

    Resolution is full — ``..`` segments and symlinks are followed before the
    containment check — so a symlink written by an earlier ``file_write``
    cannot be used to step outside a root on a later call.

    Raises:
        ToolDeniedError: the path escapes every root, or names a credential file.
    """
    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, RuntimeError) as exc:  # RuntimeError: symlink loop
        raise ToolDeniedError(f"Invalid path: {exc}") from exc

    roots = _allowed_roots()
    if not any(resolved == r or r in resolved.parents for r in roots):
        logger.warning("%s denied path outside roots: %s", tool_name, resolved)
        raise ToolDeniedError(
            f"Path is outside the permitted roots for {tool_name}. "
            f"Allowed roots: {', '.join(str(r) for r in roots)}"
        )

    if (hit := _is_sensitive(resolved)) is not None:
        logger.warning("%s denied sensitive path: %s (%s)", tool_name, resolved, hit)
        raise ToolDeniedError(f"Refusing to touch {hit!r} — credential material is off-limits.")

    return resolved


def check_writable(resolved: Path, *, tool_name: str) -> None:
    """Refuse writes to files that execute code (``_WRITE_PROTECTED_*``).

    ``.git/config`` and ``.git/hooks`` are code-execution surfaces: a
    ``core.fsmonitor`` or hook written there runs on the next ``git_status``
    or commit. ``.claude/``, ``.vscode/``, ``.idea/``, ``.github/`` and
    ``.envrc`` are the same thing for Claude Code, the editors, CI and direnv.
    Allowing a write into any of them would hand a persona that holds only
    file tools a shell. Reads stay allowed.
    """
    # Case-folded: on drvfs (/mnt/h) and NTFS ".GIT/hooks" is ".git/hooks".
    parts = {p.casefold() for p in resolved.parts}
    hit = next((d for d in _WRITE_PROTECTED_DIRS if d in parts), None)
    if hit is None and resolved.name.casefold() in _WRITE_PROTECTED_FILES:
        hit = resolved.name.casefold()
    if hit is not None:
        logger.warning("%s denied write inside %s: %s", tool_name, hit, resolved)
        where = f"inside a {hit} directory" if hit in _WRITE_PROTECTED_DIRS else f"to {hit}"
        raise ToolDeniedError(
            f"{tool_name} may not write {where} — it holds config and hooks that execute code."
        )


def check_command(command: str) -> None:
    """Raise :class:`ToolDeniedError` on an obviously destructive command.

    Defence in depth only — see layer 3 in the module docstring. Do not treat
    a pass here as evidence that a command is safe.
    """
    normalised = " ".join(command.strip().split())
    for pattern, reason in _DENY_PATTERNS:
        if pattern.search(normalised):
            logger.warning("run_command denied (%s): %s", reason, command[:200])
            raise ToolDeniedError(f"Command blocked: {reason}.")


def resolve_cwd(working_directory: str | None, *, tool_name: str) -> Path:
    """Resolve a working directory, confined to the allowed roots."""
    if working_directory is None:
        roots = _allowed_roots()
        home = Path(os.path.expanduser("~")).resolve()
        return home if any(home == r or r in home.parents for r in roots) else roots[0]
    return resolve_in_roots(working_directory, tool_name=tool_name)
