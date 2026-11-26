"""Change shadow mode (settings.context_change_shadow) only adds a change list to the trace.

It has effect only with settings.context_snapshot_shadow on. Off (either flag),
the trace has no ``context_changes`` and nothing is compared. On, for a
personal local Jarvis turn, the trace gains ``context_changes`` with kinds,
references and fixed reasons and no content; the prompt is unchanged, and a
failing or slow comparison never costs the answer.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from life_graph.config import settings
from life_graph.core.task_context import set_task_context
from life_graph.kernel.process_manager import ProcessManager
from life_graph.services.memory import changes, snapshot
from life_graph.services.memory.changes import Baseline, BaselineLookup, RowState
from life_graph.services.memory.snapshot import (
    DEFAULT_BUDGET,
    ContextItem,
    ContextSnapshot,
    SourceRef,
)

seen: dict = {}
MID = "11111111-1111-1111-1111-111111111111"
#: Close to the real clock: detect() reads it for the 30-day baseline limit.
REF_TIME = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)


async def _fake_run(self, messages, system_prompt=None, tools=None):
    seen["messages"] = [dict(m) for m in messages]
    seen["system_prompt"] = system_prompt or ""
    yield 'data: {"type": "token", "content": "ok"}\n\n'
    yield 'data: {"type": "done", "model": "m"}\n\n'


async def _block(tenant_id, msg, history=None, *, used=None):
    return "## What you remember about the owner\n- MEMORY-MARKER"


def _snap(at: datetime = REF_TIME) -> ContextSnapshot:
    item = ContextItem(
        source_ref=SourceRef("memory", MID),
        dimension="preference",
        origin="user_stated",
        confirmed=True,
        evidence="said",
        label="owner said",
        status="active",
        reason="search_hit",
        score=0.8,
        valid_from=None,
        recorded_at=(at - timedelta(days=3)).isoformat(),
        world_time_known=False,
        freshness="fresh",
        content="SECRET-CONTENT the owner's insurance number",
        fingerprint="00aa00aa00aa00aa",
    )
    return ContextSnapshot(
        query="SECRET-QUERY",
        purpose="conversation",
        as_of=None,
        reference_time=at.isoformat(),
        budget=DEFAULT_BUDGET,
        items=(item,),
        insufficient=False,
        sources=("memories",),
    )


async def _run(message: str, persona: dict) -> dict:
    root = uuid.uuid4()
    mgr = ProcessManager.__new__(ProcessManager)
    set_task_context(task_id=root, tenant_id="t1", root_task_id=root, depth=0)
    seen["task"] = root
    with (
        patch("life_graph.agents.orchestrator.AgentOrchestrator.run", _fake_run),
        patch("life_graph.services.memory.context.memory_block", _block),
    ):
        return await mgr._run_agent("t1", "jarvis", {"message": message}, persona)


@pytest.fixture
def wired(monkeypatch):
    """A built snapshot; a baseline one day older in which the memory was rejected since."""
    calls: dict[str, list] = {"assemble": [], "baseline": [], "resolve": []}

    async def fake_assemble(query, **kw):
        calls["assemble"].append(query)
        return _snap()

    async def fake_baseline(task_id):
        calls["baseline"].append(task_id)
        earlier = _snap(REF_TIME - timedelta(days=1)).compact()
        return BaselineLookup(Baseline.from_compact(earlier, task_id="prev"), frozenset())

    async def fake_resolve(refs, approvals=()):
        calls["resolve"].append(list(refs))
        return {f"memory:{MID}": RowState(ref=f"memory:{MID}", status="rejected")}

    monkeypatch.setattr(snapshot, "assemble_context", fake_assemble)
    monkeypatch.setattr(changes, "find_baseline", fake_baseline)
    monkeypatch.setattr(changes, "resolve_refs", fake_resolve)
    return calls


PERSONAL = "personal: when does my car insurance renew?"


async def test_change_flag_alone_does_nothing(monkeypatch, wired):
    monkeypatch.setattr(settings, "context_snapshot_shadow", False)
    monkeypatch.setattr(settings, "context_change_shadow", True)
    result = await _run(PERSONAL, {"allowed_tools": None})
    assert set(result["trace"]) == {"route", "local", "models", "memories", "tools"}
    assert wired == {"assemble": [], "baseline": [], "resolve": []}


async def test_snapshot_flag_alone_compares_nothing(monkeypatch, wired):
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    monkeypatch.setattr(settings, "context_change_shadow", False)
    result = await _run(PERSONAL, {"allowed_tools": None})
    assert "context_snapshot" in result["trace"]
    assert "context_changes" not in result["trace"]
    assert wired["baseline"] == [] and wired["resolve"] == []


async def test_both_on_add_the_change_list_and_leave_the_prompt(monkeypatch, wired):
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    monkeypatch.setattr(settings, "context_change_shadow", False)
    await _run(PERSONAL, {"allowed_tools": None})
    before = (seen["messages"], seen["system_prompt"])

    monkeypatch.setattr(settings, "context_change_shadow", True)
    result = await _run(PERSONAL, {"allowed_tools": None})
    assert (seen["messages"], seen["system_prompt"]) == before
    trace = result["trace"]
    assert trace["context_snapshot"]["v"] == 2
    found = trace["context_changes"]
    assert found["insufficient"] is False
    assert [(c["kind"], c["ref"]) for c in found["changes"]] == [("rejected", f"memory:{MID}")]
    assert found["baseline"] == {
        "source": "turn_trace",
        "task_id": "prev",
        "same_conversation": True,
    }
    assert isinstance(found["ms"], int)
    blob = json.dumps(found)
    assert "SECRET" not in blob and "00aa00aa00aa00aa" not in blob
    # The baseline was looked up for this very turn.
    assert wired["baseline"][-1] == seen["task"]
    assert result["response"] == "ok"


async def test_a_failing_comparison_never_costs_the_turn(monkeypatch, wired):
    async def broken(task_id):
        raise RuntimeError("SECRET-CONTENT in an error")

    monkeypatch.setattr(changes, "find_baseline", broken)
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    monkeypatch.setattr(settings, "context_change_shadow", True)
    result = await _run(PERSONAL, {"allowed_tools": None})
    assert result["response"] == "ok"
    assert result["trace"]["context_changes"]["error"] == "RuntimeError"
    assert result["trace"]["context_snapshot"]["items"]  # the snapshot is still kept
    assert "SECRET" not in json.dumps(result["trace"]["context_changes"])


async def test_a_slow_comparison_is_cut_off_inside_the_time_box(monkeypatch, wired):
    async def slow(task_id):
        await asyncio.sleep(5)

    monkeypatch.setattr(changes, "find_baseline", slow)
    monkeypatch.setattr(snapshot, "SHADOW_TIMEOUT_S", 0.1)
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    monkeypatch.setattr(settings, "context_change_shadow", True)
    result = await _run(PERSONAL, {"allowed_tools": None})
    assert result["trace"]["context_changes"]["error"] == "TimeoutError"
    assert result["trace"]["context_changes"]["ms"] < 2000


async def test_a_failed_snapshot_is_not_compared(monkeypatch, wired):
    async def broken(query, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr(snapshot, "assemble_context", broken)
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    monkeypatch.setattr(settings, "context_change_shadow", True)
    result = await _run(PERSONAL, {"allowed_tools": None})
    found = result["trace"]["context_changes"]
    assert found["insufficient"] is True and found["changes"] == []
    assert wired["baseline"] == []


async def test_a_cloud_turn_never_compares(monkeypatch, wired):
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    monkeypatch.setattr(settings, "context_change_shadow", True)
    result = await _run(
        "cloud: what is the capital of Peru?", {"allowed_tools": None, "model": "openrouter/x/y"}
    )
    assert "context_changes" not in result["trace"]
    assert wired == {"assemble": [], "baseline": [], "resolve": []}
