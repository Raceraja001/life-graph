# tests/integration/test_ambient_event_wiring.py
"""Real-event integration test for the ambient advisory findings-bridge wiring.

Every other findings-bridge test (unit and the "end-to-end" integration test)
calls `FindingsBridge.process_result` or `FindingsBridgeHandler._on_task_completed`
directly — the boundary the feature actually depends on, the real `event_bus`
delivering a TASK_COMPLETED event to the subscribed handler, is never exercised.
This test drives that real path: `findings_bridge_handler.subscribe()` registers
with the process-global `event_bus`, then `event_bus.emit(...)` is awaited and
must reach `_on_task_completed` -> the advisory-agent gate -> `process_result`.

No Postgres needed: the only DB touchpoint (`_load_task_result`) is patched.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from life_graph.core.events import EventType, event_bus
from life_graph.services import findings_bridge as fb
from life_graph.services.findings_bridge import FindingsBridge, findings_bridge_handler

CANNED_RESULT = (
    "Scouted your watch-list topics.\n"
    '[{"title":"pgvector 0.9 HNSW index","detail":"faster recall, worth a look",'
    '"urgency":"brief"},'
    '{"title":"TLS cert expires in 3 days","detail":"renew before it lapses",'
    '"urgency":"now"}]'
)


@pytest.mark.asyncio
async def test_task_completed_event_reaches_bridge_for_advisory_agent():
    """Real emit() -> subscribed handler -> gate -> process_result, for scout."""
    engine = AsyncMock()
    engine.create = AsyncMock(return_value={"id": "n1"})
    push = AsyncMock()
    push.send_to_tenant = AsyncMock(return_value=1)
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    # Process-global singleton: point its bridge at our mocks so assertions
    # observe only this test's wiring, not whatever _get_bridge() would build.
    findings_bridge_handler._bridge = bridge
    findings_bridge_handler.subscribe()  # idempotent — guarded by _subscribed

    task_id = str(uuid.uuid4())
    with patch.object(fb, "_load_task_result", AsyncMock(return_value=CANNED_RESULT)):
        await event_bus.emit(
            EventType.TASK_COMPLETED,
            {"task_id": task_id, "tenant_id": "t1", "agent_name": "scout", "token_usage": {}},
        )

    # One "brief" + one "now" finding -> two notifications created.
    assert engine.create.await_count == 2
    # The "now" finding pushes immediately; the "brief" one does not.
    push.send_to_tenant.assert_awaited_once_with(
        "t1", "TLS cert expires in 3 days", "renew before it lapses", "/m"
    )


@pytest.mark.asyncio
async def test_task_completed_event_ignores_non_advisory_agent():
    """The same real event path must NOT invoke process_result for e.g. 'cody'."""
    engine = AsyncMock()
    engine.create = AsyncMock(return_value={"id": "n1"})
    push = AsyncMock()
    push.send_to_tenant = AsyncMock(return_value=1)
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    findings_bridge_handler._bridge = bridge
    findings_bridge_handler.subscribe()

    task_id = str(uuid.uuid4())
    with patch.object(fb, "_load_task_result", AsyncMock(return_value=CANNED_RESULT)):
        await event_bus.emit(
            EventType.TASK_COMPLETED,
            {"task_id": task_id, "tenant_id": "t1", "agent_name": "cody", "token_usage": {}},
        )

    engine.create.assert_not_awaited()
    push.send_to_tenant.assert_not_awaited()
