"""A capture with a NUL character is stored without it, instead of failing.

PostgreSQL text/JSONB cannot hold U+0000; the insert failed with a 500, and the
Claude Code hook's queue retries in order, so one tool output with a NUL held
back 2,844 captures (2026-10-13 to 2026-11-02).
"""

from __future__ import annotations

from life_graph.services.capture import CaptureService, without_nul


class _FakeResult:
    def scalars(self):
        return self

    def first(self):
        return None  # no duplicate


class _FakeSession:
    def __init__(self):
        self.added = []

    async def execute(self, *_a, **_k):
        return _FakeResult()

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


def test_nul_is_removed_everywhere():
    value = {"a\x00": ["x\x00y", {"b": "\x00"}], "n": 3, "none": None}

    assert without_nul(value) == {"a": ["xy", {"b": ""}], "n": 3, "none": None}
    assert without_nul("plain") == "plain"
    assert without_nul(None) is None


async def test_a_capture_with_nul_is_stored_without_it():
    svc = CaptureService(_FakeSession(), event_bus=None)
    event = await svc.ingest(
        tenant_id="t1",
        surface="tool_exhaust",
        content="tool:Bash output: ab\x00cd",
        properties={"stderr": "e\x00rr"},
    )

    assert event.content == "tool:Bash output: abcd"
    assert event.properties == {"stderr": "err"}
