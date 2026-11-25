"""Helper and tool events on the phone's chat stream (api/jarvis.py).

An app that sends ``X-Jarvis-Events: helpers`` sees each persona Jarvis asks
(``{type: helper, state, id, persona}``) and each tool it calls
(``{type: tool, name}``). An app that does not gets the stream exactly as
before, so the installed app sees no change.
"""

from __future__ import annotations

import json

import pytest

from life_graph.api.jarvis import _app_event, _app_frames, wants_helpers

# The dashboard frames of one turn (as in tests/integration/test_chat_turn_parity.py).
DASHBOARD = [
    {"type": "start", "task_id": "t1", "persona": "jarvis", "session_id": "s1"},
    {"type": "route", "kind": "local", "model": "stub-model"},
    {"type": "assistant_delta", "text": "Hel"},
    {"type": "tool_call", "name": "clock", "arguments": "{}"},
    {"type": "tool_result", "name": "clock", "result": "12:00"},
    {"type": "tool_call", "name": "delegate_to_persona", "arguments": "null"},
    {"type": "delegation_start", "child_id": "child-1", "persona": "scout"},
    {"type": "child_delta", "child_id": "child-1", "persona": "scout", "text": "child says"},
    {"type": "child_done", "child_id": "child-1", "persona": "scout"},
    {"type": "delegation_start", "child_id": "child-2", "persona": "analyst"},
    {"type": "child_done", "child_id": "child-2", "persona": "analyst"},
    {"type": "child_error", "child_id": "child-3", "persona": "coder", "message": "child broke"},
    {"type": "assistant_delta", "text": "lo"},
    {"type": "done"},
]

OLD_PHONE = [
    {"type": "token", "content": "Hel"},
    {"type": "token", "content": "lo"},
    {"type": "done", "conversation_id": "s1", "route": "local", "task_id": "t1"},
]

NEW_PHONE = [
    {"type": "token", "content": "Hel"},
    {"type": "tool", "name": "clock"},
    {"type": "helper", "state": "start", "id": "child-1", "persona": "scout"},
    {"type": "helper", "state": "text", "id": "child-1", "persona": "scout", "text": "child says"},
    {"type": "helper", "state": "done", "id": "child-1", "persona": "scout"},
    {"type": "helper", "state": "start", "id": "child-2", "persona": "analyst"},
    {"type": "helper", "state": "done", "id": "child-2", "persona": "analyst"},
    {
        "type": "helper",
        "state": "error",
        "id": "child-3",
        "persona": "coder",
        "message": "child broke",
    },
    {"type": "token", "content": "lo"},
    {"type": "done", "conversation_id": "s1", "route": "local", "task_id": "t1"},
]


async def _stream(events):
    # Two frames per chunk and a heartbeat, as the real stream can send them.
    frames = [f"data: {json.dumps(e)}\n\n" for e in events]
    yield ": heartbeat\n\n"
    for i in range(0, len(frames), 2):
        yield "".join(frames[i : i + 2])


async def _phone(events, *, helpers):
    out = []
    async for frame in _app_frames(_stream(events), None, helpers=helpers):
        if frame.startswith("data: "):
            out.append(json.loads(frame[6:]))
    return out


@pytest.mark.parametrize(
    ("header", "want"),
    [
        (None, False),
        ("", False),
        ("cards", False),
        ("helperz", False),
        ("helpers", True),
        ("HELPERS", True),
        ("cards, helpers", True),
        (" helpers ,", True),
    ],
)
def test_wants_helpers_reads_the_header_list(header, want):
    assert wants_helpers(header) is want


@pytest.mark.asyncio
async def test_an_app_that_does_not_ask_gets_the_stream_as_before():
    assert await _phone(DASHBOARD, helpers=False) == OLD_PHONE


@pytest.mark.asyncio
async def test_an_app_that_asks_gets_helpers_and_tools_in_order():
    assert await _phone(DASHBOARD, helpers=True) == NEW_PHONE


@pytest.mark.asyncio
async def test_the_reply_goes_on_after_a_helper_fails():
    events = [
        {"type": "start", "task_id": "t1", "session_id": "s1"},
        {"type": "child_error", "child_id": "c", "persona": "coder", "message": "boom"},
        {"type": "assistant_delta", "text": "Still here"},
        {"type": "done"},
    ]
    out = await _phone(events, helpers=True)
    assert [e["type"] for e in out] == ["helper", "token", "done"]
    assert out[0]["state"] == "error" and out[0]["message"] == "boom"


@pytest.mark.parametrize(
    "event",
    [
        {"type": "delegation_start", "child_id": "c", "persona": "scout"},
        {"type": "child_delta", "child_id": "c", "persona": "scout", "text": "x"},
        {"type": "child_done", "child_id": "c", "persona": "scout"},
        {"type": "child_error", "child_id": "c", "persona": "scout", "message": "x"},
        {"type": "tool_call", "name": "clock", "arguments": "{}"},
    ],
)
def test_helper_events_are_dropped_unless_asked_for(event):
    assert _app_event(event, {}) is None
    assert _app_event(event, {"helpers": False}) is None
    assert _app_event(event, {"helpers": True}) is not None


def test_a_helper_error_is_never_blank_and_is_trimmed():
    blank = {"type": "child_error", "child_id": "c", "persona": "coder", "message": "  "}
    assert _app_event(blank, {"helpers": True})["message"] == "The helper could not finish."
    long = {"type": "child_error", "child_id": "c", "persona": "coder", "message": "x" * 1000}
    assert len(_app_event(long, {"helpers": True})["message"]) == 300


def test_missing_fields_become_empty_strings():
    out = _app_event({"type": "child_delta"}, {"helpers": True})
    assert out == {"type": "helper", "state": "text", "id": "", "persona": "", "text": ""}


def test_tool_events_carry_only_the_name():
    out = _app_event(
        {"type": "tool_call", "name": "web_search", "arguments": '{"q": "private"}'},
        {"helpers": True},
    )
    assert out == {"type": "tool", "name": "web_search"}
    # Delegation shows as helper events, and a nameless call as nothing.
    assert (
        _app_event({"type": "tool_call", "name": "delegate_to_persona"}, {"helpers": True}) is None
    )
    assert _app_event({"type": "tool_call"}, {"helpers": True}) is None


def test_the_existing_phone_events_are_the_same_with_helpers_on():
    state = {"helpers": True}
    assert _app_event({"type": "assistant_delta", "text": "Hi"}, state) == {
        "type": "token",
        "content": "Hi",
    }
    assert _app_event({"type": "error", "message": "boom"}, state) == {
        "type": "error",
        "message": "boom",
    }
    assert _app_event({"type": "tool_result", "name": "clock", "result": "12:00"}, state) is None
