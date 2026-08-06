from unittest.mock import AsyncMock

import pytest

from life_graph.services.findings_bridge import FindingsBridge, parse_findings


def test_parse_findings_extracts_trailing_json_array():
    text = 'Here is what I found.\n[{"title":"A","detail":"d1","urgency":"now"},{"title":"B","detail":"d2","urgency":"brief"}]'
    out = parse_findings(text)
    assert out == [
        {"title": "A", "detail": "d1", "urgency": "now"},
        {"title": "B", "detail": "d2", "urgency": "brief"},
    ]


def test_parse_findings_handles_fenced_json():
    text = "prose\n```json\n[{\"title\":\"A\",\"detail\":\"d\",\"urgency\":\"brief\"}]\n```"
    assert parse_findings(text) == [{"title": "A", "detail": "d", "urgency": "brief"}]


def test_parse_findings_malformed_returns_empty_list():
    assert parse_findings("no json here at all") == []


def test_parse_findings_bad_urgency_coerced_to_brief():
    text = '[{"title":"A","detail":"d","urgency":"whenever"}]'
    assert parse_findings(text) == [{"title": "A", "detail": "d", "urgency": "brief"}]


@pytest.mark.asyncio
async def test_process_result_creates_notifications_and_pushes_urgent():
    engine = AsyncMock()
    engine.create = AsyncMock(return_value={"id": "n1"})
    push = AsyncMock()
    push.send_to_tenant = AsyncMock(return_value=1)
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    text = '[{"title":"Urgent","detail":"do x","urgency":"now"},{"title":"Later","detail":"fyi","urgency":"brief"}]'
    n = await bridge.process_result("t1", "scout", "11111111-1111-1111-1111-111111111111", text)

    assert n == 2
    # brief finding: held for brief, no push
    engine.create.assert_any_await(
        "t1", "Later", body="fyi", priority="info",
        source_type="scout", source_id="11111111-1111-1111-1111-111111111111",
        deliver_at_brief=True,
    )
    # urgent finding: important + immediate push
    engine.create.assert_any_await(
        "t1", "Urgent", body="do x", priority="important",
        source_type="scout", source_id="11111111-1111-1111-1111-111111111111",
        deliver_at_brief=False,
    )
    push.send_to_tenant.assert_awaited_once_with("t1", "Urgent", "do x", "/m")


@pytest.mark.asyncio
async def test_process_result_malformed_falls_back_to_single_brief_digest():
    engine = AsyncMock()
    engine.create = AsyncMock(return_value={"id": "n1"})
    push = AsyncMock()
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    n = await bridge.process_result("t1", "admin", "22222222-2222-2222-2222-222222222222", "free-text, no json")

    assert n == 1
    args, kwargs = engine.create.call_args
    assert kwargs["deliver_at_brief"] is True
    assert kwargs["priority"] == "info"
    push.send_to_tenant.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_result_empty_array_creates_nothing():
    engine = AsyncMock()
    engine.create = AsyncMock()
    push = AsyncMock()
    bridge = FindingsBridge(notification_engine=engine, push_service=push)
    n = await bridge.process_result("t1", "scout", "33333333-3333-3333-3333-333333333333", "[]")
    assert n == 0
    engine.create.assert_not_awaited()
