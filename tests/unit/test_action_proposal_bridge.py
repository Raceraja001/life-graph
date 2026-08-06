from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.core.events import Event, EventType
from life_graph.services.action_proposal_bridge import (
    AMBIENT_PROJECT_ID,
    ActionProposalBridge,
    ActionProposalHandler,
)


@pytest.mark.asyncio
async def test_each_proposal_becomes_an_autofix_request():
    autofix = AsyncMock()
    autofix.process = AsyncMock(return_value=MagicMock(routing="queued_for_approval"))
    notifier = AsyncMock()
    bridge = ActionProposalBridge(autofix_service=autofix, notification_engine=notifier)

    text = (
        '[{"name":"restart_worker","command":"docker restart life_graph_worker",'
        '"rationale":"unhealthy 2h","risk_hint":"moderate"}]'
    )
    n = await bridge.process_result("t1", "ops", "11111111-1111-1111-1111-111111111111", text)
    assert n == 1
    _, kwargs = autofix.process.call_args
    req = kwargs.get("request") or autofix.process.call_args.args[1]
    assert req.agent_id == "ops" and req.project_id == AMBIENT_PROJECT_ID
    assert req.command == "docker restart life_graph_worker"
    assert req.action_type == "restart_worker"


@pytest.mark.asyncio
async def test_malformed_json_creates_one_advisory_notification_no_execute():
    autofix = AsyncMock()
    autofix.process = AsyncMock()
    notifier = AsyncMock()
    notifier.create = AsyncMock()
    bridge = ActionProposalBridge(autofix_service=autofix, notification_engine=notifier)
    n = await bridge.process_result(
        "t1", "ops", "22222222-2222-2222-2222-222222222222", "no json here"
    )
    assert n == 0
    autofix.process.assert_not_awaited()
    notifier.create.assert_awaited_once()  # advisory "could not parse proposals"


@pytest.mark.asyncio
async def test_empty_array_dispatches_nothing():
    autofix = AsyncMock()
    autofix.process = AsyncMock()
    bridge = ActionProposalBridge(autofix_service=autofix, notification_engine=AsyncMock())
    assert (
        await bridge.process_result("t1", "ops", "33333333-3333-3333-3333-333333333333", "[]") == 0
    )
    autofix.process.assert_not_awaited()


def _fake_row(task_name: str, response_text: str):
    row = MagicMock()
    row.task_name = task_name
    row.result = {"response": response_text}
    return row


def _make_handler(monkeypatch, row) -> tuple[ActionProposalHandler, AsyncMock]:
    """Wire an ActionProposalHandler with a fake DB row and a mocked bridge."""
    handler = ActionProposalHandler()
    fake_bridge = AsyncMock()
    handler._bridge = fake_bridge  # bypass _get_bridge's real dependency wiring
    monkeypatch.setattr(
        "life_graph.services.action_proposal_bridge._load_task_row",
        AsyncMock(return_value=row),
    )
    return handler, fake_bridge


PROPOSAL_TEXT = '[{"name":"restart_worker","command":"docker restart w","rationale":"r"}]'


@pytest.mark.asyncio
async def test_scheduled_ops_run_dispatches_proposals(monkeypatch):
    """A run the scheduler ticker fired (task_name='schedule:<job>') is the
    only source propose-mode should ever act on."""
    row = _fake_row("schedule:nightly-ops-scan", PROPOSAL_TEXT)
    handler, fake_bridge = _make_handler(monkeypatch, row)

    event = Event(
        type=EventType.TASK_COMPLETED,
        payload={
            "agent_name": "ops",
            "tenant_id": "t1",
            "task_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    await handler._on_task_completed(event)

    fake_bridge.process_result.assert_awaited_once_with(
        "t1", "ops", "11111111-1111-1111-1111-111111111111", PROPOSAL_TEXT
    )


@pytest.mark.asyncio
async def test_interactive_ops_chat_does_not_dispatch(monkeypatch):
    """An interactive ops chat completion (task_name='chat:ops') must never
    be treated as a propose-mode source, even with a JSON array in the reply."""
    row = _fake_row("chat:ops", PROPOSAL_TEXT)
    handler, fake_bridge = _make_handler(monkeypatch, row)

    event = Event(
        type=EventType.TASK_COMPLETED,
        payload={
            "agent_name": "ops",
            "tenant_id": "t1",
            "task_id": "22222222-2222-2222-2222-222222222222",
        },
    )
    await handler._on_task_completed(event)

    fake_bridge.process_result.assert_not_awaited()
