"""Config loading for the desktop capture agent.

Non-secret settings live in a TOML file; the API key is read from the OS
keyring so it never touches disk in plaintext.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import keyring

KEYRING_SERVICE = "life-graph-capture"


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


@dataclass
class HotkeyConfig:
    popup: str = "<ctrl>+<alt>+space"
    instant: str = "<ctrl>+<alt>+c"


@dataclass
class Config:
    backend_url: str
    tenant_id: str
    api_key: str = field(repr=False)
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    replay_interval_seconds: int = 30
    redact: bool = True


def default_config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "LifeGraph" / "config.toml"


def set_api_key(tenant_id: str, api_key: str, *, keyring_module=keyring) -> None:
    keyring_module.set_password(KEYRING_SERVICE, tenant_id, api_key)


def load_config(path=None, *, keyring_module=keyring) -> Config:
    path = Path(path) if path else default_config_path()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"Config file not found: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {path}: {e}") from e

    try:
        backend_url = data["backend_url"]
        tenant_id = data["tenant_id"]
    except KeyError as e:
        raise ConfigError(f"Missing required config key: {e}") from e

    api_key = keyring_module.get_password(KEYRING_SERVICE, tenant_id)
    if not api_key:
        raise ConfigError(
            f"No API key in keyring for tenant {tenant_id!r}. "
            f"Run: python -m clients.desktop.app --set-key"
        )

    hk = data.get("hotkeys", {})
    beh = data.get("behavior", {})
    return Config(
        backend_url=backend_url,
        tenant_id=tenant_id,
        api_key=api_key,
        hotkeys=HotkeyConfig(
            popup=hk.get("popup", "<ctrl>+<alt>+space"),
            instant=hk.get("instant", "<ctrl>+<alt>+c"),
        ),
        replay_interval_seconds=beh.get("replay_interval_seconds", 30),
        redact=beh.get("redact", True),
    )
