"""A run pinned to local models is a LOCAL audience for connector data.

A personal Jarvis turn runs on a local model pinned with ``only_models()``
(services/lead.py ``route``, kernel/process_manager.py), so ResilientLLM can
only fail over to the pinned local models. ``connectors/locality.run_is_local``
ignored the pin and looked at the global fallback chain, which can hold cloud
models, so the orchestrator's ``audience_for_model`` called that run CLOUD and
connector tools handed it the cloud rendering (titles only, bodies withheld).
Now the pin is the chain when one is active.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from life_graph.agents.orchestrator import AgentOrchestrator
from life_graph.config import settings
from life_graph.connectors import locality
from life_graph.connectors.locality import CLOUD, LOCAL, audience, audience_for_model
from life_graph.services.llm import fallback_pin
from life_graph.services.llm.resilient import only_models

LOCAL_A = "ollama_chat/qwen3:14b"
LOCAL_B = "ollama_chat/qwen3:4b"
CLOUD_M = "gemini/gemini-3.6-flash"


@pytest.fixture(autouse=True)
def cloud_chain(monkeypatch):
    """A global chain that leaves the machine three ways."""
    monkeypatch.setattr(settings, "connector_local_model_prefixes", "")
    monkeypatch.setattr(settings, "llm_fallback_chain", f"{LOCAL_B},{CLOUD_M}")
    monkeypatch.setattr(settings, "omniroute_api_key", "k")
    monkeypatch.setattr(settings, "omniroute_model", "openai/auto")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", "openrouter/paid")


def _audience(model):
    with audience_for_model(model):
        return locality.current_audience()


def test_unpinned_run_on_a_cloud_chain_is_cloud():
    assert fallback_pin.pinned_models() is None
    assert _audience(LOCAL_A) == CLOUD


def test_pinned_to_local_models_is_local():
    with only_models([LOCAL_A, LOCAL_B]):
        assert _audience(LOCAL_A) == LOCAL
    # The pin ends with its block.
    assert _audience(LOCAL_A) == CLOUD


def test_pinned_with_any_cloud_model_is_cloud():
    with only_models([LOCAL_A, CLOUD_M]):
        assert _audience(LOCAL_A) == CLOUD


def test_a_cloud_model_under_a_local_pin_is_cloud():
    """ResilientLLM tries the caller's model first, pin or not."""
    with only_models([LOCAL_A]):
        assert _audience(CLOUD_M) == CLOUD


def test_unknown_model_under_a_local_pin_is_cloud():
    with only_models([LOCAL_A]):
        assert _audience(None) == CLOUD


def test_an_empty_pin_leaves_only_the_model():
    with only_models([]):
        assert _audience(LOCAL_A) == LOCAL
        assert _audience(CLOUD_M) == CLOUD


def test_a_pin_never_widens_a_cloud_caller():
    with audience(CLOUD), only_models([LOCAL_A]):
        assert _audience(LOCAL_A) == CLOUD


def test_resilient_and_locality_read_the_same_pin():
    with only_models([LOCAL_A]):
        assert fallback_pin.pinned_models() == (LOCAL_A,)
    assert fallback_pin.pinned_models() is None


def _stream(chunks):
    async def gen():
        for c in chunks:
            yield SimpleNamespace(choices=[SimpleNamespace(delta=c)])

    return gen()


def _tool_call(name):
    call = SimpleNamespace(
        index=0, id="call_1", function=SimpleNamespace(name=name, arguments="{}")
    )
    return _stream([SimpleNamespace(content=None, tool_calls=[call])])


async def _audience_seen_by_tool(pin):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calendar_upcoming",
                "description": "d",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    seen: list[str] = []

    async def execute(name, args):
        seen.append(locality.current_audience())
        return json.dumps({"ok": True})

    with (
        patch("litellm.acompletion", new_callable=AsyncMock) as completion,
        patch("life_graph.agents.orchestrator.registry.execute", side_effect=execute),
        pin,
    ):
        completion.side_effect = [
            _tool_call("calendar_upcoming"),
            _stream([SimpleNamespace(content="done", tool_calls=None)]),
        ]
        async for _ in AgentOrchestrator(model=LOCAL_A).run(
            messages=[{"role": "user", "content": "personal: what's on today?"}], tools=tools
        ):
            pass
    return seen


async def test_the_orchestrator_tool_call_sees_the_pin():
    """Where the bug showed: the tool call's audience inside a pinned run."""
    assert await _audience_seen_by_tool(only_models([LOCAL_A, LOCAL_B])) == [LOCAL]
    assert await _audience_seen_by_tool(only_models([LOCAL_A, CLOUD_M])) == [CLOUD]
