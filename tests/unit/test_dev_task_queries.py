# Generated test file
import types
import uuid

import pytest

from life_graph.services.dev_tasks import _approvals_by_task, _verification_summary
from tests.unit.fakes import FakeSession, sql


@pytest.mark.asyncio
async def test_verification_summary_two_rows():
    # Two VerificationRun rows with distinct data
    row1 = types.SimpleNamespace(attempt=1, passed=True, results="foo")
    row2 = types.SimpleNamespace(attempt=2, passed=False, results="bar")
    session = FakeSession([row1, row2])
    tenant_id = "tenant1"
    task_id = uuid.uuid4()
    result = await _verification_summary(session, tenant_id, task_id)
    assert result == [
        {"attempt": 1, "passed": True, "results": "foo"},
        {"attempt": 2, "passed": False, "results": "bar"},
    ]
    # Ensure the tenant id is present in the SQL statement
    assert tenant_id in sql(session.statements[0])


@pytest.mark.asyncio
async def test_verification_summary_no_rows():
    session = FakeSession()
    tenant_id = "tenant1"
    task_id = uuid.uuid4()
    result = await _verification_summary(session, tenant_id, task_id)
    assert result == []


@pytest.mark.asyncio
async def test_approvals_by_task_grouping():
    # Three approvals, two with the same source_ref
    a1 = types.SimpleNamespace(source_ref="ref1")
    a2 = types.SimpleNamespace(source_ref="ref2")
    a3 = types.SimpleNamespace(source_ref="ref1")
    session = FakeSession([a1, a2, a3])
    tenant_id = "tenant1"
    task_ids = ["id1", "id2"]
    result = await _approvals_by_task(session, tenant_id, task_ids)
    assert set(result.keys()) == {"ref1", "ref2"}
    assert result["ref1"] == [a1, a3]
    assert result["ref2"] == [a2]
    # Ensure one query was executed and tenant id is in it
    assert len(session.statements) == 1
    assert tenant_id in sql(session.statements[0])


@pytest.mark.asyncio
async def test_approvals_by_task_empty_list():
    session = FakeSession()
    tenant_id = "tenant1"
    result = await _approvals_by_task(session, tenant_id, [])
    assert result == {}
    assert session.statements == []
