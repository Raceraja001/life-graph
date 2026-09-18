"""ClaudeCodeDriver, sandboxed: routes through sandbox.run_driver instead of
a bare host subprocess when driver_claude_sandbox="docker", stages a
throwaway copy of the CLI's own credentials rather than the live
~/.claude, cleans that copy up even on failure, and fails closed (never
falls back to host execution) when the sandbox itself is unavailable.
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.claude_code import ClaudeCodeDriver
from life_graph.services import sandbox


@pytest.fixture
def sandboxed(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "driver_claude_sandbox", "docker")


def _packet(**overrides):
    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t1",
        task_type="code",
        instruction="fix it",
        **overrides,
    )


async def test_dispatch_stages_credentials_and_calls_run_driver(tmp_path, sandboxed, monkeypatch):
    from life_graph.config import settings

    creds = tmp_path / "creds" / ".credentials.json"
    creds.parent.mkdir()
    creds.write_text('{"token": "secret"}')
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))

    seen = {}

    async def fake_run_driver(argv, workdir, credentials_dir, *, timeout):
        seen["argv"] = argv
        seen["workdir"] = workdir
        seen["credentials_dir"] = credentials_dir
        # The staged copy must exist and be separate from the real file.
        assert (credentials_dir / ".credentials.json").read_text() == '{"token": "secret"}'
        assert credentials_dir != creds.parent
        return sandbox.SandboxResult(0, '{"result": "ok", "session_id": "s1"}', "")

    monkeypatch.setattr(sandbox, "run_driver", fake_run_driver)

    driver = ClaudeCodeDriver(binary="claude")
    result = await driver.dispatch(_packet(), tmp_path / "work")

    assert result.success is True
    assert result.metadata["sandboxed"] is True
    assert seen["argv"][0] == "claude"
    # The credentials copy is gone again once the dispatch is done.
    assert not seen["credentials_dir"].exists()


async def test_credentials_are_cleaned_up_even_on_failure(tmp_path, sandboxed, monkeypatch):
    from life_graph.config import settings

    creds = tmp_path / "creds" / ".credentials.json"
    creds.parent.mkdir()
    creds.write_text("{}")
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))

    staged_dirs = []

    async def fake_run_driver(argv, workdir, credentials_dir, *, timeout):
        staged_dirs.append(credentials_dir)
        raise RuntimeError("boom")

    monkeypatch.setattr(sandbox, "run_driver", fake_run_driver)

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
        raise AssertionError("run_driver must never be called without credentials")

    monkeypatch.setattr(sandbox, "run_driver", must_not_run)

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

    async def unavailable(argv, workdir, credentials_dir, *, timeout):
        raise sandbox.SandboxUnavailableError("image not built")

    monkeypatch.setattr(sandbox, "run_driver", unavailable)

    async def must_not_run(*a, **kw):
        raise AssertionError("host subprocess must never be spawned when sandboxing is on")

    monkeypatch.setattr("asyncio.create_subprocess_exec", must_not_run)

    driver = ClaudeCodeDriver(binary="claude")
    result = await driver.dispatch(_packet(), tmp_path / "work")

    assert result.success is False
    assert result.metadata["exit_status"] == "sandbox_unavailable"
    assert "image not built" in result.error


async def test_sandbox_timeout_reports_as_timeout_not_a_generic_error(tmp_path, sandboxed, monkeypatch):
    from life_graph.config import settings

    creds = tmp_path / ".credentials.json"
    creds.write_text("{}")
    monkeypatch.setattr(settings, "driver_claude_code_creds_path", str(creds))

    async def timed_out(argv, workdir, credentials_dir, *, timeout):
        raise sandbox.SandboxUnavailableError(f"sandboxed command timed out after {timeout}s")

    monkeypatch.setattr(sandbox, "run_driver", timed_out)

    driver = ClaudeCodeDriver(binary="claude")
    result = await driver.dispatch(_packet(), tmp_path / "work", timeout=5)

    assert result.success is False
    assert result.metadata["exit_status"] == "timeout"


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
