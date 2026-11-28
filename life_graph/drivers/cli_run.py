"""Running a subscription coding CLI (codex, gemini) on the host, and finding it.

Two jobs shared by ``drivers/codex.py`` and ``drivers/gemini.py``:

- :func:`run_cli` starts the CLI with the ``host_exec`` rules (allowlisted
  environment, its own session so a timeout kills the whole process group),
  writes the prompt to stdin and hands each stdout line to a callback as it
  arrives (the live session view).
- :func:`probe` answers "is it installed, which version, is it signed in"
  without reading or printing any credential, cached for a minute because the
  dispatcher asks on every selection.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import time
from collections.abc import Awaitable, Callable  # noqa: TC003
from dataclasses import asdict, dataclass
from pathlib import Path

from life_graph.drivers.host_exec import (
    STREAM_LIMIT,
    StreamReadError,
    communicate_streaming,
    host_driver_env,
    kill_process_group,
)

logger = logging.getLogger(__name__)

# Where npm-installed CLIs usually live when the service's PATH does not
# include them (race-app's agents/env.ts uses the same list).
WELL_KNOWN_BIN_DIRS = (".local/bin", ".local/node/bin", ".npm-global/bin", ".bun/bin")

PROBE_TTL_SECONDS = 60.0
PROBE_TIMEOUT_SECONDS = 20.0


@dataclass
class CliRun:
    """One finished (or killed) CLI process."""

    returncode: int | None
    out: bytes
    err: bytes
    timed_out: bool = False


def resolve_binary(binary: str) -> str | None:
    """The CLI's absolute path: as given, on PATH, or in a well-known bin dir."""
    if not binary:
        return None
    given = Path(binary).expanduser()
    if given.is_absolute() or os.sep in binary:
        return str(given) if given.is_file() else None
    found = shutil.which(binary)
    if found:
        return found
    home = Path.home()
    for sub in WELL_KNOWN_BIN_DIRS:
        candidate = home / sub / binary
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def cli_env(binary_path: str | None, extra: dict[str, str] | None = None) -> dict[str, str]:
    """The allowlisted host environment, with the CLI's own directory first on PATH.

    Both CLIs are node scripts (``#!/usr/bin/env node``); when the binary was
    found in a well-known directory rather than on PATH, its ``node`` sits
    next to it and must be found too.
    """
    env = host_driver_env(extra)
    if binary_path:
        bin_dir = str(Path(binary_path).parent)
        parts = [p for p in env.get("PATH", "").split(os.pathsep) if p]
        if bin_dir not in parts:
            env["PATH"] = os.pathsep.join([bin_dir, *parts])
    return env


async def run_cli(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    stdin: str | None = None,
    on_stdout_line: Callable[[str], None] | None = None,
) -> CliRun:
    """Run *argv* on the host; on timeout or cancel, kill its process group.

    Returns what was read up to the kill on a timeout (``timed_out=True``), so
    a run cut off after twenty minutes still leaves its steps. Raises
    FileNotFoundError when the binary does not exist and CancelledError when
    cancelled (after killing).
    """
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        env=env,
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
        limit=STREAM_LIMIT,
    )
    out = bytearray()

    def collect(line: str) -> None:
        out.extend(line.encode())
        if on_stdout_line is not None:
            on_stdout_line(line)

    async def feed() -> None:
        if stdin is None or proc.stdin is None:
            return
        try:
            proc.stdin.write(stdin.encode())
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the CLI exited before reading its prompt; its stderr says why
        finally:
            with contextlib.suppress(Exception):
                proc.stdin.close()

    writer = asyncio.ensure_future(feed())
    try:
        raw_out, err = await communicate_streaming(proc, timeout, collect)
    except TimeoutError:
        await kill_process_group(proc)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(proc.wait(), 5)
        writer.cancel()
        return CliRun(None, bytes(out), b"", timed_out=True)
    except (asyncio.CancelledError, StreamReadError, Exception):
        await kill_process_group(proc)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(proc.wait(), 5)
        writer.cancel()
        raise
    with contextlib.suppress(Exception):
        await writer
    # communicate_streaming returns its own buffer; a stand-in process
    # without readable pipes (test fakes) only fills that one.
    return CliRun(proc.returncode, raw_out or bytes(out), err)


# ── Detection ────────────────────────────────────────────────


@dataclass
class CliProbe:
    """What :func:`probe` found. ``logged_in`` is None when it cannot tell."""

    installed: bool
    binary: str | None = None
    version: str | None = None
    logged_in: bool | None = None
    hint: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


_cache: dict[tuple[str, str], tuple[float, CliProbe]] = {}


async def _short_run(argv: list[str], env: dict[str, str]) -> tuple[int | None, str]:
    """A quick local command's (exit code, first stdout line); (None, "") on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    except OSError:
        return None, ""
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), PROBE_TIMEOUT_SECONDS)
    except TimeoutError:
        await kill_process_group(proc)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(proc.wait(), 5)
        return None, ""
    first = next((ln.strip() for ln in out.decode(errors="replace").splitlines() if ln.strip()), "")
    return proc.returncode, first


LoginCheck = Callable[[str, dict[str, str]], Awaitable[bool | None]]


async def probe(
    name: str,
    binary: str,
    *,
    login_check: LoginCheck,
    login_hint: str,
    env_extra: dict[str, str] | None = None,
    force: bool = False,
) -> CliProbe:
    """Installed? Version (``<bin> --version``)? Signed in (*login_check*)?

    Cached per (name, binary) for :data:`PROBE_TTL_SECONDS`. Never raises.
    """
    key = (name, binary)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and not force and now - cached[0] < PROBE_TTL_SECONDS:
        return cached[1]
    path = resolve_binary(binary)
    if path is None:
        result = CliProbe(installed=False, hint=f"{binary!r} not found on PATH")
    else:
        env = cli_env(path, env_extra)
        code, version = await _short_run([path, "--version"], env)
        try:
            logged_in = await login_check(path, env)
        except Exception:  # noqa: BLE001 - detection is best-effort
            logger.debug("%s login check failed", name, exc_info=True)
            logged_in = None
        result = CliProbe(
            installed=code is not None,
            binary=path,
            version=version[:80] if code == 0 and version else None,
            logged_in=logged_in,
            hint=login_hint if logged_in is False else None,
        )
    _cache[key] = (now, result)
    return result


def clear_probe_cache() -> None:
    """Forget every probe (tests, and after the owner signs a CLI in)."""
    _cache.clear()


async def exit_code_login_check(
    argv_tail: list[str], path: str, env: dict[str, str]
) -> bool | None:
    """Signed in when ``<path> <argv_tail>`` exits 0; its output is discarded."""
    code, _ = await _short_run([path, *argv_tail], env)
    return None if code is None else code == 0
