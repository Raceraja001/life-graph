"""H4 (audit 2026-11-19): a timed-out command is stopped, all of it.

The approved deploy, the post-deploy smoke check and rollback
(services/approvals.py) only cancelled the read on timeout: the command kept
running, and a retry started a second deploy beside it. The autonomy executor
(autonomy/pipeline/executor.py) killed ``/bin/sh`` only, so whatever the
shell had started lived on. Each now starts in its own session and a timeout
SIGKILLs the whole process group.

Real processes, no mocks: the command backgrounds a ``sleep`` (a grandchild
of this test), records its pid, and the test checks that pid is gone.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from types import SimpleNamespace

import pytest

from life_graph.services import approvals

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")


def _command(pidfile) -> str:
    # The grandchild is the thing a plain proc.kill() never reached.
    return f"sleep 60 & echo $! > {pidfile}; wait"


def _alive(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/stat") as fh:
            state = fh.read().rsplit(")", 1)[1].split()[0]
    except FileNotFoundError:
        return False
    return state != "Z"  # a zombie is dead, only not yet reaped by init


async def _gone(pid: int, within: float = 5.0) -> bool:
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        await asyncio.sleep(0.05)
    return False


async def _pid_from(pidfile) -> int:
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text().strip():
            return int(pidfile.read_text())
        await asyncio.sleep(0.02)
    raise AssertionError("the command never wrote its pid")


def _cleanup(pid: int | None) -> None:
    if pid and _alive(pid):
        os.kill(pid, 9)


async def test_a_timed_out_smoke_or_rollback_command_is_killed_with_its_children(tmp_path):
    pidfile = tmp_path / "pid"
    pid = None
    try:
        started = time.monotonic()
        code, output = await approvals._run_shell(_command(pidfile), str(tmp_path), 1)
        pid = await _pid_from(pidfile)

        assert code == 124
        assert "timed out" in output
        assert time.monotonic() - started < 15
        assert await _gone(pid), "the command's child outlived the timeout"
    finally:
        _cleanup(pid)


async def test_a_timed_out_deploy_is_stopped_and_stays_retryable(tmp_path, monkeypatch):
    from life_graph.tools import _guards

    monkeypatch.setattr(approvals, "DEPLOY_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(_guards, "resolve_in_roots", lambda *_a, **_k: str(tmp_path))
    pidfile = tmp_path / "pid"
    appr = SimpleNamespace(
        payload={"deploy_command": _command(pidfile), "repo_path": str(tmp_path)},
        resolution_note=None,
    )
    pid = None
    try:
        service = approvals.ApprovalService(SimpleNamespace())
        with pytest.raises(approvals.ApprovalActionError, match="timed out after 1s"):
            await service._apply_driver_deploy(appr, True)
        pid = await _pid_from(pidfile)
        assert await _gone(pid), "the deploy's child outlived the timeout"
        assert "deployed_at" not in appr.payload
    finally:
        _cleanup(pid)


async def test_a_command_that_finishes_in_time_is_untouched(tmp_path):
    code, output = await approvals._run_shell("echo ok", str(tmp_path), 10)
    assert (code, output.strip()) == (0, "ok")


async def test_the_autonomy_executor_kills_the_whole_group_on_timeout(tmp_path):
    from life_graph.autonomy.pipeline.executor import CommandExecutor

    pidfile = tmp_path / "pid"
    pid = None
    try:
        started = time.monotonic()
        result = await CommandExecutor().execute(
            _command(pidfile), timeout_seconds=1, cwd=str(tmp_path)
        )
        pid = await _pid_from(pidfile)

        # Killing /bin/sh alone left the sleep holding the pipes, and the
        # executor waited out its whole 60 seconds.
        assert time.monotonic() - started < 15
        assert result.timed_out is True
        assert result.exit_code != 0
        assert await _gone(pid), "a child of /bin/sh outlived the timeout"
    finally:
        _cleanup(pid)
