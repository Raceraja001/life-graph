"""retry_auto_merges: auto-merge is tried again after the PR's CI finishes.

maybe_auto_merge runs once, when the PR is opened and CI is still running,
so five green agent PRs (#79, #81-#84, 2026-10-19) sat unmerged. The retry
re-runs the same check from the 15-minute sync job.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from life_graph.services import approvals
from tests.unit.fakes import FakeSession, session_factory, sql


def _merge_appr(**payload):
    return SimpleNamespace(
        id=uuid.uuid4(),
        status="pending",
        payload={"driver": "local", "project_id": "p1", **payload},
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
    # The sweep, then one locking re-read per auto-merge candidate.
    session = FakeSession([green, still_running, manual], green, still_running)

    result = await approvals.retry_auto_merges(session_factory(session))

    assert result == {"tried": 2, "merged": 1}
    assert auto_merge == [("local", "p1", True), ("local", "p1", True)]
    assert green.status == "approved" and manual.status == "pending"
    # Two per claimed row: the execution claim before the merge, the outcome after.
    assert session.commits == 4
    assert green.payload["execution"]["state"] == "done"
    assert "execution" not in still_running.payload  # nothing happened: claim removed
    text = sql(session.statements[0])
    assert "'driver_merge'" in text and "'pending'" in text
    assert len(session.statements) == 3  # manual (no auto_merge) is never locked


async def test_a_merge_someone_is_resolving_is_skipped_not_merged_twice(auto_merge):
    """H4: resolve() holds the row lock while a person's approve runs; the
    sweep claims each row with FOR UPDATE SKIP LOCKED, so a locked (or by now
    resolved) row comes back empty and is left alone."""
    being_approved = _merge_appr(auto_merge=True, green=True)
    free = _merge_appr(auto_merge=True, green=True)
    # The claim of the first finds nothing (skipped); the second is claimed.
    session = FakeSession([being_approved, free], None, free)

    result = await approvals.retry_auto_merges(session_factory(session))

    assert result == {"tried": 1, "merged": 1}
    assert being_approved.status == "pending" and free.status == "approved"
    claim = sql(session.statements[1])
    assert "FOR UPDATE SKIP LOCKED" in claim
    assert "'pending'" in claim


async def test_nothing_pending_is_a_no_op(auto_merge):
    session = FakeSession([])
    assert await approvals.retry_auto_merges(session_factory(session)) == {
        "tried": 0,
        "merged": 0,
    }
    assert auto_merge == []


async def test_the_sync_job_retries_first_and_survives_a_failure(monkeypatch):
    from life_graph.services.dev import outcomes as dev_outcomes
    from life_graph.workers import tasks

    order = []

    async def stale(_factory):
        order.append("stale")
        raise RuntimeError("db hiccup")

    async def boom(_factory):
        order.append("retry")
        raise RuntimeError("gh unreachable")

    async def sync_all(_factory):
        order.append("sync")
        return {"settled": 0}

    monkeypatch.setattr(approvals, "flag_stale_claims", stale)
    monkeypatch.setattr(approvals, "retry_auto_merges", boom)
    monkeypatch.setattr(dev_outcomes, "sync_all", sync_all)

    result = await tasks.sync_dev_task_prs({})

    assert order == ["stale", "retry", "sync"]
    assert result["auto_merge_retry"]["error"] is True and result["settled"] == 0
    assert result["stale_claims_flagged"] == -1


async def test_the_claim_is_committed_before_the_merge_runs(monkeypatch):
    """P0: the merge no longer runs inside the locked transaction; the claim is
    committed first, so the lock is gone and the claim is durable while gh
    runs. Only the merge's own transaction (no row lock) is exempt from the
    idle timeout on Postgres."""
    green = _merge_appr(auto_merge=True, green=True)

    class _PgSession(FakeSession):
        def get_bind(self, *_a, **_k):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    session = _PgSession([green], green, None)
    seen = {}

    async def fake(self, appr, *_a):
        seen["commits_before_merge"] = session.commits
        seen["state"] = appr.payload["execution"]["state"]
        seen["last_statement"] = str(session.statements[-1])
        appr.status = "approved"

    monkeypatch.setattr(approvals.ApprovalService, "maybe_auto_merge", fake)

    await approvals.retry_auto_merges(session_factory(session))

    assert seen == {
        "commits_before_merge": 1,
        "state": "started",
        "last_statement": "SET LOCAL idle_in_transaction_session_timeout = 0",
    }
    assert "FOR UPDATE SKIP LOCKED" in sql(session.statements[1])
