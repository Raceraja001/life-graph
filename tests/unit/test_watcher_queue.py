"""The daily job that gathers queued watcher notifications into the brief.

``route_event`` queued important events from non-urgent watchers and nothing
ever sent them (``process_pending`` had no caller). The engine side is tested
against Postgres in tests/integration/test_watcher_queue_pg.py; this covers
the job: the schedule, the kill switch and the settings it passes.
"""

from __future__ import annotations

import pytest

from life_graph.config import settings
from life_graph.workers import watcher_queue

NAME = "life_graph.workers.watcher_queue.deliver_queued_watcher_notifications"


class _Engine:
    def __init__(self, tenants, fail=()):
        self.tenants = tenants
        self.fail = set(fail)
        self.calls: list[tuple] = []

    async def queued_tenants(self):
        return list(self.tenants)

    async def hold_queued_for_brief(self, tid, notifications, **kw):
        self.calls.append((tid, notifications, kw))
        if tid in self.fail:
            raise RuntimeError("boom")
        return {"held": 1, "merged": 0, "expired": 0, "failed": 0}


@pytest.fixture
def wired(monkeypatch):
    engine = _Engine(["t-open", "t-paused", "t-unknown"])
    kernel = object()
    stopped = {"t-paused": True, "t-unknown": True, "t-open": False}

    async def autonomy_stopped(tid):
        return stopped[tid]

    monkeypatch.setattr(watcher_queue, "get_watcher_notification_engine", lambda: engine)
    monkeypatch.setattr(watcher_queue, "get_notification_engine", lambda: kernel)
    monkeypatch.setattr(watcher_queue, "autonomy_stopped", autonomy_stopped)
    return engine, kernel


async def test_paused_tenants_are_skipped_and_the_rest_are_held(wired, monkeypatch):
    engine, kernel = wired
    monkeypatch.setattr(settings, "watcher_queue_max_age_hours", 7)
    monkeypatch.setattr(settings, "watcher_queue_max_per_run", 3)
    out = await watcher_queue.deliver_queued_watcher_notifications({})
    assert engine.calls == [("t-open", kernel, {"max_age_hours": 7, "limit": 3})]
    assert out["results"]["t-paused"] == {"skipped": "autonomy_paused"}
    # autonomy_stopped is True when the flag cannot be read (fail closed).
    assert out["results"]["t-unknown"] == {"skipped": "autonomy_paused"}
    assert out["results"]["t-open"]["held"] == 1


async def test_the_real_kill_switch_check_fails_closed(monkeypatch):
    """The job relies on autonomy_stopped answering True on a DB error."""
    from life_graph.autonomy import kill_switch

    async def broken(tid):
        raise RuntimeError("db down")

    monkeypatch.setattr(kill_switch, "_pause_state", broken)
    assert await kill_switch.autonomy_stopped("t-x") is True


async def test_one_tenant_failing_does_not_stop_the_others(wired, monkeypatch):
    engine, _ = wired
    engine.tenants = ["t-a", "t-b"]
    engine.fail = {"t-a"}

    async def never(tid):
        return False

    monkeypatch.setattr(watcher_queue, "autonomy_stopped", never)
    out = await watcher_queue.deliver_queued_watcher_notifications({})
    assert out["results"]["t-a"] == {"error": 1}
    assert out["results"]["t-b"]["held"] == 1


def test_defaults_are_a_day_with_slack_and_twenty():
    assert settings.watcher_queue_max_age_hours == 26
    assert settings.watcher_queue_max_per_run == 20


def test_cron_runs_once_a_day_just_before_the_brief():
    from life_graph.workers.settings import WorkerSettings

    assert NAME in WorkerSettings.functions
    jobs = [job for job in WorkerSettings.cron_jobs if job.name == f"cron:{NAME}"]
    assert len(jobs) == 1
    assert jobs[0].hour == (settings.brief_hour_utc - 1) % 24
    assert jobs[0].minute == 40
