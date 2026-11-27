"""Intake runner (services/dev/automation/intake.py): dedupe, limits, sync, reconcile, start/skip."""

from __future__ import annotations

import json

import pytest

from life_graph.services.dev.automation.breaker import BreakerState, intake_key
from life_graph.services.dev.automation.intake import Intake, IntakeError, build_instruction
from life_graph.services.dev.automation.ports import BacklogItem
from life_graph.services.dev.automation.settings import AutomationSettings, IntakeSource
from tests.unit.automation_fakes import (
    PROJECT_ID,
    FakeExec,
    FakeGate,
    FakeIntentions,
    FakeNotifier,
    FakeTasks,
    MemStore,
    T,
    at,
)

NOW = at("2026-11-27T10:00")


def issues(*numbers):
    return json.dumps(
        [
            {"number": n, "title": f"Issue {n}", "url": f"https://github.com/raja/app/issues/{n}"}
            for n in numbers
        ]
    )


def doc(*sources, max_concurrent=5, max_per_day=10, **kw):
    d = AutomationSettings(**{"timezone": "UTC", **kw})
    d.intake.sources = list(sources)
    d.intake.max_concurrent = max_concurrent
    d.intake.max_per_day = max_per_day
    return d


def gh_source(id="s1", **kw):
    return IntakeSource(
        **{"id": id, "kind": "github_issues", "project_id": PROJECT_ID, "enabled": True, **kw}
    )


class Env:
    def __init__(self, d, exec_=None, now=NOW, intentions=None):
        self.store = MemStore(d)
        self.tasks = FakeTasks()
        self.gate = FakeGate()
        self.notifier = FakeNotifier()
        self.exec = exec_ or FakeExec()
        self.intentions = intentions
        self.now = now

    async def intake(self, now=None):
        return Intake(
            tenant_id=T,
            doc=await self.store.get_settings(T),
            store=self.store,
            tasks=self.tasks,
            gate=self.gate,
            notifier=self.notifier,
            exec_=self.exec,
            intentions=self.intentions,
            now=now or self.now,
        )

    async def poll(self, force=True, now=None):
        return await (await self.intake(now)).poll(force=force)


async def test_poll_adds_new_items_and_never_re_adds_a_key():
    env = Env(
        doc(gh_source(), max_concurrent=0),
        FakeExec().on("gh", "issue", "list", stdout=issues(1, 2)),
    )
    first = await env.poll()
    assert first.added == 2 and first.started == 0  # maxConcurrent 0 = start nothing
    # The item is skipped (or done, or failed): its key still never comes back.
    item = next(iter(env.store.items.values()))
    await env.store.update_item(T, item.id, status="skipped")
    second = await env.poll()
    assert second.added == 0
    assert len(env.store.items) == 2


async def test_poll_due_only_respects_poll_minutes():
    env = Env(
        doc(gh_source(poll_minutes=30), max_concurrent=0),
        FakeExec().on("gh", "issue", "list", stdout=issues(1)),
    )
    await env.poll(force=False)
    assert len(env.exec.calls) == 1
    await env.poll(force=False, now=at("2026-11-27T10:10"))
    assert len(env.exec.calls) == 1  # not due yet
    await env.poll(force=False, now=at("2026-11-27T10:31"))
    assert len(env.exec.calls) == 2


async def test_disabled_source_is_not_polled_and_errors_are_per_source():
    bad = gh_source("bad")
    off = gh_source("off", enabled=False)
    env = Env(doc(bad, off), FakeExec().on("gh", "issue", "list", code=1, stderr="auth required"))
    report = await env.poll()
    assert report.errors == {"bad": "gh issue list exited 1: auth required"}
    assert env.store.polled["bad"][1] == "gh issue list exited 1: auth required"
    assert "off" not in env.store.polled


async def test_failing_ci_open_item_covers_newer_failures_of_the_workflow():
    source = IntakeSource(id="ci", kind="failing_ci", project_id=PROJECT_ID, enabled=True)
    runs = [{"databaseId": 10, "workflowName": "CI"}]
    exec_ = FakeExec().on("gh", "run", "list", stdout=json.dumps(runs)).on("gh", "run", "view")
    env = Env(doc(source, max_concurrent=0), exec_)
    assert (await env.poll()).added == 1
    exec_.on("gh", "run", "list", stdout=json.dumps([{"databaseId": 11, "workflowName": "CI"}]))
    assert (await env.poll()).added == 0  # "Fix failing CI: CI" is still open


