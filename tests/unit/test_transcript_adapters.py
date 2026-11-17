"""Watermarks, the four transcript adapters, and the normalizer.

Fixtures are written to ``tmp_path`` as real JSONL files and read through the
real adapters: these tests cover the file handling (partial trailing lines,
truncation, offsets) as much as the parsing, and that handling is the part
that silently loses or re-ingests a user's history when it is wrong.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime

import pytest

from life_graph.watchers.agent_transcripts.adapters import (
    ADAPTER_CLASSES,
    AntigravityAdapter,
    ClaudeCodeAdapter,
    CodexAdapter,
    CursorAdapter,
    adapters_for,
    all_adapters,
)
from life_graph.watchers.agent_transcripts.adapters.base import (
    BaseTranscriptAdapter,
    pick,
    snippet,
)
from life_graph.watchers.agent_transcripts.normalizer import (
    NormalizedSessionSlice,
    TranscriptNormalizer,
)
from life_graph.watchers.agent_transcripts.watermark import (
    STATE_PATH_ENV,
    WatermarkStore,
)


def write_jsonl(path, records) -> int:
    """Write *records* as JSONL and return the file size."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path.stat().st_size


def age(path, seconds: float) -> None:
    """Backdate *path*'s mtime so ``is_settled`` treats it as finished."""
    past = time.time() - seconds
    os.utime(path, (past, past))


# ── WatermarkStore ───────────────────────────────────────────────────────


def test_watermark_round_trips_through_the_state_file(tmp_path):
    state = tmp_path / "state.json"
    store = WatermarkStore(state_path=state)
    assert store.get_watermark("/transcripts/a.jsonl") == (0, 0.0)

    store.update_watermark("/transcripts/a.jsonl", 2048, 1700.5, "sess-1")
    store.save()

    reloaded = WatermarkStore(state_path=state)
    assert reloaded.get_watermark("/transcripts/a.jsonl") == (2048, 1700.5)
    assert reloaded.session_id("/transcripts/a.jsonl") == "sess-1"
    entry = reloaded.entries()["/transcripts/a.jsonl"]
    assert datetime.fromisoformat(entry["last_harvested_at"]).tzinfo is not None


def test_update_without_save_leaves_the_file_alone(tmp_path):
    """A crash mid-harvest must replay bytes, not skip them."""
    state = tmp_path / "state.json"
    store = WatermarkStore(state_path=state)
    store.update_watermark("/a.jsonl", 10, 1.0, "s")
    assert not state.exists()
    assert WatermarkStore(state_path=state).get_watermark("/a.jsonl") == (0, 0.0)


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path):
    state = tmp_path / "nested" / "state.json"
    store = WatermarkStore(state_path=state)
    store.update_watermark("/a.jsonl", 1, 2.0, "s")
    store.save()
    assert json.loads(state.read_text())["/a.jsonl"]["last_byte_offset"] == 1
    assert [p.name for p in state.parent.iterdir()] == ["state.json"]


def test_a_relative_path_and_its_absolute_form_are_one_watermark(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "t.jsonl").write_text("{}\n")
    store = WatermarkStore(state_path=tmp_path / "state.json")
    store.update_watermark("t.jsonl", 7, 1.0, "s")
    assert store.get_watermark(tmp_path / "t.jsonl") == (7, 1.0)


def test_corrupt_state_starts_empty_rather_than_raising(tmp_path):
    state = tmp_path / "state.json"
    state.write_text("{ not json")
    store = WatermarkStore(state_path=state)
    assert store.entries() == {}
    store.update_watermark("/a.jsonl", 5, 1.0, "s")
    store.save()
    assert WatermarkStore(state_path=state).get_watermark("/a.jsonl") == (5, 1.0)


def test_non_numeric_offsets_in_the_state_file_degrade_to_zero(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"/a.jsonl": {"last_byte_offset": "nope", "last_mtime": None}}))
    assert WatermarkStore(state_path=state).get_watermark("/a.jsonl") == (0, 0.0)


def test_state_path_comes_from_the_environment_when_unset(tmp_path, monkeypatch):
    monkeypatch.setenv(STATE_PATH_ENV, str(tmp_path / "from-env.json"))
    assert WatermarkStore().state_path == tmp_path / "from-env.json"
    assert WatermarkStore(state_path=tmp_path / "explicit.json").state_path == (
        tmp_path / "explicit.json"
    )


