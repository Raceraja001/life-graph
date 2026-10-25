"""GET /jarvis/plan (services/jarvis_plan.py): one row per day in the owner's
time zone, each item on its day, each source failing on its own, local_only
accounts masked, and every query scoped to the device's tenant. No database:
sources are faked or their SQL inspected."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from life_graph.services import jarvis_plan as jp
from tests.unit.fakes import FakeSession, session_factory, sql

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 25, 9, 42, tzinfo=UTC)
TODAY = date(2026, 10, 25)
SOURCES = ("_events", "_bills", "_documents", "_reminders", "_tasks")


@pytest.fixture(autouse=True)
def _owner_in_india(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")


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


def _sources(**over):
    src = {
        "events": [
            # 23:30 IST on the 25th, so the 25th although it is the 25th in UTC too.
            _event("Late call", "2026-10-25T18:00:00+00:00", "2026-10-25T18:30:00+00:00"),
            # 00:30 IST on the 26th: the 25th in UTC, the 26th for the owner.
            _event("Early run", "2026-10-25T19:00:00+00:00", "2026-10-25T20:00:00+00:00"),
            # All day on the 27th, stored local midnight to local midnight.
            _event(
                "Holiday",
                "2026-10-26T18:30:00+00:00",
                "2026-10-27T18:30:00+00:00",
                all_day=True,
            ),
            # Two days, the 28th and 29th.
            _event(
                "Trip",
                "2026-10-27T18:30:00+00:00",
                "2026-10-29T18:30:00+00:00",
                all_day=True,
                where="Ooty",
            ),
        ],
        "bills": [
            {
                "id": "b1",
                "kind": "bill",
                "payee": "TNEB",
                "due": "2026-10-26",
                "amount": 1240.0,
                "currency": "INR",
                "autopay": False,
            },
            {
                "id": "b2",
                "kind": "renewal",
                "payee": "Car insurance",
                "due": "2026-10-31",
                "amount": 14200.0,
                "currency": "INR",
                "autopay": True,
            },
            {"id": "b3", "kind": "bill", "payee": "Late one", "due": "2026-10-20"},  # overdue
            {"id": "b4", "kind": "statement", "payee": "Bank", "due": "2026-10-26"},
        ],
        "documents": [
            {"id": "d1", "title": "Passport", "expires_on": "2026-10-28", "days_left": 3},
            {"id": "d2", "title": "Licence", "expires_on": "2027-01-01", "days_left": 68},
        ],
        "reminders": [
            {"id": "r1", "text": "Call Amma", "at": "2026-10-25T19:00:00+05:30"},
            {"id": "r2", "text": "Gym", "at": "2026-10-26T06:00:00+05:30"},
        ],
        "tasks": [
            {"id": "t1", "title": "File taxes", "list": "Home", "due": "2026-10-27T00:00:00.000Z"},
            {"id": "t2", "title": "Done", "due": "2026-10-27", "done": True},
            {"id": "t3", "title": "Sub-task", "due": "2026-10-27", "parent": "t1"},
            {"id": "t4", "title": "No date"},
            {"id": "t5", "title": "Far off", "due": "2026-12-01"},
        ],
    }
    src.update(over)
    return src


def _day(out, iso):
    return next(d for d in out["days"] if d["date"] == iso)


def test_one_row_per_day_empty_days_included():
    out = jp.assemble({}, TODAY, 7, IST)
    assert [d["date"] for d in out["days"]] == [f"2026-10-{n}" for n in range(25, 32)]
    for d in out["days"]:
        assert d == {"date": d["date"], "events": [], "due": [], "reminders": [], "tasks": []}


def test_events_land_on_the_owners_days():
    out = jp.assemble(_sources(), TODAY, 7, IST)
    titles = {d["date"]: [e["title"] for e in d["events"]] for d in out["days"]}
    assert titles["2026-10-25"] == ["Late call"]
    assert titles["2026-10-26"] == ["Early run"]
    assert titles["2026-10-27"] == ["Holiday"]
    assert titles["2026-10-28"] == ["Trip"] and titles["2026-10-29"] == ["Trip"]
    assert titles["2026-10-30"] == []
    trip = _day(out, "2026-10-28")["events"][0]
    assert set(trip) == {"id", "title", "start", "end", "where", "all_day", "account"}
    assert (trip["where"], trip["all_day"], trip["account"]) == ("Ooty", True, "Work")


def test_due_bills_and_documents_on_their_dates():
    out = jp.assemble(_sources(), TODAY, 7, IST)
    tneb = _day(out, "2026-10-26")["due"]
    assert tneb == [
        {
            "id": "b1",
            "kind": "bill",
            "title": "TNEB",
            "amount": 1240.0,
            "currency": "INR",
            "autopay": False,
        }
    ]  # the bank statement is not a bill
    assert _day(out, "2026-10-31")["due"][0]["autopay"] is True
    assert _day(out, "2026-10-28")["due"] == [
        {
            "id": "d1",
            "kind": "document",
            "title": "Passport",
            "amount": None,
            "currency": None,
            "autopay": False,
        }
    ]
    assert not any(r["id"] == "b3" for d in out["days"] for r in d["due"])  # before today


def test_reminders_and_tasks():
    out = jp.assemble(_sources(), TODAY, 7, IST)
    assert _day(out, "2026-10-25")["reminders"] == [
        {"id": "r1", "text": "Call Amma", "at": "2026-10-25T19:00:00+05:30"}
    ]
    assert [r["id"] for r in _day(out, "2026-10-26")["reminders"]] == ["r2"]
    assert _day(out, "2026-10-27")["tasks"] == [
        {"id": "t1", "title": "File taxes", "list": "Home", "due": "2026-10-27"}
    ]
    assert sum(len(d["tasks"]) for d in out["days"]) == 1  # done, sub-task, undated, far off


def test_a_failed_source_empties_only_its_kind():
    out = jp.assemble(_sources(events=None, tasks=None), TODAY, 7, IST)
    assert all(d["events"] == [] and d["tasks"] == [] for d in out["days"])
    assert _day(out, "2026-10-26")["due"][0]["title"] == "TNEB"
    assert _day(out, "2026-10-25")["reminders"]


def test_a_malformed_row_is_skipped_and_the_rest_show():
    broken = [{"id": "x", "title": "broken", "starts_at": "not a date"}, *_sources()["events"]]
    out = jp.assemble(_sources(events=broken), TODAY, 7, IST)
    assert [e["title"] for e in _day(out, "2026-10-25")["events"]] == ["Late call"]


@pytest.mark.asyncio
async def test_every_source_raising_is_still_a_plan(monkeypatch, caplog):
    async def boom(*_a, **_k):
        raise RuntimeError("secret: my bank balance")

    for name in SOURCES:
        monkeypatch.setattr(jp, name, boom)
    caplog.set_level("DEBUG", logger=jp.__name__)
    out = await jp.plan("t1", 3, NOW)
    assert [d["date"] for d in out["days"]] == ["2026-10-25", "2026-10-26", "2026-10-27"]
    assert "RuntimeError" in caplog.text and "bank balance" not in caplog.text


@pytest.mark.asyncio
async def test_every_source_gets_the_tenant_and_the_days(monkeypatch):
    seen = []

    def spy(name):
        async def fn(tenant_id, *args):
            seen.append((name, tenant_id, args))
            return []

        return fn

    for name in SOURCES:
        monkeypatch.setattr(jp, name, spy(name))
    await jp.plan("t-own", 99, NOW)  # clamped to 31
    assert {n for n, _, _ in seen} == set(SOURCES)
    assert all(t == "t-own" for _, t, _ in seen)
    assert ("_events", "t-own", (TODAY, 31)) in seen


def test_reminder_query_is_this_tenants_pending_time_triggers_in_range():
    text = sql(jp._reminders_query("t-own", TODAY, 7))
    assert "tenant_id = 't-own'" in text and "'pending'" in text and "'time'" in text
    # 25 Oct 00:00 IST to 1 Nov 00:00 IST, in UTC.
    assert "2026-10-24 18:30:00" in text and "2026-10-31 18:30:00" in text


@pytest.mark.asyncio
async def test_reminders_on_the_owners_clock(monkeypatch):
    row = SimpleNamespace(
        id=uuid.uuid4(),
        content="Call Amma",
        trigger_time=datetime(2026, 10, 25, 13, 30, tzinfo=UTC),
    )
    session = FakeSession([row])
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(session))
    out = await jp._reminders("t-own", TODAY, 7)
    assert out == [{"id": str(row.id), "text": "Call Amma", "at": "2026-10-25T19:00:00+05:30"}]


@pytest.mark.asyncio
async def test_a_local_only_calendar_shows_when_but_not_what(monkeypatch):
    from life_graph.connectors import store

    def row(exposure, title):
        return {
            "id": f"e-{exposure}",
            "kind": "event",
            "account_name": "Cal",
            "account_exposure": exposure,
            "title": title,
            "location": "Clinic",
            "attendees": ["dr@example.test"],
            "starts_at": datetime(2026, 10, 25, 10, 0, tzinfo=UTC),
            "ends_at": datetime(2026, 10, 25, 11, 0, tzinfo=UTC),
            "flags": {},
        }

    async def events_between(session, tenant_id, start, end, limit=100):
        assert tenant_id == "t-own" and limit == jp.MAX_EVENTS
        return [row("standard", "Dentist"), row("local_only", "Therapy")]

    monkeypatch.setattr(store, "events_between", events_between)
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(FakeSession()))
    out = await jp._events("t-own", TODAY, 7)
    assert out[0]["title"] == "Dentist" and out[0]["location"] == "Clinic"
    assert "Therapy" not in str(out[1]) and "Clinic" not in str(out[1])
    assert out[1]["starts_at"] == "2026-10-25T10:00:00+00:00"


@pytest.mark.asyncio
async def test_plan_endpoint_answers_for_the_requests_tenant(monkeypatch):
    from life_graph.api import jarvis
    from life_graph.core.tenant import tenant_scope

    asked = []

    async def fake(tenant_id, days=7, now=None):
        asked.append((tenant_id, days))
        return {"days": []}

    monkeypatch.setattr(jp, "plan", fake)
    with tenant_scope("t-own"):
        body = await jarvis.plan(days=3)
    assert asked == [("t-own", 3)] and body["data"] == {"days": []}