async def test_starts_respect_max_concurrent_and_max_per_day():
    env = Env(
        doc(gh_source(), max_concurrent=2, max_per_day=3),
        FakeExec().on("gh", "issue", "list", stdout=issues(1, 2, 3, 4)),
    )
    report = await env.poll()
    assert report.added == 4 and report.started == 2
    assert all(not c["start_now"] for c in env.tasks.created)  # automatic = queued, unattended
    assert env.tasks.created[0]["properties"]["origin"] == "intake"
    assert env.tasks.created[0]["persona"] == "code-fixer-local"
    # Both finish: room for one more today (3 per day).
    for c in env.tasks.created:
        env.tasks.set(c["id"], "completed", "merged")
    report = await env.poll()
    assert report.started == 1
    assert len(env.tasks.created) == 3
    assert {i.status for i in env.store.items.values()} >= {"done", "queued", "new"}


async def test_max_per_day_window_is_the_tenant_local_day():
    env = Env(
        doc(gh_source(), max_per_day=1, timezone="Asia/Kolkata"),
        FakeExec().on("gh", "issue", "list", stdout=issues(1, 2)),
    )
    await env.poll(now=at("2026-11-27T18:00"))  # 23:30 IST
    assert len(env.tasks.created) == 1
    env.tasks.set(env.tasks.created[0]["id"], "completed", "merged")
    await env.poll(now=at("2026-11-27T18:20"))  # 23:50 IST, same local day
    assert len(env.tasks.created) == 1
    await env.poll(now=at("2026-11-27T18:40"))  # 00:10 IST next day
    assert len(env.tasks.created) == 2


async def test_gate_blocks_automatic_starts():
    env = Env(doc(gh_source()), FakeExec().on("gh", "issue", "list", stdout=issues(1)))
    env.gate.reasons = ["Budget: monthly cap reached"]
    report = await env.poll()
    assert report.started == 0 and report.blocked == ["Budget: monthly cap reached"]
    assert env.gate.asked == ["local"]  # the persona's driver is what the gate checks
    env.gate.reasons = []
    env.gate.is_paused = True
    assert (await env.poll()).started == 0
    assert env.tasks.created == []


async def test_tripped_breaker_stops_automatic_starts_only():
    env = Env(doc(gh_source()), FakeExec().on("gh", "issue", "list", stdout=issues(1)))
    env.store.breakers[(T, intake_key("s1"))] = BreakerState(
        key=intake_key("s1"), label="x", tripped=True, consecutive_failures=3
    )
    report = await env.poll()
    assert report.started == 0 and report.blocked
    item = next(iter(env.store.items.values()))
    started = await (await env.intake()).start(item.id, by="owner")  # manual bypasses it
    assert started.status == "queued" and env.tasks.created[0]["start_now"] is True
    assert env.tasks.created[0]["properties"]["requested_by"] == "owner"


async def test_sync_follows_the_task():
    env = Env(doc(gh_source()), FakeExec().on("gh", "issue", "list", stdout=issues(1)))
    await env.poll()
    item = next(iter(env.store.items.values()))
    task_id = env.store.items[item.id].task_id
    for (status, stage), expected in [
        (("running", None), "running"),
        (("completed", "awaiting_pr"), "running"),
        (("completed", "merged"), "done"),
    ]:
        env.tasks.set(task_id, status, stage)
        await (await env.intake()).sync()
        assert env.store.items[item.id].status == expected
    # A failed task fails the item (restartable).
    item2 = env.store.add(source_id="s1", status="running", task_id="t-x")
    env.tasks.set("t-x", "failed", error="boom")
    await (await env.intake()).sync()
    assert env.store.items[item2.id].status == "failed"
    assert env.store.items[item2.id].reason == "boom"


async def test_reconcile_closed_issue_cancels_the_task_and_skips():
    exec_ = (
        FakeExec()
        .on("gh", "issue", "list", stdout=issues(5))
        .on("gh", "issue", "view", stdout=json.dumps({"state": "OPEN"}))
    )
    env = Env(doc(gh_source()), exec_)
    await env.poll()
    item = next(iter(env.store.items.values()))
    assert env.store.items[item.id].status == "queued"
    exec_.on("gh", "issue", "view", stdout=json.dumps({"state": "CLOSED"}))
    report = await env.poll()
    assert report.reconciled == 1
    assert env.tasks.cancelled == [env.store.items[item.id].task_id]
    assert env.store.items[item.id].status == "skipped"
    assert "was closed" in env.store.items[item.id].reason


