"""Which Claude login a sandboxed claude_code run gets (2026-11-19).

Copying the host's ~/.claude login into the container revoked the host's own
login: with the host access token expired, the CLI in the container refreshed
it inside the throwaway copy, the refresh token rotated, and the host's copy
died. So a sandboxed run in oauth mode now takes the long-lived token from
``claude setup-token`` (passed by name, never copied, never refreshed), and
with no token it refuses. The old copy is an explicit opt-in.
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.config import settings
from life_graph.drivers.base import ContextPacket
from life_graph.drivers.claude_code import ClaudeCodeDriver
from life_graph.services.dev import sandbox, task_runtime

TOKEN = "sk-ant-oat01-" + "x" * 40


def _packet(**kw):
    return ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code", instruction="fix it", **kw
    )


@pytest.fixture
def oauth(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "driver_claude_code_auth", "oauth")
    monkeypatch.setattr(settings, "driver_claude_code_allow_staged_login", False)
    monkeypatch.setattr(settings, "driver_claude_code_oauth_token", "")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    creds = tmp_path / "home-claude" / ".credentials.json"
    creds.parent.mkdir()
    creds.write_text('{"claudeAiOauth": {"refreshToken": "live"}}')
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))

    async def no_staging(source):
        raise AssertionError("the host login must not be copied into the container")

    monkeypatch.setattr(sandbox, "stage_credentials", no_staging)


async def test_task_runtime_gets_the_token_by_name_and_no_login_file(oauth, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_claude_sandbox", "task")
    monkeypatch.setattr(settings, "driver_claude_code_oauth_token", TOKEN)
    got = {}

    async def fake_run(req):
        got["req"] = req
        return task_runtime.RuntimeOutcome(0, '{"result": "ok"}', "", {"runtime": "task"})

    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path)

    req = got["req"]
    assert result.success is True
    assert req.secret_env == {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}
    assert req.credentials is None  # nothing from ~/.claude is mounted
    assert req.env["CLAUDE_CONFIG_DIR"] == "/tmp/.claude"  # throwaway, on the tmpfs
    assert TOKEN not in str(req.env) and TOKEN not in " ".join(req.command)
    assert result.metadata["login"] == "oauth_token"


async def test_the_env_var_works_as_well_as_the_setting(oauth, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_claude_sandbox", "task")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", TOKEN)
    got = {}

    async def fake_run(req):
        got["req"] = req
        return task_runtime.RuntimeOutcome(0, '{"result": "ok"}', "", {"runtime": "task"})

    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)
    await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path)
    assert got["req"].secret_env == {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}


async def test_legacy_docker_mode_passes_the_token_by_name(oauth, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_claude_sandbox", "docker")
    monkeypatch.setattr(settings, "driver_claude_code_oauth_token", TOKEN)
    seen = {}

    async def fake_image():
        return "sha256:x"

    async def fake_exec(argv, timeout, container=None, env=None):
        seen["argv"], seen["env"] = argv, env
        return sandbox.SandboxResult(0, '{"result": "ok"}', "")

    monkeypatch.setattr(sandbox, "_driver_image_id", fake_image)
    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path / "work")

    argv = seen["argv"]
    assert result.success is True
    assert "CLAUDE_CODE_OAUTH_TOKEN" in argv  # by name...
    assert not any(TOKEN in a for a in argv)  # ...never the value on the command line
    assert seen["env"] == {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}
    assert not any(":/claude-config" in a for a in argv)


@pytest.mark.parametrize("mode", ["task", "docker"])
async def test_no_token_refuses_instead_of_copying_the_host_login(
    oauth, tmp_path, monkeypatch, mode
):
    monkeypatch.setattr(settings, "driver_claude_sandbox", mode)

    async def never(*a, **k):
        raise AssertionError("nothing may run without a login")

    monkeypatch.setattr(task_runtime.runtime, "run", never)
    monkeypatch.setattr(sandbox, "_exec", never)
    monkeypatch.setattr("asyncio.create_subprocess_exec", never)
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path)

    assert result.success is False
    assert result.metadata["exit_status"] == "sandbox_unavailable"
    assert "claude setup-token" in result.error


async def test_the_legacy_copy_is_an_explicit_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "driver_claude_code_auth", "oauth")
    monkeypatch.setattr(settings, "driver_claude_sandbox", "task")
    monkeypatch.setattr(settings, "driver_claude_code_allow_staged_login", True)
    monkeypatch.setattr(settings, "driver_claude_code_oauth_token", "")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    creds = tmp_path / "c" / ".credentials.json"
    creds.parent.mkdir()
    creds.write_text("{}")
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", str(tmp_path / "envs"))
    got = {}

    async def fake_run(req):
        got["mounted"] = (
            req.credentials is not None and (req.credentials / ".credentials.json").is_file()
        )
        return task_runtime.RuntimeOutcome(0, '{"result": "ok"}', "", {"runtime": "task"})

    monkeypatch.setattr(task_runtime.runtime, "run", fake_run)
    result = await ClaudeCodeDriver(binary="claude").dispatch(_packet(), tmp_path)
    assert got["mounted"] is True
    assert result.metadata["login"] == "staged_copy"


def test_only_the_driver_logins_pass_through_by_name():
    assert {"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"} == sandbox.PASSTHROUGH_ENV_ALLOWED


def test_the_token_setting_counts_as_a_configured_secret(monkeypatch):
    # A spec that tried to carry the token as a plain -e NAME=value (visible
    # in argv) is refused, whatever the variable is called.
    monkeypatch.setattr(settings, "driver_claude_code_oauth_token", TOKEN)
    bad = sandbox._env_violations({"HARMLESS_NAME": TOKEN})
    assert any("configured credential" in b or "provider key" in b for b in bad)
