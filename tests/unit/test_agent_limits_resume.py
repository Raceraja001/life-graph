"""Phase 3b part 1: plan-limit parsing, the Codex probe, and resume argv per CLI.

Fixture-only: the Claude rate_limit_event lines are race-app's
(__fixtures__/claude-code/rate-limit-windows.jsonl, built from Claude Code
2.1.328's stream); the Codex app-server replies follow the shapes race-app's
port of stablyai/orca reads. Resume flags were verified with ``--help`` of
codex-cli 0.172.0, gemini-cli 0.71.1 and Claude Code 2.1.328, not by a
signed-in resume.
"""

from __future__ import annotations

import json
import stat
import sys
import uuid
from typing import TYPE_CHECKING

import pytest

from life_graph.config import settings
from life_graph.drivers import cli_run
from life_graph.drivers.base import ContextPacket
from life_graph.drivers.cli_driver import build_resume_prompt
from life_graph.drivers.codex import CodexDriver, codex_resume_argv
from life_graph.drivers.gemini import GeminiDriver, gemini_argv
from life_graph.services.agent_accounts import limits

if TYPE_CHECKING:
    from pathlib import Path

CLAUDE_STREAM = "\n".join(
    [
        '{"type":"system","subtype":"init","session_id":"5f0c2b1e-0000-4000-8000-000000000001"}',
        '{"type":"rate_limit_event","rate_limit_info":{"status":"allowed","resetsAt":1795708800,'
        '"rateLimitType":"five_hour","utilization":0.42,"unifiedWindows":{"seven_day":'
        '{"utilization":0.71,"resetsAt":1796140800,"status":"allowed"},"five_hour":'
        '{"utilization":0.42,"resetsAt":1795708800},"seven_day_opus":{"utilization":0.05,'
        '"resetsAt":1796140800}}}}',
        '{"type":"rate_limit_event","rate_limit_info":{"status":"allowed_warning",'
        '"resetsAt":1796140800,"rateLimitType":"seven_day","utilization":0.91,"unifiedWindows":'
        '{"five_hour":{"utilization":0.44,"resetsAt":1795708800,"status":"allowed"},"seven_day":'
        '{"utilization":0.91,"resetsAt":1796140800,"status":"allowed_warning"}}}}',
        '{"type":"result","subtype":"success","is_error":false,"result":"OK"}',
    ]
)


# ── Limits ───────────────────────────────────────────────────


def test_claude_windows_take_the_last_rate_limit_event():
    windows, info = limits.claude_windows(CLAUDE_STREAM)
    assert [w["window"] for w in windows] == ["five_hour", "seven_day"]
    assert windows[0]["used_percent"] == 44.0 and windows[0]["status"] == "allowed"
    assert windows[1]["used_percent"] == 91.0 and windows[1]["status"] == "warning"
    assert windows[1]["resets_at"] == "2026-12-01T16:00:00Z"
    assert info == {"status": "allowed_warning", "resets_at": "2026-12-01T16:00:00Z"}


def test_claude_rejected_and_single_window_forms():
    info = {"status": "rejected", "rateLimitType": "five_hour", "utilization": 1.02}
    [window] = limits.claude_rate_limit_info(info)
    assert window["window"] == "five_hour" and window["status"] == "rejected"
    assert limits.claude_windows("no events here\n") == ([], None)


def test_codex_windows_classify_by_duration_with_the_legacy_fallback():
    swapped = [
        {"slot": "primary", "used_percent": 20, "window_minutes": 10080, "resets_at": 1796140800},
        {"slot": "secondary", "used_percent": 100, "window_minutes": 299, "resets_at": None},
    ]
    windows = limits.codex_windows(swapped)
    assert [(w["window"], w["used_percent"]) for w in windows] == [
        ("five_hour", 100.0),
        ("seven_day", 20.0),
    ]
    assert windows[0]["status"] == "rejected" and windows[1]["resets_at"] == "2026-12-01T16:00:00Z"
    legacy = [{"slot": "primary", "used_percent": 5, "window_minutes": None, "resets_at": None}]
    assert limits.codex_windows(legacy)[0]["window"] == "five_hour"


def test_windows_from_metadata_per_driver():
    md = {"rate_limits": [{"slot": "primary", "used_percent": 1, "window_minutes": 300}]}
    assert limits.windows_from_metadata("codex", md)[0]["window"] == "five_hour"
    claude, _ = limits.claude_windows(CLAUDE_STREAM)
    assert limits.windows_from_metadata("claude_code", {"rate_limits": claude}) == claude
    assert limits.windows_from_metadata("gemini", {}) == []


def test_probe_result_windows_reads_the_camel_case_reply():
    result = {
        "rateLimits": {
            "primary": {"usedPercent": 37, "windowDurationMins": 300, "resetsAt": 1795708800},
            "secondary": {"usedPercent": 12, "windowDurationMins": 10080, "resetsAt": 1796140800},
        }
    }
    windows = limits.probe_result_windows(result)
    assert [(w["window"], w["used_percent"]) for w in windows] == [
        ("five_hour", 37.0),
        ("seven_day", 12.0),
    ]
    cap = {"rateLimits": {"individualLimit": {"remainingPercent": 25, "resetsAt": 1796140800}}}
    assert limits.probe_result_windows(cap)[0] == {
        "window": "monthly",
        "used_percent": 75.0,
        "window_minutes": None,
        "resets_at": "2026-12-01T16:00:00Z",
        "status": None,
    }


