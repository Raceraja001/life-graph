"""What shaped a reply (services/turn_trace.py, web-chat-wave1 F3)."""

import json

from life_graph.services.turn_trace import build_trace, summary_line, tool_ok

ROUTE = {"kind": "personal", "model": "ollama_chat/qwen3:14b", "reason": "mentions 'my bills'"}


def test_a_local_turn_keeps_memories_and_tools_but_never_arguments_or_results():
    trace = build_trace(
        ROUTE,
        [{"model": "ollama_chat/qwen3:14b", "local": True}],
        [{"id": 7, "content": "The locker code is 4417 and the spare key is with Amma downstairs."}],
        [{"name": "bills_due", "ok": True, "ms": 120.4, "arguments": {"q": "x"}, "result": "secret"}],
    )
    assert trace["local"] is True and trace["route"]["kind"] == "personal"
    assert trace["memories"] == [{"id": "7", "snippet": "The locker code is 4417 and the spare key is with Amma down…"}]
    assert len(trace["memories"][0]["snippet"]) == 60
    assert trace["tools"] == [{"name": "bills_due", "ok": True, "ms": 120}]
    assert "secret" not in json.dumps(trace) and "arguments" not in json.dumps(trace)
    assert summary_line(trace) == "Local · 1 memory · 1 tool"


def test_local_only_when_every_call_is_known_local():
    assert build_trace(ROUTE, [], [], [])["local"] is False  # nothing known: not claimed
    mixed = [{"model": "a", "local": True}, {"model": "b", "local": False}]
    trace = build_trace({"kind": "general", "reason": "nothing personal in it"}, mixed, [], [])
    assert trace["local"] is False
    assert summary_line(trace) == "Cloud (nothing personal in it) · no memories · no tools"
    assert summary_line(build_trace(None, mixed, [], [])) == "Cloud · no memories · no tools"


def test_plural_counts():
    trace = build_trace(ROUTE, [{"model": "m", "local": True}], [{"id": 1}, {"id": 2}, {"id": 3}],
                        [{"name": "a", "ok": True}, {"name": "b", "ok": False}])
    assert summary_line(trace) == "Local · 3 memories · 2 tools"


def test_a_tool_result_with_an_error_reads_as_failed():
    assert tool_ok('{"error": "no time"}') is False
    assert tool_ok('{"reminded": true}') is True
    assert tool_ok("plain text") is True
    assert tool_ok(None) is True
