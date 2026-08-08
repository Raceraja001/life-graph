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
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from life_graph.config import settings
from life_graph.tools.registry import registry

logger = logging.getLogger(__name__)


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
    for tool in result.tools:
        registry.register(
            name=f"mcp_{name}_{tool.name}",
            description=tool.description or "",
            parameters_schema=tool.inputSchema,
            handler=_make_bridge_handler(session, tool.name),
        )
    logger.info("mcp_bridge: connected %r, registered %d tool(s)", name, len(result.tools))
    return len(result.tools)


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
        return "\n".join(parts)

    return handler