def _fake_app_server(tmp_path: Path, account: dict | None, *, error: str | None = None) -> Path:
    """A stand-in ``codex app-server``: answers initialize/account/rateLimits on stdio."""
    fake = tmp_path / "codex"
    limits_reply = {
        "rateLimits": {
            "primary": {"usedPercent": 50, "windowDurationMins": 300, "resetsAt": 1795708800}
        }
    }
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"account = {json.dumps(account)!r}\n"
        f"limits = {json.dumps(limits_reply)!r}\n"
        f"error = {error!r}\n"
        "assert sys.argv[1:] == ['app-server'], sys.argv\n"
        "for line in sys.stdin:\n"
        "    msg = json.loads(line)\n"
        "    if 'id' not in msg: continue\n"
        "    if msg['method'] == 'initialize': out = {'result': {}}\n"
        "    elif error: out = {'error': {'message': error}}\n"
        "    elif msg['method'] == 'account/read': out = {'result': {'account': json.loads(account)}}\n"
        "    else: out = {'result': json.loads(limits)}\n"
        "    out['id'] = msg['id']\n"
        "    print('not json noise'); print(json.dumps(out), flush=True)\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


async def test_codex_probe_reads_windows_from_a_signed_in_home(tmp_path):
    fake = _fake_app_server(tmp_path, {"type": "chatgpt", "planType": "pro"})
    result = await limits.probe_codex(str(fake), {"PATH": "/usr/bin:/bin"})
    assert result["kind"] == "windows"
    assert result["windows"][0]["window"] == "five_hour"
    assert result["windows"][0]["used_percent"] == 50.0


async def test_codex_probe_api_key_and_signed_out_are_unavailable(tmp_path):
    api = await limits.probe_codex(str(_fake_app_server(tmp_path, {"type": "apiKey"})), {})
    assert api == {"kind": "unavailable", "reason": limits.API_KEY_REASON}
    out = await limits.probe_codex(str(_fake_app_server(tmp_path, None)), {})
    assert out == {"kind": "unavailable", "reason": limits.SIGNED_OUT_REASON}
    err = await limits.probe_codex(
        str(_fake_app_server(tmp_path, None, error="token sk-abcdefghijklmnop 401")), {}
    )
    assert err["kind"] == "unavailable" and "sk-" not in repr(err)


async def test_codex_probe_times_out_and_kills_the_child(tmp_path):
    fake = tmp_path / "codex"
    fake.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    result = await limits.probe_codex(str(fake), {}, init_timeout=0.3)
    assert result == {"kind": "error", "error": "Codex did not answer in time"}
    missing = await limits.probe_codex(str(tmp_path / "nope"), {})
    assert missing["kind"] == "unavailable"


# ── Resume argv ──────────────────────────────────────────────


def test_codex_resume_argv():
    argv = codex_resume_argv("/bin/codex", "0199c0de-thread", read_only=True, model="gpt-5")
    assert argv[:8] == [
        "/bin/codex",
        "exec",
        "--json",
        "--color",
        "never",
        "-s",
        "read-only",
        "resume",
    ]
    tail = argv[8:]
    assert tail[-2:] == ["0199c0de-thread", "-"]  # thread id, prompt on stdin
    assert "--ignore-user-config" in tail and 'sandbox_mode="read-only"' in tail
    assert 'approval_policy="never"' in tail and "features.plugins=false" in tail
    assert tail[tail.index("-m") + 1] == "gpt-5"
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv
    edit = codex_resume_argv("/bin/codex", "t", read_only=False, in_git_repo=False)
    assert 'sandbox_mode="workspace-write"' in edit and "--skip-git-repo-check" in edit


def test_gemini_resume_argv():
    argv = gemini_argv("/bin/gemini", read_only=False, resume="3f2b-uuid")
    assert argv[argv.index("--resume") + 1] == "3f2b-uuid"
    assert argv[-2:] == ["-p", "Do the task described above."]
    assert "--resume" not in gemini_argv("/bin/gemini", read_only=False)
    assert "--yolo" not in argv


def test_resume_prompt_keeps_the_read_only_line():
    assert build_resume_prompt(" fix the test ", read_only=False) == "fix the test"
    assert "read-only" in build_resume_prompt("look", read_only=True)


def _recording_cli(tmp_path: Path, name: str, events: str) -> Path:
    seen = tmp_path / "seen.json"
    fake = tmp_path / name
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "data = {'argv': sys.argv[1:], 'stdin': sys.stdin.read(), 'env': dict(os.environ)}\n"
        f"json.dump(data, open({str(seen)!r}, 'w'))\n"
        f"sys.stdout.write({events!r})\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


