import tempfile

import pytest

from life_graph.drivers.claude_code import _DENIABLE_CLI_TOOLS, _RESTRICTIVE_PERMISSION_MODE
from life_graph.services.claude_cli_reply import run_claude_cli


class _FakeProcess:
    def __init__(self, returncode: int, stdout: bytes, stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr

    def kill(self):
        pass


@pytest.mark.asyncio
async def test_success_returns_parsed_result_text(monkeypatch):
    async def _fake_exec(*args, **kwargs):
        return _FakeProcess(0, b'{"result": "hello there", "is_error": false}')

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await run_claude_cli("hi")

    assert result.success is True
    assert result.text == "hello there"
    assert result.error is None


@pytest.mark.asyncio
async def test_binary_not_found_returns_failure(monkeypatch):
    async def _fake_exec(*args, **kwargs):
        raise FileNotFoundError("claude not found")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await run_claude_cli("hi")

    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_timeout_kills_process_and_returns_failure(monkeypatch):
    import asyncio

    class _HangingProcess(_FakeProcess):
        def __init__(self):
            super().__init__(0, b"")

        async def communicate(self):
            raise TimeoutError()

    async def _fake_exec(*args, **kwargs):
        return _HangingProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)
    monkeypatch.setattr(
        "asyncio.wait_for",
        lambda coro, timeout: (_ for _ in ()).throw(TimeoutError()),
    )

    result = await run_claude_cli("hi", timeout=1.0)

    assert result.success is False
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_non_zero_exit_returns_failure(monkeypatch):
    async def _fake_exec(*args, **kwargs):
        return _FakeProcess(1, b'{"result": "bad request", "is_error": true}', b"")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await run_claude_cli("hi")

    assert result.success is False
    assert "bad request" in result.error


@pytest.mark.asyncio
async def test_subprocess_call_is_permission_scoped_and_not_repo_cwd(monkeypatch):
    # Critical-finding regression guard: every claude-cli reply must run
    # with the same scoping as drivers/claude_code.py's hardened CLI calls
    # (--permission-mode manual + an explicit --disallowedTools denylist),
    # and must never inherit the FastAPI server's own cwd (the repo root).
    captured = {}

    async def _fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeProcess(0, b'{"result": "hi", "is_error": false}')

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    await run_claude_cli("hi")

    args = captured["args"]
    assert "--permission-mode" in args
    assert args[args.index("--permission-mode") + 1] == _RESTRICTIVE_PERMISSION_MODE
    assert "--disallowedTools" in args
    denied = args[args.index("--disallowedTools") + 1].split(",")
    assert set(denied) == set(_DENIABLE_CLI_TOOLS)

    cwd = captured["kwargs"].get("cwd")
    assert cwd is not None
    assert cwd == tempfile.gettempdir()


@pytest.mark.asyncio
async def test_malformed_json_output_tolerated_as_plain_text(monkeypatch):
    async def _fake_exec(*args, **kwargs):
        return _FakeProcess(0, b"not valid json at all")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)

    result = await run_claude_cli("hi")

    # Mirrors claude_code.py's _parse_output tolerance: non-JSON stdout on
    # a zero exit code is treated as the literal result text, not an error.
    assert result.success is True
    assert result.text == "not valid json at all"
