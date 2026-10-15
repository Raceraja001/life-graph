"""OpenCode driver: its config (permissions are the confinement), the event
parser (shapes copied from real `opencode run --format json` 1.19 runs), and
dispatch against a fake binary.
"""

from __future__ import annotations

import json
import stat
import uuid

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.opencode import OpencodeDriver, _config, parse_events


def _packet(tmp_path, allowed_tools=None):
    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t1",
        task_type="code_change",
        instruction="add remove()",
        project_context={"path": str(tmp_path), "isolation": False},
        allowed_tools=allowed_tools,
    )


def _event(etype, part, ts=1791942724159):
    return json.dumps({"type": etype, "timestamp": ts, "sessionID": "ses_1", "part": part})


REAL_RUN = "\n".join(
    [
        _event("step_start", {"type": "step-start"}),
        _event("text", {"type": "text", "text": "Let me read the file."}),
        _event(
            "tool_use",
            {
                "type": "tool",
                "tool": "read",
                "callID": "call_1",
                "state": {
                    "status": "completed",
                    "input": {"filePath": "/w/a.mjs"},
                    "output": "1: x",
                },
            },
        ),
        _event(
            "tool_use",
            {
                "type": "tool",
                "tool": "write",
                "callID": "call_2",
                "state": {
                    "status": "error",
                    "input": {"filePath": "/etc/x"},
                    "error": "rule prevents",
                },
            },
        ),
        _event("step_finish", {"type": "step-finish", "reason": "tool-calls"}),
        _event("text", {"type": "text", "text": "Done: added remove()."}),
        _event("step_finish", {"type": "step-finish", "reason": "stop"}),
    ]
)


def test_events_become_steps_with_calls_paired_to_results():
    text, steps, meta = parse_events(REAL_RUN)

    assert text == "Done: added remove()."
    assert meta == {"turns": 2, "session_id": "ses_1"}
    assert [(s["seq"], s["kind"], s.get("tool")) for s in steps] == [
        (1, "text", None),
        (2, "tool_call", "read"),
        (3, "tool_result", "read"),
        (4, "tool_call", "write"),
        (5, "tool_result", "write"),
        (6, "text", None),
    ]
    assert json.loads(steps[1]["content"]) == {"filePath": "/w/a.mjs"}
    assert steps[2]["content"] == "1: x" and steps[2]["ref"] == "call_1"
    assert steps[4]["is_error"] is True and steps[4]["content"] == "rule prevents"
    assert steps[0]["at"].endswith("Z")


def test_an_error_event_marks_the_run_failed():
    _, steps, meta = parse_events(
        _event("error", {"name": "ProviderError", "message": "model gone"})
    )
    assert steps[0]["kind"] == "error" and "model gone" in meta["error"]


def test_config_denies_shell_web_and_anything_outside_the_worktree(tmp_path):
    perms = _config(_packet(tmp_path, ["code_read", "code_edit"]))["permission"]
    assert perms == {
        "edit": "allow",
        "bash": "deny",
        "webfetch": "deny",
        "external_directory": "deny",
    }


def test_a_read_only_persona_cannot_edit(tmp_path):
    assert _config(_packet(tmp_path, ["code_read"]))["permission"]["edit"] == "deny"


def test_config_points_an_ollama_model_at_the_local_server(tmp_path, monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "driver_opencode_model", "ollama/gpt-oss:20b")
    provider = _config(_packet(tmp_path))["provider"]["ollama"]
    assert provider["options"]["baseURL"] == settings.driver_opencode_ollama_base
    assert provider["models"] == {"gpt-oss:20b": {}}


@pytest.mark.asyncio
async def test_unavailable_without_the_binary(tmp_path):
    assert await OpencodeDriver(binary=str(tmp_path / "no-opencode")).available() is False


@pytest.mark.asyncio
async def test_dispatch_runs_headless_with_config_outside_the_worktree(tmp_path):
    # A fake `opencode` that records how it was called, then prints events.
    seen = tmp_path / "seen.json"
    fake = tmp_path / "opencode"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"json.dump({{'argv': sys.argv[1:], 'config': os.environ.get('OPENCODE_CONFIG'),"
        f" 'stdin_closed': sys.stdin.read() == ''}}, open({str(seen)!r}, 'w'))\n"
        f"print({REAL_RUN!r})\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    work = tmp_path / "work"
    work.mkdir()

    result = await OpencodeDriver(binary=str(fake)).dispatch(_packet(work, ["code_edit"]), work)

    call = json.loads(seen.read_text())
    assert result.success is True and result.output == "Done: added remove()."
    assert call["argv"][:5] == ["run", "--format", "json", "--auto", "-m"]
    assert call["stdin_closed"] is True
    assert call["config"] and not call["config"].startswith(str(work))  # not in the diff
    assert result.metadata["driver"] == "opencode"
    assert len(result.metadata["steps"]) == 6
    assert list(work.iterdir()) == []  # the driver left nothing of its own in the worktree