def test_forget_makes_a_file_readable_from_the_start_again(tmp_path):
    store = WatermarkStore(state_path=tmp_path / "state.json")
    store.update_watermark("/a.jsonl", 99, 1.0, "s")
    store.forget("/a.jsonl")
    assert store.get_watermark("/a.jsonl") == (0, 0.0)


@pytest.mark.parametrize(
    ("seconds_old", "settled"),
    [(0, False), (5, False), (120, True)],
)
def test_is_settled_waits_for_the_writer_to_stop(tmp_path, seconds_old, settled):
    path = tmp_path / "t.jsonl"
    path.write_text("{}\n")
    age(path, seconds_old)
    assert WatermarkStore(state_path=tmp_path / "s.json").is_settled(path, 30.0) is settled


def test_a_lock_file_makes_a_settled_transcript_unsettled(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text("{}\n")
    age(path, 600)
    store = WatermarkStore(state_path=tmp_path / "s.json")
    assert store.is_settled(path) is True
    (tmp_path / "t.jsonl.lock").write_text("")
    assert store.is_settled(path) is False


def test_a_missing_transcript_is_never_settled(tmp_path):
    store = WatermarkStore(state_path=tmp_path / "s.json")
    assert store.is_settled(tmp_path / "gone.jsonl") is False


# ── Incremental reading (shared by every adapter) ────────────────────────


def test_parse_incremental_holds_back_a_half_written_line(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text('{"n": 1}\n{"n": 2}\n{"n": 3', encoding="utf-8")
    adapter = ClaudeCodeAdapter()

    events, offset = adapter.parse_incremental(path)
    assert [e["n"] for e in events] == [1, 2]
    assert offset == len('{"n": 1}\n{"n": 2}\n')

    # The partial line completes; the next pass reads only it.
    with path.open("a", encoding="utf-8") as handle:
        handle.write('}\n{"n": 4}\n')
    events, offset = adapter.parse_incremental(path, offset)
    assert [e["n"] for e in events] == [3, 4]
    assert offset == path.stat().st_size


def test_parse_incremental_at_the_end_of_the_file_reads_nothing(tmp_path):
    path = tmp_path / "t.jsonl"
    size = write_jsonl(path, [{"n": 1}])
    events, offset = ClaudeCodeAdapter().parse_incremental(path, size)
    assert (events, offset) == ([], size)


def test_a_single_incomplete_line_yields_nothing_and_does_not_move(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text('{"half": ', encoding="utf-8")
    assert ClaudeCodeAdapter().parse_incremental(path) == ([], 0)


def test_a_truncated_transcript_is_re_read_from_the_start(tmp_path):
    path = tmp_path / "t.jsonl"
    write_jsonl(path, [{"n": 1}])
    events, offset = ClaudeCodeAdapter().parse_incremental(path, start_offset=10_000)
    assert [e["n"] for e in events] == [1]
    assert offset == path.stat().st_size


def test_unparseable_and_non_object_lines_are_skipped(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text('{"n": 1}\nnot json at all\n[1, 2]\n{"n": 2}\n', encoding="utf-8")
    events, _ = ClaudeCodeAdapter().parse_incremental(path)
    assert [e["n"] for e in events] == [1, 2]


def test_parse_incremental_on_a_missing_file_is_quiet(tmp_path):
    assert ClaudeCodeAdapter().parse_incremental(tmp_path / "nope.jsonl", 5) == ([], 5)


# ── Discovery ────────────────────────────────────────────────────────────


def test_each_adapter_finds_its_own_transcripts_under_a_fake_home(tmp_path, monkeypatch):
    layout = {
        "claude_code": ".claude/projects/-home-raja-proj/abc.jsonl",
        "antigravity": ".gemini/antigravity/brain/run-1/transcript.jsonl",
        "cursor": ".cursor/projects/proj/agent-transcripts/thread.jsonl",
        "codex": ".codex/sessions/2026/11/rollout-1.jsonl",
    }
    for relative in layout.values():
        write_jsonl(tmp_path / relative, [{"n": 1}])
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    for adapter in all_adapters():
        found = adapter.find_transcript_files()
        assert found == [(tmp_path / layout[adapter.agent_type]).absolute()], adapter.agent_type


def test_discovery_is_oldest_first_so_a_backlog_drains_in_order(tmp_path):
    for name, seconds in (("new.jsonl", 10), ("old.jsonl", 9000), ("mid.jsonl", 500)):
        path = tmp_path / name
        write_jsonl(path, [{"n": 1}])
        age(path, seconds)
    found = ClaudeCodeAdapter().find_transcript_files([tmp_path])
    assert [p.name for p in found] == ["old.jsonl", "mid.jsonl", "new.jsonl"]


def test_base_dirs_override_the_home_globs(tmp_path):
    write_jsonl(tmp_path / "anywhere" / "x.jsonl", [{"n": 1}])
    assert len(ClaudeCodeAdapter().find_transcript_files([tmp_path])) == 1


def test_a_missing_base_dir_is_not_an_error(tmp_path):
    assert ClaudeCodeAdapter().find_transcript_files([tmp_path / "nope"]) == []


def test_adapters_for_resolves_aliases_and_rejects_unknown_agents():
    assert [a.agent_type for a in adapters_for("claude")] == ["claude_code"]
    assert [a.agent_type for a in adapters_for("OpenClaw")] == ["codex"]
    assert len(adapters_for(None)) == len(ADAPTER_CLASSES)
    with pytest.raises(ValueError, match="Unknown agent"):
        adapters_for("emacs")


def test_every_adapter_declares_a_distinct_agent_type_and_a_search_path():
    types = [cls.agent_type for cls in ADAPTER_CLASSES]
    assert len(types) == len(set(types))
    for cls in ADAPTER_CLASSES:
        assert cls.home_globs, f"{cls.__name__} would never find anything"
        assert cls.agent_type != BaseTranscriptAdapter.agent_type


# ── Claude Code ──────────────────────────────────────────────────────────

CLAUDE_RECORDS = [
    {"type": "queue-operation", "operation": "enqueue", "content": "ignored bookkeeping"},
    {
        "type": "user",
        "sessionId": "sess-cc",
        "cwd": "/home/raja/projects/life-graph",
        "gitBranch": "feat/x",
        "timestamp": "2026-11-10T08:00:00.000Z",
        "message": {"role": "user", "content": "pytest fails with ModuleNotFoundError"},
    },
    {
        "type": "assistant",
        "sessionId": "sess-cc",
        "timestamp": "2026-11-10T08:00:05.000Z",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "probably the wrong venv"},
                {"type": "text", "text": "Running the suite to see the failure."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "Bash",
                    "input": {"command": "pytest -q"},
                },
            ],
        },
    },
    {
        "type": "user",
        "sessionId": "sess-cc",
        "timestamp": "2026-11-10T08:00:20.000Z",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": "ModuleNotFoundError: No module named 'pgvector'",
                    "is_error": True,
                }
            ],
        },
        "toolUseResult": {
            "stdout": "",
            "stderr": "ModuleNotFoundError: No module named 'pgvector'",
            "interrupted": False,
        },
    },
    {
        "type": "assistant",
        "sessionId": "sess-cc",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "Write",
                    "input": {"file_path": "/repo/requirements.txt", "content": "pgvector\n"},
                }
            ],
        },
    },
    {
        "type": "user",
        "sessionId": "sess-cc",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_2", "content": "File created"}
            ],
        },
        "toolUseResult": {"type": "create", "filePath": "/repo/requirements.txt"},
    },
    {
        "type": "assistant",
        "sessionId": "sess-cc",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Added pgvector; the suite passes now."}],
        },
    },
]


