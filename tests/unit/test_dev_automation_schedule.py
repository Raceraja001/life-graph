"""Dev-task schedules and chains: slot matching (catch-up, DST), the scheduler, chains, cycles."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from life_graph.services.dev.automation.breaker import BreakerState, schedule_key
from life_graph.services.dev.automation.clock import (
    decide_slot,
    local_parts,
    previous_local_parts,
)
from life_graph.services.dev.automation.scheduler import ScheduleError, Scheduler
from life_graph.services.dev.automation.settings import (
    AutomationSettings,
    ScheduledDevJob,
    assign_ids,
    chain_problem,
    settings_problem,
)
from tests.unit.automation_fakes import (
    PROJECT_ID,
    FakeGate,
    FakeNotifier,
    FakeTasks,
    MemStore,
    T,
    at,
)

UTC_ZONE = ZoneInfo("UTC")
NY = ZoneInfo("America/New_York")
J1 = "00000000-0000-0000-0000-0000000000a1"
J2 = "00000000-0000-0000-0000-0000000000a2"
J3 = "00000000-0000-0000-0000-0000000000a3"


def decide(time, now, zone=UTC_ZONE, days=range(7), handled=(), after=None, enabled=True):
    return decide_slot(
        enabled=enabled,
        days=days,
        time=time,
        after=after,
        today=local_parts(now, zone),
        yesterday=previous_local_parts(now, zone),
        handled=lambda d: d in handled,
    )


# ── slot matching ──────────────────────────────────────────


def test_slot_due_once_the_time_passed():
    assert decide("02:00", at("2026-11-27T01:59")).kind == "not_due"
    d = decide("02:00", at("2026-11-27T02:00"))
    assert (d.kind, d.date, d.late_minutes) == ("run", "2026-11-27", 0)
    assert decide("02:00", at("2026-11-27T02:05"), handled={"2026-11-27"}).kind == "not_due"


def test_slot_weekdays_disabled_and_chained():
    friday = at("2026-11-27T03:00")  # a Friday
    assert local_parts(friday, UTC_ZONE).weekday == 5
    assert decide("02:00", friday, days=[1, 2]).kind == "not_due"
    assert decide("02:00", friday, days=[5]).kind == "run"
    assert decide("02:00", friday, enabled=False).kind == "not_due"
    assert decide("02:00", friday, after=J1).kind == "not_due"


def test_catch_up_within_two_hours_else_missed():
    assert decide("02:00", at("2026-11-27T04:00")).kind == "run"  # 120 min late
    missed = decide("02:00", at("2026-11-27T04:01"))
    assert (missed.kind, missed.late_minutes) == ("missed", 121)


def test_yesterdays_slot_caught_up_after_midnight():
    d = decide("23:30", at("2026-11-28T00:20"), days=[5])  # Friday's slot, now Saturday
    assert (d.kind, d.date, d.late_minutes) == ("run", "2026-11-27", 50)
    assert decide("23:30", at("2026-11-28T01:31"), days=[5]).kind == "not_due"  # 121 min: gone


def test_dst_spring_forward_runs_once_late():
    # 2026-03-08 in New York: 02:00 → 03:00. A 02:30 job runs at 03:00 local (07:00 UTC).
    before = at("2026-03-08T06:59")  # 01:59 EST
    assert decide("02:30", before, NY).kind == "not_due"
    d = decide("02:30", at("2026-03-08T07:00"), NY)  # 03:00 EDT
    assert (d.kind, d.date, d.late_minutes) == ("run", "2026-03-08", 30)


def test_dst_fall_back_never_runs_twice():
    # 2026-11-01 in New York: 01:00-02:00 happens twice. Runs at the first 01:30 only.
    first = at("2026-11-01T05:30")  # 01:30 EDT
    second = at("2026-11-01T06:30")  # 01:30 EST
    assert local_parts(first, NY).minutes == local_parts(second, NY).minutes == 90
    assert decide("01:30", first, NY).kind == "run"
    assert decide("01:30", second, NY, handled={"2026-11-01"}).kind == "not_due"


# ── scheduler ──────────────────────────────────────────────


def job(id=J1, **kw):
    base = {
        "id": id,
        "name": f"job-{id[-2:]}",
        "enabled": True,
        "project_id": PROJECT_ID,
        "instruction": "Update dependencies within semver; run tests.",
        "time": "02:00",
    }
    return ScheduledDevJob(**{**base, **kw})


class Env:
    def __init__(self, *jobs, tz="UTC"):
        d = AutomationSettings(timezone=tz)
        d.schedules = list(jobs)
        self.store = MemStore(d)
        self.tasks = FakeTasks()
        self.gate = FakeGate()
        self.notifier = FakeNotifier()

    async def scheduler(self, now):
        self.store.run_time = now
        return Scheduler(
            tenant_id=T,
            doc=await self.store.get_settings(T),
            store=self.store,
            tasks=self.tasks,
            gate=self.gate,
            notifier=self.notifier,
            now=now,
        )

    async def tick(self, now):
        return await (await self.scheduler(now)).tick()


async def test_tick_runs_a_job_once_per_day():
    env = Env(job())
    assert await env.tick(at("2026-11-27T01:59")) == []
    results = await env.tick(at("2026-11-27T02:00"))
    assert [r["outcome"] for r in results] == ["started"]
    created = env.tasks.created[0]
    assert created["start_now"] is False and created["persona"] == "code-fixer-local"
    assert created["properties"]["automation"]["job_id"] == J1
    env.tasks.set(created["id"], "completed", "awaiting_pr")
    assert await env.tick(at("2026-11-27T02:01")) == []
    assert await env.tick(at("2026-11-27T13:00")) == []
    assert len(env.tasks.created) == 1
    assert [r["outcome"] for r in await env.tick(at("2026-11-28T02:00"))] == ["started"]


async def test_missed_slot_is_recorded_and_skipped():
    env = Env(job())
    results = await env.tick(at("2026-11-27T05:00"))
    assert results[0]["outcome"] == "missed" and "Missed by 180 min" in results[0]["detail"]
    assert env.tasks.created == []
    assert await env.tick(at("2026-11-27T05:01")) == []


async def test_refusals_are_recorded_not_retried():
    env = Env(job())
    env.gate.is_paused = True
    r = await env.tick(at("2026-11-27T02:00"))
    assert r[0]["outcome"] == "skipped_kill_switch"
    env.gate.is_paused = False
    assert await env.tick(at("2026-11-27T02:01")) == []  # the slot is handled
    env.gate.reasons = ["Budget: cap reached"]
    r = await env.tick(at("2026-11-28T02:00"))
    assert r[0]["outcome"] == "skipped_budget" and "cap reached" in r[0]["detail"]


async def test_overlap_with_the_previous_run_still_going():
    env = Env(job())
    await env.tick(at("2026-11-27T02:00"))
    r = await env.tick(at("2026-11-28T02:00"))  # yesterday's task still queued
    assert r[0]["outcome"] == "skipped_overlap"


async def test_tripped_breaker_skips_automatic_but_not_run_now():
    env = Env(job())
    env.store.breakers[(T, schedule_key(J1))] = BreakerState(
        key=schedule_key(J1), label="j", tripped=True
    )
    r = await env.tick(at("2026-11-27T02:00"))
    assert r[0]["outcome"] == "skipped_breaker"
    env.gate.reasons = ["Budget: cap reached"]  # run now bypasses the budget too
    out = await (await env.scheduler(at("2026-11-27T09:00"))).run_now(J1)
    assert out["taskId"] == env.tasks.created[0]["id"]
    assert env.tasks.created[0]["start_now"] is True


async def test_run_now_errors():
    env = Env(job())
    sched = await env.scheduler(at("2026-11-27T09:00"))
    with pytest.raises(ScheduleError) as missing:
        await sched.run_now("nope")
    assert missing.value.status == 404
    env.gate.is_paused = True
    with pytest.raises(ScheduleError) as paused:
        await sched.run_now(J1)
    assert paused.value.status == 409


async def test_create_failure_counts_for_the_breaker():
    env = Env(job())
    env.tasks.fail_create = "Persona 'x' not found or has no driver"
    r = await env.tick(at("2026-11-27T02:00"))
    assert r[0]["outcome"] == "failed"
    assert env.store.breakers[(T, schedule_key(J1))].consecutive_failures == 1


async def test_timezone_decides_the_local_time():
    env = Env(job(time="07:30"), tz="Asia/Kolkata")
    assert await env.tick(at("2026-11-27T01:59")) == []  # 07:29 IST
    assert [r["outcome"] for r in await env.tick(at("2026-11-27T02:00"))] == ["started"]


# ── chains ─────────────────────────────────────────────────


async def test_chain_runs_after_the_predecessor_finished_once():
    env = Env(job(J1), job(J2, after=J1, days=[]))
    await env.tick(at("2026-11-27T02:00"))
    first = env.tasks.created[0]["id"]
    assert await env.tick(at("2026-11-27T02:30")) == []  # predecessor still queued
    env.tasks.set(first, "completed", "awaiting_pr")
    r = await env.tick(at("2026-11-27T03:00"))
    assert [(x["jobId"], x["outcome"]) for x in r] == [(J2, "started")]
    chained = env.tasks.created[1]
    assert chained["properties"]["automation"]["after_task_id"] == first
    env.tasks.set(chained["id"], "completed", "merged")
    assert await env.tick(at("2026-11-27T03:01")) == []  # once per predecessor task


async def test_chain_is_held_while_blocked_then_runs():
    env = Env(job(J1), job(J2, after=J1))
    await env.tick(at("2026-11-27T02:00"))
    env.tasks.set(env.tasks.created[0]["id"], "completed", "pr_open")
    env.gate.reasons = ["Budget: cap reached"]
    assert await env.tick(at("2026-11-27T03:00")) == []  # held: nothing claimed
    assert not any(r.trigger == "chain" for _, r in env.store.runs)
    env.gate.reasons = []
    r = await env.tick(at("2026-11-27T20:00"))
    assert [x["outcome"] for x in r] == ["started"]


async def test_chain_window_is_24_hours():
    env = Env(job(J1), job(J2, after=J1))
    await env.tick(at("2026-11-27T02:00"))
    env.tasks.set(env.tasks.created[0]["id"], "completed", "awaiting_pr")
    env.gate.is_paused = True
    await env.tick(at("2026-11-27T03:00"))
    env.gate.is_paused = False
    late = at("2026-11-27T02:00") + timedelta(hours=24, minutes=1)
    r = await env.tick(late)
    assert all(x["jobId"] != J2 for x in r)


async def test_chain_needs_finished_work_not_a_failure():
    env = Env(job(J1), job(J2, after=J1))
    await env.tick(at("2026-11-27T02:00"))
    env.tasks.set(env.tasks.created[0]["id"], "failed", error="boom")
    assert await env.tick(at("2026-11-27T03:00")) == []


def test_chain_problems_are_rejected():
    assert chain_problem([job(J1), job(J2, after=J1)]) is None
    assert "itself" in chain_problem([job(J1, after=J1)])
    assert "doesn't exist" in chain_problem([job(J1, after=J3)])
    loop = [job(J1, after=J3), job(J2, after=J1), job(J3, after=J2)]
    assert "loop" in chain_problem(loop)


def test_assign_ids_translates_draft_ids():
    d = AutomationSettings()
    d.schedules = [job("draft-1"), job("draft-2", after="draft-1")]
    d = assign_ids(d)
    first, second = d.schedules
    assert first.id != "draft-1" and second.after == first.id
    assert settings_problem(d) is None
    d.schedules[0].days = []
    assert "at least one day" in settings_problem(d)


def test_job_validation():
    with pytest.raises(ValueError):
        job(time="25:00")
    with pytest.raises(ValueError):
        job(days=[7])
    assert job(days=[3, 1, 1]).days == [1, 3]
