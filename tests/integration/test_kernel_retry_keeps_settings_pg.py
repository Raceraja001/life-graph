"""A kernel retry runs with the settings of the run that failed (M2).

`_retry_task` carried retry_count, max_retries, root_task_id and depth
(#359) but nothing else: a retry got the default timeout and priority, no
session or project, and the name ``retry-N-of-<id>``. A retried scheduled
run (``schedule:<job>``) was then skipped by the action-proposal bridge,
which looks for that name. Now the retry keeps them all.

Real ProcessManager and database; only the model run is replaced.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from life_graph.api.dependencies import get_process_manager
from life_graph.core.tenant import tenant_scope
from life_graph.kernel.process_manager import ProcessManager
from life_graph.models.db import AgentSession, AgentTask
from tests.integration.conftest import skip_on_db_error

TENANT = f"retry_settings_{uuid.uuid4().hex[:8]}"


async def _boom(self, *args, **kwargs):
    raise RuntimeError("always fails")


async def _retry_of(pm, task_id: uuid.UUID) -> AgentTask:
    """Wait (the first backoff is 1 s) for the failed retry of `task_id`."""
    for _ in range(100):
        async with pm._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(AgentTask).where(AgentTask.parent_task_id == task_id)
                    )
                )
                .scalars()
                .all()
            )
        if rows and rows[0].status == "failed":
            assert len(rows) == 1
            return rows[0]
        await asyncio.sleep(0.1)
    pytest.fail("no failed retry appeared")


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_retry_keeps_name_priority_timeout_session_and_project():
    pm = get_process_manager()
    conv = AgentSession(tenant_id=TENANT, user_message="retry settings", routed_to="scout")
    async with pm._session_factory() as session:
        session.add(conv)
        await session.commit()
    project_id = uuid.uuid4()

    with tenant_scope(TENANT), patch.object(ProcessManager, "_run_agent", _boom):
        spawn = await pm.spawn(
            TENANT,
            "scout",
            {"message": "go"},
            task_name="schedule:nightly-check",
            priority="high",
            timeout_seconds=123,
            max_retries=1,
            session_id=conv.id,
            project_id=project_id,
        )
        first = uuid.UUID(spawn["task_id"])
        retry = await _retry_of(pm, first)

    assert retry.retry_count == 1
    assert retry.task_name == "schedule:nightly-check"
    assert retry.priority == "high"
    assert retry.timeout_seconds == 123
    assert retry.session_id == conv.id
    assert retry.project_id == project_id


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_unnamed_task_is_still_labelled_as_a_retry():
    pm = get_process_manager()
    with tenant_scope(TENANT), patch.object(ProcessManager, "_run_agent", _boom):
        spawn = await pm.spawn(TENANT, "scout", {"message": "go"}, max_retries=1)
        first = uuid.UUID(spawn["task_id"])
        retry = await _retry_of(pm, first)

    assert retry.task_name == f"retry-1-of-{first!s:.8}"
    assert retry.priority == "normal"
    assert retry.timeout_seconds == pm._default_timeout
    assert retry.session_id is None
    assert retry.project_id is None
