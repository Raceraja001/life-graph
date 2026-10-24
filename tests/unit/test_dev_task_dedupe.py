"""The same instruction for the same project, while one is still to run, is
one task (services/dev_tasks.py create_dev_task)."""

from __future__ import annotations

import uuid

from life_graph.models.db import AgentTask
from life_graph.services import dev_tasks
from tests.unit.fakes import FakeSession, session_factory, sql

PROJECT = {"id": str(uuid.uuid4()), "name": "life-graph"}
INSTRUCTION = "Write unit tests for `merchant_from` in life_graph/services/money.py"


def _open_task(status: str = "queued") -> AgentTask:
    return AgentTask(
        id=uuid.uuid4(),
        tenant_id="raja",
        agent_name="dev_task",
        title=INSTRUCTION,
        instructions=INSTRUCTION,
        task_type="code_change",
        assigned_agent="code-fixer-local",
        project_id=uuid.UUID(PROJECT["id"]),
        status=status,
        properties={
            "kind": "dev_task",
            "instruction_key": dev_tasks.instruction_key(INSTRUCTION),
            "project_name": "life-graph",
        },
        status_history=[],
    )


class TestInstructionKey:
    def test_whitespace_and_case_do_not_matter(self):
        a = dev_tasks.instruction_key("Fix  the\nbug in X")
        assert a == dev_tasks.instruction_key("fix the bug in x")
        assert a == dev_tasks.instruction_key("  FIX THE BUG IN X  ")

    def test_different_instructions_differ(self):
        assert dev_tasks.instruction_key("fix a") != dev_tasks.instruction_key("fix b")


async def test_same_instruction_while_queued_returns_the_existing_task():
    existing = _open_task()
    session = FakeSession(existing)

    data = await dev_tasks.create_dev_task(
        session_factory(session),
        "raja",
        instruction=INSTRUCTION,
        project=PROJECT,
        persona_name="code-fixer-local",
        start=False,
    )

    assert data["duplicate_of"] == str(existing.id)
    assert data["id"] == str(existing.id)
    assert session.added == []
    assert session.commits == 0
    lookup = sql(session.statements[0])
    assert "'queued'" in lookup and "'running'" in lookup
    assert dev_tasks.instruction_key(INSTRUCTION) in lookup
    assert PROJECT["id"] in lookup.replace("'", "")


async def test_a_new_instruction_is_recorded_with_its_key():
    session = FakeSession(None)

    data = await dev_tasks.create_dev_task(
        session_factory(session),
        "raja",
        instruction="  write unit tests for   `other` ",
        project=PROJECT,
        persona_name="code-fixer-local",
        start=False,
        properties={"origin": "nightly"},
    )

    assert "duplicate_of" not in data
    (task,) = session.added
    assert task.properties["instruction_key"] == dev_tasks.instruction_key(
        "write unit tests for `other`"
    )
    assert task.properties["origin"] == "nightly"
    assert task.status == "queued"
    assert session.commits == 1
