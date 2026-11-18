"""What a coding CLI run directly on the host is given, and how it is stopped.

Used only when a driver is NOT in a container (``driver_claude_sandbox=none``,
and OpenCode always today). Two rules:

- **Environment is an allowlist.** The API process's own environment holds
  the database URL, provider keys and every ``LIFE_GRAPH_*`` setting; a
  prompt-injected agent with a shell would print them. A host-run CLI gets
  the variables a CLI needs to find itself and its own login (PATH, HOME,
  locale, XDG dirs, CA bundles, a corporate proxy) plus the names listed in
  ``driver_host_env_passthrough`` — never ``LIFE_GRAPH_*``.
- **Timeouts kill the process group.** ``proc.kill()`` reaches the CLI only;
  a test server or shell it started kept running. Each CLI starts in its own
  session, and a timeout signals the whole group.

This is hygiene, not a sandbox: a host-run CLI can still read any file this
user can. The shell is therefore denied on the host by default
(``driver_allow_host_shell``); the boundary is the task runtime.
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
from typing import TYPE_CHECKING

from life_graph.config import settings

if TYPE_CHECKING:
    import asyncio

logger = logging.getLogger(__name__)

BASE_ENV_KEYS: tuple[str, ...] = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "TERM",
    "TMPDIR",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "XDG_STATE_HOME",
    "XDG_RUNTIME_DIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
    "https_proxy",
    "http_proxy",
    "no_proxy",
)

_APP_PREFIX = "LIFE_GRAPH_"


def host_driver_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The whole environment for a host-run driver CLI."""
    names = list(BASE_ENV_KEYS)
    for name in settings.driver_host_env_passthrough_list:
        if name.upper().startswith(_APP_PREFIX):
            logger.warning("driver_host_env_passthrough: %s is app configuration; not passed", name)
            continue
        names.append(name)
    env = {k: os.environ[k] for k in names if k in os.environ}
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    if extra:
        env.update(extra)
    return env


async def kill_process_group(proc: asyncio.subprocess.Process) -> None:
    """SIGKILL *proc*'s whole process group (it was started with start_new_session)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, AttributeError, OSError):
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
