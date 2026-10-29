"""The standard memory tools (docs/modular_memory_service_plan.md, 2B):
``recall(query, limit)``, ``remember(content, importance, tags)`` and
``get_profile(category)``, and the standalone entry point. No network: httpx's
verbs are patched, as in test_mcp_server.py."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest
from fastmcp import Client

from life_graph import mcp_server


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _patched(payload):
    calls: list[tuple[str, str, dict]] = []

    def _make(verb):
        async def _call(self, url, **kw):
            calls.append((verb, url, kw))
            return _Resp(payload)

        return _call

    return calls, [
        patch.object(httpx.AsyncClient, v, _make(v)) for v in ("get", "post", "delete", "patch")
    ]


async def _call(tool, args, payload=None):
    calls, patches = _patched(payload if payload is not None else {"data": {"ok": True}})
    for p in patches:
        p.start()
    try:
        async with Client(mcp_server.mcp) as client:
            result = await client.call_tool(tool, args)
    finally:
        for p in patches:
            p.stop()
    return calls, json.loads(result.content[0].text)


async def test_the_three_standard_tools_are_offered():
    async with Client(mcp_server.mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert {"recall", "remember", "get_profile"} <= set(tools)
    assert {"query", "limit"} <= set(tools["recall"].inputSchema["properties"])
    assert {"content", "importance", "tags"} <= set(tools["remember"].inputSchema["properties"])
    assert "category" in tools["get_profile"].inputSchema["properties"]


async def test_recall_with_a_query_is_a_judged_search():
    calls, _ = await _call("recall", {"query": "which phone do I use?", "limit": 3})
    assert [(v, u) for v, u, _ in calls] == [("post", "/api/v1/search/")]
    body = calls[0][2]["json"]
    assert body["query"] == "which phone do I use?"
    assert body["limit"] == 3 and body["search_mode"] == "judged"


async def test_recall_with_a_context_is_still_proactive_recall():
    calls, _ = await _call("recall", {"context": {"project": "life-graph"}})
    assert [(v, u) for v, u, _ in calls] == [("post", "/api/v1/search/recall")]
    assert calls[0][2]["json"]["context"] == {"project": "life-graph"}


async def test_recall_with_neither_says_so():
    calls, out = await _call("recall", {})
    assert calls == [] and "query or a context" in out["error"]


@pytest.mark.parametrize(
    ("category", "urls"),
    [
        ("all", ["/api/v1/identity/beliefs", "/api/v1/preferences/"]),
        ("beliefs", ["/api/v1/identity/beliefs"]),
        ("preferences", ["/api/v1/preferences/"]),
    ],
)
async def test_get_profile_reads_beliefs_and_preferences(category, urls):
    calls, out = await _call("get_profile", {"category": category}, {"data": ["x"]})
    assert [u for _, u, _ in calls] == urls
    assert set(out) == {u.split("/")[3] if "identity" not in u else "beliefs" for u in urls}


async def test_get_profile_refuses_an_unknown_category():
    calls, out = await _call("get_profile", {"category": "money"})
    assert calls == [] and "category must be one of" in out["error"]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], {"transport": "stdio", "show_banner": False}),
        (
            ["--transport", "sse", "--port", "9000"],
            {"transport": "sse", "host": "127.0.0.1", "port": 9000, "show_banner": False},
        ),
    ],
)
def test_the_standalone_entry_point_picks_a_transport(argv, expected):
    with patch.object(mcp_server.mcp, "run") as run:
        mcp_server.main(argv)
    run.assert_called_once_with(**expected)
