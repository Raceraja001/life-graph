"""The MCP server had no test at all, and it is the layer models actually read.

Everything here is about what reaches a model's context window, because that
is the only thing this file is for. Two defects it was written to catch:

* **Double emission.** Every tool was annotated ``-> dict[str, Any]``.
  FastMCP derives an output schema from that annotation and then sends the
  payload twice — once JSON-encoded as a text block in ``content``, once
  again as ``structured_content``. A model reads the text block; the
  duplicate is pure cost, measured at roughly double the bytes per call.
  ``ToolResult`` opts out of the derivation.

* **A docstring that lied about the ranker.** ``recall`` advertised
  "6-signal ranking" and listed six, but ``scoring/ranking.py`` blends seven
  — it omitted ``impact``. Tool docstrings are tokens sent to the model every
  session, and this one described a system that does not exist.

No network: httpx.AsyncClient's verbs are patched, so these exercise the
tool wiring rather than the API.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest
from fastmcp import Client

from life_graph import mcp_server
from life_graph.scoring import ranking


class _Resp:
    """Minimal stand-in for an httpx.Response."""

    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _patched(payload):
    """Patch every httpx verb the tools use to return *payload*."""
    calls: list[tuple[str, str, dict]] = []

    def _make(verb):
        async def _call(self, url, **kw):
            calls.append((verb, url, kw))
            return _Resp(payload)

        return _call

    ctx = [patch.object(httpx.AsyncClient, verb, _make(verb)) for verb in ("post", "get", "delete")]
    return ctx, calls


# ── Tool surface ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_expected_tools_are_registered():
    async with Client(mcp_server.mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert {"remember", "search", "recall", "ask", "get_memories", "forget"} <= names


@pytest.mark.asyncio
async def test_there_is_a_by_id_read_tool():
    """Progressive disclosure needs a second step, and there was none."""
    async with Client(mcp_server.mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert "get_memories" in tools, (
        "search/recall can return an index only if something can expand an id"
    )
    assert "ids" in tools["get_memories"].inputSchema["properties"]


# ── Double emission ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_tool_declares_an_output_schema():
    """An output schema is what makes FastMCP emit structured_content too."""
    async with Client(mcp_server.mcp) as client:
        offenders = [t.name for t in await client.list_tools() if t.outputSchema]
    assert not offenders, (
        f"{offenders} still derive an output schema, so every payload is sent "
        "twice — as content text and again as structured_content. Return "
        "ToolResult instead of an annotated dict."
    )


@pytest.mark.asyncio
async def test_a_payload_is_sent_once_not_twice():
    payload = {"data": {"identity": [{"id": "x", "content": "hello"}]}}
    ctxs, _ = _patched(payload)
    for c in ctxs:
        c.start()
    try:
        async with Client(mcp_server.mcp) as client:
            result = await client.call_tool("recall", {"context": {}})
    finally:
        for c in ctxs:
            c.stop()

    assert len(result.content) == 1, "one text block, not several"
    assert result.structured_content is None, (
        "structured_content duplicates the text block a model already read"
    )
    assert "hello" in result.content[0].text


@pytest.mark.asyncio
async def test_the_single_block_is_compact_json():
    """No pretty-printing: whitespace in a payload is tokens in a context."""
    payload = {"data": {"a": 1, "b": [1, 2]}}
    ctxs, _ = _patched(payload)
    for c in ctxs:
        c.start()
    try:
        async with Client(mcp_server.mcp) as client:
            result = await client.call_tool("recall", {"context": {}})
    finally:
        for c in ctxs:
            c.stop()

    text = result.content[0].text
    assert json.loads(text) == payload["data"]
    assert ", " not in text and ": " not in text


# ── Progressive disclosure wiring ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_memories_posts_the_ids_to_the_batch_endpoint():
    ctxs, calls = _patched({"data": []})
    for c in ctxs:
        c.start()
    try:
        async with Client(mcp_server.mcp) as client:
            await client.call_tool("get_memories", {"ids": ["id-1", "id-2"]})
    finally:
        for c in ctxs:
            c.stop()

    verb, url, kw = calls[-1]
    assert verb == "post"
    assert url == "/api/v1/memories/batch"
    assert kw["json"]["ids"] == ["id-1", "id-2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["search", "recall"])
async def test_index_only_defaults_on_and_can_be_turned_off(tool):
    """The MCP surface defaults to the compact index; the caller can opt out.

    The caller here is always a language model paying per token, so the index
    is the right default and `get_memories` is the expansion step. The HTTP API
    keeps defaulting to full objects — see
    test_progressive_disclosure.test_index_only_defaults_off_everywhere.
    """
    ctxs, calls = _patched({"data": {}})
    args = {"query": "q"} if tool == "search" else {"context": {}}
    for c in ctxs:
        c.start()
    try:
        async with Client(mcp_server.mcp) as client:
            await client.call_tool(tool, args)
            default_body = calls[-1][2]["json"]
            await client.call_tool(tool, {**args, "index_only": False})
            opted_out_body = calls[-1][2]["json"]
    finally:
        for c in ctxs:
            c.stop()

    assert default_body["index_only"] is True
    assert opted_out_body["index_only"] is False, "an explicit false must win"


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        (None, True),
        ("true", True),
        ("1", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("off", False),
        (" False ", False),
    ],
)
def test_index_only_default_is_env_overridable(monkeypatch, env, expected):
    """A deployment that wants the old full-object behaviour can have it back.

    Read at import, so this reloads the module rather than poking the constant.
    """
    import importlib

    if env is None:
        monkeypatch.delenv("LIFE_GRAPH_MCP_INDEX_ONLY_DEFAULT", raising=False)
    else:
        monkeypatch.setenv("LIFE_GRAPH_MCP_INDEX_ONLY_DEFAULT", env)
    try:
        reloaded = importlib.reload(mcp_server)
        assert reloaded.INDEX_ONLY_DEFAULT is expected
    finally:
        monkeypatch.delenv("LIFE_GRAPH_MCP_INDEX_ONLY_DEFAULT", raising=False)
        importlib.reload(mcp_server)


# ── Tenant scoping ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_every_request_carries_a_tenant_header():
    ctxs, calls = _patched({"data": []})
    for c in ctxs:
        c.start()
    try:
        async with Client(mcp_server.mcp) as client:
            await client.call_tool("get_memories", {"ids": ["a"], "tenant_id": "acme"})
    finally:
        for c in ctxs:
            c.stop()

    assert calls[-1][2]["headers"]["X-Tenant-ID"] == "acme"


def test_headers_fall_back_to_the_default_tenant():
    assert mcp_server._headers()["X-Tenant-ID"] == mcp_server.DEFAULT_TENANT


# ── The docstring is part of the payload ──────────────────────────────


@pytest.mark.asyncio
async def test_the_recall_docstring_names_every_signal_the_ranker_uses():
    """A tool description is sent to the model every session; it must be true."""
    async with Client(mcp_server.mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    description = (tools["recall"].description or "").lower()

    assert "6-signal" not in description, "the ranker blends seven signals, not six"
    assert f"{len(ranking._SIGNAL_WEIGHTS)}-signal" in description
    missing = [s for s in ranking._SIGNAL_WEIGHTS if s not in description]
    assert not missing, f"recall's docstring does not mention {missing}, which the ranker weights"
