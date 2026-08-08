import sys
from contextlib import AsyncExitStack
from pathlib import Path

import pytest

from life_graph.services import mcp_bridge
from life_graph.tools.registry import registry

FIXTURE = str(Path(__file__).parent.parent / "fixtures" / "reference_mcp_server.py")


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
