"""Shadow mode (settings.context_snapshot_shadow) only adds references to the trace.

Off: the turn's trace is exactly what it was, and no snapshot is built. On, for
a personal local Jarvis turn: the trace gains ``context_snapshot`` with
references and labels and no content, the prompt is unchanged, and a failing
or slow snapshot never costs the answer. A cloud turn never builds one.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import patch

import pytest

from life_graph.config import settings
from life_graph.core.task_context import set_task_context
from life_graph.kernel.process_manager import ProcessManager
from life_graph.services.memory import snapshot
from life_graph.services.memory.snapshot import (
    DEFAULT_BUDGET,
    ContextItem,
    ContextSnapshot,
    SourceRef,
)

seen: dict = {}


async def _fake_run(self, messages, system_prompt=None, tools=None):
    seen["messages"] = [dict(m) for m in messages]
    seen["system_prompt"] = system_prompt or ""
    yield 'data: {"type": "token", "content": "ok"}\n\n'
    yield 'data: {"type": "done", "model": "m"}\n\n'


async def _block(tenant_id, msg, history=None, *, used=None):
    return "## What you remember about the owner\n- MEMORY-MARKER"


def _snap() -> ContextSnapshot:
    item = ContextItem(
        source_ref=SourceRef("memory", "11111111-1111-1111-1111-111111111111"),
        dimension="preference",
        origin="user_stated",
        confirmed=True,
        evidence="said",
        label="owner said",
        status="active",
        reason="search_hit",
        score=0.8,
        valid_from=None,
        recorded_at=None,
        world_time_known=False,
        freshness="fresh",
        content="SECRET-CONTENT the owner's insurance number",
    )
    return ContextSnapshot(
        query="SECRET-QUERY",
        purpose="conversation",
        as_of=None,
        reference_time="2026-11-20T12:00:00+00:00",
        budget=DEFAULT_BUDGET,
        items=(item,),
        exclusions=(("expired", 2),),
        insufficient=False,
    )


async def _run(message: str, persona: dict) -> dict:
    root = uuid.uuid4()
    mgr = ProcessManager.__new__(ProcessManager)
    set_task_context(task_id=root, tenant_id="t1", root_task_id=root, depth=0)
    with (
        patch("life_graph.agents.orchestrator.AgentOrchestrator.run", _fake_run),
        patch("life_graph.services.memory.context.memory_block", _block),
    ):
        return await mgr._run_agent("t1", "jarvis", {"message": message}, persona)


@pytest.fixture
def built(monkeypatch):
    calls: list[str] = []

    async def fake_assemble(query, **kw):
        calls.append(query)
        return _snap()

    monkeypatch.setattr(snapshot, "assemble_context", fake_assemble)
    return calls


PERSONAL = "personal: when does my car insurance renew?"


async def test_shadow_off_leaves_the_trace_exactly_as_before(monkeypatch, built):
    monkeypatch.setattr(settings, "context_snapshot_shadow", False)
    result = await _run(PERSONAL, {"allowed_tools": None})
    assert set(result["trace"]) == {"route", "local", "models", "memories", "tools"}
    assert built == []


async def test_shadow_on_adds_references_only_and_leaves_the_prompt(monkeypatch, built):
    monkeypatch.setattr(settings, "context_snapshot_shadow", False)
    await _run(PERSONAL, {"allowed_tools": None})
    before = (seen["messages"], seen["system_prompt"])

    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    result = await _run(PERSONAL, {"allowed_tools": None})
    assert (seen["messages"], seen["system_prompt"]) == before
    shadow = result["trace"]["context_snapshot"]
    assert shadow["items"] == [
        {
            "ref": "memory:11111111-1111-1111-1111-111111111111",
            "dimension": "preference",
            "origin": "user_stated",
            "confirmed": True,
            "evidence": "said",
            "status": "active",
            "reason": "search_hit",
            "freshness": "fresh",
            "world_time_known": False,
            # Format 2 (M8 Stage 2): a fingerprint ("" here, the item was
            # built by hand) and the recorded time; still no content.
            "fp": "",
            "rec": None,
        }
    ]
    assert shadow["v"] == 2 and shadow["reference_time"] == "2026-11-20T12:00:00+00:00"
    assert shadow["exclusions"] == {"expired": 2} and shadow["insufficient"] is False
    assert isinstance(shadow["ms"], int)
    assert "SECRET" not in json.dumps(shadow)
    assert built == ["when does my car insurance renew?"]
    assert result["response"] == "ok"


async def test_a_failing_snapshot_never_costs_the_turn(monkeypatch):
    async def broken(query, **kw):
        raise RuntimeError("SECRET-CONTENT in an error")

    monkeypatch.setattr(snapshot, "assemble_context", broken)
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    result = await _run(PERSONAL, {"allowed_tools": None})
    assert result["response"] == "ok"
    assert result["trace"]["context_snapshot"]["error"] == "RuntimeError"
    assert "SECRET" not in json.dumps(result["trace"]["context_snapshot"])


async def test_a_slow_snapshot_is_cut_off_at_its_time_box(monkeypatch):
    async def slow(query, **kw):
        await asyncio.sleep(5)

    monkeypatch.setattr(snapshot, "assemble_context", slow)
    monkeypatch.setattr(snapshot, "SHADOW_TIMEOUT_S", 0.05)
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    result = await _run(PERSONAL, {"allowed_tools": None})
    assert result["trace"]["context_snapshot"]["error"] == "TimeoutError"
    assert result["trace"]["context_snapshot"]["ms"] < 2000


async def test_a_cloud_turn_never_builds_one(monkeypatch, built):
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    result = await _run(
        "cloud: what is the capital of Peru?", {"allowed_tools": None, "model": "openrouter/x/y"}
    )
    assert "context_snapshot" not in result["trace"]
    assert built == []
