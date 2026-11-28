"""The per-account CLI home directories life-graph manages.

Each account gets ``<driver_accounts_home_root>/<tenant>/<driver>/<account id>``,
created mode 0700. The CLI writes its own login there when the owner signs in
(race-app runs ``claude auth login`` / ``codex login`` / ``gemini`` in its PTY
with the home variable set); life-graph never reads what is inside. A path
from the database is used only when it still resolves under the root, so an
edited row cannot point a run at ``~/.ssh``.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from life_graph.config import settings

_SAFE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class HomeError(ValueError):
    """A home directory that is missing, unsafe or outside the root."""


def root() -> Path:
    """The configured root, absolute (it need not exist yet)."""
    return Path(settings.driver_accounts_home_root).expanduser().resolve()


def home_path(tenant_id: str, driver: str, account_id: object) -> Path:
    """Where an account's home lives (not created)."""
    parts = [tenant_id, driver, str(account_id)]
    if not all(_SAFE.fullmatch(p) and p not in (".", "..") for p in parts):
        raise HomeError("tenant, driver and account id must be plain names")
    return root().joinpath(*parts)


def ensure_home(tenant_id: str, driver: str, account_id: object) -> Path:
    """Create the home (0700, parents 0700) and return it."""
    path = home_path(tenant_id, driver, account_id)
    base = root()
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    current = base
    for part in path.relative_to(base).parts:
        current = current / part
        current.mkdir(exist_ok=True, mode=0o700)
        os.chmod(current, 0o700)
    return path


def checked_home(stored: str | None) -> Path:
    """A stored home, if it is still a private directory under the root.

    Raises HomeError when it is missing, a symlink, outside the root, or
    readable by group or others (the CLI's login would be).
    """
    if not stored:
        raise HomeError("account has no home directory")
    raw = Path(stored)
    if raw.is_symlink():
        raise HomeError("account home is a symlink")
    path = raw.resolve()
    if not path.is_relative_to(root()) or path == root():
        raise HomeError("account home is outside driver_accounts_home_root")
    if not path.is_dir():
        raise HomeError("account home does not exist")
    if path.stat().st_mode & 0o077:
        raise HomeError("account home is readable by others; chmod 700 it")
    return path


def remove_home(stored: str | None) -> bool:
    """Delete an account's home (its CLI login with it). False if nothing removed."""
    try:
        path = checked_home(stored)
    except HomeError:
        return False
    shutil.rmtree(path, ignore_errors=True)
    return True
