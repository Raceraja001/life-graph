"""Terminal tool — execute shell commands.

Provides the agent with the ability to run shell commands on the host system.

This module used to *claim* it was "restricted to the personal tenant" while
implementing no such check — the only gate was a persona's ``allowed_tools``
list. That restriction is now enforced in :mod:`life_graph.tools._guards`,
along with a master switch (``LIFE_GRAPH_TOOL_SHELL_ENABLED``) and working
directory confinement.

WARNING: this executes an arbitrary shell string. The command denylist below
is a mistake-catcher, NOT a security boundary — denylisting a shell cannot
work, and should not be reasoned about as though it does. The real controls
are the tenant gate and the master switch. Anything a shell can reach, a
persona holding this tool can reach.
"""

from __future__ import annotations

import asyncio
import logging

from life_graph.config import settings
from life_graph.tools._guards import (
    ToolDeniedError,
    check_command,
    check_tenant,
    resolve_cwd,
)
from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

# Safety: max output size and timeout
MAX_OUTPUT_CHARS = 8000
COMMAND_TIMEOUT_SECONDS = 30


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

    if not settings.tool_shell_enabled:
        return json.dumps({"error": "Shell execution is disabled on this deployment."})

    try:
        check_tenant("run_command")
        check_command(command)
        cwd = resolve_cwd(working_directory, tool_name="run_command")
    except ToolDeniedError as exc:
        return json.dumps({"error": str(exc)})

    logger.info("Executing command: %s (cwd=%s)", command, cwd)

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
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

    except TimeoutError:
        logger.warning("Command timed out after %ds: %s", COMMAND_TIMEOUT_SECONDS, command)
        return json.dumps({"error": f"Command timed out after {COMMAND_TIMEOUT_SECONDS}s"})
    except Exception as exc:
        logger.exception("Command execution failed: %s", exc)
        return json.dumps({"error": f"Execution failed: {exc}"})
