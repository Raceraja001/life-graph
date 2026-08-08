import sys
from contextlib import AsyncExitStack
from pathlib import Path

import pytest

from life_graph.services import mcp_bridge
from life_graph.services.mcp_bridge import _make_bridge_handler
from life_graph.tools.registry import registry

FIXTURE = str(Path(__file__).parent.parent / "fixtures" / "reference_mcp_server.py")


class _FakeAsyncCM:
    """Minimal async-context-manager wrapper, for faking stdio_client()/
    ClientSession() without spawning a real subprocess transport."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc_info):
        return False


class _FakeBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _FakeCallToolResult:
    def __init__(self, text: str, is_error: bool = False):
        self.content = [_FakeBlock(text)]
        self.isError = is_error


class _FakeTool:
    def __init__(self, name: str, description: str = "", input_schema: dict | None = None):
        self.name = name
        self.description = description
        self.inputSchema = input_schema or {}


class _FakeListToolsResult:
    def __init__(self, tools):
        self.tools = tools


class _FakeSession:
    """Fakes the subset of ClientSession that mcp_bridge._connect_one uses."""

    def __init__(self, tools):
        self._tools = tools

    async def initialize(self):
        pass

    async def list_tools(self):
        return _FakeListToolsResult(self._tools)

    async def call_tool(self, name, arguments=None):
        return _FakeCallToolResult("unused")


@pytest.fixture(autouse=True)
def _clean_registry():
    # Bridge tests register real tool names into the global registry —
    # snapshot and restore so they don't leak into other test files.
    before = dict(registry._tools)
    yield
    registry._tools.clear()
    registry._tools.update(before)


@pytest.mark.asyncio
async def test_connect_all_registers_tools_from_reference_server():
    # connect_all reads servers from settings.mcp_servers_list directly, so
    # this calls the per-server helper with a config passed explicitly —
    # exercising the same connection/registration code without needing to
    # monkeypatch global settings for this test.
    server_config = {"name": "ref", "command": sys.executable, "args": [FIXTURE]}
    async with AsyncExitStack() as stack:
        registered = await mcp_bridge._connect_one(stack, server_config)

        assert registered == 2
        assert "mcp_ref_echo" in registry.tool_names
        assert "mcp_ref_add" in registry.tool_names


@pytest.mark.asyncio
async def test_bridged_tool_call_round_trips_through_registry():
    server_config = {"name": "ref", "command": sys.executable, "args": [FIXTURE]}
    async with AsyncExitStack() as stack:
        await mcp_bridge._connect_one(stack, server_config)
        result = await registry.execute("mcp_ref_echo", {"text": "hello"})
        assert result == "hello"


@pytest.mark.asyncio
async def test_bad_server_config_skipped_second_server_still_connects(monkeypatch):
    import json
    monkeypatch.setattr(
        "life_graph.config.settings.mcp_servers",
        json.dumps([
            {"name": "broken", "command": "this-binary-does-not-exist", "args": []},
            {"name": "ref", "command": sys.executable, "args": [FIXTURE]},
        ]),
        raising=False,
    )
    async with AsyncExitStack() as stack:
        count = await mcp_bridge.connect_all(stack)

    assert count == 2  # only the "ref" server's 2 tools — "broken" contributed 0
    assert "mcp_ref_echo" in registry.tool_names
    assert "mcp_broken_echo" not in registry.tool_names


@pytest.mark.asyncio
async def test_connect_all_returns_zero_with_no_servers_configured(monkeypatch):
    # Cheapest possible guard, at the bridge-module level rather than only
    # via the (DB-dependent, often-skipped) integration boot test: the app
    # boots exactly as today when zero servers are configured.
    monkeypatch.setattr("life_graph.config.settings.mcp_servers", "[]", raising=False)
    async with AsyncExitStack() as stack:
        count = await mcp_bridge.connect_all(stack)
    assert count == 0


@pytest.mark.asyncio
async def test_bridge_handler_raises_when_call_tool_result_is_error():
    # A failing external tool's isError result must not be returned as if
    # it were a successful result — the caller (ToolRegistry.execute) treats
    # a raised exception as failure and a returned string as success, so
    # swallowing isError here would corrupt downstream success/failure
    # tracking.
    session = _FakeSession(tools=[])

    async def _call_tool(name, arguments=None):
        return _FakeCallToolResult("boom: rate limited", is_error=True)

    session.call_tool = _call_tool
    handler = _make_bridge_handler(session, "some_tool")

    with pytest.raises(RuntimeError, match="boom: rate limited"):
        await handler()


@pytest.mark.asyncio
async def test_connect_one_skips_tool_with_invalid_composed_name(monkeypatch):
    # OpenAI-shape function names are constrained to ^[a-zA-Z0-9_-]{1,64}$.
    # A dotted name (or one that overflows 64 chars once prefixed with
    # "mcp_<server>_") must be skipped rather than registered, so one bad
    # bridged tool can't break tool-calling for every persona that shares
    # the global registry.
    good = _FakeTool("good_tool")
    bad_dotted = _FakeTool("bad.tool.name")
    bad_too_long = _FakeTool("x" * 70)
    fake_session = _FakeSession(tools=[good, bad_dotted, bad_too_long])

    monkeypatch.setattr(mcp_bridge, "stdio_client", lambda params: _FakeAsyncCM((None, None)))
    monkeypatch.setattr(
        mcp_bridge, "ClientSession", lambda read, write: _FakeAsyncCM(fake_session)
    )

    server_config = {"name": "srv", "command": "unused", "args": []}
    async with AsyncExitStack() as stack:
        registered = await mcp_bridge._connect_one(stack, server_config)

    assert registered == 1
    assert "mcp_srv_good_tool" in registry.tool_names
    assert "mcp_srv_bad.tool.name" not in registry.tool_names
    assert not any(n.startswith("mcp_srv_xxx") for n in registry.tool_names)
