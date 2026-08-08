"""One-shot, non-streaming, tool-free replies via the Claude CLI.

Mirrors drivers/claude_code.py's subprocess mechanics (binary resolution,
timeout handling, JSON parsing) but is a standalone caller for the model-
routing path (AgentOrchestrator selecting "claude-cli" as a persona's
model), not a Driver — this is unrelated to the claude_code driver's
task-dispatch use case, which is untouched by this module.

Despite being "tool-free" from Life Graph's own registry's point of view,
every call is still scoped the same way drivers/claude_code.py scopes its
own CLI invocations: `--permission-mode manual` plus an explicit
`--disallowedTools` denylist (reusing that module's `_DENIABLE_CLI_TOOLS` /
`_RESTRICTIVE_PERMISSION_MODE`), so a permissive host-level
`~/.claude/settings.json` can't silently hand an unattended reply more
capability than intended, and `cwd` is pinned to a scratch temp directory
rather than inheriting the FastAPI server's own working directory.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import tempfile
import time
from dataclasses import dataclass

from life_graph.config import settings
from life_graph.drivers.claude_code import _DENIABLE_CLI_TOOLS, _RESTRICTIVE_PERMISSION_MODE

logger = logging.getLogger(__name__)


@dataclass
class ClaudeCliResult:
    success: bool
    text: str
    error: str | None
    duration_ms: int


def _binary() -> str:
    return getattr(settings, "driver_claude_code_bin", "claude")


async def run_claude_cli(prompt: str, timeout: float = 60.0) -> ClaudeCliResult:
    """Shell out to the Claude CLI for a one-shot, non-streaming reply.

    No tool-calling — this is a plain text-in, text-out call. See
    docs/superpowers/specs/2026-08-08-claude-cli-model-routing-design.md
    for why that's a deliberate v1 scope limit, not an oversight.
    """
    start = time.monotonic()
    binary = _binary()

    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--permission-mode",
            _RESTRICTIVE_PERMISSION_MODE,
            "--disallowedTools",
            ",".join(_DENIABLE_CLI_TOOLS),
            cwd=tempfile.gettempdir(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return ClaudeCliResult(
            success=False,
            text="",
            error=f"claude_cli binary {binary!r} not found",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    except Exception as exc:
        logger.error("claude_cli_reply dispatch failed: %s", exc, exc_info=True)
        return ClaudeCliResult(
            success=False,
            text="",
            error=str(exc),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        with contextlib.suppress(Exception):
            # kill() can itself raise ProcessLookupError if the process
            # already exited in the race window right at the timeout
            # boundary — cover it with the same suppress as the drain below.
            proc.kill()
            await proc.communicate()
        return ClaudeCliResult(
            success=False,
            text="",
            error=f"claude_cli timed out after {timeout}s",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    try:
        duration = int((time.monotonic() - start) * 1000)
        data = _parse_output(out)
        is_error = bool(data.get("is_error", False))
        success = proc.returncode == 0 and not is_error

        if success:
            return ClaudeCliResult(
                success=True, text=str(data.get("result", "")), error=None, duration_ms=duration
            )
        return ClaudeCliResult(
            success=False,
            text="",
            error=str(data.get("result") or err.decode(errors="replace"))[:2000]
            or f"exit code {proc.returncode}",
            duration_ms=duration,
        )
    except Exception as exc:
        logger.error("claude_cli_reply result building failed: %s", exc, exc_info=True)
        return ClaudeCliResult(
            success=False,
            text="",
            error=str(exc),
            duration_ms=int((time.monotonic() - start) * 1000),
        )


def _parse_output(out: bytes) -> dict:
    """Parse the CLI's JSON stdout; tolerate plain-text output.

    Same tolerance as drivers/claude_code.py's _parse_output — kept as a
    separate copy here rather than importing that module's private
    staticmethod, since claude_code.py is driver-specific and this module
    is intentionally independent of it.
    """
    text = (out or b"").decode(errors="replace").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"result": data}
    except json.JSONDecodeError:
        return {"result": text}
