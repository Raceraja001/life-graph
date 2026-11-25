"""Kernel tasks a dead process left queued/running are failed at startup.

kernel/recovery.py fail_interrupted_kernel_tasks, against the real database:
only rows past their own timeout plus the margin are closed, so a run that a
live process (the API or the ARQ worker) is still doing is never touched,
and dev tasks and task-board rows are left to their own owners.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from life_graph.kernel.recovery import (
    DEFAULT_MARGIN_SECONDS,
    INTERRUPTED_ERROR,
    fail_interrupted_kernel_tasks,
)
from life_graph.models.db import AgentTask
from life_graph.storage.database import async_session
from tests.integration.conftest import skip_on_db_error

TENANT = f"kernel_recover_{uuid.uuid4().hex[:8]}"


def _row(name: str, status: str, age: timedelta, *, timeout: int = 300, **extra) -> AgentTask:
    """A task row whose clock started ``age`` ago."""
    at = datetime.now(UTC) - age
    return AgentTask(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        task_name=name,
        agent_name=extra.pop("agent_name", "jarvis"),
        status=status,
        timeout_seconds=timeout,
        created_at=at,
        updated_at=at,
        started_at=at if status == "running" else None,
        **extra,
    )


@pytest.mark.asyncio
@skip_on_db_error
async def test_only_stale_kernel_tasks_are_failed():
    stale = timedelta(seconds=300 + DEFAULT_MARGIN_SECONDS + 60)
    rows = {
        "stale_running": _row("chat:jarvis", "running", stale),
        "stale_queued": _row("chat:jarvis", "queued", stale),
        # Live: a fresh run, and one past its timeout but inside the margin.
        "fresh_running": _row("chat:jarvis", "running", timedelta(seconds=10)),
        "inside_margin": _row("chat:jarvis", "running", timedelta(seconds=300 + 60)),
        # A long timeout keeps an old row alive.
        "long_timeout": _row("scheduled", "running", stale, timeout=3 * DEFAULT_MARGIN_SECONDS),
        # Not ProcessManager's to close.
        "dev_task": _row(
            "dev", "running", stale, agent_name="dev_task", properties={"kind": "dev_task"}
        ),
        "board_task": _row(
            "board",
            "queued",
            stale,
            status_history=[{"status": "queued", "at": "2026-11-01T00:00:00+00:00"}],
        ),
        "already_done": _row("chat:jarvis", "completed", stale),
    }
    async with async_session() as session:
        session.add_all(rows.values())
        await session.commit()
    ids = {name: row.id for name, row in rows.items()}

    failed = await fail_interrupted_kernel_tasks(async_session)
    assert failed >= 2  # other tests' rows in this database may be stale too

    async with async_session() as session:
        after = {
            t.id: t
            for t in (
                await session.execute(select(AgentTask).where(AgentTask.tenant_id == TENANT))
            ).scalars()
        }

    for name in ("stale_running", "stale_queued"):
        task = after[ids[name]]
        assert task.status == "failed", name
        assert task.error == INTERRUPTED_ERROR
        assert task.completed_at is not None
        assert [h["status"] for h in task.status_history] == ["failed"]
        was = "running" if name == "stale_running" else "queued"
        assert was in task.status_history[0]["note"]

    expected = {
        "fresh_running": "running",
        "inside_margin": "running",
        "long_timeout": "running",
        "dev_task": "running",
        "board_task": "queued",
        "already_done": "completed",
    }
    for name, status in expected.items():
        task = after[ids[name]]
        assert task.status == status, name
        assert task.error is None, name

    # Run again: nothing of ours is left to close.
    await fail_interrupted_kernel_tasks(async_session)
    async with async_session() as session:
        again = (
            await session.execute(
                select(AgentTask.status).where(AgentTask.id == ids["fresh_running"])
            )
        ).scalar_one()
    assert again == "running"
