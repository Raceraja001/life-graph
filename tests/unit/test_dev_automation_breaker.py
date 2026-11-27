"""Circuit breaker: normalising, counting, tripping + notice, once per task, success, reset."""

from __future__ import annotations

from life_graph.services.dev.automation.breaker import (
    Breaker,
    apply_failure,
    intake_key,
    normalise_reason,
)
from life_graph.services.dev.automation.settings import BreakerSettings
from life_graph.services.dev.automation.status import failure_reason, finished, item_status_for
from tests.unit.automation_fakes import FakeNotifier, MemStore, T, at

NOW = at("2026-11-27T10:00")
KEY = intake_key("s1")


def breaker(store=None, notifier=None, **settings):
    return Breaker(
        store or MemStore(), notifier or FakeNotifier(), T, BreakerSettings(**settings), NOW
    )


def test_normalise_strips_varying_parts():
    a = normalise_reason(
        "Task 3f2a9c1e-1111-2222-3333-444455556666 failed at 2026-11-27T10:00:01Z in /tmp/lg_x/wt: exit 2"
    )
    b = normalise_reason(
        "Task 00000000-aaaa-bbbb-cccc-ddddeeeeffff failed at 2026-11-28T03:12:44Z in /tmp/lg_y/wt: exit 17"
    )
    assert a == b == "Task <id> failed at <time> in <path>: exit #"
    assert normalise_reason("commit deadbeef12 broke task_ab12cd at 10:30") == (
        "commit <id> broke <id> at <time>"
    )
    assert normalise_reason("") == "Unknown failure"
    assert len(normalise_reason("x" * 1000)) == 300


def test_apply_failure_counts_same_reason_and_resets_on_a_different_one():
    s1, t1 = apply_failure(None, KEY, "src", "boom 1", 3, NOW)
    s2, t2 = apply_failure(s1, KEY, "src", "boom 2", 3, NOW)
    s3, t3 = apply_failure(s2, KEY, "src", "other", 3, NOW)
    assert (s1.consecutive_failures, s2.consecutive_failures, s3.consecutive_failures) == (1, 2, 1)
    assert not (t1 or t2 or t3)


async def test_trips_at_the_threshold_and_publishes_a_notice():
    notifier = FakeNotifier()
    b = breaker(notifier=notifier)
    for n in range(1, 4):
        state = await b.record_failure(KEY, "GitHub issues · race-app", f"gh exited {n}")
    assert state.tripped and state.consecutive_failures == 3 and state.tripped_at == NOW
    assert await b.is_tripped(KEY)
    assert len(notifier.notices) == 1
    notice = notifier.notices[0]
    assert notice["kind"] == "breaker"
    assert notice["title"] == "Automation paused: GitHub issues · race-app — gh exited #"
    # Further failures keep it tripped without a second notice.
    await b.record_failure(KEY, "x", "gh exited 9")
    assert len(notifier.notices) == 1


async def test_each_task_is_counted_once():
    b = breaker()
    for _ in range(5):
        await b.record_failure(KEY, "src", "boom", task_id="t1")
    state = await b.record_failure(KEY, "src", "boom", task_id="t2")
    assert state.consecutive_failures == 2 and not state.tripped


async def test_success_resets_and_untrips():
    store = MemStore()
    b = breaker(store)
    for i in range(3):
        await b.record_failure(KEY, "src", "boom", task_id=f"t{i}")
    assert await b.is_tripped(KEY)
    await b.record_success(KEY, "src", task_id="manual")
    state = await store.get_breaker(T, KEY)
    assert not state.tripped and state.consecutive_failures == 0
    assert "manual" in state.counted


async def test_disabled_breaker_records_nothing_and_never_trips():
    store = MemStore()
    b = breaker(store, enabled=False)
    for _ in range(5):
        assert await b.record_failure(KEY, "src", "boom") is None
    assert store.breakers == {} and not await b.is_tripped(KEY)


async def test_threshold_setting_and_reset():
    store = MemStore()
    b = breaker(store, threshold=2)
    await b.record_failure(KEY, "src", "boom")
    await b.record_failure(KEY, "src", "boom")
    assert await b.is_tripped(KEY)
    state = await b.reset(KEY)
    assert state is not None and not state.tripped and state.consecutive_failures == 0
    assert await b.reset("intake:unknown") is None
    dumped = state.dump()
    assert set(dumped) == {
        "key",
        "label",
        "tripped",
        "consecutiveFailures",
        "lastReason",
        "trippedAt",
        "updatedAt",
    }


async def test_observe_maps_task_outcomes():
    store = MemStore()
    b = breaker(store)
    await b.observe(KEY, "src", {"id": "t1", "status": "failed", "error": "boom"})
    await b.observe(KEY, "src", {"id": "t1", "status": "failed", "error": "boom"})  # once
    await b.observe(KEY, "src", {"id": "t2", "status": "completed", "stage": "needs_review"})
    state = await store.get_breaker(T, KEY)
    assert state.consecutive_failures == 1  # a different reason restarts the count
    await b.observe(KEY, "src", {"id": "t3", "status": "completed", "stage": "awaiting_pr"})
    assert (await store.get_breaker(T, KEY)).consecutive_failures == 0
    await b.observe(KEY, "src", {"id": "t4", "status": "cancelled", "stage": "cancelled"})
    assert (await store.get_breaker(T, KEY)).consecutive_failures == 0


def test_status_rules():
    plan_waiting = {
        "status": "completed",
        "stage": "needs_review",
        "approvals": [{"kind": "driver_plan", "status": "pending"}],
    }
    assert finished(plan_waiting) and failure_reason(plan_waiting) is None
    assert item_status_for(plan_waiting) == ("running", None)
    assert finished({"status": "completed", "stage": "merged"})
    assert not finished({"status": "running", "stage": "running"})
    assert item_status_for(None)[0] == "failed"
    assert item_status_for({"status": "parked", "stage": "parked"}) == ("queued", None)
    assert item_status_for({"status": "completed", "stage": "pr_rejected"})[0] == "failed"
    assert item_status_for({"status": "completed", "stage": "landed"}) == ("done", None)
