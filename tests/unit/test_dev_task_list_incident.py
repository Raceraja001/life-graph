"""Tasks tagged ``properties.incident`` stay in the table but out of the list
and the stats (services/dev_tasks.py list_dev_tasks)."""

from __future__ import annotations

from life_graph.services import dev_tasks
from tests.unit.fakes import FakeSession, sql


async def test_list_leaves_out_incident_tagged_rows():
    session = FakeSession([], [])

    assert await dev_tasks.list_dev_tasks(session, "raja", limit=10) == []

    query = sql(session.statements[0])
    assert "'incident'" in query
    assert "IS NULL" in query
    assert "'dev_task'" in query
    assert "'raja'" in query
