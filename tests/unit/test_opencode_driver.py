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

    assert text == "Let me read the file.\n\nDone: added remove()."
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


def test_every_text_part_is_kept_so_an_early_spec_survives():
    """Task 81de2480 wrote its ## Spec and its ## Understanding in separate
    text parts; only the last was kept, so the task's spec was null."""
    from life_graph.drivers.plan_spec import _extract_spec
    from life_graph.services.proof_checks import _UNDERSTANDING_RE

    run = "\n".join(
        [
            _event("text", {"type": "text", "text": "## Spec\n**Requirements:**\nAC-1: x"}),
            _event("step_finish", {"type": "step-finish", "reason": "tool-calls"}),
            _event("text", {"type": "text", "text": "## Understanding\nChange: y"}),
        ]
    )
    text, _, _ = parse_events(run)
    assert _extract_spec(text) == "**Requirements:**\nAC-1: x"
    assert _UNDERSTANDING_RE.search(text).group(1).strip() == "Change: y"


def test_the_prompt_allows_a_new_test_file_the_task_names(tmp_path):
    prompt = OpencodeDriver._prompt(_packet(tmp_path))
    assert "change only the files the task needs, including any new test file it names." in prompt


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
@pytest.mark.asyncio
async def test_a_timed_out_run_keeps_the_steps_it_printed(tmp_path):
    fake = tmp_path / "opencode"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, time\n"
        f"print({REAL_RUN!r}, flush=True)\n"
        "time.sleep(30)\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    work = tmp_path / "work"
    work.mkdir()

    result = await OpencodeDriver(binary=str(fake)).dispatch(
        _packet(work, ["code_edit"]), work, timeout=3
    )

    assert result.success is False and "timed out" in result.error
    assert result.metadata["exit_status"] == "timeout"
    assert len(result.metadata["steps"]) == 6


def test_the_prompt_says_what_can_and_cannot_run(tmp_path, monkeypatch):
    from life_graph.services import sandbox

    monkeypatch.setattr(sandbox, "enabled", lambda: False)
    assert "cannot run tests" in OpencodeDriver._prompt(_packet(tmp_path))
    monkeypatch.setattr(sandbox, "enabled", lambda: True)
    prompt = OpencodeDriver._prompt(_packet(tmp_path, ["code_edit", "run_tests"]))
    assert "cannot run shell commands" in prompt and "lg_tests_run_tests" in prompt


def test_run_tests_is_served_over_mcp_only_with_the_sandbox(tmp_path, monkeypatch):
    from life_graph.services import sandbox

    packet = _packet(tmp_path, ["code_edit", "run_tests"])
    packet.project_context["sandbox_setup"] = "uv sync --frozen"
    monkeypatch.setattr(sandbox, "enabled", lambda: True)
    server = _config(packet, tmp_path)["mcp"]["lg_tests"]
    assert server["command"][1:] == ["-I", "-m", "life_graph.tools.run_tests_mcp"]
    assert server["environment"]["LG_RUN_TESTS_WORKDIR"] == str(tmp_path)
    assert server["environment"]["LG_RUN_TESTS_SETUP"] == "uv sync --frozen"
    assert server["environment"]["LIFE_GRAPH_VERIFIER_SANDBOX"]
    # Bash is still denied: the tests run in the sandbox, not on the host.
    assert _config(packet, tmp_path)["permission"]["bash"] == "deny"

    assert "mcp" not in _config(_packet(tmp_path, ["code_edit"]), tmp_path)
    monkeypatch.setattr(sandbox, "enabled", lambda: False)
    assert "mcp" not in _config(packet, tmp_path)


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
    assert result.success is True
    assert result.output == "Let me read the file.\n\nDone: added remove()."
    assert call["argv"][:5] == ["run", "--format", "json", "--auto", "-m"]
    assert call["stdin_closed"] is True
    assert call["config"] and not call["config"].startswith(str(work))  # not in the diff
    assert result.metadata["driver"] == "opencode"
    assert len(result.metadata["steps"]) == 6
    assert list(work.iterdir()) == []  # the driver left nothing of its own in the worktree
