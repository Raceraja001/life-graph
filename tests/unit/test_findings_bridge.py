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
    text = 'prose\n```json\n[{"title":"A","detail":"d","urgency":"brief"}]\n```'
    assert parse_findings(text) == [{"title": "A", "detail": "d", "urgency": "brief"}]


def test_parse_findings_malformed_returns_empty_list():
    assert parse_findings("no json here at all") == []


def test_parse_findings_bad_urgency_coerced_to_brief():
    text = '[{"title":"A","detail":"d","urgency":"whenever"}]'
    assert parse_findings(text) == [{"title": "A", "detail": "d", "urgency": "brief"}]


def test_parse_findings_extracts_last_array_not_first():
    """Test that we extract the last [..] block, not from first [ to last ]."""
    text = 'see [1]\n[{"title":"A","detail":"found it","urgency":"brief"}]'
    assert parse_findings(text) == [{"title": "A", "detail": "found it", "urgency": "brief"}]


def test_parse_findings_array_with_no_valid_items_returns_empty():
    """Test that an array missing required 'title' field returns empty."""
    text = '[{"note":"x"},{"detail":"y"}]'
    assert parse_findings(text) == []


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
        "t1",
        "Later",
        body="fyi",
        priority="info",
        source_type="scout",
        source_id="11111111-1111-1111-1111-111111111111",
        deliver_at_brief=True,
    )
    # urgent finding: important + immediate push
    engine.create.assert_any_await(
        "t1",
        "Urgent",
        body="do x",
        priority="important",
        source_type="scout",
        source_id="11111111-1111-1111-1111-111111111111",
        deliver_at_brief=False,
    )
    push.send_to_tenant.assert_awaited_once_with("t1", "Urgent", "do x", "/m")


@pytest.mark.asyncio
async def test_process_result_malformed_falls_back_to_single_brief_digest():
    engine = AsyncMock()
    engine.create = AsyncMock(return_value={"id": "n1"})
    push = AsyncMock()
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    n = await bridge.process_result(
        "t1", "admin", "22222222-2222-2222-2222-222222222222", "free-text, no json"
    )

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


@pytest.mark.asyncio
async def test_process_result_array_with_no_valid_items_falls_back_to_digest():
    """Test that a non-empty array with no valid items creates a digest."""
    engine = AsyncMock()
    engine.create = AsyncMock(return_value={"id": "n1"})
    push = AsyncMock()
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    text = '[{"note":"x"},{"detail":"y"}]'  # Array exists but no "title" fields
    n = await bridge.process_result("t1", "scout", "44444444-4444-4444-4444-444444444444", text)

    assert n == 1
    args, kwargs = engine.create.call_args
    # Fallback digest should be created
    assert "scout update" in args[1]  # title is the second positional arg
    assert kwargs["deliver_at_brief"] is True
    push.send_to_tenant.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_result_notification_create_failure_continues_to_next():
    """Test that failure in engine.create for one finding doesn't drop others."""
    engine = AsyncMock()
    # First call raises, second succeeds
    engine.create = AsyncMock(
        side_effect=[
            Exception("notification create failed"),
            {"id": "n2"},
        ]
    )
    push = AsyncMock()
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    text = '[{"title":"A","detail":"a","urgency":"brief"},{"title":"B","detail":"b","urgency":"brief"}]'
    n = await bridge.process_result("t1", "scout", "55555555-5555-5555-5555-555555555555", text)

    # Should have created 1 notification (second one), first one raised but was caught
    assert n == 1
    assert engine.create.await_count == 2


@pytest.mark.asyncio
async def test_process_result_push_failure_is_swallowed():
    """Test that push.send_to_tenant failure is logged but doesn't affect count."""
    engine = AsyncMock()
    engine.create = AsyncMock(return_value={"id": "n1"})
    push = AsyncMock()
    push.send_to_tenant = AsyncMock(side_effect=Exception("push failed"))
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    text = '[{"title":"Urgent","detail":"do x","urgency":"now"}]'
    n = await bridge.process_result("t1", "scout", "66666666-6666-6666-6666-666666666666", text)

    # Notification should be created despite push failure
    assert n == 1
    engine.create.assert_awaited_once()
    # Push was attempted but exception was caught
    push.send_to_tenant.assert_awaited_once()
