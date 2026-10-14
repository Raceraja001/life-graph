"""docs/specs/agent-condenser.md, end to end with a mocked model:
the orchestrator nudges then stops a looping run, condenses a long one before
sending it, and the local driver reports both outcomes honestly."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from life_graph.agents import condenser
from life_graph.agents.orchestrator import AgentOrchestrator


def _delta(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _call(id_, name, args):
    return SimpleNamespace(index=0, id=id_, function=SimpleNamespace(name=name, arguments=args))


async def _stream(chunks):
    for chunk in chunks:
        yield SimpleNamespace(choices=[SimpleNamespace(delta=chunk)])


def _tool(name):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "d",
            "parameters": {"type": "object", "properties": {}},
        },
    }


async def _events(agen):
    out = []
    async for e in agen:
        out.append(json.loads(e.removeprefix("data: ").strip()))
    return out


@pytest.mark.asyncio
async def test_a_looping_model_is_nudged_then_stopped():
    orch = AgentOrchestrator(model="test-model")
    orch.MAX_ITERATIONS = 20
    orch.condense = False

    def looping(*_a, **_kw):
        return _stream([_delta(tool_calls=[_call(None, "code_read", '{"path": "missing.py"}')])])

    with (
        patch("litellm.acompletion", new_callable=AsyncMock) as llm,
        patch(
            "life_graph.agents.orchestrator.registry.execute",
            new_callable=AsyncMock,
            return_value=json.dumps({"error": "file not found"}),
        ) as execute,
    ):
        llm.side_effect = looping
        events = await _events(
            orch.run(messages=[{"role": "user", "content": "read it"}], tools=[_tool("code_read")])
        )

    stuck = [e for e in events if e["type"] == "stuck"]
    assert [s["action"] for s in stuck] == ["nudged", "stopped"]
    assert events[-1]["type"] == "done" and events[-1]["stop_reason"] == "stuck"
    assert execute.await_count == 6  # 3 to notice, nudge, 3 more to give up — not 20
    # The nudge reached the model as a user message after the turn's results.
    later = llm.call_args_list[3].kwargs["messages"]
    assert any(m["role"] == "user" and m["content"].startswith("[Loop detected") for m in later)
    assert condenser.valid([m for m in later if m["role"] != "system"][1:])


@pytest.mark.asyncio
async def test_a_long_run_is_condensed_before_it_is_sent(monkeypatch):
    monkeypatch.setattr(
        condenser,
        "count_tokens",
        lambda messages, model=None: sum(len(condenser._text(m)) for m in messages) // 4,
    )
    orch = AgentOrchestrator(model="test-model", max_tokens=500)
    orch.context_tokens = 8000  # budget = 8000*0.8 - 500 = 5900 tokens ≈ 23.6k chars
    orch.MAX_ITERATIONS = 12
    turn = {"n": 0}

    def reading(*_a, **kw):
        if not kw.get("stream", True):  # the summary side call
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="summary"))]
            )
        turn["n"] += 1
        if turn["n"] > 10:
            return _stream([_delta(content="done")])
        return _stream(
            [
                _delta(
                    tool_calls=[
                        _call(
                            f"c{turn['n']}", "code_read", json.dumps({"path": f"f{turn['n']}.py"})
                        )
                    ]
                )
            ]
        )

    with (
        patch("litellm.acompletion", new_callable=AsyncMock) as llm,
        patch(
            "life_graph.agents.orchestrator.registry.execute",
            new_callable=AsyncMock,
            side_effect=lambda name, args: f"{args['path']}: " + "y" * 5000,
        ),
    ):
        llm.side_effect = reading
        events = await _events(
            orch.run(
                messages=[{"role": "user", "content": "TASK: refactor"}],
                system_prompt="SYSTEM RULES",
                tools=[_tool("code_read")],
            )
        )

    assert any(e["type"] == "condensed" for e in events)
    assert events[-1]["stop_reason"] == "completed"
    budget = condenser.budget_for(8000, 500)
    for call in llm.call_args_list:
        if call.kwargs.get("stream", True):
            sent = call.kwargs["messages"]
            assert condenser.count_tokens(sent) <= budget
            assert (
                sent[0]["content"].startswith("SYSTEM RULES")
                and sent[1]["content"] == "TASK: refactor"
            )


@pytest.mark.asyncio
async def test_one_huge_result_is_capped_in_the_conversation():
    orch = AgentOrchestrator(model="test-model")
    orch.condense = False
    calls = iter(
        [
            _stream([_delta(tool_calls=[_call("c1", "code_read", '{"path": "log"}')])]),
            _stream([_delta(content="ok")]),
        ]
    )
    with (
        patch("litellm.acompletion", new_callable=AsyncMock) as llm,
        patch(
            "life_graph.agents.orchestrator.registry.execute",
            new_callable=AsyncMock,
            return_value="z" * 100_000,
        ),
    ):
        llm.side_effect = lambda *a, **k: next(calls)
        await _events(
            orch.run(messages=[{"role": "user", "content": "x"}], tools=[_tool("code_read")])
        )
    tool_msg = next(m for m in llm.call_args_list[1].kwargs["messages"] if m["role"] == "tool")
    assert len(tool_msg["content"]) < condenser.MAX_RESULT_CHARS + 200


# ── Local driver: honest outcomes ───────────────────────────────────────────


class _FakeOrch:
    MAX_ITERATIONS = 0

    def __init__(self, events, model=None):
        self.events, self.model = events, "test-model"

    async def run(self, **_kw):
        for e in self.events:
            yield "data: " + json.dumps(e)


async def _dispatch(events, tmp_path):
    from life_graph.drivers.base import ContextPacket
    from life_graph.drivers.local import LocalDriver

    with patch(
        "life_graph.agents.orchestrator.AgentOrchestrator", lambda *a, **k: _FakeOrch(events)
    ):
        return await LocalDriver().dispatch(
            ContextPacket(
                task_id="t1", tenant_id="t", task_type="code_change", instruction="do it"
            ),
            tmp_path,
            timeout=30,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("events", "success", "reason"),
    [
        (
            [
                {"type": "tool_call", "name": "code_read"},
                {"type": "done", "stop_reason": "completed"},
            ],
            True,
            "completed",
        ),
        (
            [
                {"type": "partial_error", "message": "All models are currently unavailable."},
                {"type": "done"},
            ],
            False,
            "error",
        ),
        (
            [
                {
                    "type": "done",
                    "warning": "Max tool-calling iterations reached.",
                    "stop_reason": "max_iterations",
                }
            ],
            False,
            "max_iterations",
        ),
        (
            [
                {"type": "stuck", "pattern": "repeat", "tool": "code_read", "action": "stopped"},
                {
                    "type": "done",
                    "stop_reason": "stuck",
                    "warning": "Stopped: stuck in a loop (repeat).",
                },
            ],
            False,
            "stuck",
        ),
    ],
)
async def test_local_driver_outcomes(events, success, reason, tmp_path):
    result = await _dispatch(events, tmp_path)
    assert result.success is success
    assert result.metadata["stop_reason"] == reason
    if reason == "stuck":
        assert any(s["kind"] == "stuck" for s in result.metadata["steps"])


def test_failure_causes_name_the_new_stops():
    from life_graph.services.failure_causes import classify

    stuck = classify(status="failed", error="Stopped: stuck in a loop (repeat).", steps=[])
    assert stuck["cause"] == "stuck"
    rounds = classify(status="failed", error="ran out of tool rounds", steps=[])
    assert rounds["cause"] == "out_of_rounds"


@pytest.mark.asyncio
async def test_a_coding_run_with_no_tool_calls_is_not_a_success(tmp_path):
    from life_graph.drivers.base import ContextPacket
    from life_graph.drivers.local import LocalDriver

    events = [
        {"type": "token", "content": "I added remove()."},
        {"type": "done", "stop_reason": "completed"},
    ]
    with patch(
        "life_graph.agents.orchestrator.AgentOrchestrator", lambda *a, **k: _FakeOrch(events)
    ):
        r = await LocalDriver().dispatch(
            ContextPacket(task_id="t", tenant_id="t", task_type="code_change", instruction="x"),
            tmp_path,
        )
    assert not r.success and r.metadata["stop_reason"] == "no_action"
    assert "no tool calls" in r.error

    text_calls = [
        {"type": "token", "content": '<tool_call>{"name": "code_read"}</tool_call>'},
        {"type": "done"},
    ]
    with patch(
        "life_graph.agents.orchestrator.AgentOrchestrator", lambda *a, **k: _FakeOrch(text_calls)
    ):
        r = await LocalDriver().dispatch(
            ContextPacket(task_id="t", tenant_id="t", task_type="code_change", instruction="x"),
            tmp_path,
        )
    assert "as text" in r.error

    with patch(
        "life_graph.agents.orchestrator.AgentOrchestrator", lambda *a, **k: _FakeOrch(events)
    ):
        r = await LocalDriver().dispatch(
            ContextPacket(task_id="t", tenant_id="t", task_type="research", instruction="x"),
            tmp_path,
        )
    assert r.success  # answering in prose is the job for non-coding tasks
