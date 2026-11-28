"""Morning digest push, the start gate, the notice handler, the service and the SQL store."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.core.budget import BudgetDecision
from life_graph.core.events import Event, EventType
from life_graph.services.dev.automation import wiring
from life_graph.services.dev.automation.digest import Digest
from life_graph.services.dev.automation.ports import Candidate
from life_graph.services.dev.automation.service import AutomationService, SettingsError
from life_graph.services.dev.automation.settings import AutomationSettings, IntakeSource
from life_graph.services.dev.automation.store import SqlStore
from tests.unit.automation_fakes import (
    PROJECT_ID,
    FakeExec,
    FakeGate,
    FakeNotifier,
    FakeTasks,
    MemStore,
    T,
    at,
)
from tests.unit.fakes import FakeResult, FakeSession, sql

EMPTY = {"since": "", "merged": [], "waiting": [], "failed": [], "queued": 0}
BUSY = {
    "since": "",
    "merged": [{"id": "1", "title": "Fix login", "stage": "merged", "pr_url": "https://pr/1"}],
    "waiting": [
        {
            "id": "2",
            "title": "Bump deps",
            "stage": "awaiting_pr",
            "pr_url": None,
            "reason": "auto-merge is off",
        }
    ],
    "failed": [],
    "queued": 1,
}


def digest_doc(enabled=True, time="08:00", tz="UTC"):
    d = AutomationSettings(timezone=tz)
    d.digest.enabled = enabled
    d.digest.time = time
    return d


def make_digest(store, notifier, report, now, doc=None, seen=None):
    async def report_fn(tenant_id, since):
        if seen is not None:
            seen.append(since)
        return report

    return Digest(
        tenant_id=T,
        doc=doc or digest_doc(),
        store=store,
        notifier=notifier,
        report_fn=report_fn,
        now=now,
    )


async def test_digest_off_by_default_and_not_before_its_time():
    store, notifier = MemStore(), FakeNotifier()
    assert AutomationSettings().digest.enabled is False
    assert (
        await make_digest(store, notifier, BUSY, at("2026-11-27T09:00"), digest_doc(False)).tick()
        is None
    )
    assert await make_digest(store, notifier, BUSY, at("2026-11-27T07:59")).tick() is None
    assert notifier.notices == []


async def test_digest_sends_once_per_local_day_through_the_notice_path():
    store, notifier = MemStore(), FakeNotifier()
    seen = []
    out = await make_digest(store, notifier, BUSY, at("2026-11-27T08:00"), seen=seen).tick()
    assert out["sent"] and out["merged"] == 1 and out["needsYou"] == 1
    assert seen == [at("2026-11-26T08:00")]  # the first window: the last 24 h
    notice = notifier.notices[0]
    assert notice["kind"] == "digest"
    assert notice["title"].startswith("Night shift: 1 merged, 1 waiting for you")
    assert "merged: Fix login — https://pr/1" in notice["body"]
    assert await make_digest(store, notifier, BUSY, at("2026-11-27T12:00")).tick() is None
    seen.clear()
    await make_digest(store, notifier, BUSY, at("2026-11-28T08:05"), seen=seen).tick()
    assert seen == [at("2026-11-27T08:00")]  # since the previous digest
    assert len(notifier.notices) == 2


async def test_quiet_night_is_recorded_but_not_pushed():
    store, notifier = MemStore(), FakeNotifier()
    out = await make_digest(store, notifier, EMPTY, at("2026-11-27T08:00")).tick()
    assert out["quiet"] and out["sent"] is False and notifier.notices == []
    assert store.state[T]["digest_date"] == "2026-11-27"


async def test_digest_time_is_tenant_local_and_preview_does_not_record():
    store, notifier = MemStore(), FakeNotifier()
    doc = digest_doc(time="07:30", tz="Asia/Kolkata")
    assert await make_digest(store, notifier, BUSY, at("2026-11-27T01:59"), doc).tick() is None
    preview = await make_digest(store, notifier, BUSY, at("2026-11-27T01:59"), doc).preview()
    assert preview["summary"].startswith("1 merged") and T not in store.state
    assert (await make_digest(store, notifier, BUSY, at("2026-11-27T02:00"), doc).tick())["sent"]


# ── start gate ─────────────────────────────────────────────


def _decision(allowed=True, reason="ok"):
    return BudgetDecision(
        allowed=allowed, throttled=False, reason=reason, spent_usd=0, cap_usd=10, remaining_usd=10
    )


@pytest.fixture
def gate_env(monkeypatch):
    from life_graph.autonomy import kill_switch
    from life_graph.drivers import accounts_hook
    from life_graph.services import governor as gov_mod

    env = SimpleNamespace(paused=False, preview=None, decision=_decision(), asked=0)

    async def stopped(tenant_id):
        return env.paused

    async def preview(driver, tenant_id, *, unattended=False, now=None):
        assert unattended is True
        return env.preview

    async def authorize(tenant_id, category, estimated_usd=0.0, *, interactive=False):
        assert interactive is False
        env.asked += 1
        return env.decision

    monkeypatch.setattr(kill_switch, "autonomy_stopped", stopped)
    monkeypatch.setattr(accounts_hook, "preview", preview)
    monkeypatch.setattr(gov_mod.governor, "authorize", authorize)
    return env


async def test_gate_allows_and_checks_the_governor(gate_env):
    assert await wiring.StartGate().blockers(T, "claude_code") == []
    assert gate_env.asked == 1


async def test_gate_kill_switch_and_missing_driver(gate_env):
    gate_env.paused = True
    assert "paused" in (await wiring.StartGate().blockers(T, "local"))[0].lower()
    gate_env.paused = False
    assert await wiring.StartGate().blockers(T, None) == ["The persona has no driver."]


async def test_gate_subscription_share_and_pool_states(gate_env):
    gate_env.preview = {"state": "over_budget"}
    assert "plan-window share" in (await wiring.StartGate().blockers(T, "codex"))[0]
    gate_env.preview = {"state": "cooling"}
    assert "cooling" in (await wiring.StartGate().blockers(T, "codex"))[0]
    gate_env.preview = {"state": "error"}
    assert "could not be read" in (await wiring.StartGate().blockers(T, "codex"))[0]
    gate_env.asked = 0
    gate_env.preview = {"state": "selected", "kind": "subscription"}
    assert await wiring.StartGate().blockers(T, "codex") == []
    assert gate_env.asked == 0  # a subscription run is not dollar-budgeted
    gate_env.preview = {"state": "selected", "kind": "api_key"}
    gate_env.decision = _decision(False, "monthly budget exhausted")
    assert await wiring.StartGate().blockers(T, "codex") == ["Budget: monthly budget exhausted"]


async def test_gate_fails_closed(gate_env, monkeypatch):
    gate_env.decision = _decision(True, "governor unavailable — failed open")
    assert await wiring.StartGate().blockers(T, "local") == ["The budget could not be checked."]
    from life_graph.drivers import accounts_hook

    async def broken(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(accounts_hook, "preview", broken)
    assert "could not be checked" in (await wiring.StartGate().blockers(T, "local"))[0]


# ── notices ────────────────────────────────────────────────


async def test_notice_handler_creates_pushes_and_telegrams():
    calls = []

    class Engine:
        async def create(self, tenant_id, title, body=None, **kw):
            calls.append(("notification", tenant_id, title, kw["priority"], kw["source_type"]))

    class Push:
        async def send_to_tenant(self, tenant_id, title, body, url):
            calls.append(("push", tenant_id, title, url))

    class Channel:
        async def send(self, **kw):
            calls.append(("telegram", kw["tenant_id"], kw["title"]))

    handler = wiring.NoticeHandler(
        session_factory=object(), engine=Engine(), push=Push(), channel=Channel()
    )
    await handler.on_notice(
        Event(
            type=EventType.AUTOMATION_NOTICE,
            payload={
                "tenant_id": T,
                "kind": "breaker",
                "title": "Automation paused: x — y",
                "body": "b",
            },
        )
    )
    assert calls == [
        ("notification", T, "Automation paused: x — y", "important", "dev_automation_breaker"),
        ("push", T, "Automation paused: x — y", "/m"),
        ("telegram", T, "Automation paused: x — y"),
    ]
    await handler.on_notice(Event(type=EventType.AUTOMATION_NOTICE, payload={"kind": "digest"}))
    assert len(calls) == 3  # no tenant: nothing


async def test_event_notifier_emits_on_the_bus(monkeypatch):
    from life_graph.core.events import event_bus

    seen = []

    async def handler(event):
        seen.append(event.payload)

    event_bus.subscribe(EventType.AUTOMATION_NOTICE, handler)
    try:
        await wiring.EventNotifier().publish(T, kind="digest", title="t", body="b", data={"x": 1})
    finally:
        event_bus.unsubscribe(EventType.AUTOMATION_NOTICE, handler)
    assert seen == [{"tenant_id": T, "kind": "digest", "title": "t", "body": "b", "x": 1}]


# ── service ────────────────────────────────────────────────


def service(store=None, tasks=None):
    async def report_fn(tenant_id, since):
        return EMPTY

    return AutomationService(
        store=store or MemStore(),
        tasks=tasks or FakeTasks(),
        gate=FakeGate(),
        notifier=FakeNotifier(),
        exec_=FakeExec(),
        intentions=None,
        report_fn=report_fn,
        clock=lambda: at("2026-11-27T10:00"),
    )


async def test_save_settings_validates_projects_personas_and_chains():
    svc = service()
    d = AutomationSettings()
    d.intake.sources = [IntakeSource(kind="todo_comments", project_id=PROJECT_ID)]
    saved = await svc.save_settings(T, d, "owner")
    assert saved.intake.sources[0].id  # server-set id
    d.intake.sources = [IntakeSource(kind="todo_comments", project_id="nope")]
    with pytest.raises(SettingsError, match="project nope not found"):
        await svc.save_settings(T, d, "owner")
    d.intake.sources = [IntakeSource(kind="todo_comments", project_id=PROJECT_ID, persona="ghost")]
    with pytest.raises(SettingsError, match="persona 'ghost'"):
        await svc.save_settings(T, d, "owner")


async def test_tick_tenant_isolates_failures():
    store = MemStore()

    async def broken(*a, **k):
        raise RuntimeError("db down")

    store.latest_run_with_task = broken
    d = AutomationSettings()
    from tests.unit.test_dev_automation_schedule import job

    d.schedules = [job()]
    store.docs[T] = d
    out = await service(store).tick_tenant(T)
    assert out["schedules"] == {"error": "db down"}
    assert out["digest"] is None and "intake" not in out  # no enabled source: no poll


def test_settings_document_mirrors_race_app_names():
    d = AutomationSettings.model_validate(
        {
            "intake": {
                "maxConcurrent": 2,
                "maxPerDay": 9,
                "sources": [
                    {
                        "kind": "github_issues",
                        "projectId": PROJECT_ID,
                        "agentId": "code-fixer",
                        "pollMinutes": 15,
                        "commentOnIssue": True,
                    }
                ],
            },
            "budget": {"enabled": False},  # race-app sections are ignored
            "runHealth": {},
        }
    )
    out = d.dump()
    assert out["intake"]["maxConcurrent"] == 2 and out["intake"]["maxPerDay"] == 9
    src = out["intake"]["sources"][0]
    assert src["persona"] == "code-fixer" and src["pollMinutes"] == 15 and src["commentOnIssue"]
    assert out["breaker"] == {"enabled": True, "threshold": 3}
    assert out["digest"] == {"enabled": False, "time": "08:00"}
    assert src["enabled"] is False  # off by default
    with pytest.raises(ValueError):
        AutomationSettings.model_validate({"timezone": "Mars/Base"})


# ── SQL store (rendered statements) ────────────────────────


class _SF:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


async def test_sql_insert_item_is_on_conflict_do_nothing_per_tenant():
    session = FakeSession(FakeResult([], rowcount=1))
    added = await SqlStore(_SF(session)).insert_item(T, PROJECT_ID, Candidate("github:a/b#1", "t"))
    assert added is True
    from sqlalchemy.dialects import postgresql

    text = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT ON CONSTRAINT uq_dev_backlog_tenant_key DO NOTHING" in text
    session2 = FakeSession(FakeResult([], rowcount=0))
    assert await SqlStore(_SF(session2)).insert_item(T, PROJECT_ID, Candidate("k", "t")) is False


async def test_sql_update_item_is_tenant_scoped_compare_and_set():
    session = FakeSession(None)
    item = await SqlStore(_SF(session)).update_item(
        T, "00000000-0000-0000-0000-000000000001", expect=("new", "failed"), status="queued"
    )
    assert item is None
    text = sql(session.statements[0])
    assert (
        "dev_backlog.tenant_id = 'raja'" in text
        and "dev_backlog.status IN ('new', 'failed')" in text
    )
    with pytest.raises(ValueError):
        await SqlStore(_SF(session)).update_item(T, "x", external_key="other")


async def test_sql_reads_filter_by_tenant():
    session = FakeSession(None)
    store = SqlStore(_SF(session))
    await store.list_items(T, "new")
    await store.count_active(T)
    await store.has_slot(T, PROJECT_ID, "2026-11-27")
    await store.latest_run_with_task(T, PROJECT_ID)
    await store.list_breakers(T)
    for stmt in session.statements:
        assert "tenant_id = 'raja'" in sql(stmt)
