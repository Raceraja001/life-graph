"""Driver run steps: the claude_code stream-json parser and the local driver's
step collector both produce one driver-neutral step list, and the recorder
redacts and caps what it stores.
"""

from __future__ import annotations

import json
import uuid

from life_graph.drivers.steps import StepCollector, parse_claude_stream


def _stream(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events)


# Shapes copied from a real `claude -p --output-format stream-json --verbose`
# run (Claude Code 2.1.272), trimmed to the fields the parser reads.
_INIT = {"type": "system", "subtype": "init", "model": "claude-opus-5", "cwd": "/work"}
_CALL = {
    "type": "assistant",
    "timestamp": "2026-10-13T09:40:32.579Z",
    "message": {
        "content": [
            {"type": "thinking", "thinking": "I should read the file first."},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "Read",
                "input": {"file_path": "/work/hello.txt"},
            },
        ]
    },
}
_RESULT_BLOCK = {
    "type": "user",
    "timestamp": "2026-10-13T09:40:33.001Z",
    "message": {
        "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "1\thi\n2\t"}]
    },
}
_REPLY = {
    "type": "assistant",
    "timestamp": "2026-10-13T09:40:34.120Z",
    "message": {"content": [{"type": "text", "text": "HI"}]},
}
_DONE = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "result": "HI",
    "total_cost_usd": 0.0977,
    "session_id": "s1",
    "num_turns": 2,
}


def test_stream_yields_the_final_result_and_every_step_in_order():
    result, steps = parse_claude_stream(_stream(_INIT, _CALL, _RESULT_BLOCK, _REPLY, _DONE))

    assert result["result"] == "HI"
    assert result["total_cost_usd"] == 0.0977
    assert result["session_id"] == "s1"
    assert result["model"] == "claude-opus-5"
    assert [(s["seq"], s["kind"], s.get("tool")) for s in steps] == [
        (1, "thinking", None),
        (2, "tool_call", "Read"),
        (3, "tool_result", "Read"),  # tool name carried over from its call
        (4, "text", None),
    ]
    assert json.loads(steps[1]["content"]) == {"file_path": "/work/hello.txt"}
    assert steps[2]["content"] == "1\thi\n2\t"
    assert steps[2]["ref"] == "toolu_1"
    assert steps[0]["at"] == "2026-10-13T09:40:32.579Z"


def test_a_failed_tool_result_is_marked_and_list_content_is_flattened():
    failed = {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t",
                    "is_error": True,
                    "content": [{"type": "text", "text": "No such file"}],
                }
            ]
        },
    }
    _, steps = parse_claude_stream(_stream(failed, _DONE))
    assert steps[0]["is_error"] is True
    assert steps[0]["content"] == "No such file"


def test_old_single_object_output_still_parses_with_no_steps():
    result, steps = parse_claude_stream(json.dumps({"result": "done", "is_error": False}))
    assert result == {"result": "done", "is_error": False}
    assert steps == []


def test_a_stream_cut_off_before_its_result_is_an_error_but_keeps_its_steps():
    result, steps = parse_claude_stream(_stream(_INIT, _CALL))
    assert result["is_error"] is True
    assert [s["kind"] for s in steps] == ["thinking", "tool_call"]


def test_empty_and_plain_text_output():
    assert parse_claude_stream("") == ({}, [])
    assert parse_claude_stream("not json at all") == ({"result": "not json at all"}, [])


def test_local_collector_joins_tokens_into_one_text_step():
    c = StepCollector()
    for event in [
        {"type": "token", "content": "Let me "},
        {"type": "token", "content": "look."},
        {"type": "tool_call", "name": "code_read", "arguments": {"path": "a.py"}},
        {"type": "tool_result", "name": "code_read", "result": "print(1)"},
        {"type": "token", "content": "Done."},
        {"type": "partial_error", "message": "model unavailable"},
        {"type": "usage", "completion_tokens": 3},  # not a step
    ]:
        c.add(event)

    steps = c.finish()

    assert [(s["seq"], s["kind"], s.get("tool"), s["content"]) for s in steps] == [
        (1, "text", None, "Let me look."),
        (2, "tool_call", "code_read", '{"path": "a.py"}'),
        (3, "tool_result", "code_read", "print(1)"),
        (4, "text", None, "Done."),
        (5, "error", None, "model unavailable"),
    ]


def test_recorder_redacts_and_caps_what_it_stores(monkeypatch):
    from life_graph.config import settings
    from life_graph.services.trajectories import to_rows

    monkeypatch.setattr(settings, "trajectory_step_max_chars", 50)
    steps = [
        {
            "seq": 1,
            "kind": "tool_result",
            "tool": "Read",
            "content": "LIFE_GRAPH_API_KEY=supersecretvalue123\nok",
            "ref": "t1",
        },
        {"seq": 2, "kind": "text", "content": "x" * 500},
    ]

    rows = to_rows("t1", uuid.uuid4(), "claude_code", 2, steps)

    assert "supersecretvalue123" not in rows[0].content
    assert "REDACTED" in rows[0].content
    assert rows[0].properties == {"ref": "t1"}
    assert len(rows[1].content) == 50
    assert rows[1].properties["original_chars"] == 500
    assert all(r.attempt == 2 and r.driver == "claude_code" for r in rows)
