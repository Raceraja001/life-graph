"""Unit pins for the 2026-10-22 session/intention review findings.

No database: the DB-backed half lives in
tests/integration/test_session_tenancy_and_links.py. This half covers the
wiring a database cannot see — what the MCP tools send, what the request
models accept, and that recall hands the session to the store.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastmcp import Client

from life_graph import mcp_server
from life_graph.core.tenant import tenant_scope


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


async def _call(tool: str, args: dict, payload=None):
    """Call an MCP tool with httpx patched; return (result, recorded calls)."""
    calls: list[tuple[str, str, dict]] = []

    def _make(verb):
        async def _do(self, url, **kw):
            calls.append((verb, url, kw))
            return _Resp(payload if payload is not None else {"data": {}})

        return _do

    patches = [patch.object(httpx.AsyncClient, v, _make(v)) for v in ("post", "get", "delete")]
    for p in patches:
        p.start()
    try:
        async with Client(mcp_server.mcp) as client:
            result = await client.call_tool(tool, args, raise_on_error=False)
    finally:
        for p in patches:
            p.stop()
    return result, calls


# ── 2. end_session: summary is accepted, outcome is sendable ─────────


def test_end_session_request_accepts_a_summary():
    from life_graph.api.sessions import EndSessionRequest

    body = EndSessionRequest.model_validate({"summary": "did things", "outcome": "success"})
    assert body.summary == "did things"
    assert body.outcome == "success"
    assert EndSessionRequest().summary is None


@pytest.mark.asyncio
async def test_mcp_end_session_sends_summary_and_outcome():
    sid = str(uuid.uuid4())
    _, calls = await _call(
        "end_session", {"session_id": sid, "summary": "done", "outcome": "failure"}
    )
    verb, url, kw = calls[-1]
    assert (verb, url) == ("post", f"/api/v1/sessions/{sid}/end")
    assert kw["json"] == {"summary": "done", "outcome": "failure"}


# ── 3. IntentionService.create sets the tenant ───────────────────────


@pytest.mark.asyncio
async def test_intention_create_sets_the_current_tenant():
    from life_graph.services.intentions import IntentionService

    added = []
    session = MagicMock()
    session.add = added.append
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with tenant_scope("acme"):
        await IntentionService(factory).create(content="x", trigger_type="time")
    assert added[0].tenant_id == "acme", "fell back to the column's 'legacy' default"


# ── 4. set_intention passes real triggers through ────────────────────


@pytest.mark.asyncio
async def test_set_intention_sends_trigger_time_and_context_match():
    _, calls = await _call(
        "set_intention",
        {
            "content": "Run migrations",
            "trigger_type": "time",
            "trigger_time": "2026-11-01T09:00:00+05:30",
        },
    )
    body = calls[-1][2]["json"]
    assert body["trigger_time"] == "2026-11-01T09:00:00+05:30"

    _, calls = await _call(
        "set_intention",
        {"content": "Check CI", "context_match": {"project": "life-graph"}},
    )
    body = calls[-1][2]["json"]
    assert body["trigger_type"] == "context"
    assert body["context_match"] == {"project": "life-graph"}
    assert "trigger_time" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["next tuesday", "2026-11-01T09:00:00"])
async def test_set_intention_rejects_unparseable_or_naive_times(bad):
    """No natural-language parsing, and no guessing a timezone."""
    result, calls = await _call(
        "set_intention", {"content": "x", "trigger_type": "time", "trigger_time": bad}
    )
    assert result.is_error
    assert not calls, "a bad trigger_time must not reach the API"


@pytest.mark.asyncio
async def test_set_intention_warns_when_nothing_can_fire_it():
    result, calls = await _call(
        "set_intention",
        {"content": "x", "trigger_condition": "when deploying"},
        payload={"data": {"id": "i1"}},
    )
    assert calls, "the old free-text-only call still goes through"
    out = json.loads(result.content[0].text)
    assert out["id"] == "i1"
    assert "never fire" in out["warning"]


# ── 5. session_id reaches the API from every MCP surface ─────────────


@pytest.mark.asyncio
async def test_mcp_tools_forward_session_id():
    sid = str(uuid.uuid4())

    _, calls = await _call("remember", {"content": "x", "session_id": sid})
    assert calls[-1][2]["json"]["properties"] == {"session_id": sid}

    _, calls = await _call("recall", {"context": {}, "session_id": sid})
    assert calls[-1][2]["json"]["session_id"] == sid

    _, calls = await _call("get_memories", {"ids": ["a"], "session_id": sid})
    assert calls[-1][2]["json"] == {"ids": ["a"], "session_id": sid}

    # Omitted stays omitted: the request shape is unchanged for old callers.
    _, calls = await _call("recall", {"context": {}})
    assert "session_id" not in calls[-1][2]["json"]
    _, calls = await _call("remember", {"content": "x"})
    assert "properties" not in calls[-1][2]["json"]


def test_recall_session_id_prefers_the_field_then_the_context():
    from life_graph.api.search import RecallRequest, _recall_session_id

    a, b = uuid.uuid4(), uuid.uuid4()
    assert _recall_session_id(RecallRequest(context={}, session_id=a)) == a
    assert _recall_session_id(RecallRequest(context={"session_id": str(b)}, session_id=a)) == a
    assert _recall_session_id(RecallRequest(context={"session_id": str(b)})) == b
    assert _recall_session_id(RecallRequest(context={"session_id": "junk"})) is None
    assert _recall_session_id(RecallRequest(context={})) is None


def _engine(store):
    from life_graph.services.recall import RecallEngine

    return RecallEngine(store, ranker=MagicMock(), context_builder=MagicMock())


@pytest.mark.asyncio
async def test_disclosure_in_a_session_links_the_memories_as_recalled(monkeypatch):
    from life_graph.services import recall

    monkeypatch.setattr(recall, "get_redis", lambda: None)
    store = SimpleNamespace(
        touch_many=AsyncMock(), link_recalls_to_session=AsyncMock(return_value=1)
    )
    sid, mid = uuid.uuid4(), uuid.uuid4()

    with tenant_scope("acme"):
        await _engine(store).record_disclosure([mid], session_id=sid)
    store.link_recalls_to_session.assert_awaited_once_with([mid], sid)

    store.link_recalls_to_session.reset_mock()
    with tenant_scope("acme"):
        await _engine(store).record_disclosure([mid])
    store.link_recalls_to_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failed_link_never_costs_the_caller_its_recall(monkeypatch):
    from life_graph.services import recall

    monkeypatch.setattr(recall, "get_redis", lambda: None)
    store = SimpleNamespace(
        touch_many=AsyncMock(),
        link_recalls_to_session=AsyncMock(side_effect=RuntimeError("db down")),
    )
    with tenant_scope("acme"):
        await _engine(store).record_disclosure([uuid.uuid4()], session_id=uuid.uuid4())
    store.touch_many.assert_awaited_once()