async def test_reconcile_todo_removed_and_ci_green_and_intention_gone():
    todo = IntakeSource(id="todo", kind="todo_comments", project_id=PROJECT_ID, enabled=True)
    ci = IntakeSource(id="ci", kind="failing_ci", project_id=PROJECT_ID, enabled=True)
    lg = IntakeSource(id="lg", kind="life_graph_intentions", project_id=PROJECT_ID, enabled=True)
    exec_ = (
        FakeExec()
        .on("git", "grep", stdout="main:a.py:3:# TODO(race): fix it")
        .on(
            "gh",
            "run",
            "list",
            "failure",
            stdout=json.dumps([{"databaseId": 10, "workflowName": "CI"}]),
        )
        .on("gh", "run", "view")
        .on("gh", "run", "list", "success", stdout="[]")
    )
    intentions = FakeIntentions([{"id": "i1", "content": "Do it #dev", "status": "pending"}])
    env = Env(doc(todo, ci, lg), exec_, intentions=intentions)
    await env.poll()
    assert len(env.tasks.created) == 3
    # Nothing changed: nothing reconciled.
    assert (await env.poll()).reconciled == 0
    exec_.on("git", "grep", code=1)  # the TODO is gone
    exec_.on("gh", "run", "list", "success", stdout=json.dumps([{"databaseId": 11}]))
    intentions.rows[0]["status"] = "completed"
    report = await env.poll()
    assert report.reconciled == 3
    assert sorted(i.reason for i in env.store.items.values()) == [
        'A newer run of "CI" passed on main.',
        "The TODO comment is gone from main.",
        "The intention is no longer active.",
    ]
    assert len(env.tasks.cancelled) == 3


async def test_reconcile_leaves_finished_tasks_alone():
    exec_ = (
        FakeExec()
        .on("gh", "issue", "list", stdout=issues(5))
        .on("gh", "issue", "view", stdout=json.dumps({"state": "CLOSED"}))
    )
    env = Env(doc(gh_source()), exec_)
    await env.poll()
    item = next(iter(env.store.items.values()))
    env.tasks.set(env.store.items[item.id].task_id, "completed", "pr_open")
    await env.poll()
    assert env.tasks.cancelled == []


async def test_launch_failure_marks_failed_and_counts_for_the_breaker():
    env = Env(doc(gh_source()), FakeExec().on("gh", "issue", "list", stdout=issues(1)))
    env.tasks.fail_create = "persona missing"
    await env.poll()
    item = next(iter(env.store.items.values()))
    assert env.store.items[item.id].status == "failed"
    state = env.store.breakers[(T, intake_key("s1"))]
    assert state.consecutive_failures == 1 and state.last_reason == "persona missing"


async def test_start_and_skip_rules():
    env = Env(doc(gh_source()))
    intake = await env.intake()
    with pytest.raises(IntakeError) as missing:
        await intake.start("nope")
    assert missing.value.status == 404
    running = env.store.add(source_id="s1", status="running")
    with pytest.raises(IntakeError) as busy:
        await intake.start(running.id)
    assert busy.value.status == 409
    with pytest.raises(IntakeError):
        await intake.skip(running.id)
    orphan = env.store.add(source_id="gone")
    with pytest.raises(IntakeError, match="no longer exists"):
        await intake.start(orphan.id)
    new = env.store.add(source_id="s1")
    env.gate.is_paused = True
    with pytest.raises(IntakeError, match="kill switch"):
        await intake.start(new.id)
    skipped = await intake.skip(new.id)
    assert skipped.status == "skipped"
    assert (await intake.skip(new.id)).status == "skipped"  # idempotent
    env.gate.is_paused = False
    restarted = await intake.start(new.id)  # a skipped item may be started again
    assert restarted.status == "queued"


async def test_issue_comments_only_when_enabled_and_once_per_stage():
    exec_ = FakeExec().on("gh", "issue", "list", stdout=issues(3)).on("gh", "issue", "comment")
    env = Env(doc(gh_source()), exec_)
    await env.poll()
    assert exec_.ran("comment") == []  # off by default
    env2 = Env(doc(gh_source(comment_on_issue=True)), exec_)
    exec_.calls.clear()
    await env2.poll()
    assert len(exec_.ran("comment")) == 1  # picked
    task_id = env2.tasks.created[0]["id"]
    env2.tasks.set(task_id, "completed", "pr_open", pr_url="https://github.com/raja/app/pull/9")
    await env2.poll()
    await env2.poll()
    env2.tasks.set(task_id, "completed", "merged", pr_url="https://github.com/raja/app/pull/9")
    await env2.poll()
    await env2.poll()
    bodies = [c[c.index("--body") + 1] for c in exec_.ran("comment")]
    assert len(bodies) == 3
    assert "picked this up" in bodies[0] and "pull/9" in bodies[1] and "merged" in bodies[2]


def test_build_instruction_fits_the_limit():
    item = BacklogItem(
        id="1",
        tenant_id=T,
        source_id="s",
        external_key="k",
        title="Fix it",
        body="x" * 9000,
        url="https://u",
    )
    text = build_instruction(item)
    assert len(text) <= 8000
    assert (
        text.startswith("Fix it\n\n")
        and "Source: https://u" in text
        and text.endswith("tests pass.")
    )
