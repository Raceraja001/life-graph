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

import asyncio
import contextlib
import logging
import os
import signal
from collections.abc import Callable  # noqa: TC003

from life_graph.config import settings

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
    # Where the Claude CLI keeps its login and which endpoint it talks to:
    # locations, not credentials.
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
    "GEMINI_CLI_HOME",
    "ANTHROPIC_BASE_URL",
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


async def communicate_streaming(
    proc: asyncio.subprocess.Process,
    timeout: float,
    on_stdout_line: Callable[[str], None] | None,
) -> tuple[bytes, bytes]:
    """Like ``proc.communicate()`` under a timeout, but hands each stdout line
    to *on_stdout_line* as it arrives (the live session view, Stage 4).

    Raises TimeoutError like ``asyncio.wait_for``; the caller kills. A stand-in
    process without readable pipes (test fakes) just gets ``communicate()``.
    """
    stdout = getattr(proc, "stdout", None)
    if on_stdout_line is None or stdout is None or not hasattr(stdout, "readline"):
        return await asyncio.wait_for(proc.communicate(), timeout=timeout)
    out = bytearray()
    err = bytearray()

    async def read_out() -> None:
        while line := await stdout.readline():
            out.extend(line)
            try:
                on_stdout_line(line.decode(errors="replace"))
            except Exception:  # a broken viewer never breaks the run
                logger.debug("live line handler failed", exc_info=True)

    async def read_err() -> None:
        if proc.stderr is not None:
            while chunk := await proc.stderr.read(65536):
                err.extend(chunk)

    async def run() -> None:
        # A TaskGroup: if one reader fails, the other is cancelled too.
        async with asyncio.TaskGroup() as tg:
            tg.create_task(read_out())
            tg.create_task(read_err())
        await proc.wait()

    try:
        await asyncio.wait_for(run(), timeout=timeout)
    except* (ValueError, asyncio.LimitOverrunError, asyncio.IncompleteReadError) as group:
        # A line beyond the pipe's buffer limit (STREAM_LIMIT): report it as
        # a plain error; the caller kills and reaps the process.
        raise StreamReadError(str(group.exceptions[0])) from group.exceptions[0]
    return bytes(out), bytes(err)


class StreamReadError(RuntimeError):
    """Reading a CLI's output failed (e.g. a line over STREAM_LIMIT)."""


# Pipes for streamed CLIs read line by line: asyncio's default 64 KiB line
# limit is less than one stream-json event that carries a whole file read.
STREAM_LIMIT = 16 * 1024 * 1024
