"""ClaudeCodeDriver must translate a persona's allowed_tools into the Claude
Code CLI's own --allowedTools flag, and use the persona's real system
prompt — mirroring what LocalDriver already does via the Python tool
registry (ClaudeCodeDriver has no access to that registry; it shells out to
the CLI, which has its own, different tool vocabulary and its own flag for
restricting it).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.claude_code import ClaudeCodeDriver, _allowed_cli_tools


def test_allowed_cli_tools_maps_known_names():
    result = _allowed_cli_tools(["file_read", "file_write", "run_command"])
    assert result == sorted({"Read", "Write", "Bash"})


def test_allowed_cli_tools_none_means_unscoped():
    assert _allowed_cli_tools(None) is None


def test_allowed_cli_tools_unmapped_name_is_dropped_fail_closed():
    assert _allowed_cli_tools(["delegate_to_persona"]) == []


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
    assert args[flag_index + 1] == "Bash,Read"
    assert "You are Cody." in args[args.index("-p") + 1]


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
