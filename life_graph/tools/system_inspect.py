"""Read-only system inspection tool for ambient action roles.

Exposes a FIXED allowlist of read-only inspection commands so a scheduled ops
role can investigate system state WITHOUT any write capability. There is no
arbitrary-command path here by design.
"""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from life_graph.tools.registry import tool

# check-name -> read-only command template. `{target}` is filled from a
# shlex-quoted `target` arg; templates without `{target}` ignore it.
_ALLOWED: dict[str, str] = {
    "disk": "df -h",
    "memory": "free -h",
    "uptime": "uptime",
    "docker_ps": "docker ps --format '{{.Names}}: {{.Status}}'",
    "docker_logs": "docker logs --tail 50 {target}",
    "systemctl_status": "systemctl status {target}",
    "git_status": "git status --porcelain --branch",
}
_TIMEOUT = 20


@tool(
    name="inspect_system",
    description=(
        "Read-only system inspection. `check` must be one of: "
        + ", ".join(sorted(_ALLOWED))
        + ". Optional `target` names a container/service where relevant. "
        "Cannot modify anything."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "check": {"type": "string", "description": "One of the allowed checks."},
            "target": {
                "type": "string",
                "description": "Container/service name, if the check needs one.",
            },
        },
        "required": ["check"],
    },
)
async def inspect_system(check: str, target: str = "") -> dict[str, Any]:
    """Run one allowlisted read-only inspection command.

    Args:
        check: Name of the allowlisted check to run (see ``_ALLOWED``).
        target: Optional container/service name for checks that need one.

    Returns:
        A dict with ``check``, ``output``, and ``exit_code``. Never raises —
        inspection failures are reported in the result, not the agent loop.
    """
    template = _ALLOWED.get(check)
    if template is None:
        return {"check": check, "output": f"'{check}' is not an allowed check.", "exit_code": 2}
    command = (
        template.replace("{target}", shlex.quote(target)) if "{target}" in template else template
    )
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT)
        return {
            "check": check,
            "output": out.decode("utf-8", "replace")[:8000],
            "exit_code": proc.returncode,
        }
    except TimeoutError:
        return {"check": check, "output": f"timeout after {_TIMEOUT}s", "exit_code": 124}
    except Exception as exc:  # inspection must never raise into the agent loop
        return {"check": check, "output": f"error: {exc}", "exit_code": 1}
