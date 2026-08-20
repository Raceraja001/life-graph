"""Filesystem tools — read and write files on the host system.

The original trust model here was "the LLM supplies an absolute path, no
sandboxing", justified on the grounds that a persona with ``run_command``
could achieve the same via shell redirection anyway, so ``file_write`` was
not a new privilege.

That argument holds only when a persona has *both* tools. It does not hold
for a persona granted ``file_write`` alone, and it never held for the
``file_read`` half — an unconfined read is credential exfiltration with no
shell involved. Both functions now resolve paths through
:mod:`life_graph.tools._guards`, which confines them to configured roots
(symlinks resolved before the check) and refuses credential material such as
``~/.ssh`` and ``.env`` outright.
"""

from __future__ import annotations

import json
import logging

from life_graph.tools._guards import ToolDeniedError, check_tenant, resolve_in_roots
from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

MAX_READ_CHARS = 20000
MAX_WRITE_CHARS = 200000


@tool(
    name="file_read",
    description=(
        "Read the contents of a file on the host system. Provide an "
        "absolute path. Returns the file's text content, truncated if "
        "very large."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to read.",
            },
        },
        "required": ["path"],
    },
)
async def file_read(path: str) -> str:
    """Read a file and return its text content as a JSON string."""
    try:
        check_tenant("file_read")
        p = resolve_in_roots(path, tool_name="file_read")
        if not p.is_file():
            return json.dumps({"error": f"Not a file: {path}"})
        content = p.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > MAX_READ_CHARS
        return json.dumps({"content": content[:MAX_READ_CHARS], "truncated": truncated})
    except ToolDeniedError as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        logger.warning("file_read failed for %s: %s", path, exc)
        return json.dumps({"error": f"Read failed: {exc}"})


@tool(
    name="file_write",
    description=(
        "Write text content to a file on the host system, creating it "
        "(and parent directories) if needed, or overwriting it if it "
        "already exists. Provide an absolute path."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to write.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write to the file.",
            },
        },
        "required": ["path", "content"],
    },
)
async def file_write(path: str, content: str) -> str:
    """Write text content to a file, creating parent directories as needed."""
    if len(content) > MAX_WRITE_CHARS:
        return json.dumps(
            {"error": (f"Content too large ({len(content)} chars, max {MAX_WRITE_CHARS})")}
        )
    try:
        check_tenant("file_write")
        p = resolve_in_roots(path, tool_name="file_write")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return json.dumps({"bytes_written": len(content.encode("utf-8")), "path": str(p)})
    except ToolDeniedError as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        logger.warning("file_write failed for %s: %s", path, exc)
        return json.dumps({"error": f"Write failed: {exc}"})
