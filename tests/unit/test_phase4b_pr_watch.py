"""Phase 4b: the PR feedback loop -- signals, dedupe, one round in flight, max rounds, merged."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from life_graph.config import settings
from life_graph.models.db import AgentTask, Approval, PrWatch
from life_graph.services.dev import pr_feedback_signals as sig
from life_graph.services.dev import pr_watch
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev.continuation import ContinueError
from tests.unit.fakes import FakeSession, session_factory

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
PR = "https://github.com/raja/app/pull/7"
SHA = "c" * 40

VIEW = {
    "state": "OPEN",
    "mergeable": "MERGEABLE",
    "headRefOid": SHA,
    "statusCheckRollup": [
        {"__typename": "CheckRun", "name": "test", "workflowName": "CI", "conclusion": "FAILURE",
         "detailsUrl": "https://github.com/raja/app/actions/runs/42/job/1"},
        {"__typename": "CheckRun", "name": "lint", "conclusion": "SUCCESS"},
        {"__typename": "StatusContext", "context": "deploy/preview", "state": "ERROR",
         "targetUrl": "https://example.test/x"},
    ],
    "reviews": [
        {"id": "R1", "state": "CHANGES_REQUESTED", "body": "Please rename x.",
         "author": {"login": "raja"}, "submittedAt": "2026-11-27T11:00:00Z"},
        {"id": "R2", "state": "APPROVED", "body": "ok", "author": {"login": "bob"}},
        {"id": "R3", "state": "COMMENTED", "body": "", "author": {"login": "bob"}},
    ],
    "comments": [
        {"id": "C1", "body": "Life Graph opened this PR", "author": {"login": "raja"},
         "createdAt": "2026-11-27T11:05:00Z"},
        {"id": "C2", "body": "Also update the docs", "author": {"login": "raja"},
         "createdAt": "2026-11-27T11:06:00Z"},
        {"id": "C0", "body": "old note", "author": {"login": "raja"},
         "createdAt": "2026-11-20T00:00:00Z"},
    ],
}  # fmt: skip
INLINE = [
    {"id": 9, "body": "off by one here", "user": {"login": "raja"}, "path": "a.py", "line": 3,
     "created_at": "2026-11-27T11:07:00Z"},
]  # fmt: skip


# ── Parsing and signals (pure) ──────────────────────────────────


def test_parse_pr_view_and_inline_comments():
    snap = sig.parse_pr_view(VIEW)
    assert snap.state == "OPEN" and snap.head_sha == SHA
    assert [c.name for c in snap.failing_checks] == ["CI / test", "deploy/preview"]
    assert snap.failing_checks[0].run_id == "42"
    keys = [c.key for c in snap.comments]
    assert keys == ["review:R1", "comment:C2", "comment:C0"]  # own, approval, empty skipped
    inline = sig.parse_inline_comments(INLINE)
    assert inline[0].key == "inline:9" and inline[0].path == "a.py" and inline[0].line == 3
    assert sig.parse_pr_url(PR) == ("raja/app", 7)
    assert sig.parse_pr_url("https://gitlab.com/x/y/-/merge_requests/1") is None


def test_new_signals_dedupe_by_head_sha_and_ignore_older_comments():
    snap = sig.parse_pr_view(VIEW)
    since = datetime(2026, 11, 27, tzinfo=UTC)
    first = sig.new_signals(snap, set(), since)
    assert [c.name for c in first.checks] == ["CI / test", "deploy/preview"]
    assert [c.key for c in first.comments] == ["review:R1", "comment:C2"]  # C0 predates
    again = sig.new_signals(snap, set(first.keys), since)
    assert not again.any()
    # The same check failing on a new head commit is new feedback.
    snap.head_sha = "d" * 40
    assert [c.name for c in sig.new_signals(snap, set(first.keys), since).checks] == [
        "CI / test",
        "deploy/preview",
    ]


def test_conflicts_and_the_toggles():
    snap = sig.parse_pr_view({**VIEW, "mergeable": "CONFLICTING"})
    s = sig.new_signals(snap, set(), None, on_checks=False, on_comments=False)
    assert s.conflict and not s.checks and not s.comments
    assert s.keys == [f"conflict:{SHA}"]
    assert not sig.new_signals(snap, set(s.keys), None, on_checks=False, on_comments=False).any()


def test_the_feedback_message():
    snap = sig.parse_pr_view({**VIEW, "mergeable": "CONFLICTING"})
    snap.comments.extend(sig.parse_inline_comments(INLINE))
    signals = sig.new_signals(snap, set(), datetime(2026, 11, 27, tzinfo=UTC))
    text = sig.build_feedback(
        pr_url=PR, head_sha=SHA, base_branch="main", signals=signals,
        logs={"CI / test": "AssertionError: 1 != 2"},
    )  # fmt: skip
    assert "## Failing checks (head cccccccc)" in text and "AssertionError: 1 != 2" in text
    assert "@raja (changes requested):" in text and "on a.py:3" in text
    assert "git merge origin/main" in text
    assert "Don't push" in text and len(text) <= sig.MESSAGE_CHARS
    assert sig.summarize(signals).startswith("2 failing checks: CI / test, deploy/preview")


# ── The watcher ─────────────────────────────────────────────────


class FakeGh:
    def __init__(self, view=None, inline=None):
        self.view = view or VIEW
        self.inline = INLINE if inline is None else inline
        self.calls: list[str] = []

    async def pr_view(self, url, cwd):
        self.calls.append("view")
        return self.view

    async def inline_comments(self, repo, number, cwd):
        self.calls.append(f"inline {repo}#{number}")
        return self.inline

    async def failed_log(self, run_id, repo, cwd):
        self.calls.append(f"log {run_id}")
        return "Traceback: boom"


def cfg(**kw) -> pr_watch.PrFeedbackSettings:
    base = dict(enabled=True, poll_minutes=10, max_rounds=3, on_failing_checks=True,
                on_review_comments=True, on_conflicts=True)  # fmt: skip
    return pr_watch.PrFeedbackSettings(**{**base, **kw})


def make_task(tmp_path, status="completed", **props) -> AgentTask:
    wt = tmp_path / "wt"
    wt.mkdir(exist_ok=True)
    continuation = {"worktree": str(wt), "origin": str(tmp_path), "driver": "codex",
                    "session_id": "s1", "account_id": "acc-1"}  # fmt: skip
    return AgentTask(
        id=uuid.uuid4(), tenant_id="t1", agent_name="dev_task", status=status,
        properties={"kind": "dev_task", "continuation": continuation, **props},
        result={}, status_history=[], title="x",
    )  # fmt: skip


def approval(task, status="approved", url=PR, minutes=0) -> Approval:
    return Approval(
        id=uuid.uuid4(), tenant_id="t1", kind="driver_pr", status=status,
        source_ref=str(task.id), title="Open PR",
        payload={"pr_url": url, "base_branch": "main"} if url else {},
        created_at=NOW + timedelta(minutes=minutes),
    )  # fmt: skip


def watch(task, **kw) -> PrWatch:
    base = dict(id=uuid.uuid4(), tenant_id="t1", task_id=task.id, pr_url=PR, state="watching",
                rounds=0, seen=[], since=datetime(2026, 11, 27, tzinfo=UTC))  # fmt: skip
    return PrWatch(**{**base, **kw})


@pytest.fixture
def world(monkeypatch):
    sent: list = []
    events: list = []

    async def cont(_sf, tenant_id, task_id, feedback, reason):
        sent.append({"tenant": tenant_id, "task": task_id, "feedback": feedback, "reason": reason})

    async def gate(*_a, **_k):
        return []

    async def bus(name, payload):
        events.append(name)

    async def notify(row, reason):
        events.append("notified")

    monkeypatch.setattr(dev_tasks, "_emit_bus", bus)
    monkeypatch.setattr(dev_tasks.task_events, "emit", lambda *a, **k: None)
    monkeypatch.setattr(pr_watch, "_notify_needs_you", notify)
    return {"sent": sent, "events": events, "cont": cont, "gate": gate}


async def check(world, row, task, approvals, gh=None, s=None, force=False, cont=None, gate=None):
    session = FakeSession(row, task, approvals)
    out = await pr_watch.check_one(
        session_factory(session), "t1", row.id, s or cfg(), force=force, gh=gh or FakeGh(), now=NOW,
        continue_fn=cont or world["cont"], gate=gate or world["gate"],
    )  # fmt: skip
    return out, session


async def test_new_feedback_becomes_one_continue_round(world, tmp_path):
    task = make_task(tmp_path)
    row = watch(task)
    gh = FakeGh()

    out, session = await check(world, row, task, [approval(task)], gh=gh)

    assert out == "sent"
    [round_] = world["sent"]
    assert round_["task"] == str(task.id) and round_["reason"].startswith("pr_feedback: ")
    assert "Traceback: boom" in round_["feedback"] and "off by one here" in round_["feedback"]
    assert row.state == "feeding_back" and row.rounds == 1
    assert set(row.seen) >= {f"check:{SHA}:CI / test", "review:R1", "comment:C2", "inline:9"}
    assert row.last_checked_at == NOW
    assert gh.calls == ["view", "inline raja/app#7", "log 42"]  # read only
    assert "PR_WATCH_FEEDBACK" in world["events"]
    assert session.commits == 1


async def test_feedback_already_handed_back_is_not_sent_twice(world, tmp_path):
    task = make_task(tmp_path)
    keys = [f"check:{SHA}:CI / test", f"check:{SHA}:deploy/preview", "review:R1", "comment:C2",
            "inline:9"]  # fmt: skip
    out, _ = await check(world, watch(task, seen=keys), task, [approval(task)])
    assert out == "quiet" and world["sent"] == []


async def test_one_round_in_flight(world, tmp_path):
    task = make_task(tmp_path, status="running")
    row = watch(task, state="feeding_back", rounds=1)
    gh = FakeGh()
    assert (await check(world, row, task, [approval(task)], gh=gh))[0] == "in_flight"
    # Finished, but its update approval waits for the owner: still in flight.
    task.status = "completed"
    pending = approval(task, status="pending", url=None, minutes=5)
    assert (await check(world, row, task, [approval(task), pending], gh=gh))[0] == "in_flight"
    assert gh.calls == [] and world["sent"] == []
    # Approved (pushed): back to watching and read at once, whatever the interval.
    row.last_checked_at = NOW
    pushed = approval(task, status="approved", minutes=5)
    out, _ = await check(world, row, task, [approval(task), pushed], gh=gh)
    assert out == "sent" and row.rounds == 2


async def test_a_round_that_failed_needs_the_owner(world, tmp_path):
    task = make_task(tmp_path, status="failed")
    row = watch(task, state="feeding_back", rounds=1)
    out, _ = await check(world, row, task, [approval(task)])
    assert out == "needs_you" and row.state == "needs_you"
    assert "notified" in world["events"]


async def test_after_max_rounds_it_needs_the_owner_and_says_so_once(world, tmp_path):
    task = make_task(tmp_path)
    row = watch(task, rounds=3)
    out, _ = await check(world, row, task, [approval(task)])
    assert out == "needs_you" and row.state == "needs_you"
    assert row.notified_at == NOW and world["sent"] == []
    assert world["events"].count("notified") == 1
    assert "after 3 feedback rounds" in row.last_feedback


async def test_merged_or_closed_stops_the_watch(world, tmp_path):
    task = make_task(tmp_path)
    row = watch(task)
    gh = FakeGh(view={**VIEW, "state": "MERGED"})
    out, _ = await check(world, row, task, [approval(task)], gh=gh)
    assert out == "merged" and row.state == "merged"
    assert gh.calls == ["view"] and world["sent"] == []
    row2 = watch(task)
    out, _ = await check(
        world, row2, task, [approval(task)], gh=FakeGh(view={**VIEW, "state": "CLOSED"})
    )
    assert out == "closed"


async def test_the_gate_holds_a_round(world, tmp_path):
    task = make_task(tmp_path)
    row = watch(task)
    seen = {}

    async def closed(tenant_id, *, driver=None, account_id=None):
        seen.update(driver=driver, account=account_id)
        return ["Budget: monthly budget exhausted."]

    out, _ = await check(world, row, task, [approval(task)], gate=closed)
    assert out == "blocked" and world["sent"] == []
    assert row.last_error == "Waiting: Budget: monthly budget exhausted."
    assert seen == {"driver": "codex", "account": "acc-1"}  # the session's own account
    assert row.seen == [] and row.state == "watching"


async def test_a_busy_task_is_left_for_the_next_poll(world, tmp_path):
    task = make_task(tmp_path)
    row = watch(task)

    async def busy(*_a, **_k):
        raise ContinueError("busy", "Dev task is running")

    out, _ = await check(world, row, task, [approval(task)], cont=busy)
    assert out == "in_flight" and row.state == "watching" and row.seen == []


async def test_a_gone_worktree_stops_the_watch(world, tmp_path):
    task = make_task(tmp_path)
    task.properties["continuation"]["worktree"] = str(tmp_path / "missing")
    row = watch(task)
    out, _ = await check(world, row, task, [approval(task)])
    assert out == "stopped" and "worktree" in row.last_error


async def test_not_due_until_the_poll_interval_passed(world, tmp_path):
    task = make_task(tmp_path)
    row = watch(task, last_checked_at=NOW - timedelta(minutes=3))
    gh = FakeGh()
    assert (await check(world, row, task, [approval(task)], gh=gh))[0] == "not_due"
    assert gh.calls == []
    assert (await check(world, row, task, [approval(task)], gh=gh, force=True))[0] == "sent"


async def test_poll_is_off_by_default():
    assert settings.driver_pr_feedback_enabled is False
    out = await pr_watch.poll(session_factory(FakeSession()))
    assert out == {"enabled": False, "checked": 0, "outcomes": {}}


async def test_discover_watches_open_prs_with_a_kept_worktree(tmp_path):
    task = make_task(tmp_path)
    no_worktree = make_task(tmp_path)
    no_worktree.properties["continuation"] = {"session_id": "s", "worktree": "/nope"}
    session = FakeSession([task, no_worktree], [], [approval(task)], None)

    created = await pr_watch.discover(session, now=NOW)

    assert created == [str(task.id)]
    insert = session.statements[-1]
    assert insert.table.name == "pr_watches"


# ── API ─────────────────────────────────────────────────────────

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "svc-key-9876543210"


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)


@pytest_asyncio.fixture
async def client(keys, monkeypatch):
    from life_graph.api import drivers_automation as api
    from life_graph.api.middleware import TenantMiddleware
    from life_graph.core.tenant import get_current_tenant_id

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_e):
            return False

    async def listing(_s, tenant_id):
        return [{"task_id": "x", "state": "watching", "tenant": tenant_id}]

    async def stop(_sf, tenant_id, task_id):
        return None if task_id.startswith("0") else {"task_id": task_id, "state": "stopped"}

    async def poll(_sf, *, force, tenant_id):
        return {"enabled": True, "checked": 1, "force": force, "tenant": tenant_id}

    monkeypatch.setattr(api, "async_session", lambda: _Session())
    monkeypatch.setattr(api._pr_watch, "list_watches", listing)
    monkeypatch.setattr(api._pr_watch, "stop_watch", stop)
    monkeypatch.setattr(api._pr_watch, "poll", poll)
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(api.router, prefix="/api/v1")
    app.dependency_overrides[get_current_tenant_id] = lambda: "raja"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _as(key):
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": "raja"}


async def test_pr_watch_routes(client):
    r = await client.get("/api/v1/kernel/drivers/pr-watch", headers=_as(SERVICE_KEY))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["settings"]["enabled"] is False and data["settings"]["max_rounds"] == 3
    assert data["watches"][0]["tenant"] == "raja"

    r = await client.post("/api/v1/kernel/drivers/pr-watch/poll", headers=_as(SERVICE_KEY))
    assert r.status_code == 403
    r = await client.post("/api/v1/kernel/drivers/pr-watch/poll", headers=_as(OWNER_KEY))
    assert r.json()["data"] == {"enabled": True, "checked": 1, "force": True, "tenant": "raja"}

    task = "1" + str(uuid.uuid4())[1:]
    r = await client.post(f"/api/v1/kernel/drivers/pr-watch/{task}/stop", headers=_as(OWNER_KEY))
    assert r.status_code == 200 and r.json()["data"]["state"] == "stopped"
    missing = "0" + str(uuid.uuid4())[1:]
    r = await client.post(f"/api/v1/kernel/drivers/pr-watch/{missing}/stop", headers=_as(OWNER_KEY))
    assert r.status_code == 404
    r = await client.post("/api/v1/kernel/drivers/pr-watch/nope/stop", headers=_as(OWNER_KEY))
    assert r.status_code == 400
