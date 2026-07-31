"""Unit tests for AgentOrchestrator's tool-execution enforcement.

Task 3 of the personal-roles work filters which tools are *advertised*
to the LLM based on a persona's allowed_tools. That's advisory only
until the executor re-checks the model's tool_call against the same
allowed set — otherwise a persona could still invoke a disallowed
tool (e.g. a restricted persona invoking delegate_to_persona) simply
because the model emitted a tool_call for it, such as via prompt
injection in ingested content.

These tests mock litellm.acompletion's streaming response to emit a
tool_call for a tool that was NOT included in the ``tools`` passed to
``AgentOrchestrator.run`` and assert the registry is never asked to
execute it — the loop instead returns a "not permitted" tool result
and continues.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from life_graph.agents.orchestrator import AgentOrchestrator


def _delta(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _tool_call(index, id_, name, arguments):
    return SimpleNamespace(
        index=index,
        id=id_,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


async def _stream(chunks):
    for chunk in chunks:
        yield SimpleNamespace(choices=[SimpleNamespace(delta=chunk)])


def _tool_call_response(tool_name: str, tool_id: str = "call_1"):
    """A one-shot streaming response emitting a single tool call."""
    return _stream(
        [
            _delta(
                tool_calls=[_tool_call(0, tool_id, tool_name, "{}")],
            ),
        ]
    )


def _final_text_response(text: str = "done"):
    """A one-shot streaming response with plain text, no tool calls."""
    return _stream([_delta(content=text)])


async def _collect_events(agen):
    events = []
    async for event_str in agen:
        assert event_str.startswith("data: ")
        events.append(json.loads(event_str.removeprefix("data: ").strip()))
    return events


class TestDisallowedToolCallIsNotExecuted:
    """The model emitting a tool_call outside the advertised set must
    not reach registry.execute — the loop must degrade gracefully."""

    @pytest.mark.asyncio
    async def test_disallowed_tool_call_is_blocked_not_executed(self):
        orchestrator = AgentOrchestrator(model="test-model")

        # Only "get_current_datetime" is advertised for this run — the
        # model tries to call "terminal" anyway.
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_datetime",
                    "description": "d",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        with (
            patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion,
            patch(
                "life_graph.agents.orchestrator.registry.execute",
                new_callable=AsyncMock,
            ) as mock_execute,
        ):
            mock_acompletion.side_effect = [
                _tool_call_response("terminal"),
                _final_text_response(),
            ]

            events = await _collect_events(
                orchestrator.run(
                    messages=[{"role": "user", "content": "rm -rf /"}],
                    tools=tools,
                )
            )

        mock_execute.assert_not_called()

        tool_results = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_results) == 1
        result = json.loads(tool_results[0]["result"])
        assert "not permitted" in result["error"]
        assert "terminal" in result["error"]

    @pytest.mark.asyncio
    async def test_restricted_persona_cannot_execute_delegate_to_persona(self):
        """A scout/admin-like persona (no delegate_to_persona in its
        advertised tools) must not be able to execute it even if the
        model emits the tool_call."""
        orchestrator = AgentOrchestrator(model="test-model")

        # Mirrors scout/admin's allowed_tools — delegate_to_persona is
        # intentionally absent.
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "memory_search",
                    "description": "d",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        with (
            patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion,
            patch(
                "life_graph.agents.orchestrator.registry.execute",
                new_callable=AsyncMock,
            ) as mock_execute,
        ):
            mock_acompletion.side_effect = [
                _tool_call_response("delegate_to_persona"),
                _final_text_response(),
            ]

            events = await _collect_events(
                orchestrator.run(
                    messages=[{"role": "user", "content": "escalate this to cody"}],
                    tools=tools,
                )
            )

        mock_execute.assert_not_called()

        tool_results = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_results) == 1
        result = json.loads(tool_results[0]["result"])
        assert "not permitted" in result["error"]
        assert "delegate_to_persona" in result["error"]

    @pytest.mark.asyncio
    async def test_allowed_tool_call_still_executes_normally(self):
        """Sanity check: an allowed tool call is unaffected by the
        enforcement check."""
        orchestrator = AgentOrchestrator(model="test-model")

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_datetime",
                    "description": "d",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        with (
            patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion,
            patch(
                "life_graph.agents.orchestrator.registry.execute",
                new_callable=AsyncMock,
            ) as mock_execute,
        ):
            mock_execute.return_value = json.dumps({"now": "2026-07-31T00:00:00Z"})
            mock_acompletion.side_effect = [
                _tool_call_response("get_current_datetime"),
                _final_text_response(),
            ]

            events = await _collect_events(
                orchestrator.run(
                    messages=[{"role": "user", "content": "what time is it"}],
                    tools=tools,
                )
            )

        mock_execute.assert_awaited_once_with("get_current_datetime", {})
        tool_results = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_results) == 1
        assert json.loads(tool_results[0]["result"]) == {"now": "2026-07-31T00:00:00Z"}