def test_claude_code_extracts_prompts_tools_results_and_thoughts():
    events = ClaudeCodeAdapter().canonical_events(CLAUDE_RECORDS)
    kinds = [e["kind"] for e in events]
    assert kinds.count("user") == 1
    assert kinds.count("tool_call") == 2
    assert kinds.count("tool_result") == 2

    thoughts = [e for e in events if e["kind"] == "assistant" and e.get("is_thought")]
    assert [t["text"] for t in thoughts] == ["probably the wrong venv"]

    call = next(e for e in events if e["kind"] == "tool_call")
    assert (call["tool_name"], call["command"], call["tool_id"]) == (
        "Bash",
        "pytest -q",
        "toolu_1",
    )
    assert call["session_id"] == "sess-cc"
    # The assistant record carries no cwd; the prompt's project reaches the
    # slice through the normalizer's per-turn fallback.
    assert next(e for e in events if e["kind"] == "user")["project"] == "life-graph"

    failed = next(e for e in events if e["kind"] == "tool_result")
    assert failed["is_error"] is True
    assert "pgvector" in failed["output"]
    assert failed["tool_id"] == "toolu_1"


def test_claude_code_describes_a_write_by_the_file_it_wrote():
    events = ClaudeCodeAdapter().canonical_events(CLAUDE_RECORDS)
    write = next(e for e in events if e.get("tool_name") == "Write")
    assert write["command"] == "/repo/requirements.txt"
    result = [e for e in events if e["kind"] == "tool_result"][1]
    assert result["output"] == "File created"


