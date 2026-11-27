"""The codex and gemini drivers (Phase 3a): argv, event parsing, failure
classification, the host run (env allowlist, stdin prompt, timeout kill),
detection, registration and selection.

The event streams in tests/fixtures/cli are not recorded runs: both CLIs were
signed out on the workstation (2026-11-27). ``codex_edit/plan/rate_limit/
token_count.jsonl`` are race-app's synthesized fixtures (built from codex-cli
0.172.0's event schema); ``codex_auth.jsonl`` and ``gemini_*.jsonl`` follow
the shapes in codex-cli 0.172.0 and gemini-cli 0.71.1 (its StreamJsonFormatter,
read from the installed bundle). Replace them with recorded runs once signed in.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.drivers import cli_run
from life_graph.drivers.base import ContextPacket
from life_graph.drivers.cli_driver import build_prompt, needs_read_only
from life_graph.drivers.cli_failure import (
    classify_failure,
    normalize_reset,
    reset_from_text,
    scrub_secrets,
)
from life_graph.drivers.codex import CodexDriver, CodexEventParser, codex_argv
from life_graph.drivers.gemini import (
    EXCLUDED_TOOLS,
    NO_MCP_SERVER,
    GeminiDriver,
    GeminiEventParser,
    gemini_argv,
)
from life_graph.drivers.steps import number

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "cli"
NOW = datetime(2026, 11, 27, 9, 0, tzinfo=UTC)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def _packet(path: Path | None = None, *, task_type="code_change", allowed_tools=None, **kw):
    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t1",
        task_type=task_type,
        instruction="append 'fixture ok' to README.md",
        project_context={"path": str(path), "isolation": False} if path else {},
        allowed_tools=allowed_tools,
        **kw,
    )


@pytest.fixture(autouse=True)
def _fresh_probe_cache():
    cli_run.clear_probe_cache()
    yield
    cli_run.clear_probe_cache()


def _fake_cli(tmp_path: Path, name: str, body: str) -> Path:
    """An executable Python script standing in for the CLI."""
    fake = tmp_path / name
    fake.write_text(f"#!{sys.executable}\n{body}")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


def _recording_cli(tmp_path: Path, name: str, events: str, exit_code: int = 0) -> Path:
    """A fake CLI that records argv, stdin, cwd and env, then prints *events*."""
    seen = tmp_path / "seen.json"
    return _fake_cli(
        tmp_path,
        name,
        "import json, os, sys\n"
        "data = {'argv': sys.argv[1:], 'stdin': sys.stdin.read(), 'cwd': os.getcwd(),"
        " 'env': dict(os.environ)}\n"
        "sp = os.environ.get('GEMINI_CLI_SYSTEM_SETTINGS_PATH')\n"
        "data['system_settings'] = json.load(open(sp)) if sp else None\n"
        f"json.dump(data, open({str(seen)!r}, 'w'))\n"
        f"sys.stdout.write({events!r})\n"
        "sys.stdout.flush()\n"
        "sys.stderr.write('note on stderr\\n')\n"
        f"sys.exit({exit_code})\n",
    )


def _seen(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "seen.json").read_text())


# ── Codex: argv ──────────────────────────────────────────────


def test_codex_argv_maps_the_task_mode_to_the_sandbox():
    edit = codex_argv("/bin/codex", read_only=False)
    plan = codex_argv("/bin/codex", read_only=True, model="gpt-5.3-codex")

    assert edit[:6] == ["/bin/codex", "exec", "--json", "--color", "never", "--ignore-user-config"]
    assert edit[edit.index("-s") + 1] == "workspace-write"
    assert plan[plan.index("-s") + 1] == "read-only"
    assert plan[plan.index("-m") + 1] == "gpt-5.3-codex" and "-m" not in edit
    for argv in (edit, plan):
        assert argv[-1] == "-"  # prompt on stdin
        assert 'approval_policy="never"' in argv
        assert "sandbox_workspace_write.network_access=false" in argv
        assert 'web_search="disabled"' in argv
        assert "features.browser_use=false" in argv and "features.computer_use=false" in argv
        assert "--skip-git-repo-check" not in argv
        for never in (
            "--dangerously-bypass-approvals-and-sandbox",
            "--add-dir",
            "--cd",
            "-C",
            "--worktree",
            "--remote",
            "--trust",
            "danger-full-access",
            "--disable",
        ):
            assert never not in argv


def test_codex_skips_the_git_check_only_outside_a_repository():
    assert "--skip-git-repo-check" in codex_argv("codex", read_only=False, in_git_repo=False)


def test_a_plan_or_a_persona_without_write_tools_runs_read_only(tmp_path):
    assert needs_read_only(_packet(task_type="plan")) is True
    assert needs_read_only(_packet(allowed_tools=["file_read", "code_search"])) is True
    assert needs_read_only(_packet(allowed_tools=["file_read", "code_edit"])) is False
    assert needs_read_only(_packet()) is False  # unscoped


# ── Codex: events ────────────────────────────────────────────


def test_codex_edit_stream_becomes_steps_summary_thread_and_usage():
    parser = CodexEventParser()
    parser.feed_text(_fixture("codex_edit.jsonl"))
    run = parser.run
    steps = number(run.steps, tool_names=True)

    assert run.session_id == "0199c0de-0000-7000-8000-00000000c0de"
    assert run.completed is True and run.turns == 1
    assert run.texts == ["Appended 'fixture ok' to README.md."]
    assert run.usage == {"input_tokens": 12840, "cached_input_tokens": 11008, "output_tokens": 312}
    assert [(s["kind"], s.get("tool")) for s in steps] == [
        ("thinking", None),  # reasoning
        ("thinking", None),  # todo list (the identical update is not repeated)
        ("tool_call", "shell"),
        ("tool_result", "shell"),
        ("thinking", None),  # todo list, first item done
        ("tool_call", "apply_patch"),
        ("tool_result", "apply_patch"),
        ("tool_call", "docs.search"),
        ("tool_result", "docs.search"),
        ("tool_call", "web_search"),
        ("tool_result", "web_search"),
        ("thinking", None),  # todo list, all done
        ("text", None),
    ]
    assert json.loads(steps[2]["content"]) == {"command": "bash -lc 'cat README.md'"}
    assert steps[3]["content"] == "# demo\n" and steps[3]["ref"] == "item_2"
    assert "is_error" not in steps[3]
    assert json.loads(steps[5]["content"]) == {"changes": [{"path": "README.md", "kind": "update"}]}
    assert steps[8]["content"] == "no hits"
    assert [s["seq"] for s in steps] == list(range(1, 14))


def test_a_failed_command_is_an_error_result():
    parser = CodexEventParser()
    parser.feed(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "id": "i9",
                    "type": "command_execution",
                    "command": "pytest",
                    "aggregated_output": "1 failed",
                    "exit_code": 1,
                    "status": "completed",
                },
            }
        )
    )
    call, result = parser.run.steps
    assert call["kind"] == "tool_call" and result["is_error"] is True


def test_codex_ignores_garbage_and_unknown_lines():
    parser = CodexEventParser()
    for line in ("", "not json", "{broken", "[1,2]", '{"type":"something.new"}', '{"x":1}'):
        assert parser.feed(line) == []
    assert parser.run.steps == [] and parser.run.completed is False


def test_codex_rate_limit_snapshot_and_turn_failure_classify_as_rate_limited():
    parser = CodexEventParser()
    parser.feed_text(_fixture("codex_rate_limit.jsonl"))
    run = parser.run

    assert run.completed is False and run.rate_limit_rejected is True
    assert run.rate_limits[0] == {
        "slot": "primary",
        "used_percent": 100.0,
        "window_minutes": 300,
        "resets_at": "2026-11-26T16:00:00Z",
    }
    failure = classify_failure(
        final_error=run.final_error,
        warnings=run.warnings,
        rate_limit_resets=run.rate_limit_resets,
        rejected=run.rate_limit_rejected,
        now=NOW,
    )
    # The structured snapshot wins over the "try again in 2 hours 5 minutes" text.
    assert failure["kind"] == "rate_limited"
    assert failure["resets_at"] == "2026-11-26T16:00:00Z"
    assert "usage limit" in failure["message"]


def test_codex_token_count_arrives_in_any_envelope():
    lines = _fixture("codex_token_count.jsonl").splitlines()
    seen = []
    for line in lines:
        parser = CodexEventParser()
        parser.feed(line)
        seen.append([w["used_percent"] for w in parser.run.rate_limits])
    assert seen == [[42.0, 71.0], [10.0, 5.0], [20.0], []]


def test_codex_signed_out_classifies_as_auth_with_the_login_hint():
    parser = CodexEventParser()
    parser.feed_text(_fixture("codex_auth.jsonl"))
    failure = classify_failure(
        final_error=parser.run.final_error,
        warnings=parser.run.warnings,
        login_hint="run `codex login`",
    )
    assert failure["kind"] == "auth" and failure["hint"] == "run `codex login`"


# ── Failure text ─────────────────────────────────────────────


def test_relative_and_absolute_resets():
    assert reset_from_text("try again in 2 hours 5 minutes", NOW) == "2026-11-27T11:05:00Z"
    assert reset_from_text("try again in 1 day and 3h", NOW) == "2026-11-28T12:00:00Z"
    assert reset_from_text("Please retry in 23.5s.", NOW) == "2026-11-27T09:00:23.500000Z"
    assert reset_from_text("limit resets at 2026-11-28T00:00:00Z", NOW) == "2026-11-28T00:00:00Z"
    assert reset_from_text("no time here", NOW) is None
    assert normalize_reset(1795708800) == normalize_reset(1795708800000) == "2026-11-26T16:00:00Z"
    assert normalize_reset(12) is None and normalize_reset(True) is None


def test_429_from_stderr_is_rate_limited_and_other_is_other():
    stderr = '{"type":"x"}\nERROR: exceeded retry limit, last status: 429 Too Many Requests\n'
    assert classify_failure(stderr=stderr)["kind"] == "rate_limited"
    other = classify_failure(final_error="", stderr="segfault\n", exit_code=139)
    assert other == {"kind": "other", "message": "segfault"}
    assert classify_failure(exit_code=2) == {"kind": "other", "message": "exited with code 2"}


def test_failure_messages_never_carry_a_token():
    text = "401 Unauthorized: invalid api key sk-proj-ABCDEFGHIJKLMNOP1234 (Bearer abcdefghij123)"
    failure = classify_failure(final_error=text)
    assert failure["kind"] == "auth"
    assert "sk-proj" not in failure["message"] and "abcdefghij123" not in failure["message"]
    assert "AIza" not in scrub_secrets("key AIzaSyA1234567890abcdefghijklmnop")
    assert len(classify_failure(final_error="x" * 500 + " boom")["message"]) <= 200


# ── Gemini: argv, settings, events ───────────────────────────


def test_gemini_argv_maps_the_task_mode_to_the_approval_mode():
    edit = gemini_argv("/bin/gemini", read_only=False)
    plan = gemini_argv("/bin/gemini", read_only=True, model="gemini-3-flash")

    assert edit[:3] == ["/bin/gemini", "-o", "stream-json"]
    assert edit[edit.index("--approval-mode") + 1] == "auto_edit"
    assert plan[plan.index("--approval-mode") + 1] == "plan"
    assert plan[plan.index("-m") + 1] == "gemini-3-flash" and "-m" not in edit
    for argv in (edit, plan):
        assert argv[argv.index("--allowed-mcp-server-names") + 1] == NO_MCP_SERVER
        assert argv[-2] == "-p"  # the task itself goes on stdin
        for never in ("--yolo", "-y", "yolo", "-w", "--worktree", "--skip-trust", "-s"):
            assert never not in argv


def test_gemini_stream_merges_deltas_and_pairs_tool_results():
    parser = GeminiEventParser()
    parser.feed_text(_fixture("gemini_edit.jsonl"))
    parser.finish()
    run = parser.run
    steps = number(run.steps, tool_names=True)

    assert run.session_id == "5f0c1d2e-3a4b-4c5d-8e6f-7a8b9c0d1e2f"
    assert run.model == "gemini-3-pro" and run.completed is True
    assert run.texts == ["I'll read README.md first.", "Appended 'fixture ok' to README.md."]
    assert run.usage == {
        "input_tokens": 8800,
        "cached_input_tokens": 4096,
        "output_tokens": 320,
        "total_tokens": 9120,
    }
    assert [(s["kind"], s.get("tool")) for s in steps] == [
        ("text", None),
        ("tool_call", "read_file"),
        ("tool_result", "read_file"),
        ("tool_call", "read_file"),
        ("tool_result", "read_file"),
        ("tool_call", "replace"),
        ("tool_result", "replace"),
        ("text", None),
    ]
    assert steps[0]["at"] == "2026-11-27T09:00:01.000Z"
    assert json.loads(steps[1]["content"]) == {"file_path": "README.md"}
    assert steps[4]["is_error"] is True and "workspace directories" in steps[4]["content"]


def test_gemini_text_cut_off_mid_stream_is_kept():
    parser = GeminiEventParser()
    parser.feed('{"type":"message","role":"assistant","content":"half a sen","delta":true}')
    parser.finish()
    assert parser.run.texts == ["half a sen"] and parser.run.completed is False


def test_gemini_quota_classifies_as_rate_limited_with_the_retry_time():
    parser = GeminiEventParser()
    parser.feed_text(_fixture("gemini_quota.jsonl"))
    run = parser.run
    failure = classify_failure(final_error=run.final_error, warnings=run.warnings, now=NOW)
    assert run.completed is False
    assert failure["kind"] == "rate_limited"
    assert failure["resets_at"] == "2026-11-27T09:00:23.500000Z"


async def test_gemini_login_check_looks_only_for_the_login_file_or_a_key(tmp_path):
    driver = GeminiDriver()
    assert await driver.login_check("gemini", {"HOME": str(tmp_path)}) is False
    assert await driver.login_check("gemini", {"HOME": str(tmp_path), "GEMINI_API_KEY": "k"})
    (tmp_path / ".gemini").mkdir()
    creds = tmp_path / ".gemini" / "oauth_creds.json"
    creds.write_text("{}")
    creds.chmod(0)  # existence is enough; it is never opened
    assert await driver.login_check("gemini", {"HOME": str(tmp_path)}) is True


# ── The prompt ───────────────────────────────────────────────


def test_the_prompt_never_carries_personal_data_even_when_not_private(tmp_path):
    packet = _packet(
        tmp_path,
        persona_system_prompt="You are code-fixer.",
        private=False,
        memories=[{"content": "MEMORY-SECRET"}],
        preferences=[{"key": "PREF-SECRET"}],
        procedures=[{"name": "PROC-SECRET"}],
    )
    packet.project_context["name"] = "demo"
    prompt = build_prompt(packet, read_only=False)
    assert prompt.startswith("You are code-fixer.")
    assert packet.instruction in prompt and '"name": "demo"' in prompt
    for secret in ("MEMORY-SECRET", "PREF-SECRET", "PROC-SECRET", str(tmp_path)):
        assert secret not in prompt
    assert "read-only" in build_prompt(packet, read_only=True)


# ── Dispatch against a fake CLI ──────────────────────────────


async def test_codex_dispatch_runs_in_the_workdir_with_an_allowlisted_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_allow_host_shell", True)
    monkeypatch.setenv("LIFE_GRAPH_DATABASE_URL", "postgresql://secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-pass")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    fake = _recording_cli(tmp_path, "codex", _fixture("codex_edit.jsonl"))
    work = tmp_path / "work"
    work.mkdir()
    (work / ".git").mkdir()

    result = await CodexDriver(binary=str(fake)).dispatch(_packet(work), work)

    call = _seen(tmp_path)
    assert result.success is True, result.error
    assert result.output == "Appended 'fixture ok' to README.md."
    assert result.cost_usd == 0.0
    assert call["argv"][:2] == ["exec", "--json"] and call["argv"][-1] == "-"
    assert call["argv"][call["argv"].index("-s") + 1] == "workspace-write"
    assert "--skip-git-repo-check" not in call["argv"]
    assert "append 'fixture ok'" in call["stdin"]
    assert Path(call["cwd"]) == work
    assert "LIFE_GRAPH_DATABASE_URL" not in call["env"] and "OPENAI_API_KEY" not in call["env"]
    assert call["env"]["CODEX_HOME"] == str(tmp_path / "codex-home")
    assert call["env"]["PATH"].split(os.pathsep)[0] == str(tmp_path)  # the CLI's own dir
    meta = result.metadata
    assert meta["driver"] == "codex" and meta["billing"] == "subscription"
    assert meta["session_id"] == "0199c0de-0000-7000-8000-00000000c0de"
    assert meta["usage"]["output_tokens"] == 312
    assert meta["exit_status"] == "ok" and meta["sandbox"] == "workspace-write"
    assert meta["boundary"] == "host" and meta["read_only"] is False
    assert len(meta["steps"]) == 13
    assert sorted(p.name for p in work.iterdir()) == [".git"]  # nothing of the driver's own


async def test_codex_plan_dispatch_is_read_only(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_allow_host_shell", True)
    fake = _recording_cli(tmp_path, "codex", _fixture("codex_plan.jsonl"))
    work = tmp_path / "work"
    work.mkdir()

    result = await CodexDriver(binary=str(fake)).dispatch(_packet(work, task_type="plan"), work)

    argv = _seen(tmp_path)["argv"]
    assert result.success is True
    assert argv[argv.index("-s") + 1] == "read-only"
    assert "--skip-git-repo-check" in argv  # no .git in this directory
    assert result.output.startswith("1. Open README.md")


async def test_codex_is_refused_on_the_host_without_the_host_shell(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_allow_host_shell", False)
    fake = _recording_cli(tmp_path, "codex", _fixture("codex_edit.jsonl"))

    result = await CodexDriver(binary=str(fake)).dispatch(_packet(tmp_path), tmp_path)

    assert result.success is False
    assert result.metadata["exit_status"] == "refused_host_shell"
    assert "driver_allow_host_shell" in result.error
    assert not (tmp_path / "seen.json").exists()  # never started


async def test_codex_rate_limited_run_reports_the_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_allow_host_shell", True)
    fake = _recording_cli(tmp_path, "codex", _fixture("codex_rate_limit.jsonl"), exit_code=1)

    result = await CodexDriver(binary=str(fake)).dispatch(_packet(tmp_path), tmp_path, now=NOW)

    assert result.success is False
    assert result.metadata["exit_status"] == "rate_limited"
    assert result.metadata["failure"]["resets_at"] == "2026-11-26T16:00:00Z"
    assert "resets 2026-11-26T16:00:00Z" in result.error
    assert result.metadata["rate_limits"][0]["used_percent"] == 100.0


async def test_codex_signed_out_run_says_how_to_sign_in(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_allow_host_shell", True)
    fake = _recording_cli(tmp_path, "codex", _fixture("codex_auth.jsonl"), exit_code=1)

    result = await CodexDriver(binary=str(fake)).dispatch(_packet(tmp_path), tmp_path)

    assert result.metadata["exit_status"] == "auth"
    assert "codex login" in result.error


async def test_a_zero_exit_without_a_completed_turn_is_not_success(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_allow_host_shell", True)
    fake = _recording_cli(tmp_path, "codex", '{"type":"thread.started","thread_id":"t"}\n')

    result = await CodexDriver(binary=str(fake)).dispatch(_packet(tmp_path), tmp_path)

    assert result.success is False and result.metadata["exit_status"] == "failed"
    assert result.metadata["session_id"] == "t"


async def test_a_timeout_kills_the_whole_process_group_and_keeps_the_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_allow_host_shell", True)
    pidfile = tmp_path / "child.pid"
    first_lines = "\n".join(_fixture("codex_edit.jsonl").splitlines()[:6]) + "\n"
    fake = _fake_cli(
        tmp_path,
        "codex",
        "import subprocess, sys, time\n"
        "sys.stdin.read()\n"
        # A grandchild, like a test server the agent started.
        f"child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pidfile)!r}, 'w').write(str(child.pid))\n"
        f"sys.stdout.write({first_lines!r}); sys.stdout.flush()\n"
        "time.sleep(60)\n",
    )
    started = time.monotonic()

    result = await CodexDriver(binary=str(fake)).dispatch(_packet(tmp_path), tmp_path, timeout=3)

    assert time.monotonic() - started < 20
    assert result.success is False and result.metadata["exit_status"] == "timeout"
    assert "timed out after 3s" in result.error
    assert [s["kind"] for s in result.metadata["steps"]][:3] == [
        "thinking",
        "thinking",
        "tool_call",
    ]
    child_pid = int(pidfile.read_text())
    for _ in range(50):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        # A zombie still answers signal 0; reap-free check via /proc state.
        status = Path(f"/proc/{child_pid}/stat")
        if status.exists() and status.read_text().split()[2] == "Z":
            break
        time.sleep(0.1)
    else:
        pytest.fail("the CLI's child survived the timeout")


async def test_gemini_dispatch_writes_run_scoped_settings_and_no_shell(tmp_path):
    fake = _recording_cli(tmp_path, "gemini", _fixture("gemini_edit.jsonl"))
    work = tmp_path / "work"
    work.mkdir()

    result = await GeminiDriver(binary=str(fake)).dispatch(_packet(work), work)

    call = _seen(tmp_path)
    assert result.success is True, result.error
    assert result.output == "I'll read README.md first.\n\nAppended 'fixture ok' to README.md."
    assert call["argv"][:2] == ["-o", "stream-json"]
    assert "append 'fixture ok'" in call["stdin"]
    assert call["system_settings"]["tools"]["exclude"] == list(EXCLUDED_TOOLS)
    assert call["system_settings"]["hooksConfig"] == {"enabled": False}
    settings_path = Path(call["env"]["GEMINI_CLI_SYSTEM_SETTINGS_PATH"])
    assert not settings_path.exists()  # removed after the run
    assert not str(settings_path).startswith(str(work))  # never in the diff
    meta = result.metadata
    assert meta["session_id"] == "5f0c1d2e-3a4b-4c5d-8e6f-7a8b9c0d1e2f"
    assert meta["model"] == "gemini-3-pro" and meta["approval_mode"] == "auto_edit"
    assert meta["steps"][2]["tool"] == "read_file"  # filled from its call
    assert list(work.iterdir()) == []


async def test_gemini_quota_dispatch_is_rate_limited(tmp_path):
    fake = _recording_cli(tmp_path, "gemini", _fixture("gemini_quota.jsonl"), exit_code=1)

    result = await GeminiDriver(binary=str(fake)).dispatch(
        _packet(tmp_path, task_type="plan"), tmp_path, now=NOW
    )

    argv = _seen(tmp_path)["argv"]
    assert argv[argv.index("--approval-mode") + 1] == "plan"
    assert result.metadata["exit_status"] == "rate_limited"
    assert result.metadata["failure"]["resets_at"] == "2026-11-27T09:00:23.500000Z"


async def test_a_missing_binary_fails_cleanly(tmp_path):
    result = await GeminiDriver(binary=str(tmp_path / "no-gemini")).dispatch(
        _packet(tmp_path), tmp_path
    )
    assert result.success is False and result.metadata["exit_status"] == "not_installed"


# ── Detection ────────────────────────────────────────────────


def _codex_with_login(tmp_path: Path, logged_in: bool) -> Path:
    return _fake_cli(
        tmp_path,
        "codex",
        "import sys\n"
        "if sys.argv[1:] == ['--version']:\n    print('codex-cli 0.172.0'); sys.exit(0)\n"
        "if sys.argv[1:] == ['login', 'status']:\n"
        f"    print('Logged in using an API key - sk-proj-***'); sys.exit({0 if logged_in else 1})\n"
        "sys.exit(2)\n",
    )


async def test_detection_reports_version_and_login_without_the_output(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_codex_enabled", True)
    driver = CodexDriver(binary=str(_codex_with_login(tmp_path, logged_in=True)))

    assert await driver.available() is True
    detail = await driver.describe()
    assert detail["version"] == "codex-cli 0.172.0" and detail["logged_in"] is True
    assert "sk-proj" not in json.dumps(detail)


async def test_signed_out_or_disabled_is_unavailable(tmp_path, monkeypatch):
    driver = CodexDriver(binary=str(_codex_with_login(tmp_path, logged_in=False)))
    monkeypatch.setattr(settings, "driver_codex_enabled", False)
    assert await driver.available() is False  # off, installed or not
    monkeypatch.setattr(settings, "driver_codex_enabled", True)
    assert await driver.available() is False
    assert (await driver.describe())["hint"] == "run `codex login`"
    monkeypatch.setattr(settings, "driver_gemini_enabled", True)
    assert await GeminiDriver(binary=str(tmp_path / "missing")).available() is False


def test_a_cli_in_a_well_known_dir_is_found_off_path(tmp_path, monkeypatch):
    bin_dir = tmp_path / ".local" / "node" / "bin"
    bin_dir.mkdir(parents=True)
    _fake_cli(bin_dir, "gemini", "print('0.71.1')\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert cli_run.resolve_binary("gemini") == str(bin_dir / "gemini")
    assert cli_run.resolve_binary("no-such-cli") is None


# ── Registry and selection ───────────────────────────────────


def test_both_drivers_register_with_subscription_billing():
    from life_graph.drivers.registry import DriverRegistry, billing_of, selection_key
    from life_graph.drivers.setup import register_default_drivers

    names = register_default_drivers()
    assert {"codex", "gemini"} <= set(names)
    reg = DriverRegistry()
    for d in (CodexDriver(), GeminiDriver()):
        reg.register(d)
        assert billing_of(d) == "subscription" and d.cost_per_task() == 0.0
        assert d.max_concurrency == 1
    assert {d.name for d in reg.available_for_task("code_change")} == {"codex", "gemini"}
    local = SimpleNamespace(billing="local", cost_per_task=lambda: 0.0)
    api = SimpleNamespace(cost_per_task=lambda: 0.0)  # no attribute: counts as api
    claude = SimpleNamespace(billing="subscription", cost_per_task=lambda: 0.10)
    ordered = sorted([claude, api, CodexDriver(), local], key=selection_key)
    assert ordered[0] is local and isinstance(ordered[1], CodexDriver)
    assert ordered[2] is api and ordered[3] is claude


class _Fake:
    def __init__(self, name, billing, cost, up=True):
        self.name, self.billing, self._cost, self._up = name, billing, cost, up

    async def available(self):
        return self._up

    def capabilities(self):
        return ["code_change"]

    def cost_per_task(self):
        return self._cost


async def _select(monkeypatch, drivers, persona=None):
    from life_graph.drivers import dispatcher as disp_mod
    from life_graph.drivers.registry import DriverRegistry

    reg = DriverRegistry()
    for d in drivers:
        reg.register(d)
    monkeypatch.setattr(disp_mod, "driver_registry", reg)
    disp = disp_mod.TaskDispatcher(session_factory=lambda: None, event_bus=None)

    async def stats(*_a, **_k):
        return {}

    monkeypatch.setattr(disp, "_get_driver_stats", stats)
    return await disp._select_driver(
        "code_change", "p" if persona else None, "raja", session=None, persona=persona
    )


async def test_selection_prefers_local_then_subscription_at_equal_cost(monkeypatch):
    local = _Fake("local", "local", 0.0)
    codex = _Fake("codex", "subscription", 0.0)
    claude = _Fake("claude_code", "subscription", 0.10)
    assert (await _select(monkeypatch, [claude, codex, local])).name == "local"
    local._up = False
    assert (await _select(monkeypatch, [claude, codex, local])).name == "codex"


async def test_a_persona_pinned_to_gemini_gets_it(monkeypatch):
    local = _Fake("local", "local", 0.0)
    gemini = _Fake("gemini", "subscription", 0.0)
    persona = SimpleNamespace(driver="gemini", properties={})
    assert (await _select(monkeypatch, [local, gemini], persona)).name == "gemini"
    gemini._up = False  # not pin_required: falls through to cheapest-capable
    assert (await _select(monkeypatch, [local, gemini], persona)).name == "local"
