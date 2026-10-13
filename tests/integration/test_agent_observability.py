"""Read models behind the observability pages (docs/specs/agent-observability.md):
plans with their tasks, per-driver scorecards, failure causes, budget, and
decision gaps -- each against real rows, scoped to one tenant.

Services are called directly rather than over HTTP: the HTTP layer is thin,
and this machine's .env sets API keys, which the ASGI test client lacks.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = ""


@pytest.fixture(autouse=True)
def _fresh_tenant():
    """Each test gets its own tenant: these read models aggregate everything in one."""
    global TENANT
    TENANT = f"obs_{uuid.uuid4().hex[:8]}"


async def _add(*rows):
    from life_graph.storage.database import async_session

    async with async_session() as s:
        s.add_all(rows)
        await s.commit()


def _task(
    status="completed",
    task_type="code_change",
    props=None,
    result=None,
    error=None,
    persona="code-fixer",
):
    from life_graph.models.db import AgentTask

    return AgentTask(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        agent_name="dev_task",
        task_name="t",
        title="t",
        instructions="do it",
        task_type=task_type,
        assigned_agent=persona,
        status=status,
        error=error,
        result=result,
        properties={"kind": "dev_task", "project_name": "p", **(props or {})},
    )


@pytest.mark.asyncio
@skip_on_db_error
async def test_plan_board_lists_a_plan_with_its_tasks_criteria_and_causes():
    from life_graph.models.db import Approval
    from life_graph.services.agent_insights import get_plan, list_plans
    from life_graph.storage.database import async_session

    spec = (
        "**Requirements:**\nAC-1: works — test: tests/unit/test_x.py::test_works\n"
        "AC-2: fails safe — test: tests/unit/test_x.py::test_safe\n"
        "**Tasks:**\n1. build (AC-1)\n2. guard (AC-2)\n"
    )
    plan = _task(
        task_type="plan",
        result={"metadata": {"spec": spec}},
        props={"conformance": {"criteria": [{"id": "AC-1", "status": "passing"}]}},
    )
    pid = str(plan.id)
    t1 = _task(
        result={"metadata": {"driver": "claude_code"}, "cost_usd": 1.5},
        props={"plan_task_id": pid, "plan_task_index": 1},
    )
    t2 = _task(
        status="failed",
        error="budget: monthly budget exhausted",
        props={"plan_task_id": pid, "plan_task_index": 2},
    )
    await _add(plan, t1, t2)
    await _add(
        Approval(
            tenant_id=TENANT,
            kind="driver_merge",
            title="m",
            status="approved",
            source="driver_merge",
            source_ref=str(t1.id),
            payload={},
            resolution_note="Reviewed: diff matches",
            resolved_by="claude-reviewer",
            resolved_at=datetime.now(UTC),
        ),
    )

    async with async_session() as s:
        plans = await list_plans(s, TENANT)
        board = await get_plan(s, TENANT, pid)
        assert await get_plan(s, "someone-else", pid) is None

    assert plans[0]["id"] == pid
    assert plans[0]["children"] == {"total": 2, "by_stage": {"merged": 1, "failed": 1}}
    assert [(c["id"], c["status"]) for c in board["criteria"]] == [
        ("AC-1", "passing"),
        ("AC-2", "unchecked"),
    ]
    assert [t["plan_task_index"] for t in board["tasks"]] == [1, 2]
    assert board["tasks"][0]["stage"] == "merged"
    assert board["tasks"][0]["approvals"][0]["note"] == "Reviewed: diff matches"
    assert board["tasks"][1]["failure"]["cause"] == "budget_exhausted"


@pytest.mark.asyncio
@skip_on_db_error
async def test_scorecards_group_by_driver_and_failures_carry_causes():
    from life_graph.models.db import VerificationRun
    from life_graph.services.agent_insights import failures, scorecards
    from life_graph.storage.database import async_session

    ok = _task(result={"metadata": {"driver": "claude_code", "model": "opus"}, "cost_usd": 2.0})
    # No driver recorded (pre-2026-10-13 row): the persona's pinned driver is used.
    bounced = _task(
        status="failed",
        error="Verification failed after bounce",
        result={"metadata": {}, "cost_usd": 1.0},
    )
    local = _task(
        result={"metadata": {"tool_calls": 3, "model": "qwen"}}, persona="code-fixer-local"
    )
    await _add(ok, bounced, local)
    await _add(
        VerificationRun(
            tenant_id=TENANT,
            task_id=bounced.id,
            attempt=1,
            passed=False,
            results=[{"verifier": "tests_pass", "passed": False}],
        ),
        VerificationRun(
            tenant_id=TENANT,
            task_id=bounced.id,
            attempt=2,
            passed=False,
            results=[{"verifier": "tests_pass", "passed": False}],
        ),
    )

    async with async_session() as s:
        cards = {c["driver"]: c for c in (await scorecards(s, TENANT, 30))["cards"]}
        report = await failures(s, TENANT, 30)

    assert set(cards) == {"claude_code", "local"}
    claude = cards["claude_code"]
    assert (claude["runs"], claude["succeeded"], claude["failed"], claude["bounced"]) == (
        2,
        1,
        1,
        1,
    )
    assert claude["cost_usd"] == 3.0 and claude["models"] == ["opus"]
    assert claude["top_causes"][0]["cause"] == "verification_failed"
    assert cards["local"]["models"] == ["qwen"]
    assert report["total"] == 1
    assert report["failures"][0]["cause"] == "verification_failed"
    assert report["failures"][0]["detail"] == "tests_pass"


@pytest.mark.asyncio
@skip_on_db_error
async def test_decision_gaps_find_busy_topics_without_a_decision():
    from life_graph.models.db import Memory
    from life_graph.services.observability import decision_gaps
    from life_graph.storage.database import async_session

    def mem(content, entities, fact_type="fact"):
        return Memory(
            tenant_id=TENANT,
            content=content,
            status="active",
            properties={"entities": entities, "fact_type": fact_type},
        )

    await _add(
        *[mem(f"OpenHands note {i}", ["OpenHands"]) for i in range(4)],
        *[mem(f"n8n note {i}", ["n8n"]) for i in range(4)],
        mem("We will not use n8n", ["N8N"], fact_type="decision"),
        *[mem(f"pronoun {i}", ["it"]) for i in range(5)],
    )

    async with async_session() as s:
        gaps = await decision_gaps(s, TENANT, min_mentions=4)

    assert [g["entity"] for g in gaps] == ["openhands"]
    assert gaps[0]["mentions"] == 4
    assert len(gaps[0]["recent"]) == 3


@pytest.mark.asyncio
@skip_on_db_error
async def test_budget_reports_spend_against_the_cap_and_top_tasks():
    from life_graph.services.governor import BudgetCategory, governor
    from life_graph.services.observability import budget
    from life_graph.storage.database import async_session

    spender = _task(result={"metadata": {}, "cost_usd": 0.75})
    await _add(spender)
    await governor.record(TENANT, BudgetCategory.DRIVER, 0.75)

    async with async_session() as s:
        b = await budget(s, TENANT)

    assert b["spent_usd"] == 0.75
    assert b["by_category"] == {"driver": 0.75}
    assert b["top_tasks"][0]["id"] == str(spender.id)
    assert b["projected_month_usd"] >= 0.75
