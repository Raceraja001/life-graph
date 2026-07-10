"""Sandboxed command executor for autonomous actions.

Runs shell commands in restricted subprocess with timeout.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a command execution."""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False


class CommandExecutor:
    """Sandboxed command executor with timeout and restricted environment.

    Runs commands via asyncio subprocess with:
    - Configurable timeout (kills process on expiry)
    - Restricted PATH (only essential system binaries)
    - stdout/stderr capture
    - Duration tracking
    """

    # Only allow essential system paths
    SAFE_PATH = "/usr/bin:/usr/local/bin:/bin"

    async def execute(
        self,
        command: str,
        timeout_seconds: int = 60,
        cwd: str | None = None,
    ) -> ExecutionResult:
        """Execute a shell command with timeout.

        Args:
            command: Shell command to execute.
            timeout_seconds: Max seconds before kill.
            cwd: Working directory for the command.

        Returns:
            ExecutionResult with exit code, stdout, stderr, duration.
        """
        env = {
            "PATH": self.SAFE_PATH,
            "HOME": "/tmp",
            "LANG": "en_US.UTF-8",
        }

        t0 = time.monotonic()
        timed_out = False

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                timed_out = True
                logger.warning(
                    "Command timed out after %ds, killing: %s",
                    timeout_seconds,
                    command[:100],
                )
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass
                stdout_bytes = b""
                stderr_bytes = f"Process killed: timeout after {timeout_seconds}s".encode()

            duration_ms = (time.monotonic() - t0) * 1000
            exit_code = process.returncode or -1 if timed_out else process.returncode

            result = ExecutionResult(
                exit_code=exit_code,
                stdout=stdout_bytes.decode("utf-8", errors="replace")[:50_000],
                stderr=stderr_bytes.decode("utf-8", errors="replace")[:10_000],
                duration_ms=round(duration_ms, 1),
                timed_out=timed_out,
            )

            logger.info(
                "Command completed: exit=%d duration=%.1fms timed_out=%s cmd=%s",
                result.exit_code,
                result.duration_ms,
                result.timed_out,
                command[:80],
            )

            return result

        except Exception as e:
            duration_ms = (time.monotonic() - t0) * 1000
            logger.exception("Command execution failed: %s", command[:100])
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e)[:10_000],
                duration_ms=round(duration_ms, 1),
                timed_out=False,
            )
