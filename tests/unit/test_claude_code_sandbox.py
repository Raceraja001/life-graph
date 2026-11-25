"""ClaudeCodeDriver, sandboxed: routes through the per-task runtime instead of
a bare host subprocess when driver_claude_sandbox="task", stages a throwaway
copy of the CLI's own credentials (legacy opt-in) rather than the live
~/.claude, cleans that copy up even on failure, and fails closed (never falls
back to host execution) when the sandbox itself is unavailable.

The old "docker" mode (open-network container, no policy check) is fenced
(owner decision D25, 2026-11-25): every dispatch in it refuses before any
login is staged or any process starts.
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.claude_code import ClaudeCodeDriver
from life_graph.services.dev import sandbox, task_runtime


@pytest.fixture
def sandboxed(monkeypatch, tmp_path):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "driver_claude_sandbox", "task")
    # No project environment build: these tests are about the login and the
    # boundary, not the mounted test tools (test_driver_tool_env.py).
    monkeypatch.setattr(settings, "driver_runtime_project_tools", False)
    # These tests exercise the legacy staged copy; the long-lived token path
    # is in test_claude_code_sandbox_login.py.
    monkeypatch.setattr(settings, "driver_claude_code_allow_staged_login", True)
    monkeypatch.setattr(settings, "driver_claude_code_oauth_token", "")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))


def _packet(**overrides):
    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t1",
        task_type="code",
        instruction="fix it",
        **overrides,
    )


def _ok(stdout='{"result": "ok", "session_id": "s1"}'):
    return task_runtime.RuntimeOutcome(0, stdout, "", {"runtime": "task"})


async def test_dispatch_stages_credentials_and_runs_in_the_runtime(
    tmp_path, sandboxed, monkeypatch
):
    from life_graph.config import settings

    creds = tmp_path / "creds" / ".credentials.json"
    creds.parent.mkdir()
    creds.write_text('{"token": "secret"}')
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))

    seen = {}

    async def fake_run(req):
        seen["req"] = req
        # The staged copy must exist and be separate from the real file.
        assert (req.credentials / ".credentials.json").read_text() == '{"token": "secret"}'
        assert req.credentials != creds.parent
        return _ok()

    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)

    driver = ClaudeCodeDriver(binary="claude")
    result = await driver.dispatch(_packet(), tmp_path / "work")

    assert result.success is True
    assert result.metadata["sandboxed"] is True
    assert result.metadata["boundary"] == "task"
    assert seen["req"].command[0] == sandbox.DRIVER_CLI
    # The credentials copy is gone again once the dispatch is done.
    assert not seen["req"].credentials.exists()


async def test_credentials_are_cleaned_up_even_on_failure(tmp_path, sandboxed, monkeypatch):
    from life_graph.config import settings

    creds = tmp_path / "creds" / ".credentials.json"
    creds.parent.mkdir()
    creds.write_text("{}")
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))

    staged_dirs = []

    async def fake_run(req):
        staged_dirs.append(req.credentials)
        raise RuntimeError("boom")

    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)

    driver = ClaudeCodeDriver(binary="claude")
    result = await driver.dispatch(_packet(), tmp_path / "work")

    assert result.success is False
    assert not staged_dirs[0].exists()


async def test_missing_credentials_file_refuses_without_running(tmp_path, sandboxed, monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(
        settings, "driver_claude_code_creds_path", str(tmp_path / "nope" / ".credentials.json")
    )

    async def must_not_run(*a, **kw):
        raise AssertionError("the runtime must never be started without credentials")

    monkeypatch.setattr(task_runtime.runtime, "run", must_not_run)

    driver = ClaudeCodeDriver(binary="claude")
    result = await driver.dispatch(_packet(), tmp_path / "work")

    assert result.success is False
    assert result.metadata["exit_status"] == "sandbox_unavailable"


async def test_sandbox_unavailable_never_falls_back_to_the_host(tmp_path, sandboxed, monkeypatch):
    """The whole point of sandboxing: a missing image must fail the
    dispatch, not silently run the CLI unsandboxed on the host."""
    from life_graph.config import settings

    creds = tmp_path / ".credentials.json"
    creds.write_text("{}")
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))

    async def unavailable(req):
        raise sandbox.SandboxUnavailableError("image not built")

    monkeypatch.setattr(task_runtime.runtime, "run", unavailable)

    async def must_not_run(*a, **kw):
        raise AssertionError("host subprocess must never be spawned when sandboxing is on")

    monkeypatch.setattr("asyncio.create_subprocess_exec", must_not_run)

    driver = ClaudeCodeDriver(binary="claude")
    result = await driver.dispatch(_packet(), tmp_path / "work")

    assert result.success is False
    assert result.metadata["exit_status"] == "sandbox_unavailable"
    assert "image not built" in result.error


async def test_sandbox_timeout_reports_as_timeout_not_a_generic_error(
    tmp_path, sandboxed, monkeypatch
):
    from life_graph.config import settings

    creds = tmp_path / ".credentials.json"
    creds.write_text("{}")
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))

    async def timed_out(req):
        raise sandbox.SandboxUnavailableError(f"sandboxed command timed out after {req.timeout}s")

    monkeypatch.setattr(task_runtime.runtime, "run", timed_out)

    driver = ClaudeCodeDriver(binary="claude")
    result = await driver.dispatch(_packet(), tmp_path / "work", timeout=5)

    assert result.success is False
    assert result.metadata["exit_status"] == "timeout"


async def test_legacy_docker_mode_is_fenced_and_nothing_runs(tmp_path, monkeypatch):
    """D25: driver_claude_sandbox=docker refuses every dispatch, before any
    login is staged, any container is started, or any host process runs."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "driver_claude_sandbox", "docker")
    monkeypatch.setattr(settings, "driver_claude_code_oauth_token", "sk-ant-oat01-" + "x" * 40)

    async def never(*a, **kw):
        raise AssertionError("the fenced docker mode must not run anything")

    monkeypatch.setattr(task_runtime.runtime, "run", never)
    monkeypatch.setattr(sandbox, "_exec", never)
    monkeypatch.setattr(sandbox, "stage_credentials", never)
    monkeypatch.setattr("asyncio.create_subprocess_exec", never)

    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path / "work")

    assert result.success is False
    assert result.metadata["exit_status"] == "sandbox_unavailable"
    assert result.metadata["boundary"] == "docker"
    assert "driver_claude_sandbox=docker is switched off" in result.error
    assert "SANDBOX=task" in result.error  # says what to set instead


