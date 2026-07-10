"""Terminal tool — execute shell commands.

Provides the agent with the ability to run shell commands on the
host system. Restricted to the personal tenant for safety.

WARNING: This tool executes arbitrary commands. Only enable for
trusted, personal-use tenants. Never expose to customer tenants.
"""

from __future__ import annotations

import asyncio
import logging
import os

from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

# Safety: max output size and timeout
MAX_OUTPUT_CHARS = 8000
COMMAND_TIMEOUT_SECONDS = 30

# Commands that should NEVER be run
BLOCKED_COMMANDS = frozenset([
    "rm -rf /",
    "format",
    "del /f /s /q",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
])


def _is_blocked(command: str) -> bool:
    """Check if a command matches any blocked pattern."""
    cmd_lower = command.strip().lower()
    return any(blocked in cmd_lower for blocked in BLOCKED_COMMANDS)


@tool(
    name="run_command",
    description=(
        "Execute a shell command on the host system and return the output. "
        "Use for: checking system status, running scripts, git operations, "
        "docker commands, file listing, etc. "
        "Commands time out after 30 seconds. "
        "DANGEROUS: Only use when explicitly asked by the user."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory for the command. Defaults to home directory.",
            },
        },
        "required": ["command"],
    },
)
async def run_command(command: str, working_directory: str | None = None) -> str:
    """Execute a shell command and return stdout + stderr.

    Args:
        command: The shell command to execute.
        working_directory: Optional working directory.

    Returns:
        JSON string with exit_code, stdout, stderr.
    """
    import json

    if _is_blocked(command):
        return json.dumps({"error": "Command blocked for safety reasons."})

    cwd = working_directory or os.path.expanduser("~")

    logger.info("Executing command: %s (cwd=%s)", command, cwd)

    try:
        # Use shell=True on Windows, subprocess on Unix
        if os.name == "nt":
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        else:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=COMMAND_TIMEOUT_SECONDS,
        )

        stdout_str = stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
        stderr_str = stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS]

        result = {
            "exit_code": process.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str,
        }

        logger.info(
            "Command completed: exit_code=%d, stdout=%d chars, stderr=%d chars",
            process.returncode,
            len(stdout_str),
            len(stderr_str),
        )

        return json.dumps(result)

    except asyncio.TimeoutError:
        logger.warning("Command timed out after %ds: %s", COMMAND_TIMEOUT_SECONDS, command)
        return json.dumps({"error": f"Command timed out after {COMMAND_TIMEOUT_SECONDS}s"})
    except Exception as exc:
        logger.exception("Command execution failed: %s", exc)
        return json.dumps({"error": f"Execution failed: {exc}"})
