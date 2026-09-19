"""Per-account connector credentials, kept out of the repo, the DB and ``.env``.

One JSON file per account: ``<connector_secrets_dir>/<tenant>/<account_id>.json``
(default ``~/.config/life-graph/connectors``), mode 0600 inside a 0700
directory — the same treatment as the restic password. Shapes:

- ``{"method": "app_password", "password": "…"}``
- ``{"method": "oauth", "refresh_token": "…", "scopes": [...]}``
- ``{"method": "none", "url": "…"}`` (a calendar feed URL is itself the secret)

Nothing here logs a secret value. Right for one person on one machine; a
multi-user deployment would need an encrypted per-tenant store instead.
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

from life_graph.config import settings

_SAFE = re.compile(r"^[A-Za-z0-9._-]+$")

# The OAuth client (downloaded from Google Cloud, "Desktop app") lives beside
# the account secrets, not per account.
GOOGLE_CLIENT_FILE = "google-oauth-client.json"


class SecretError(Exception):
    """A secret is missing, unreadable, or too widely readable."""


def _root() -> Path:
    return Path(os.path.expanduser(settings.connector_secrets_dir))


def _check_part(value: str, what: str) -> str:
    if not value or not _SAFE.match(value):
        raise SecretError(f"invalid {what}: {value!r}")
    return value


def secret_path(tenant_id: str, account_id: str) -> Path:
    return _root() / _check_part(tenant_id, "tenant") / f"{_check_part(account_id, 'account')}.json"


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(path, 0o700)


def _read_private(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SecretError(f"no credential stored ({path.name})")
    if os.name == "posix":
        mode = path.stat().st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise SecretError(f"credential file {path} is readable by other users; chmod 600 it")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SecretError(f"credential file {path.name} is unreadable") from exc
    if not isinstance(data, dict):
        raise SecretError(f"credential file {path.name} is not a JSON object")
    return data


def _write_private(path: Path, data: dict[str, Any]) -> None:
    _ensure_private_dir(path.parent)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        if os.name == "posix":
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_secret(tenant_id: str, account_id: str) -> dict[str, Any]:
    return _read_private(secret_path(tenant_id, account_id))


def write_secret(tenant_id: str, account_id: str, data: dict[str, Any]) -> None:
    _write_private(secret_path(tenant_id, account_id), data)


def update_secret(tenant_id: str, account_id: str, **changes: Any) -> dict[str, Any]:
    data = read_secret(tenant_id, account_id)
    data.update(changes)
    write_secret(tenant_id, account_id, data)
    return data


def has_secret(tenant_id: str, account_id: str) -> bool:
    return secret_path(tenant_id, account_id).exists()


def delete_secret(tenant_id: str, account_id: str) -> None:
    secret_path(tenant_id, account_id).unlink(missing_ok=True)


def google_client() -> dict[str, str]:
    """The Google OAuth client id/secret (a "Desktop app" client JSON)."""
    data = _read_private(_root() / GOOGLE_CLIENT_FILE)
    inner = data.get("installed") or data.get("web") or data
    client_id, client_secret = inner.get("client_id"), inner.get("client_secret")
    if not client_id or not client_secret:
        raise SecretError(f"{GOOGLE_CLIENT_FILE} has no client_id/client_secret")
    return {"client_id": client_id, "client_secret": client_secret}


def has_google_client() -> bool:
    return (_root() / GOOGLE_CLIENT_FILE).exists()


def write_google_client(data: dict[str, Any]) -> None:
    _write_private(_root() / GOOGLE_CLIENT_FILE, data)
    google_client()  # validate the shape now, not at first sign-in