def test_claude_code_drops_injected_system_reminders():
    """A reminder-only turn must not split the slice away from its prompt."""
    records = [
        {
            "type": "user",
            "sessionId": "s",
            "message": {
                "role": "user",
                "content": "<system-reminder>\ncall SubagentHandback\n</system-reminder>",
            },
        },
        {
            "type": "user",
            "sessionId": "s",
            "message": {
                "role": "user",
                "content": "fix the build\n<system-reminder>be brief</system-reminder>",
            },
        },
    ]
    events = ClaudeCodeAdapter().canonical_events(records)
    assert [e["text"] for e in events] == ["fix the build"]


def test_claude_code_marks_an_interrupted_tool_as_an_error():
    records = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "t", "content": "partial"}],
            },
            "toolUseResult": {"stdout": "partial", "stderr": "", "interrupted": True},
        }
    ]
    result = ClaudeCodeAdapter().canonical_events(records)[0]
    assert result["is_error"] is True
    assert "[interrupted]" in result["output"]


# ── Antigravity ──────────────────────────────────────────────────────────

ANTIGRAVITY_RECORDS = [
    {
        "type": "USER_INPUT",
        "text": "docker compose up fails: port already allocated",
        "session_id": "ag-1",
        "workspace": "/home/raja/projects/life-graph",
        "timestamp": "2026-11-11T09:00:00Z",
    },
    {
        "type": "PLANNER_RESPONSE",
        "text": "Checking what holds the port.",
        "tool_calls": [
            {
                "name": "run_command",
                "id": "call-1",
                "args": {"command": "ss -ltnp | grep 55432"},
                "output": 'users:(("postgres",pid=9))',
                "exit_code": 0,
            }
        ],
    },
    {
        "type": "TOOL_OUTPUT",
        "call_id": "call-2",
        "output": "",
        "error": "Error: port is allocated",
        "exit_code": 1,
    },
    {"type": "FINAL_RESPONSE", "text": "Changed the host port in the override file."},
]


def test_antigravity_reads_steps_tool_calls_and_outputs():
    events = AntigravityAdapter().canonical_events(ANTIGRAVITY_RECORDS)
    assert [e["kind"] for e in events] == [
        "user",
        "assistant",
        "tool_call",
        "tool_result",
        "tool_result",
        "assistant",
    ]
    assert events[0]["session_id"] == "ag-1"
    assert events[2]["command"] == "ss -ltnp | grep 55432"
    assert events[3]["is_error"] is False
    assert events[4]["is_error"] is True and events[4]["exit_code"] == 1
    assert events[5]["text"] == "Changed the host port in the override file."


def test_antigravity_reads_a_payload_wrapped_step():
    events = AntigravityAdapter().canonical_events(
        [{"payload": {"step_type": "USER_INPUT", "content": "why is the build red"}}]
    )
    assert events[0]["kind"] == "user"
    assert events[0]["text"] == "why is the build red"


def test_antigravity_ignores_a_step_kind_it_does_not_know():
    assert AntigravityAdapter().canonical_events([{"type": "TELEMETRY", "text": "noise"}]) == []


# ── Cursor ───────────────────────────────────────────────────────────────

