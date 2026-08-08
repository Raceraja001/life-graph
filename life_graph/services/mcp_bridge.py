"""MCP-client bridge: connects to configured external MCP servers and
registers their tools into Life Graph's ToolRegistry, so personas can call
external MCP servers (browser automation, calendar, voice, etc.) the same
way they call any local tool.

life_graph/mcp_server.py is the SERVER side (exposes Life Graph's own tools
outward). This module is the CLIENT side — the two are independent,
unrelated directions; nothing here talks to mcp_server.py.
"""

from __future__ import annotations

import logging
import re
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from life_graph.config import settings
from life_graph.tools.registry import registry

logger = logging.getLogger(__name__)

# OpenAI-shape function-calling names are constrained to this pattern.
# registry.get_tools() is one global list every persona/model shares, so a
# single bridged tool with an out-of-spec name (illegal characters, or too
# long once prefixed with "mcp_<server>_") could break tool-calling for
# every persona that can see it, not just calls to that one tool. Validate
# and skip rather than fail the whole server's connection over one bad name.
_VALID_TOOL_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


async def connect_all(exit_stack: AsyncExitStack) -> int:
    """Connect every server in settings.mcp_servers_list and register its
    tools. Never raises — each server's connection is independently
    isolated so one broken config never blocks the others or app startup.
    Returns the total number of tools registered."""
    registered = 0
    for server_config in settings.mcp_servers_list:
        try:
            registered += await _connect_one(exit_stack, server_config)
        except Exception:
            logger.warning(
                "mcp_bridge: failed to connect server %r",
                server_config.get("name", "<unnamed>"),
                exc_info=True,
            )
    return registered


async def _connect_one(exit_stack: AsyncExitStack, server_config: dict) -> int:
    """Connect one server, register its tools. Raises on failure — the
    caller (connect_all) is responsible for catching and isolating."""
    name = server_config["name"]
    params = StdioServerParameters(
        command=server_config["command"],
        args=server_config.get("args", []),
        env=server_config.get("env") or None,
    )
    read, write = await exit_stack.enter_async_context(stdio_client(params))
    session = await exit_stack.enter_async_context(ClientSession(read, write))
    await session.initialize()

    result = await session.list_tools()
    registered = 0
    for tool in result.tools:
        composed_name = f"mcp_{name}_{tool.name}"
        if not _VALID_TOOL_NAME.match(composed_name):
            logger.warning(
                "mcp_bridge: skipping tool %r on server %r — composed name %r is not a "
                "valid function-calling name",
                tool.name,
                name,
                composed_name,
            )
            continue
        registry.register(
            name=composed_name,
            description=tool.description or "",
            parameters_schema=tool.inputSchema,
            handler=_make_bridge_handler(session, tool.name),
        )
        registered += 1
    logger.info("mcp_bridge: connected %r, registered %d tool(s)", name, registered)
    return registered


def _make_bridge_handler(session: ClientSession, tool_name: str):
    """Returns an async handler matching ToolRegistry's expected signature
    for the given MCP tool on the given (already-connected) session."""

    async def handler(**kwargs: Any) -> str:
        result = await session.call_tool(tool_name, arguments=kwargs)
        parts: list[str] = []
        for block in result.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
            else:
                parts.append(f"[non-text content: {getattr(block, 'type', 'unknown')}]")
        joined_text = "\n".join(parts)
        if getattr(result, "isError", False):
            # The MCP server reported this call as an error. Raise rather
            # than returning the error text as if it were a successful
            # result — ToolRegistry.execute() already catches handler
            # exceptions and converts them into an error result, so raising
            # here is sufficient to keep downstream success/failure tracking
            # honest.
            raise RuntimeError(joined_text)
        return joined_text

    return handler
