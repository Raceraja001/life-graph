"""Hook configuration — env vars only, no import of ``life_graph.config``.

The hook runs as a short-lived subprocess of Claude Code, potentially with a
different working directory and without a ``.env``. It therefore reads plain
environment variables rather than the pydantic ``Settings`` object (which is
owned by the backend and would pull in far more than a hook needs).

Every knob has a working default, so an installed hook with zero configuration
posts to a local backend as tenant ``personal``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

# Defaults ---------------------------------------------------------------
DEFAULT_API_URL = "http://localhost:8080"
DEFAULT_TENANT_ID = "personal"

#: Ported verbatim from ``life_graph.services.tool_observation``. Duplicated as
#: a value (not an import) only because the hook must not import the service
#: layer; the test suite asserts the two stay equal.
DAILY_CAP = 500
LOW_SIGNAL_SAMPLE_RATE = 0.10

#: Hard timeouts. A dead backend must cost the developer ~nothing.
CAPTURE_TIMEOUT_SECONDS = 2.0
RECALL_TIMEOUT_SECONDS = 5.0

#: Truncation before anything leaves the machine. Prompts and tool results can
#: be enormous; the spine wants a signal, not a transcript.
MAX_CONTENT_CHARS = 8000

#: Capture surfaces. These are *trust discriminators* (see
#: ``life_graph.core.trust._SURFACE_TIER``), not free-text labels — do not
#: invent new ones, they would resolve to EXTERNAL and be prompt-fenced.
SURFACE_CLI = "cli"
SURFACE_TOOL_EXHAUST = "tool_exhaust"
SURFACE_ASSISTANT_MESSAGE = "assistant_message"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, TypeError, ValueError):
        return default


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class HookConfig:
    """Resolved hook settings for one invocation."""

    api_url: str
    tenant_id: str
    api_key: str | None
    state_dir: Path
    disabled: bool
    debug: bool
    capture_timeout: float
    recall_timeout: float
    daily_cap: int
    sample_rate: float
    max_content_chars: int
    #: Only sessions whose cwd is under one of these run the hook at all.
    #: Empty means every session (the historical behaviour).
    project_roots: tuple[str, ...] = ()

    @property
    def capture_url(self) -> str:
        """Absolute URL of the Capture Spine ingest endpoint."""
        return f"{self.api_url}/api/v1/capture/"

    @property
    def recall_url(self) -> str:
        """Absolute URL of the session-start proactive recall endpoint."""
        return f"{self.api_url}/api/v1/search/recall"

    @property
    def headers(self) -> dict[str, str]:
        """Request headers. ``X-Tenant-ID`` is mandatory (TenantMiddleware)."""
        headers = {
            "X-Tenant-ID": self.tenant_id,
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @property
    def spool_path(self) -> Path:
        """SQLite spool holding captures that could not be delivered."""
        return self.state_dir / "spool.db"

    @property
    def counter_path(self) -> Path:
        """JSON file holding the cross-process daily observation counter."""
        return self.state_dir / "daily_count.json"

    @property
    def log_path(self) -> Path:
        """Debug log (only written when ``LIFE_GRAPH_HOOK_DEBUG`` is set)."""
        return self.state_dir / "hook.log"


def _default_state_dir() -> Path:
    """Prefer the plugin's own data dir; fall back to ``~/.life-graph``.

    ``CLAUDE_PLUGIN_DATA`` is exported for plugin hooks and is the correct home
    for per-plugin state. A hook installed directly into ``settings.json`` gets
    no such variable, hence the home-directory fallback.
    """
    explicit = os.environ.get("LIFE_GRAPH_HOOK_STATE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return Path(plugin_data).expanduser() / "life-graph"
    return Path.home() / ".life-graph" / "claude-code"


def _file_config() -> dict:
    """Optional JSON config file; environment variables override it.

    The API key has to live somewhere the hook can read it. Putting it in
    Claude Code's ``settings.json`` ``env`` block would export it into every
    shell the agent runs, where the agent itself could read it; a 0600 file in
    the user's home keeps it out of the session environment. Read from
    ``LIFE_GRAPH_HOOK_CONFIG``, else ``~/.life-graph/claude-code/config.json``.
    Keys: ``api_url``, ``tenant_id``, ``api_key``, ``project_roots`` (list).
    """
    path = Path(
        os.environ.get("LIFE_GRAPH_HOOK_CONFIG")
        or Path.home() / ".life-graph" / "claude-code" / "config.json"
    ).expanduser()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


_WINDOWS_DRIVE_PATH = re.compile(r"^([A-Za-z]):[\\/](.*)$")


def normalize_path(path: str) -> str:
    r"""Map a Windows path to its WSL mount (``H:\x\y`` -> ``/mnt/h/x/y``).

    Windows Claude Code runs the hook through ``wsl.exe`` and hands it its own
    Windows ``cwd``; the hook, running in Linux, can only read the mount path.
    Other paths are returned unchanged.
    """
    m = _WINDOWS_DRIVE_PATH.match(path or "")
    if not m or os.name == "nt":
        return path
    rest = m.group(2).replace("\\", "/").rstrip("/")
    return f"/mnt/{m.group(1).lower()}/{rest}" if rest else f"/mnt/{m.group(1).lower()}"


def in_project_roots(cwd: str | None, roots: tuple[str, ...]) -> bool:
    """Whether a session in *cwd* is in scope. No roots configured = all are."""
    if not roots:
        return True
    if not cwd:
        return False
    here = normalize_path(cwd).rstrip("/").lower()
    for root in roots:
        base = normalize_path(root).rstrip("/").lower()
        if here == base or here.startswith(base + "/"):
            return True
    return False


def load_config() -> HookConfig:
    """Read hook settings from the environment, falling back to the config file."""
    file_cfg = _file_config()
    api_url = os.environ.get("LIFE_GRAPH_API_URL") or file_cfg.get("api_url") or DEFAULT_API_URL
    roots_env = os.environ.get("LIFE_GRAPH_HOOK_PROJECT_ROOTS")
    roots = (
        [r.strip() for r in roots_env.split(",") if r.strip()]
        if roots_env is not None
        else [str(r) for r in file_cfg.get("project_roots") or []]
    )
    return HookConfig(
        api_url=api_url.rstrip("/"),
        project_roots=tuple(roots),
        tenant_id=os.environ.get("LIFE_GRAPH_TENANT_ID")
        or file_cfg.get("tenant_id")
        or DEFAULT_TENANT_ID,
        api_key=os.environ.get("LIFE_GRAPH_API_KEY") or file_cfg.get("api_key") or None,
        state_dir=_default_state_dir(),
        disabled=_env_flag("LIFE_GRAPH_HOOK_DISABLED"),
        debug=_env_flag("LIFE_GRAPH_HOOK_DEBUG"),
        capture_timeout=_env_float("LIFE_GRAPH_HOOK_CAPTURE_TIMEOUT", CAPTURE_TIMEOUT_SECONDS),
        recall_timeout=_env_float("LIFE_GRAPH_HOOK_RECALL_TIMEOUT", RECALL_TIMEOUT_SECONDS),
        daily_cap=_env_int("LIFE_GRAPH_HOOK_DAILY_CAP", DAILY_CAP),
        sample_rate=_env_float("LIFE_GRAPH_HOOK_SAMPLE_RATE", LOW_SIGNAL_SAMPLE_RATE),
        max_content_chars=_env_int("LIFE_GRAPH_HOOK_MAX_CONTENT", MAX_CONTENT_CHARS),
    )