CURSOR_RECORDS = [
    {
        "type": "message",
        "role": "user",
        "content": "eslint is failing on the dashboard",
        "composerId": "cmp-7",
        "workspacePath": "/home/raja/projects/life-graph/dashboard",
        "timestamp": "2026-11-12T10:00:00Z",
    },
    {
        "type": "message",
        "role": "assistant",
        "content": "Running lint.",
        "thinking": "probably the new rule",
        "toolCalls": [
            {
                "name": "terminal",
                "id": "tc-1",
                "arguments": {"command": "npm run lint"},
                "result": "1 problem (1 error, 0 warnings)",
                "exitCode": 1,
            }
        ],
    },
    {"type": "tool_result", "toolCallId": "tc-2", "output": "clean", "exitCode": 0},
    {
        "type": "message",
        "role": "assistant",
        "content": "Fixed the import order rule.",
        "toolResult": {"id": "tc-3", "error": "ENOENT: no such file"},
    },
]


def test_cursor_reads_prompts_assistant_turns_tools_and_results():
    events = CursorAdapter().canonical_events(CURSOR_RECORDS)
    assert [e["kind"] for e in events] == [
        "user",
        "assistant",
        "assistant",
        "tool_call",
        "tool_result",
        "tool_result",
        "assistant",
        "tool_result",
    ]
    assert events[0]["session_id"] == "cmp-7"
    assert events[2]["is_thought"] is True
    assert events[3]["command"] == "npm run lint"
    assert events[4]["is_error"] is True and events[4]["exit_code"] == 1
    assert events[5]["is_error"] is False
    assert events[7]["is_error"] is True


def test_cursor_finds_both_its_transcript_directories(tmp_path):
    write_jsonl(tmp_path / "p" / "agent-transcripts" / "a.jsonl", [{"n": 1}])
    write_jsonl(tmp_path / "p" / "composer" / "deep" / "b.jsonl", [{"n": 1}])
    write_jsonl(tmp_path / "p" / "unrelated" / "c.jsonl", [{"n": 1}])
    found = {p.name for p in CursorAdapter().find_transcript_files([tmp_path])}
    assert found == {"a.jsonl", "b.jsonl"}


# ── Codex / OpenClaw ─────────────────────────────────────────────────────

CODEX_RECORDS = [
    {
        "type": "session_meta",
        "timestamp": "2026-11-13T11:00:00Z",
        "payload": {"id": "codex-3", "cwd": "/home/raja/projects/life-graph"},
    },
    {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "alembic upgrade head fails"}],
        },
    },
    {
        "type": "response_item",
        "payload": {
            "type": "reasoning",
            "summary": [{"type": "summary_text", "text": "check the current revision"}],
        },
    },
    {
        "type": "response_item",
        "payload": {
            "type": "function_call",
            "name": "shell",
            "call_id": "fc-1",
            "arguments": json.dumps({"command": ["bash", "-lc", "alembic upgrade head"]}),
        },
    },
    {
        "type": "response_item",
        "payload": {
            "type": "function_call_output",
            "call_id": "fc-1",
            "output": json.dumps(
                {
                    "output": "Target database is not up to date.",
                    "metadata": {"exit_code": 1, "duration_seconds": 2},
                }
            ),
        },
    },
    {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Stamped the head revision."}],
        },
    },
]


def test_codex_decodes_argv_commands_and_json_wrapped_output():
    events = CodexAdapter().canonical_events(CODEX_RECORDS)
    assert [e["kind"] for e in events] == [
        "user",
        "assistant",
        "tool_call",
        "tool_result",
        "assistant",
    ]
    assert events[0]["session_id"] == "codex-3"
    assert events[0]["project"] == "life-graph"
    assert events[1]["is_thought"] is True
    assert events[2]["command"] == "bash -lc alembic upgrade head"
    assert events[3]["exit_code"] == 1 and events[3]["is_error"] is True
    assert events[3]["output"] == "Target database is not up to date."


def test_codex_reads_an_unwrapped_flat_record():
    events = CodexAdapter().canonical_events(
        [{"type": "message", "role": "user", "content": "why is CI red"}]
    )
    assert events == [
        {"kind": "user", "text": "why is CI red", "ts": None, "session_id": None, "project": None}
    ]


def test_codex_finds_openclaw_sessions_too(tmp_path):
    write_jsonl(tmp_path / "sessions" / "2026" / "rollout-1.jsonl", [{"n": 1}])
    write_jsonl(tmp_path / "profile" / "sessions" / "s.jsonl", [{"n": 1}])
    found = {p.name for p in CodexAdapter().find_transcript_files([tmp_path])}
    assert found == {"rollout-1.jsonl", "s.jsonl"}


