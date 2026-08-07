"""ClaudeCodeDriver must translate a persona's allowed_tools into the Claude
Code CLI's own --allowedTools flag, and use the persona's real system
prompt — mirroring what LocalDriver already does via the Python tool
registry (ClaudeCodeDriver has no access to that registry; it shells out to
the CLI, which has its own, different tool vocabulary and its own flag for
restricting it).
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.claude_code import (
    ClaudeCodeDriver,
    _allowed_cli_tools,
    _disallowed_cli_tools,
)


def test_allowed_cli_tools_maps_known_names():
    result = _allowed_cli_tools(["file_read", "file_write", "run_command"])
    # file_read covers the CLI's whole read/search surface, and file_write
    # must include Edit — the CLI's Write tool only creates/overwrites whole
    # files, so Write alone cannot modify an existing one.
    assert result == sorted({"Read", "Glob", "Grep", "Write", "Edit", "Bash"})


def test_allowed_cli_tools_none_means_unscoped():
    assert _allowed_cli_tools(None) is None


def test_allowed_cli_tools_unmapped_name_is_dropped_fail_closed():
    assert _allowed_cli_tools(["delegate_to_persona"]) == []


def test_dependency_updater_persona_can_edit_existing_files():
    """dependency-updater is pinned to driver=claude_code and its whole job
    is editing existing manifests/lockfiles. Regression guard for the
    Write-without-Edit mapping that silently disabled it."""
    from life_graph.kernel.personas import _BUILTIN_PERSONAS

    persona = next(p for p in _BUILTIN_PERSONAS if p["name"] == "dependency-updater")
    assert persona.get("driver") == "claude_code"

    cli_tools = _allowed_cli_tools(persona["allowed_tools"])

    assert "Edit" in cli_tools
    assert "Write" in cli_tools
    assert "Read" in cli_tools
    assert "Bash" in cli_tools


def test_disallowed_cli_tools_is_the_dangerous_complement():
    """A read-only persona must have the write/exec tools explicitly DENIED,
    not merely left out of the pre-approval list."""
    denied = _disallowed_cli_tools(["Glob", "Grep", "Read"])
    assert "Bash" in denied
    assert "Write" in denied
    assert "Edit" in denied
    # Read-only tools carry no blast radius and are never denied.
    assert "Read" not in denied and "Glob" not in denied and "Grep" not in denied


def test_disallowed_cli_tools_empty_when_everything_dangerous_is_allowed():
    assert _disallowed_cli_tools(["Bash", "Edit", "NotebookEdit", "Write"]) == []


@pytest.mark.asyncio
async def test_dispatch_passes_allowed_tools_flag_to_the_cli(tmp_path, monkeypatch):
    driver = ClaudeCodeDriver(binary="claude")
    packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
        instruction="fix it", allowed_tools=["file_read", "run_command"],
        persona_system_prompt="You are Cody.",
    )

    captured_args = {}

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return b'{"result": "ok", "session_id": "s1"}', b""

    async def _fake_exec(*args, **kwargs):
        captured_args["args"] = args
        return _FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await driver.dispatch(packet, tmp_path)

    assert result.success is True
    args = captured_args["args"]
    assert "--allowedTools" in args
    flag_index = args.index("--allowedTools")
    assert args[flag_index + 1] == "Bash,Glob,Grep,Read"
    assert "You are Cody." in args[args.index("-p") + 1]
    # --allowedTools is only a pre-approval list; pin the permission mode too
    # so a permissive host default can't widen an unattended dispatch.
    assert "--permission-mode" in args
    assert args[args.index("--permission-mode") + 1] == "manual"
    # ...and belt-and-suspenders: the write/exec tools this persona did NOT
    # earn are denied outright, not just omitted from the pre-approval list.
    assert "--disallowedTools" in args
    denied = args[args.index("--disallowedTools") + 1].split(",")
    assert "Write" in denied
    assert "Edit" in denied
    assert "Bash" not in denied  # run_command WAS granted


@pytest.mark.asyncio
async def test_dispatch_omits_flag_when_unscoped(tmp_path, monkeypatch):
    driver = ClaudeCodeDriver(binary="claude")
    packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
        instruction="fix it",
    )

    captured_args = {}

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return b'{"result": "ok"}', b""

    async def _fake_exec(*args, **kwargs):
        captured_args["args"] = args
        return _FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    await driver.dispatch(packet, tmp_path)

    assert "--allowedTools" not in captured_args["args"]
    # No scoping requested → don't touch the CLI's own permission handling.
    assert "--permission-mode" not in captured_args["args"]
    assert "--disallowedTools" not in captured_args["args"]


@pytest.mark.asyncio
async def test_dispatch_refuses_when_no_tool_maps_to_the_cli(tmp_path, monkeypatch):
    """Fail-closed without depending on unverified `--allowedTools ""` CLI
    semantics: never invoke the subprocess at all."""
    driver = ClaudeCodeDriver(binary="claude")
    packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
        instruction="fix it", allowed_tools=["delegate_to_persona"],
    )

    calls = []

    async def _fake_exec(*args, **kwargs):
        calls.append(args)
        raise AssertionError("subprocess must never be spawned")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await driver.dispatch(packet, tmp_path)

    assert calls == []
    assert result.success is False
    assert "refusing to dispatch unscoped" in result.error
    assert result.metadata["exit_status"] == "refused_unscoped"


@pytest.mark.asyncio
async def test_dispatch_still_runs_for_an_empty_but_unscoped_packet(tmp_path, monkeypatch):
    """allowed_tools=[] is "scoped to nothing" and must be refused, while
    allowed_tools=None is "unscoped" and must still run — the two must not
    be conflated."""
    driver = ClaudeCodeDriver(binary="claude")
    packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
        instruction="fix it", allowed_tools=[],
    )

    async def _fake_exec(*args, **kwargs):
        raise AssertionError("subprocess must never be spawned")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await driver.dispatch(packet, tmp_path)

    assert result.success is False
    assert result.metadata["exit_status"] == "refused_unscoped"