def _packet(work: Path) -> ContextPacket:
    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t1",
        task_type="code_change",
        instruction="ORIGINAL INSTRUCTION",
        project_context={"path": str(work), "isolation": False},
        memories=[{"content": "MEMORY-SECRET"}],
    )


@pytest.fixture(autouse=True)
def _no_accounts(monkeypatch):
    monkeypatch.setattr(settings, "driver_accounts_enabled", False)
    cli_run.clear_probe_cache()


async def test_codex_resume_runs_resume_with_the_feedback_on_stdin(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_allow_host_shell", True)
    events = (
        '{"type":"thread.started","thread_id":"0199c0de-0000-7000-8000-00000000c0de"}\n'
        '{"type":"item.completed","item":{"id":"i","type":"agent_message","text":"fixed"}}\n'
        '{"type":"turn.completed","usage":{}}\n'
    )
    fake = _recording_cli(tmp_path, "codex", events)
    work = tmp_path / "work"
    (work / ".git").mkdir(parents=True)
    result = await CodexDriver(binary=str(fake)).resume(
        _packet(work), work, "0199c0de-0000-7000-8000-00000000c0de", "The test still fails."
    )
    seen = json.loads((tmp_path / "seen.json").read_text())
    assert result.success, result.error
    assert seen["argv"][:7] == [
        "exec",
        "--json",
        "--color",
        "never",
        "-s",
        "workspace-write",
        "resume",
    ]
    assert seen["argv"][-2:] == ["0199c0de-0000-7000-8000-00000000c0de", "-"]
    assert seen["stdin"] == "The test still fails."
    assert "MEMORY-SECRET" not in seen["stdin"] and "ORIGINAL" not in seen["stdin"]
    assert result.metadata["resumed_from"] == "0199c0de-0000-7000-8000-00000000c0de"


async def test_resume_refuses_something_that_is_not_a_session_id(tmp_path):
    for bad in ("", "--last", "../x", "a b c d e f g h"):
        result = await GeminiDriver(binary="gemini").resume(_packet(tmp_path), tmp_path, bad, "x")
        assert result.metadata["exit_status"] == "bad_session"


async def test_gemini_resume_passes_the_session(tmp_path, monkeypatch):
    events = (
        '{"type":"init","session_id":"s-1234567890","model":"gemini-2.5-pro"}\n'
        '{"type":"message","role":"assistant","content":"ok"}\n'
        '{"type":"result","status":"success","stats":{}}\n'
    )
    fake = _recording_cli(tmp_path, "gemini", events)
    work = tmp_path / "work"
    work.mkdir()
    result = await GeminiDriver(binary=str(fake)).resume(_packet(work), work, "s-1234567890", "go")
    seen = json.loads((tmp_path / "seen.json").read_text())
    assert result.success, result.error
    assert seen["argv"][seen["argv"].index("--resume") + 1] == "s-1234567890"


async def test_claude_resume_adds_the_flag_and_is_host_only(tmp_path, monkeypatch):
    from life_graph.drivers import claude_code
    from life_graph.drivers.claude_code import ClaudeCodeDriver

    stream = (
        CLAUDE_STREAM + '\n{"type":"result","is_error":false,"result":"done","session_id":"x"}\n'
    )
    fake = _recording_cli(tmp_path, "claude", stream)
    monkeypatch.setattr(settings, "driver_claude_sandbox", "none")
    work = tmp_path / "work"
    work.mkdir()
    sid = "5f0c2b1e-0000-4000-8000-000000000001"
    result = await ClaudeCodeDriver(binary=str(fake)).resume(
        _packet(work), work, sid, "and the docs"
    )
    seen = json.loads((tmp_path / "seen.json").read_text())
    assert result.success, result.error
    argv = seen["argv"]
    assert argv[argv.index("-p") + 1] == "and the docs"
    assert argv[argv.index("--resume") + 1] == sid
    assert [w["window"] for w in result.metadata["rate_limits"]] == ["five_hour", "seven_day"]

    monkeypatch.setattr(claude_code.sandbox, "driver_sandbox_enabled", lambda: True)
    refused = await ClaudeCodeDriver(binary=str(fake)).resume(_packet(work), work, sid, "x")
    assert refused.metadata["exit_status"] == "resume_unsupported"


async def test_claude_rate_limited_failure_is_classified(tmp_path, monkeypatch):
    from life_graph.drivers.claude_code import ClaudeCodeDriver

    stream = (
        '{"type":"rate_limit_event","rate_limit_info":{"status":"rejected","resetsAt":1795708800,'
        '"rateLimitType":"five_hour","utilization":1.0}}\n'
        '{"type":"result","is_error":true,"result":"Claude usage limit reached"}\n'
    )
    fake = _recording_cli(tmp_path, "claude", stream)
    monkeypatch.setattr(settings, "driver_claude_sandbox", "none")
    work = tmp_path / "work"
    work.mkdir()
    result = await ClaudeCodeDriver(binary=str(fake)).dispatch(_packet(work), work)
    failure = result.metadata["failure"]
    assert result.success is False
    assert failure["kind"] == "rate_limited" and failure["resets_at"] == "2026-11-26T16:00:00Z"
