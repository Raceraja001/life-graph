"""After a queued run: a rate-limited cloud run goes back on the queue, and a
failed nightly local run is handed to OpenCode once."""

from __future__ import annotations

import uuid

import pytest

from life_graph.models.db import AgentTask
from life_graph.services import compute_router, dev_tasks
from tests.unit.fakes import FakeSession, session_factory

EXHAUSTED = "All models are currently unavailable. Please try again shortly."


def _task(**kw):
    props = {
        "kind": "dev_task",
        "origin": "nightly",
        "project_name": "life-graph",
        "finding_key": "untested:x",
        "finding_kind": "untested",
        "run_mode": "queue",
        **kw.pop("properties", {}),
    }
    return AgentTask(
        id=uuid.uuid4(),
        tenant_id="raja",
        agent_name="dev_task",
        project_id=uuid.uuid4(),
        instructions="Write tests for x",
        assigned_agent=kw.pop("assigned_agent", "code-fixer-local"),
        status=kw.pop("status", "failed"),
        error=kw.pop("error", "ran out of tool rounds"),
        result=kw.pop("result", {"success": False, "metadata": {"stop_reason": "max_iterations"}}),
        properties=props,
        status_history=[],
        **kw,
    )


@pytest.fixture
def created(monkeypatch):
    calls = []

    async def fake_create(_factory, tenant_id, **kw):
        calls.append({"tenant_id": tenant_id, **kw})
        return {"id": "new-task"}

    monkeypatch.setattr(dev_tasks, "create_dev_task", fake_create)
    return calls


@pytest.fixture
def benched(monkeypatch):
    calls = []

    async def cool(seconds=None):
        calls.append(seconds)

    monkeypatch.setattr(compute_router, "cool_cloud_route", cool)
    return calls


async def _after(task):
    session = FakeSession(objects={(AgentTask, task.id): task})
    await dev_tasks._after_queued_run(session_factory(session), str(task.id))
    return session


async def test_rate_limited_cloud_run_goes_back_on_the_queue(created, benched):
    task = _task(
        assigned_agent="code-fixer-cloud",
        error=EXHAUSTED,
        properties={"route": "cloud", "routed_from": "code-fixer-local"},
    )
    session = await _after(task)
    assert task.status == "queued"
    assert task.assigned_agent == "code-fixer-local"
    assert task.error is None and task.result == {}
    assert "route" not in task.properties and "routed_from" not in task.properties
    assert task.properties["cloud_requeues"] == 1
    assert task.status_history[-1]["status"] == "queued"
    assert benched == [None] and session.commits == 1
    assert created == []  # not escalated: nothing was wrong with the task


async def test_a_mid_stream_429_counts_as_rate_limited(created, benched):
    task = _task(
        assigned_agent="code-fixer-cloud",
        error="Internal error: RateLimitError",
        properties={"route": "cloud", "routed_from": "code-fixer-local"},
    )
    await _after(task)
    assert task.status == "queued" and benched


async def test_requeues_stop_after_the_limit(created, benched):
    task = _task(
        assigned_agent="code-fixer-cloud",
        error=EXHAUSTED,
        properties={
            "route": "cloud",
            "routed_from": "code-fixer-local",
            "cloud_requeues": dev_tasks.MAX_CLOUD_REQUEUES,
        },
    )
    await _after(task)
    assert task.status == "failed" and benched == []
    assert created == []  # exhausted models are not the model's failure


async def test_failed_nightly_local_run_is_handed_to_opencode(created, benched):
    task = _task()
    await _after(task)
    (call,) = created
    assert call["persona_name"] == dev_tasks.ESCALATION_PERSONA
    assert call["start"] is False
    assert call["instruction"] == "Write tests for x"
    assert call["project"] == {"id": str(task.project_id), "name": "life-graph"}
    props = call["properties"]
    assert props["escalated_from"] == str(task.id)
    assert props["local_only"] is True
    assert (props["origin"], props["finding_key"]) == ("nightly", "untested:x")
    assert task.properties["escalated_to"] == dev_tasks.ESCALATION_PERSONA


async def test_a_failed_cloud_run_escalates_as_its_original_persona(created, benched):
    task = _task(
        assigned_agent="code-fixer-cloud",
        properties={"route": "cloud", "routed_from": "code-fixer-local"},
    )
    await _after(task)
    assert len(created) == 1


@pytest.mark.parametrize(
    "task_kw",
    [
        {"status": "completed", "error": None},
        {"properties": {"origin": "dashboard"}},
        {"assigned_agent": "code-fixer-opencode"},
        {"properties": {"escalated_from": "earlier"}},
        {"properties": {"escalated_to": "code-fixer-opencode"}},
        {"result": {}},  # dispatch error: the agent never ran
        {"result": {"success": False, "metadata": {"budget_throttled": True}}},
        {"error": EXHAUSTED},
    ],
)
async def test_not_escalated(task_kw, created, benched):
    await _after(_task(**task_kw))
    assert created == []


async def test_a_missing_task_is_ignored(created, benched):
    session = FakeSession()
    await dev_tasks._after_queued_run(session_factory(session), str(uuid.uuid4()))
    assert created == [] and session.commits == 0
