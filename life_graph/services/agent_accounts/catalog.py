"""Which accounts each driver CLI supports, and the variables each may set.

Verified against the installed CLIs on 2026-11-27 (without signing in):

- Claude Code 2.1.328: ``CLAUDE_CONFIG_DIR`` (config + login home),
  ``ANTHROPIC_API_KEY``, Vertex via ``CLAUDE_CODE_USE_VERTEX`` /
  ``ANTHROPIC_VERTEX_PROJECT_ID`` / ``CLOUD_ML_REGION`` (race-app
  AGENT_CONNECTIONS.md §3, same version).
- codex-cli 0.172.0: ``CODEX_HOME`` (``--ignore-user-config``: "auth still
  uses CODEX_HOME"); ``CODEX_API_KEY`` for an API key in ``exec`` (the binary's
  own hint: "run `codex login` or set CODEX_API_KEY").
- gemini-cli 0.71.1: ``GEMINI_CLI_HOME`` replaces the home directory the CLI
  puts ``.gemini/`` under (``homedir()`` in its bundle); ``GEMINI_API_KEY``;
  Vertex via ``GOOGLE_GENAI_USE_VERTEXAI`` / ``GOOGLE_CLOUD_PROJECT`` /
  ``GOOGLE_CLOUD_LOCATION``.

An account's environment may contain only the names listed here for its
driver and kind (:func:`allowed_env_names`); anything else is refused when it
is built, so a stored property can never become ``LD_PRELOAD``.
"""

from __future__ import annotations

import re

DRIVERS: tuple[str, ...] = ("claude_code", "codex", "gemini", "opencode")
KINDS: tuple[str, ...] = ("subscription", "api_key", "vertex")

#: The variable that points each CLI at an account's own home.
HOME_ENV: dict[str, str] = {
    "claude_code": "CLAUDE_CONFIG_DIR",
    "codex": "CODEX_HOME",
    "gemini": "GEMINI_CLI_HOME",
}

#: The variable an API key is handed to the CLI in.
API_KEY_ENV: dict[str, str] = {
    "claude_code": "ANTHROPIC_API_KEY",
    "codex": "CODEX_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

#: The origin a driver's API key is stored for in the vault. The vault only
#: resolves a secret for an origin it was stored with, so a key handle
#: leaked elsewhere resolves to nothing.
API_ORIGIN: dict[str, str] = {
    "claude_code": "https://api.anthropic.com",
    "codex": "https://api.openai.com",
    "gemini": "https://generativelanguage.googleapis.com",
}

#: Vertex: (flag variable and value, project variable, region variable).
VERTEX_ENV: dict[str, tuple[tuple[str, str], str, str]] = {
    "claude_code": (
        ("CLAUDE_CODE_USE_VERTEX", "1"),
        "ANTHROPIC_VERTEX_PROJECT_ID",
        "CLOUD_ML_REGION",
    ),
    "gemini": (
        ("GOOGLE_GENAI_USE_VERTEXAI", "true"),
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
    ),
}

#: Kinds each driver supports. OpenCode is parked (config/drivers.py) and
#: its login location is unverified, so it has none yet.
DRIVER_KINDS: dict[str, tuple[str, ...]] = {
    "claude_code": ("subscription", "api_key", "vertex"),
    "codex": ("subscription", "api_key"),
    "gemini": ("subscription", "api_key", "vertex"),
    "opencode": (),
}

#: Every credential-bearing variable per driver. A subscription account's
#: run gets none of them, even when driver_host_env_passthrough lists one,
#: so a stray key cannot turn a subscription run into a metered one.
CREDENTIAL_ENV: dict[str, tuple[str, ...]] = {
    "claude_code": (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_BEDROCK",
        "ANTHROPIC_VERTEX_PROJECT_ID",
    ),
    "codex": ("CODEX_API_KEY", "OPENAI_API_KEY", "CODEX_ACCESS_TOKEN"),
    "gemini": (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_GENAI_USE_VERTEXAI",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ),
    "opencode": (),
}

#: How the owner signs an account's home in, on the host, in race-app's PTY.
LOGIN_COMMAND: dict[str, list[str]] = {
    "claude_code": ["claude", "auth", "login"],
    "codex": ["codex", "login"],
    "gemini": ["gemini"],
}

_NAME = re.compile(r"^[\w .·@()+\-]{1,60}$")
_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,61}[a-z0-9]$")
_REGION = re.compile(r"^[a-z0-9-]{2,40}$")


class AccountError(ValueError):
    """An account request that cannot be honoured (maps to HTTP 400)."""


def check_driver_kind(driver: str, kind: str) -> None:
    """Raise AccountError unless *driver* supports *kind*."""
    if driver not in DRIVERS:
        raise AccountError(f"unknown driver {driver!r}; one of {list(DRIVERS)}")
    if kind not in KINDS:
        raise AccountError(f"unknown kind {kind!r}; one of {list(KINDS)}")
    supported = DRIVER_KINDS.get(driver, ())
    if kind not in supported:
        if not supported:
            raise AccountError(f"{driver} accounts are not supported yet")
        raise AccountError(f"{driver} supports {list(supported)}, not {kind!r}")


def clean_name(name: str) -> str:
    """A display name: 1-60 characters of letters, digits and simple punctuation."""
    value = " ".join((name or "").split())
    if not _NAME.fullmatch(value):
        raise AccountError("name must be 1-60 letters, digits, spaces or . · @ ( ) + -")
    return value


def clean_properties(driver: str, kind: str, properties: dict | None) -> dict:
    """The non-secret settings an account may carry, validated; others dropped.

    Vertex needs ``project`` and ``region``. Any kind may set ``model``.
    """
    props = properties or {}
    out: dict = {}
    model = props.get("model")
    if model:
        if not isinstance(model, str) or not re.fullmatch(r"[\w.:@/\-]{1,100}", model):
            raise AccountError("model must be a model id")
        out["model"] = model
    if kind == "vertex":
        project, region = props.get("project"), props.get("region")
        if not isinstance(project, str) or not _PROJECT.fullmatch(project):
            raise AccountError("vertex needs properties.project (a GCP project id)")
        if not isinstance(region, str) or not _REGION.fullmatch(region):
            raise AccountError("vertex needs properties.region (e.g. us-east5)")
        out["project"], out["region"] = project, region
    return out


def allowed_env_names(driver: str, kind: str) -> frozenset[str]:
    """The only variable names an account of this driver and kind may set."""
    names = {HOME_ENV[driver]} if driver in HOME_ENV else set()
    if kind == "api_key" and driver in API_KEY_ENV:
        names.add(API_KEY_ENV[driver])
    if kind == "vertex" and driver in VERTEX_ENV:
        (flag, _), project, region = VERTEX_ENV[driver]
        names.update({flag, project, region})
    return frozenset(names)