async def test_host_dispatch_is_unaffected_when_sandbox_is_off(tmp_path, monkeypatch):
    """Default posture (driver_claude_sandbox="none"): unchanged host
    subprocess path, sandboxed=False in the result metadata.

    Explicitly set, not relied on as the ambient default: a deployment
    (this one, via .env) may turn sandboxing on process-wide, and this test
    must still prove the *off* behavior rather than accidentally testing
    whatever the environment happens to have configured.
    """
    from life_graph.config import settings

    monkeypatch.setattr(settings, "driver_claude_sandbox", "none")

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return b'{"result": "ok"}', b""

    async def fake_exec(*args, **kwargs):
        return _FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    driver = ClaudeCodeDriver(binary="claude")
    result = await driver.dispatch(_packet(), tmp_path)

    assert result.success is True
    assert result.metadata["sandboxed"] is False


def test_dispatch_timeout_comes_from_settings_not_the_300s_fallback(monkeypatch):
    from life_graph.config import settings

    assert ClaudeCodeDriver().dispatch_timeout == 1200
    monkeypatch.setattr(settings, "driver_claude_code_timeout_seconds", 1800)
    assert ClaudeCodeDriver().dispatch_timeout == 1800


async def test_dispatch_streams_and_returns_every_step(tmp_path, sandboxed, monkeypatch):
    import json

    from life_graph.config import settings

    creds = tmp_path / "creds" / ".credentials.json"
    creds.parent.mkdir()
    creds.write_text("{}")
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))
    seen = {}
    stream = "\n".join(
        json.dumps(e)
        for e in [
            {"type": "system", "subtype": "init", "model": "claude-opus-5"},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "Read",
                            "input": {"file_path": "a"},
                        }
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "hi"}]
                },
            },
            {
                "type": "result",
                "is_error": False,
                "result": "ok",
                "session_id": "s1",
                "total_cost_usd": 0.25,
                "num_turns": 2,
            },
        ]
    )

    async def fake_run(req):
        seen["argv"] = list(req.command)
        return _ok(stream)

    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)

    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path / "work")

    fmt = seen["argv"].index("--output-format")
    assert seen["argv"][fmt + 1] == "stream-json" and "--verbose" in seen["argv"]
    assert result.success is True and result.output == "ok" and result.cost_usd == 0.25
    assert result.metadata["model"] == "claude-opus-5"
    assert [(s["kind"], s["tool"]) for s in result.metadata["steps"]] == [
        ("tool_call", "Read"),
        ("tool_result", "Read"),
    ]


async def test_api_key_mode_passes_the_key_by_name_and_stages_no_login(
    tmp_path, sandboxed, monkeypatch
):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "driver_claude_code_auth", "api_key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-1234567890")
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(tmp_path / "nope"))

    async def no_staging(source):
        raise AssertionError("api_key mode must never stage the personal login")

    monkeypatch.setattr(sandbox, "stage_credentials", no_staging)
    seen = {}

    async def fake_run(req):
        seen["req"] = req
        return _ok('{"result": "ok"}')

    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)

    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path / "work")

    assert result.success is True
    req = seen["req"]
    assert req.secret_env == {"ANTHROPIC_API_KEY": "sk-ant-test-key-1234567890"}  # by name only
    assert not any("sk-ant-test-key" in a for a in req.command)  # never on the command line
    assert "sk-ant-test-key" not in str(req.env)
    assert req.credentials is None  # no login mounted


async def test_api_key_mode_without_a_key_fails_instead_of_using_the_login(
    tmp_path, sandboxed, monkeypatch
):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "driver_claude_code_auth", "api_key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(settings, "driver_claude_code_api_key", "")

    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path / "work")

    assert result.success is False and "ANTHROPIC_API_KEY" in result.error
