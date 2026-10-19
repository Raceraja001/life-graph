"""retry_auto_merges: auto-merge is tried again after the PR's CI finishes.

maybe_auto_merge runs once, when the PR is opened and CI is still running,
so five green agent PRs (#79, #81-#84, 2026-10-19) sat unmerged. The retry
re-runs the same check from the 15-minute sync job.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.services import approvals
from tests.unit.fakes import FakeSession, session_factory, sql


def _merge_appr(**payload):
    return SimpleNamespace(
        status="pending", payload={"driver": "local", "project_id": "p1", **payload}
    )


@pytest.fixture
def auto_merge(monkeypatch):
    calls = []

    async def fake(self, appr, driver_name, project_id, auto_merge):
        calls.append((driver_name, project_id, auto_merge))
        if appr.payload.get("green"):
            appr.status = "approved"

    monkeypatch.setattr(approvals.ApprovalService, "maybe_auto_merge", fake)
    return calls


async def test_retries_only_merges_that_asked_for_auto_merge(auto_merge):
    green = _merge_appr(auto_merge=True, green=True)
    still_running = _merge_appr(auto_merge=True)
    manual = _merge_appr(auto_merge=False, green=True)
    session = FakeSession([green, still_running, manual])

    result = await approvals.retry_auto_merges(session_factory(session))

    assert result == {"tried": 2, "merged": 1}
    assert auto_merge == [("local", "p1", True), ("local", "p1", True)]
    assert green.status == "approved" and manual.status == "pending"
    assert session.commits == 1
    text = sql(session.statements[0])
    assert "'driver_merge'" in text and "'pending'" in text


async def test_nothing_pending_is_a_no_op(auto_merge):
    session = FakeSession([])
    assert await approvals.retry_auto_merges(session_factory(session)) == {
        "tried": 0,
        "merged": 0,
    }
    assert auto_merge == []


async def test_the_sync_job_retries_first_and_survives_a_failure(monkeypatch):
    from life_graph.services import dev_outcomes
    from life_graph.workers import tasks

    order = []

    async def boom(_factory):
        order.append("retry")
        raise RuntimeError("gh unreachable")

    async def sync_all(_factory):
        order.append("sync")
        return {"settled": 0}

    monkeypatch.setattr(approvals, "retry_auto_merges", boom)
    monkeypatch.setattr(dev_outcomes, "sync_all", sync_all)

    result = await tasks.sync_dev_task_prs({})

    assert order == ["retry", "sync"]
    assert result["auto_merge_retry"]["error"] is True and result["settled"] == 0