# ── Shared helpers ───────────────────────────────────────────────────────


def test_snippet_clips_long_output_and_says_how_much_it_dropped():
    assert snippet("short") == "short"
    clipped = snippet("x" * 50, limit=10)
    assert clipped.startswith("x" * 10)
    assert "+40 chars" in clipped
    assert snippet(None) == ""
    assert snippet({"a": 1}) == '{"a": 1}'


def test_pick_takes_the_first_key_that_carries_something():
    assert pick({"a": "", "b": "x"}, "a", "b") == "x"
    assert pick({"a": None}, "a", default="fallback") == "fallback"
    assert pick("not a dict", "a", default=None) is None


def test_the_base_adapter_refuses_to_guess_a_format():
    with pytest.raises(NotImplementedError):
        BaseTranscriptAdapter().canonical_events([{"type": "user"}])


# ── Normalizer ───────────────────────────────────────────────────────────


def normalize_claude(records, path="/tmp/-home-raja-projects-life-graph/sess.jsonl"):
    adapter = ClaudeCodeAdapter()
    return TranscriptNormalizer().normalize(adapter, path, records)


def test_normalizer_builds_one_slice_per_user_turn_with_its_tools():
    slices = normalize_claude(CLAUDE_RECORDS)
    assert len(slices) == 1
    only = slices[0]
    assert only.agent_type == "claude_code"
    assert only.session_id == "sess-cc"
    assert only.project_name == "life-graph"
    assert only.user_prompt == "pytest fails with ModuleNotFoundError"
    assert only.tool_names == ["Bash", "Write"]
    assert only.resolution_summary == "Added pgvector; the suite passes now."
    assert only.occurred_at == datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
    assert only.file_path.endswith("sess.jsonl")


def test_normalizer_pairs_each_tool_call_with_its_own_result():
    only = normalize_claude(CLAUDE_RECORDS)[0]
    failed, wrote = only.tool_calls
    assert failed["tool_name"] == "Bash"
    assert failed["is_error"] is True
    assert "pgvector" in failed["output_snippet"]
    assert wrote["tool_name"] == "Write"
    assert wrote["is_error"] is False


def test_an_error_followed_by_a_successful_edit_counts_as_fixed():
    only = normalize_claude(CLAUDE_RECORDS)[0]
    assert (only.has_errors, only.has_fixes) == (True, True)
    assert [c["tool_name"] for c in only.error_calls] == ["Bash"]
    assert [c["tool_name"] for c in only.mutating_calls] == ["Bash", "Write"]


def test_a_second_prompt_starts_a_second_slice():
    records = [
        *CLAUDE_RECORDS,
        {
            "type": "user",
            "sessionId": "sess-cc",
            "message": {"role": "user", "content": "now update the changelog"},
        },
    ]
    slices = normalize_claude(records)
    assert len(slices) == 2
    assert slices[1].user_prompt == "now update the changelog"
    assert slices[1].tool_calls == []


def test_an_unresolved_error_is_not_a_fix():
    records = [
        {
            "type": "user",
            "sessionId": "s",
            "message": {"role": "user", "content": "run the migration"},
        },
        {
            "type": "assistant",
            "sessionId": "s",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Bash",
                        "input": {"command": "alembic upgrade head"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "sessionId": "s",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": "psycopg.OperationalError: connection refused",
                        "is_error": True,
                    }
                ],
            },
        },
    ]
    only = normalize_claude(records)[0]
    assert (only.has_errors, only.has_fixes) == (True, False)


def test_a_zero_exit_traceback_still_reads_as_an_error():
    """Wrappers routinely return 0 while printing the failure."""
    slices = TranscriptNormalizer().from_canonical(
        "claude_code",
        "/t/sess.jsonl",
        [
            {"kind": "user", "text": "run the suite"},
            {"kind": "tool_call", "tool_name": "Bash", "command": "pytest", "tool_id": "x"},
            {
                "kind": "tool_result",
                "tool_id": "x",
                "output": "Traceback (most recent call last):\nValueError: boom",
                "is_error": False,
                "exit_code": 0,
            },
        ],
    )
    assert slices[0].has_errors is True


