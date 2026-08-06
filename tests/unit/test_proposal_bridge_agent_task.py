"""kind-aware ActionProposalBridge.process_result routing: agent_task vs command.

Task 5 (Phase B2): the bridge must recognize both proposal shapes returned by a
scheduled ambient-action persona — command items (``{"name","command",...}``,
today's ops contract) and agent_task items (``{"kind":"agent_task","name",
"instruction",...}``, the new cody-ready contract) — and route each to the
correct ``AutoFixRequest`` shape. Malformed/typeless items must still be
skipped with no execute (B1's default-safe behavior).
"""

from unittest.mock import AsyncMock

import pytest

from life_graph.services.action_proposal_bridge import ActionProposalBridge


@pytest.fixture
def bridge_with_mock_autofix():
    autofix = AsyncMock()
    autofix.process = AsyncMock(return_value=None)
    notifier = AsyncMock()
    bridge = ActionProposalBridge(autofix_service=autofix, notification_engine=notifier)
    return bridge, autofix


@pytest.mark.asyncio
async def test_bridge_routes_agent_task_proposal(bridge_with_mock_autofix):
    bridge, autofix = bridge_with_mock_autofix
    text = (
        'Here you go. [{"kind":"agent_task","name":"cody_fix","instruction":"Fix test X",'
        '"rationale":"broken","risk_hint":"moderate"}]'
    )
    n = await bridge.process_result("t1", "cody", "schedule:cody-ambient", text)
    assert n == 1
    req = autofix.process.call_args.args[1]
    assert req.kind == "agent_task"
    assert req.instruction == "Fix test X"
    assert req.command is None
    assert req.action_type == "cody_fix"


@pytest.mark.asyncio
async def test_bridge_still_routes_command_proposal(bridge_with_mock_autofix):
    bridge, autofix = bridge_with_mock_autofix
    text = '[{"name":"restart","command":"docker restart x","rationale":"stuck","risk_hint":"moderate"}]'
    n = await bridge.process_result("t1", "ops", "schedule:ops-ambient", text)
    assert n == 1
    req = autofix.process.call_args.args[1]
    assert req.kind == "command"
    assert req.command == "docker restart x"


@pytest.mark.asyncio
async def test_bridge_skips_item_missing_both_command_and_instruction(bridge_with_mock_autofix):
    bridge, autofix = bridge_with_mock_autofix
    text = '[{"name":"noop","rationale":"nothing"}]'
    n = await bridge.process_result("t1", "cody", "schedule:cody-ambient", text)
    assert n == 0
    autofix.process.assert_not_called()
