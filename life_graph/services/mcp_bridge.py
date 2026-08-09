"""MCP-client bridge: connects to configured external MCP servers and
registers their tools into Life Graph's ToolRegistry, so personas can call
external MCP servers (browser automation, calendar, voice, etc.) the same
way they call any local tool.

life_graph/mcp_server.py is the SERVER side (exposes Life Graph's own tools
outward). This module is the CLIENT side — the two are independent,
unrelated directions; nothing here talks to mcp_server.py.
"""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

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

# Registry.execute()'s global default (15s) is tuned for fast local tools.
# Bridged tools are inherently doing real network I/O against a remote
# process — observed in production: real-world sites (financial/news pages
# with heavy ad-tech and anti-bot JS) routinely took well past 15s for a
# headless browser_navigate to settle, and every one of those got cut off
# by the registry's timeout before Playwright's own (60s default) action
# timeout ever got a chance to fire and return a clean, specific error.
# Set just above that so Playwright's own timeout resolves first.
BRIDGED_TOOL_TIMEOUT_SECONDS = 65


class _Connection:
    """Owns exactly one open transport+session, running its actual
    lifetime in a dedicated background task.

    Why a background task, not a plain `async with`: the underlying
    transports (stdio_client, streamable_http_client) are anyio
    TaskGroup-based, and anyio requires a cancel scope to be exited from
    the SAME task that entered it. A `_BridgedServer` needs to close an
    OLD connection from inside a RECONNECT triggered by a later, unrelated
    call — a different point in the call stack than where the old one was
    opened. Tried the straightforward version first (build the stack,
    `pop_all()` it out of an `async with` block, close it later via a
    plain method call) — it reliably raised "Attempted to exit cancel
    scope in a different task than it was entered in" the moment a second
    connection's close overlapped the first's, for BOTH stdio and HTTP
    transports. Running each connection's `async with` in its own task,
    and closing it by signaling that same task to fall through and exit
    its own block, is the actual fix — that satisfies anyio regardless of
    which other task calls close().
    """

    def __init__(self, server_config: dict) -> None:
        self._config = server_config
        self._ready = asyncio.Event()
        self._close_requested = asyncio.Event()
        self._task: asyncio.Task | None = None
        self.session: ClientSession | None = None
        self._error: BaseException | None = None

    async def start(self) -> ClientSession:
        self._task = asyncio.create_task(self._run())
        await self._ready.wait()
        if self._error is not None:
            raise self._error
        assert self.session is not None
        return self.session

    async def _run(self) -> None:
        try:
            async with AsyncExitStack() as stack:
                transport = self._config.get("transport", "stdio")
                if transport == "http":
                    read, write, _get_session_id = await stack.enter_async_context(
                        streamable_http_client(self._config["url"])
                    )
                else:
                    params = StdioServerParameters(
                        command=self._config["command"],
                        args=self._config.get("args", []),
                        env=self._config.get("env") or None,
                    )
                    read, write = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                self.session = session
                self._ready.set()
                await self._close_requested.wait()
        except Exception as exc:  # noqa: BLE001 - reported to start()'s waiter, not swallowed
            self._error = exc
            self._ready.set()

    async def close(self) -> None:
        self._close_requested.set()
        if self._task is not None:
            await self._task


class _BridgedServer:
    """Owns one configured server's live connection, with reconnect-on-
    failure. Every tool registered for this server shares ONE instance
    (via closures in _make_bridge_handler), so a single reconnect fixes
    every one of that server's tools, not just whichever call triggered it.

    Why this exists: a stdio subprocess dying is immediate and visible —
    the spawn itself fails synchronously, caught at connect time. An HTTP
    session (e.g. Playwright MCP, running as its own long-lived container)
    can be unilaterally terminated by the REMOTE server at any later point
    — an idle timeout, the browser context it was backing being closed —
    without this process crashing or even being notified until the next
    call. Observed in production: every mcp_playwright_* call started
    failing with "Session terminated" mid-session, and stayed broken until
    the app itself was manually restarted, because the bridge held one
    ClientSession for its entire lifetime with no way to detect or recover
    from the remote side dropping it.
    """

    def __init__(self, server_config: dict) -> None:
        self._config = server_config
        self._session: ClientSession | None = None
        self._conn: _Connection | None = None
        self._reconnect_lock = asyncio.Lock()

    async def open(self) -> ClientSession:
        """(Re)connect, replacing any existing session."""
        conn = _Connection(self._config)
        session = await conn.start()

        old_conn, self._conn = self._conn, conn
        self._session = session
        if old_conn is not None:
            await old_conn.close()
        return session

    async def call_tool(self, tool_name: str, **kwargs: Any):
        session = self._session
        if session is None:
            session = await self._reconnect(expected_current=None)
        try:
            return await session.call_tool(tool_name, arguments=kwargs)
        except Exception:
            logger.warning(
                "mcp_bridge: call to %r on server %r failed on the existing "
                "session, reconnecting and retrying once",
                tool_name,
                self._config.get("name"),
                exc_info=True,
            )
            session = await self._reconnect(expected_current=session)
            return await session.call_tool(tool_name, arguments=kwargs)

    async def _reconnect(self, expected_current: ClientSession | None) -> ClientSession:
        """Reconnect, coalescing concurrent callers that hit the same dead
        session — only the first one through the lock actually reconnects;
        the rest see self._session already replaced and reuse it."""
        async with self._reconnect_lock:
            if self._session is not expected_current:
                return self._session
            return await self.open()

    async def aclose(self) -> None:
        if self._conn is not None:
            await self._conn.close()


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
    caller (connect_all) is responsible for catching and isolating.

    Two transports: "stdio" (default — spawns server_config["command"] as a
    local subprocess of this process, e.g. `npx <mcp-server-package>`) or
    "http" (connects to server_config["url"], an already-running server —
    e.g. a separate container, used when the server needs its own resource
    isolation rather than running inside the app process, such as
    Playwright MCP's headless browser).

    The initial connect+list_tools happens before anything is registered
    on the caller's long-lived exit_stack — if either fails, the server
    object cleans up after itself immediately and the exception propagates
    to connect_all's per-server catch, rather than leaving a half-open
    connection for the caller's eventual (app-shutdown-time) teardown to
    discover.
    """
    name = server_config["name"]
    server = _BridgedServer(server_config)
    try:
        session = await server.open()
        result = await session.list_tools()
    except Exception:
        await server.aclose()
        raise

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
            handler=_make_bridge_handler(server, tool.name),
            timeout_seconds=BRIDGED_TOOL_TIMEOUT_SECONDS,
        )
        registered += 1
    logger.info("mcp_bridge: connected %r, registered %d tool(s)", name, registered)
    exit_stack.push_async_callback(server.aclose)
    return registered


def _make_bridge_handler(server: _BridgedServer, tool_name: str):
    """Returns an async handler matching ToolRegistry's expected signature
    for the given MCP tool on the given bridged server (transparently
    reconnects on a dead session — see _BridgedServer)."""

    async def handler(**kwargs: Any) -> str:
        result = await server.call_tool(tool_name, **kwargs)
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