def test_results_with_no_ids_are_paired_in_order():
    slices = TranscriptNormalizer().from_canonical(
        "cursor",
        "/t/sess.jsonl",
        [
            {"kind": "user", "text": "lint and test"},
            {"kind": "tool_call", "tool_name": "terminal", "command": "npm run lint"},
            {"kind": "tool_call", "tool_name": "terminal", "command": "npm test"},
            {"kind": "tool_result", "output": "lint clean", "is_error": False},
            {"kind": "tool_result", "output": "1 failing", "is_error": True},
        ],
    )
    calls = slices[0].tool_calls
    assert [c["command"] for c in calls] == ["npm run lint", "npm test"]
    assert [c["output_snippet"] for c in calls] == ["lint clean", "1 failing"]
    assert [c["is_error"] for c in calls] == [False, True]


def test_a_result_whose_call_was_in_an_earlier_read_is_kept():
    """The call is in bytes already harvested; its failure still matters."""
    slices = TranscriptNormalizer().from_canonical(
        "claude_code",
        "/t/sess.jsonl",
        [
            {"kind": "tool_result", "tool_id": "old", "output": "boom", "is_error": True},
            {"kind": "user", "text": "carry on"},
        ],
    )
    assert len(slices) == 2
    assert slices[0].tool_calls[0]["tool_name"] == "unknown"
    assert slices[0].has_errors is True


def test_session_and_project_fall_back_to_the_path_when_records_are_silent():
    slices = TranscriptNormalizer().from_canonical(
        "claude_code",
        "/home/raja/.claude/projects/-home-raja-projects-life-graph/abc-123.jsonl",
        [{"kind": "user", "text": "hello"}],
    )
    assert slices[0].session_id == "abc-123"
    assert slices[0].project_name == "home-raja-projects-life-graph"


def test_a_session_id_from_the_first_record_reaches_every_later_slice():
    slices = TranscriptNormalizer().from_canonical(
        "cursor",
        "/t/file.jsonl",
        [
            {"kind": "user", "text": "first ask", "session_id": "cmp-9"},
            {"kind": "user", "text": "second ask"},
        ],
    )
    assert [s.session_id for s in slices] == ["cmp-9", "cmp-9"]


def test_empty_and_unknown_event_streams_produce_no_slices():
    normalizer = TranscriptNormalizer()
    assert normalizer.from_canonical("claude_code", "/t/x.jsonl", []) == []
    assert normalizer.from_canonical("claude_code", "/t/x.jsonl", [{"kind": "nonsense"}]) == []


def test_a_thinking_only_turn_has_no_resolution():
    slices = TranscriptNormalizer().from_canonical(
        "claude_code",
        "/t/x.jsonl",
        [
            {"kind": "user", "text": "think about it"},
            {"kind": "assistant", "text": "hmm", "is_thought": True},
        ],
    )
    assert slices[0].resolution_summary == ""


def test_an_oversized_prompt_is_clipped():
    slices = TranscriptNormalizer().from_canonical(
        "claude_code", "/t/x.jsonl", [{"kind": "user", "text": "x" * 5000}]
    )
    assert slices[0].user_prompt.endswith("[truncated]")
    assert len(slices[0].user_prompt) < 5000


def test_capture_content_reads_as_a_turn_report():
    only = normalize_claude(CLAUDE_RECORDS)[0]
    content = only.to_capture_content()
    assert content.startswith("# Coding session turn — life-graph (claude_code)")
    assert "## Request" in content
    assert "## Tool sequence" in content
    assert "## Errors encountered" in content
    assert "## Resolution" in content
    assert "pytest -q" in content
    assert "sess-cc" in content
    assert content.endswith("\n")
    # Deterministic, so the capture spine's content-hash dedup recognises a re-read.
    assert content == only.to_capture_content()


def test_capture_content_of_an_empty_turn_says_so():
    content = NormalizedSessionSlice(
        session_id="s", project_name="p", agent_type="codex", user_prompt=""
    ).to_capture_content()
    assert "_(no prompt text captured)_" in content
    assert "_(session ended without a closing summary)_" in content


def test_normalize_accepts_canonical_events_with_an_agent_name():
    slices = TranscriptNormalizer().normalize(
        "codex", "/t/x.jsonl", [{"kind": "user", "text": "hello there"}]
    )
    assert slices[0].agent_type == "codex"
