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
from pathlib import Path

from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id, has_tenant_context

logger = logging.getLogger(__name__)


class ToolDeniedError(Exception):
    """A host tool refused to act. The message is safe to return to the model."""


# Files/directories that stay off-limits even inside an allowed root.
# Reading these is credential theft; writing them is persistence.
_SENSITIVE_DIR_NAMES = frozenset({".ssh", ".aws", ".gnupg", ".kube", ".docker", ".config/gcloud"})
_SENSITIVE_FILE_NAMES = frozenset(
    {".env", ".netrc", ".htpasswd", ".pgpass", "id_rsa", "id_ed25519", "credentials"}
)

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


def _allowed_roots() -> list[Path]:
    roots: list[Path] = []
    for raw in settings.tool_fs_roots_list:
        try:
            roots.append(Path(raw).expanduser().resolve())
        except OSError:  # unreadable/nonexistent root — ignore rather than crash
            logger.warning("tool_fs_roots: skipping unresolvable root %r", raw)
    return roots


def _is_sensitive(resolved: Path) -> str | None:
    parts = set(resolved.parts)
    for name in _SENSITIVE_DIR_NAMES:
        if name in parts:
            return name
    if resolved.name in _SENSITIVE_FILE_NAMES:
        return resolved.name
    return None


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
