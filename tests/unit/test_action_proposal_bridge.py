from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.services.action_proposal_bridge import AMBIENT_PROJECT_ID, ActionProposalBridge


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
