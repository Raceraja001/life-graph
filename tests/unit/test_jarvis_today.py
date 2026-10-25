"""GET /jarvis/today (services/jarvis_today.py): the Today screen's assembly,
each source failing on its own, the insight rules, and every query scoped to
the device's tenant. No database: sources are faked or their SQL inspected."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from life_graph.services import jarvis_today as jt
from tests.unit.fakes import FakeSession, session_factory, sql

NOW = datetime(2026, 10, 25, 9, 42, tzinfo=UTC)
TODAY = date(2026, 10, 25)
TOMORROW = "2026-10-26"

KEYS = {
    "counts",
    "insights",
    "next_event",
    "brief",
    "schedule",
    "due",
    "money",
    "mail_waiting",
    "work",
    "study_due",
    "learnt",
}


def _event(title, start, end, *, all_day=False, where=None):
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "starts_at": start,
        "ends_at": end,
        "all_day": all_day,
        "location": where,
        "account": "Work",
    }


def _bill(payee, due, *, kind="bill", amount=1240.0, autopay=False):
    return {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "payee": payee,
        "due": due,
        "amount": amount,
        "currency": "INR",
        "autopay": autopay,
        "state": "open",
    }


def _sources(**over):
    src = {
        "events": [
            _event("Standup", "2026-10-25T04:30:00+00:00", "2026-10-25T04:45:00+00:00"),
            _event(
                "Dentist",
                "2026-10-25T07:00:00+00:00",
                "2026-10-25T08:00:00+00:00",
                where="Anna Nagar",
            ),
            _event("Holiday", "2026-10-25T00:00:00+00:00", None, all_day=True),
            _event("Demo", "2026-10-25T10:30:00+00:00", "2026-10-25T11:30:00+00:00"),
        ],
        "bills": [
            _bill("TNEB", TOMORROW),
            _bill("Airtel", "2026-10-31", amount=599.0, autopay=True),
            _bill("Car insurance", "2026-11-01", kind="renewal", amount=14200.0),
        ],
        "documents": [
            {"id": "d1", "title": "Passport", "expires_on": "2026-10-30", "days_left": 5},
            {"id": "d2", "title": "Licence", "expires_on": "2027-01-01", "days_left": 68},
        ],
        "todos": [
            {"id": "t1", "title": "Call the bank", "due": "2026-10-27T00:00:00.000Z"},
            {"id": "t2", "title": "Done one", "due": "2026-10-26", "done": True},
            {"id": "t3", "title": "Sub-task", "due": "2026-10-26", "parent": "t1"},
            {"id": "t4", "title": "No date"},
        ],
        "birthdays": [{"id": "c1", "name": "Amma"}],
        "approvals": 5,
        "to_review": 2,
        "reminders": 1,
        "brief": {"id": "b1", "summary": "Today · Bills", "has_audio": True, "created_at": None},
        "money": {"spent": 27200.0, "budget": 40000.0, "month": "2026-10"},
        "mail_waiting": 6,
        "night_run": {"passed": 3, "total": 4},
        "down": [{"name": "uzhavu.race", "since": "2026-10-25T00:42:00+00:00"}],
        "study_due": 12,
        "learnt": [{"id": "m1", "content": "x", "source": "Jarvis", "status": "pending"}],
    }
    src.update(over)
    return src


def test_the_screen_has_every_part_of_the_contract():
    out = jt.assemble(_sources(), NOW, TODAY)
    assert set(out) == KEYS
    assert out["counts"] == {
        "bills_due": 3,
        "events_today": 4,
        "approvals": 5,
        "to_review": 2,
        "reminders": 1,
    }
    assert out["work"] == {
        "approvals": 5,
        "night_run": {"passed": 3, "total": 4},
        "down": [{"name": "uzhavu.race", "since": "2026-10-25T00:42:00+00:00"}],
    }
    assert (out["mail_waiting"], out["study_due"]) == (6, 12)
    assert out["money"] == {"spent": 27200.0, "budget": 40000.0, "month": "2026-10"}
    assert out["brief"]["id"] == "b1"
    assert [s["title"] for s in out["schedule"]] == ["Standup", "Dentist", "Holiday", "Demo"]
    assert set(out["schedule"][1]) >= {"title", "start", "end", "where"}
    assert out["schedule"][1]["where"] == "Anna Nagar"


def test_next_event_is_the_first_timed_one_not_yet_over():
    out = jt.assemble(_sources(), NOW, TODAY)  # 09:42 UTC: standup and dentist are over
    assert out["next_event"]["title"] == "Demo"
    assert out["next_event"]["start"] == "2026-10-25T10:30:00+00:00"
    late = NOW + timedelta(hours=5)
    assert jt.assemble(_sources(), late, TODAY)["next_event"] is None


def test_due_lists_bills_documents_and_todos_this_week_soonest_first():
    due = jt.assemble(_sources(), NOW, TODAY)["due"]
    assert [(d["kind"], d["title"], d["when"]) for d in due] == [
        ("bill", "TNEB", TOMORROW),
        ("task", "Call the bank", "2026-10-27"),
        ("document", "Passport", "2026-10-30"),
        ("bill", "Airtel", "2026-10-31"),
        ("renewal", "Car insurance", "2026-11-01"),
    ]
    tneb = due[0]
    assert set(tneb) >= {"kind", "title", "when", "amount", "source"}
    assert (tneb["amount"], tneb["source"], tneb["autopay"]) == (1240.0, "email", False)
    assert due[3]["autopay"] is True


def test_insights_bill_tomorrow_document_this_week_birthday_tomorrow():
    ins = jt.assemble(_sources(), NOW, TODAY)["insights"]
    assert [i["kind"] for i in ins] == ["bill", "document", "birthday"]
    bill, doc, bday = ins
    assert bill["title"] == "TNEB ₹1,240 due tomorrow"
    assert bill["actions"] == [{"id": "paid", "label": "Mark paid"}]
    assert bill["id"] == f"bill:{bill['item_id']}"
    assert doc["title"] == "Passport expires in 5 days" and doc["actions"] == []
    assert bday["title"] == "Amma's birthday is tomorrow"
    for i in ins:
        assert set(i) >= {"id", "title", "body", "actions"}


def test_no_insight_for_autopay_or_bills_not_due_tomorrow():
    src = _sources(
        bills=[_bill("Airtel", TOMORROW, autopay=True), _bill("Water", "2026-10-28")],
        documents=[],
        birthdays=[],
    )
    assert jt.assemble(src, NOW, TODAY)["insights"] == []


def test_a_failed_source_empties_only_its_own_part():
    src = _sources(events=None, bills=None, money=None, night_run=None, learnt=None)
    out = jt.assemble(src, NOW, TODAY)
    assert out["counts"]["events_today"] is None and out["counts"]["bills_due"] is None
    assert out["schedule"] == [] and out["next_event"] is None
    assert out["money"] is None and out["work"]["night_run"] is None and out["learnt"] == []
    # The rest is still there.
    assert out["counts"]["approvals"] == 5 and out["study_due"] == 12
    assert [d["kind"] for d in out["due"]] == ["task", "document"]


def test_a_malformed_row_empties_only_its_own_part():
    src = _sources(events=[{"title": "broken", "starts_at": "not a date", "ends_at": None}])
    out = jt.assemble(src, NOW, TODAY)
    assert out["next_event"] is None  # could not be built
    assert out["schedule"][0]["title"] == "broken"
    assert out["counts"]["approvals"] == 5


def test_everything_failing_is_still_a_screen():
    out = jt.assemble({}, NOW, TODAY)
    assert set(out) == KEYS
    assert out["insights"] == [] and out["due"] == [] and out["work"]["down"] == []


@pytest.mark.asyncio
async def test_collect_survives_every_source_raising(monkeypatch, caplog):
    async def boom(*_a, **_k):
        raise RuntimeError("secret: my bank balance")

    for name in (
        "_events",
        "_bills",
        "_documents",
        "_todos",
        "_birthdays_tomorrow",
        "_count",
        "_brief",
        "_money",
        "_mail_waiting",
        "_night_run",
        "_down",
        "_study_due",
        "_learnt",
    ):
        monkeypatch.setattr(jt, name, boom)
    caplog.set_level("DEBUG", logger=jt.__name__)
    out = await jt.today_screen("t1", NOW)
    assert set(out) == KEYS and out["counts"]["approvals"] is None
    # Logged by source and exception type, never the content.
    assert "RuntimeError" in caplog.text and "bank balance" not in caplog.text


@pytest.mark.asyncio
async def test_collect_passes_the_tenant_to_every_source(monkeypatch):
    seen = []

    def spy(name):
        async def fn(tenant_id, *_a, **_k):
            seen.append((name, tenant_id))
            return []

        return fn

    for name in (
        "_events",
        "_bills",
        "_documents",
        "_todos",
        "_birthdays_tomorrow",
        "_brief",
        "_money",
        "_mail_waiting",
        "_night_run",
        "_down",
        "_study_due",
        "_learnt",
    ):
        monkeypatch.setattr(jt, name, spy(name))

    async def count(query):
        seen.append(("_count", "t-own" if "'t-own'" in sql(query) else "other"))
        return 0

    monkeypatch.setattr(jt, "_count", count)
    await jt.collect("t-own", NOW)
    assert seen and all(t == "t-own" for _, t in seen)
    assert sum(1 for n, _ in seen if n == "_count") == 3


def test_count_queries_are_scoped_to_the_tenant():
    for q in (
        jt._approvals_query("t-own"),
        jt._to_review_query("t-own"),
        jt._reminders_query("t-own", TODAY),
    ):
        text = sql(q)
        assert "tenant_id = 't-own'" in text and "'pending'" in text


@pytest.mark.asyncio
async def test_learnt_reads_this_tenants_pending_then_recently_kept(monkeypatch):
    pending = SimpleNamespace(
        id=uuid.uuid4(),
        content="You have a project called home-lab",
        status="pending",
        properties={"surface": "cli"},
        source_type="capture",
        created_at=NOW,
    )
    kept = SimpleNamespace(
        id=uuid.uuid4(),
        content="Rule: local HTML files",
        status="active",
        properties={},
        source_type="explicit",
        created_at=NOW,
    )
    session = FakeSession([pending], [kept])
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(session))
    out = await jt._learnt("t-own", NOW)
    assert [(m["content"], m["source"], m["status"]) for m in out] == [
        ("You have a project called home-lab", "Claude Code", "pending"),
        ("Rule: local HTML files", "Jarvis", "active"),
    ]
    assert all("tenant_id = 't-own'" in sql(s) for s in session.statements)


@pytest.mark.asyncio
async def test_brief_card_from_the_newest_brief(monkeypatch):
    from life_graph.config import settings

    row = SimpleNamespace(
        id=uuid.uuid4(),
        title="Daily Brief — 2026-10-25",
        body="## Today (Sun 25 Oct)\n- x\n\n## Bills & renewals\n- y\n## Night shift\n- z",
        created_at=NOW,
    )
    session = FakeSession(row)
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(session))
    monkeypatch.setattr(settings, "tts_base_url", "http://localhost:8010")
    out = await jt._brief("t-own")
    assert out["summary"] == "Today (Sun 25 Oct) · Bills & renewals · Night shift"
    assert out["has_audio"] is True and out["id"] == str(row.id)
    assert "tenant_id = 't-own'" in sql(session.statements[0])
    monkeypatch.setattr(settings, "tts_base_url", "")
    assert (await jt._brief("t-own"))["has_audio"] is False
    monkeypatch.setattr(
        "life_graph.storage.database.async_session", session_factory(FakeSession(None))
    )
    assert await jt._brief("t-own") is None


def test_money_card_and_night_run():
    summary = {
        "month": "2026-10",
        "total_spent": 27200.0,
        "categories": [
            {"category": "food", "spent": 9000.0, "budget": 10000.0},
            {"category": "fuel", "spent": 3000.0, "budget": None},
            {"category": "rent", "spent": 15200.0, "budget": 30000.0},
        ],
    }
    assert jt.money_card(summary) == {"spent": 27200.0, "budget": 40000.0, "month": "2026-10"}
    no_budget = {**summary, "categories": [{"category": "food", "spent": 1.0, "budget": None}]}
    assert jt.money_card(no_budget)["budget"] is None
    assert jt.money_card({"month": "2026-10", "total_spent": 0.0, "categories": []}) is None
    rep = {"merged": [1, 2], "waiting": [3], "failed": [4], "queued": 2}
    assert jt.night_run(rep) == {"passed": 3, "total": 4}


@pytest.mark.asyncio
async def test_down_lists_apps_down_with_when_the_outage_began(monkeypatch):
    pid_down, pid_up = uuid.uuid4(), uuid.uuid4()
    meta = {"health_url": "https://example.test/health"}
    projects = [
        SimpleNamespace(id=pid_down, name="uzhavu.race", scan_metadata=meta),
        SimpleNamespace(id=pid_up, name="life-graph", scan_metadata=meta),
    ]
    since = "2026-10-25T00:42:00+00:00"
    states = {
        str(pid_down): {"down": True, "down_since": since, "last": {"ok": False}},
        str(pid_up): {"down": False, "down_since": "stale", "last": {"ok": True}},
    }
    config = SimpleNamespace(config={"state": states}, enabled=True)
    session = FakeSession(projects, config)
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(session))
    assert await jt._down("t-own") == [{"name": "uzhavu.race", "since": since}]
    assert all("'t-own'" in sql(s) for s in session.statements)


@pytest.mark.asyncio
async def test_today_endpoint_answers_for_the_requests_tenant(monkeypatch):
    from life_graph.api import jarvis
    from life_graph.core.tenant import tenant_scope

    asked = []

    async def screen(tenant_id, now=None):
        asked.append(tenant_id)
        return jt.assemble({}, NOW, TODAY)

    monkeypatch.setattr(jt, "today_screen", screen)
    with tenant_scope("t-own"):
        body = await jarvis.today()
    assert asked == ["t-own"] and set(body["data"]) == KEYS


@pytest.mark.asyncio
async def test_mark_paid_from_the_phone(monkeypatch):
    from fastapi import HTTPException

    from life_graph.api import jarvis
    from life_graph.connectors import bills
    from life_graph.core.tenant import tenant_scope

    calls = []

    async def mark_paid(session, tenant_id, item_id, paid_at):
        calls.append((tenant_id, item_id))
        return None if item_id == "gone" else 2

    session = FakeSession()
    monkeypatch.setattr(bills, "mark_paid", mark_paid)
    monkeypatch.setattr(jarvis, "async_session", session_factory(session))
    with tenant_scope("t-own"):
        body = await jarvis.bill_paid("i1")
        assert body["data"] == {"id": "i1", "state": "paid", "marked": 2}
        with pytest.raises(HTTPException) as err:
            await jarvis.bill_paid("gone")
    assert err.value.status_code == 404
    assert calls == [("t-own", "i1"), ("t-own", "gone")] and session.commits == 1
