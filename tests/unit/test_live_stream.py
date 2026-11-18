"""Live session streaming (Stage 4): lines are handed over as they arrive."""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from life_graph.drivers import claude_code
from life_graph.drivers.host_exec import communicate_streaming


class _Proc:
    """A process whose stdout yields lines over time."""

    def __init__(self, lines: list[bytes], delay: float = 0.0, err: bytes = b""):
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.returncode = None
        self._lines, self._delay, self._err = lines, delay, err
        self._feeder = asyncio.get_running_loop().create_task(self._feed())

    async def _feed(self):
        for line in self._lines:
            await asyncio.sleep(self._delay)
            self.stdout.feed_data(line)
        self.stdout.feed_eof()
        self.stderr.feed_data(self._err)
        self.stderr.feed_eof()
        self.returncode = 0

    async def wait(self):
        await self._feeder
        return self.returncode


async def test_each_line_is_handed_over_before_the_process_ends():
    seen: list[tuple[float, str]] = []
    loop = asyncio.get_running_loop()
    proc = _Proc([b"one\n", b"two\n", b"three\n"], delay=0.1, err=b"warn")
    t0 = loop.time()
    out, err = await communicate_streaming(
        proc, 5, lambda line: seen.append((loop.time() - t0, line))
    )
    assert [line for _, line in seen] == ["one\n", "two\n", "three\n"]
    assert seen[0][0] < seen[-1][0]  # streamed, not delivered at the end
    assert out == b"one\ntwo\nthree\n" and err == b"warn"


async def test_a_broken_handler_never_breaks_the_run():
    def boom(_line):
        raise RuntimeError("viewer crashed")

    out, _ = await communicate_streaming(_Proc([b"a\n", b"b\n"]), 5, boom)
    assert out == b"a\nb\n"


async def test_a_timeout_still_raises():
    with pytest.raises(TimeoutError):
        await communicate_streaming(_Proc([b"a\n"] * 50, delay=0.2), 0.3, lambda _l: None)


async def test_a_fake_without_pipes_falls_back_to_communicate():
    class Fake:
        async def communicate(self):
            return b"out", b"err"

    assert await communicate_streaming(Fake(), 5, lambda _l: None) == (b"out", b"err")


def test_stream_json_lines_become_session_events(monkeypatch):
    emitted = []
    monkeypatch.setattr(
        "life_graph.services.dev.task_events.emit",
        lambda tenant, task, kind, content="", **kw: emitted.append((kind, content, kw)),
    )
    packet = claude_code.ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code", instruction="x"
    )
    live = claude_code._LiveStream(packet)
    live(json.dumps({"type": "system", "subtype": "init", "model": "claude-x"}))
    live(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Reading the code"},
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "pytest -q"}},
    ]}}))  # fmt: skip
    live(json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "2 passed", "is_error": False},
    ]}}))  # fmt: skip
    live("not json at all")
    kinds = [k for k, _, _ in emitted]
    assert kinds == ["agent_start", "text", "tool_call", "tool_result"]
    assert emitted[2][2]["data"]["tool"] == "Bash"
    assert "pytest -q" in emitted[2][1]
    assert emitted[3][1] == "2 passed"
    assert all(kw["source"] == "agent" for _, _, kw in emitted)
