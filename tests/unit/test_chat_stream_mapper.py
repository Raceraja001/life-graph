from __future__ import annotations

from life_graph.services.chat_stream import map_bus_event


def ev(depth, persona, etype, **payload):
    return {
        "task_id": f"tid-{persona}",
        "agent_name": persona,
        "depth": depth,
        "event": {"type": etype, **payload},
    }


def test_depth0_token_is_assistant_delta():
    seen = set()
    out = map_bus_event(ev(0, "jarvis", "token", content="hi"), seen)
    assert out == {"type": "assistant_delta", "text": "hi"}


def test_child_first_token_emits_delegation_start_then_child_delta():
    seen = set()
    first = map_bus_event(ev(1, "tutor", "token", content="A"), seen)
    assert first == {"type": "delegation_start", "child_id": "tid-tutor", "persona": "tutor"}
    assert "tid-tutor" in seen
    second = map_bus_event(ev(1, "tutor", "token", content="B"), seen)
    assert second == {
        "type": "child_delta",
        "child_id": "tid-tutor",
        "persona": "tutor",
        "text": "B",
    }


def test_child_done_maps_to_child_done():
    seen = {"tid-tutor"}
    out = map_bus_event(ev(1, "tutor", "done"), seen)
    assert out == {"type": "child_done", "child_id": "tid-tutor", "persona": "tutor"}


def test_depth0_done_maps_to_done():
    assert map_bus_event(ev(0, "jarvis", "done"), set()) == {"type": "done"}


def test_tool_call_and_usage_are_dropped():
    assert map_bus_event(ev(0, "jarvis", "tool_call", name="delegate_to_persona"), set()) is None
    assert map_bus_event(ev(0, "jarvis", "usage"), set()) is None


def test_child_done_without_prior_token_signals_both():
    out = map_bus_event(ev(1, "scout", "done"), set())
    assert out == {"type": "delegation_start+done", "child_id": "tid-scout", "persona": "scout"}
