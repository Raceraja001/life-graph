"""Every driver's execution boundary, as the work order requires it documented.

- claude_code, driver_claude_sandbox="task": runs in task_runtime, never on
  the host, and the run's runtime metadata reaches the DriverResult.
- claude_code on the host: no Bash unless driver_allow_host_shell; an
  allowlisted environment; its own process group.
- opencode (host only today): bash denied by default; allowlisted environment.
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.config import settings
from life_graph.drivers import opencode as opencode_mod
from life_graph.drivers.base import ContextPacket
from life_graph.drivers.claude_code import ClaudeCodeDriver
from life_graph.services.dev import sandbox, task_runtime


def _packet(**kw):
    return ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code", instruction="fix it", **kw
    )


class _Proc:
    returncode = 0
    pid = 999_999

    async def communicate(self):
        return b'{"result": "ok", "session_id": "s1"}', b""


@pytest.fixture
def host_capture(monkeypatch):
    seen: dict = {}

    async def fake_exec(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return _Proc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    return seen


# ── claude_code in the task runtime ───────────────────────────


@pytest.fixture
def task_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "driver_claude_sandbox", "task")
    creds = tmp_path / ".credentials.json"
    creds.write_text('{"token": "t"}')
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))


async def test_task_mode_runs_in_the_runtime_and_records_it(task_mode, tmp_path, monkeypatch):
    got = {}

    async def fake_run(req):
        got["req"] = req
        assert (req.credentials / ".credentials.json").is_file()
        return task_runtime.RuntimeOutcome(
            0, '{"result": "ok"}', "", {"runtime": "task", "rid": "r1"}
        )

    async def no_host(*a, **k):
        raise AssertionError("task mode must never start a host process")

    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)
    monkeypatch.setattr("asyncio.create_subprocess_exec", no_host)
    packet = _packet(allowed_tools=["file_read", "run_command"])
    result = await ClaudeCodeDriver(binary="/home/x/.local/bin/claude").dispatch(packet, tmp_path)

    req = got["req"]
    assert result.success is True
    assert result.metadata["boundary"] == "task"
    assert result.metadata["runtime"]["rid"] == "r1"
    assert req.task_id == str(packet.task_id)
    assert req.command[0] == sandbox.DRIVER_CLI  # the image's CLI, not the host path
    assert "Bash" in req.command[req.command.index("--allowedTools") + 1]  # shell is contained
    assert req.egress_allowlist == tuple(settings.driver_runtime_egress_allowlist_list)
    assert not any(k.startswith("LIFE_GRAPH_") for k in req.env)
    assert not req.credentials.exists()  # staged token removed afterwards


async def test_task_mode_unavailable_never_falls_back_to_the_host(task_mode, tmp_path, monkeypatch):
    async def unavailable(req):
        err = sandbox.SandboxUnavailableError("runtime image missing")
        err.runtime_metadata = {"runtime": "task", "teardown": {"ok": True}}
        raise err

    async def no_host(*a, **k):
        raise AssertionError("host subprocess must never be spawned when sandboxing is on")

    monkeypatch.setattr(task_runtime.runtime, "run", unavailable)
    monkeypatch.setattr("asyncio.create_subprocess_exec", no_host)
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path)

    assert result.success is False
    assert result.metadata["exit_status"] == "sandbox_unavailable"
    assert result.metadata["runtime"]["teardown"]["ok"] is True
    assert "runtime image missing" in result.error


async def test_task_mode_timeout_is_a_timeout(task_mode, tmp_path, monkeypatch):
    async def deadline(req):
        raise sandbox.SandboxUnavailableError("sandboxed command timed out after 5s")

    monkeypatch.setattr(task_runtime.runtime, "run", deadline)
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path)
    assert result.metadata["exit_status"] == "timeout"


# ── claude_code on the host ───────────────────────────────────


async def test_host_bash_is_removed_from_a_scoped_persona(host_capture, tmp_path):
    result = await ClaudeCodeDriver(binary="claude").dispatch(
        _packet(allowed_tools=["file_read", "file_write", "run_command"]), tmp_path
    )
    args = host_capture["args"]
    assert result.metadata["host_shell"] == "denied"
    assert "Bash" not in args[args.index("--allowedTools") + 1].split(",")
    assert "Bash" in args[args.index("--disallowedTools") + 1].split(",")


async def test_host_bash_is_denied_on_an_unscoped_dispatch(host_capture, tmp_path):
    await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path)
    args = host_capture["args"]
    assert args[args.index("--disallowedTools") + 1] == "Bash"


async def test_a_shell_only_persona_is_refused_on_the_host(host_capture, tmp_path):
    result = await ClaudeCodeDriver(binary="claude").dispatch(
        _packet(allowed_tools=["run_command"]), tmp_path
    )
    assert result.success is False
    assert result.metadata["exit_status"] == "refused_host_shell"
    assert "args" not in host_capture


async def test_the_host_shell_opt_in_restores_bash(host_capture, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_allow_host_shell", True)
    await ClaudeCodeDriver(binary="claude").dispatch(
        _packet(allowed_tools=["run_command"]), tmp_path
    )
    args = host_capture["args"]
    assert "Bash" in args[args.index("--allowedTools") + 1]


async def test_host_cli_gets_an_allowlisted_environment(host_capture, tmp_path, monkeypatch):
    monkeypatch.setenv("LIFE_GRAPH_DATABASE_URL", "postgresql://secret@db/x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-v1-secret")
    monkeypatch.setenv("PATH", "/usr/bin")
    await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path)
    env = host_capture["kwargs"]["env"]
    assert env is not None  # None would mean "inherit everything"
    assert "LIFE_GRAPH_DATABASE_URL" not in env
    assert "OPENROUTER_API_KEY" not in env
    assert env["PATH"] == "/usr/bin"
    assert host_capture["kwargs"]["start_new_session"] is True


async def test_passthrough_never_admits_app_configuration(monkeypatch):
    from life_graph.drivers.host_exec import host_driver_env

    monkeypatch.setenv("LIFE_GRAPH_SECRET_KEY", "x" * 20)
    monkeypatch.setenv("MY_TOOL_HOME", "/opt/tool")
    monkeypatch.setattr(
        settings, "driver_host_env_passthrough", "MY_TOOL_HOME,LIFE_GRAPH_SECRET_KEY"
    )
    env = host_driver_env()
    assert env["MY_TOOL_HOME"] == "/opt/tool"
    assert "LIFE_GRAPH_SECRET_KEY" not in env


# ── opencode (host only) ──────────────────────────────────────


def test_opencode_bash_is_denied_by_default():
    assert settings.driver_opencode_allow_bash is False
    config = opencode_mod._config(_packet())
    assert config["permission"]["bash"] == "deny"
    assert config["permission"]["external_directory"] == "deny"


async def test_opencode_gets_an_allowlisted_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFE_GRAPH_DATABASE_URL", "postgresql://secret@db/x")
    seen = {}

    async def fake_invoke(self, prompt, cwd, env, timeout, session_id):
        seen["env"] = env
        return opencode_mod._Run(0, b"", b"")

    monkeypatch.setattr(opencode_mod.OpencodeDriver, "_invoke", fake_invoke)
    await opencode_mod.OpencodeDriver(binary="opencode").dispatch(_packet(), tmp_path)
    assert "LIFE_GRAPH_DATABASE_URL" not in seen["env"]
    assert "OPENCODE_CONFIG" in seen["env"]


async def test_opencode_is_parked_by_default(monkeypatch):
    assert settings.driver_opencode_enabled is False
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/opencode")
    assert await opencode_mod.OpencodeDriver(binary="opencode").available() is False
    monkeypatch.setattr(settings, "driver_opencode_enabled", True)
    assert await opencode_mod.OpencodeDriver(binary="opencode").available() is True
