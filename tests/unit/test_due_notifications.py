"""Due items as phone notifications (services/due_notifications.py): what is
due, lead times, the dedup key, wording, and the write's dedup — no database."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from life_graph.services import due_notifications as dn

TODAY = date(2026, 10, 21)
IST = ZoneInfo("Asia/Kolkata")


@pytest.mark.parametrize(
    ("due", "want"),
    [
        (TODAY - timedelta(days=8), None),  # long past: dealt with or abandoned
        (TODAY - timedelta(days=7), dn.OVERDUE),
        (TODAY - timedelta(days=1), dn.OVERDUE),
        (TODAY, dn.TODAY),
        (TODAY + timedelta(days=1), dn.TOMORROW),
        (TODAY + timedelta(days=2), None),
    ],
)
def test_day_lead(due, want):
    assert dn.day_lead(due, TODAY) == want


@pytest.mark.parametrize(
    ("days", "sent", "want"),
    [
        (31, [], None),
        (30, [], "30"),
        (20, [], "30"),
        (7, [], "7"),
        (5, [], "7"),  # filed late: one notice, not three
        (5, ["7"], None),  # the daily sweep already sent it
        (1, ["60", "30", "7"], "1"),
        (0, [], "1"),
        (-1, [], None),  # expired is the daily sweep's
    ],
)
def test_document_lead(days, sent, want):
    assert dn.document_lead(TODAY + timedelta(days=days), TODAY, sent) == want


@pytest.mark.parametrize(
    ("lead", "hour", "want"),
    [
        (dn.TODAY, 7, False),
        (dn.TODAY, 8, True),
        (dn.OVERDUE, 21, True),
        (dn.TODAY, 22, False),
        (dn.TOMORROW, 8, False),
        (dn.TOMORROW, 18, True),
        (dn.TOMORROW, 23, False),
    ],
)
def test_lead_open(lead, hour, want):
    assert dn.lead_open(lead, hour) is want


def test_priority():
    assert dn.priority_for(0) == "important"
    assert dn.priority_for(-3) == "important"
    assert dn.priority_for(1) == "info"
    assert dn.priority_for(0, autopay=True) == "info"


def test_short_amount():
    assert dn.short_amount(1240.0, "INR") == "₹1,240"
    assert dn.short_amount(1240.5, "INR") == "₹1,240.50"
    assert dn.short_amount(None, None) == ""


def test_dedup_key():
    assert dn.dedup_key("bill", "tneb", "2026-10-22", "tomorrow") == "bill:tneb:2026-10-22:tomorrow"


def _bill(**kw):
    return {
        "kind": "bill",
        "payee": "TNEB",
        "amount": 1240.0,
        "currency": "INR",
        "due": "2026-10-22",
        "autopay": False,
        "state": "open",
        **kw,
    }


def test_bill_wording():
    assert dn.bill_text(_bill(), dn.TOMORROW) == ("TNEB bill due tomorrow", "₹1,240 to TNEB.")
    assert dn.bill_text(_bill(amount=None), dn.TODAY) == ("TNEB bill due today", "Pay TNEB.")
    title, body = dn.bill_text(_bill(due="2026-10-19", autopay=True), dn.OVERDUE)
    assert title == "TNEB bill overdue"
    assert body == "₹1,240 to TNEB. It was due Mon 19 Oct. Autopay is on."
    assert dn.bill_text(_bill(kind="renewal", payee="GoDaddy", amount=999.0), dn.TODAY) == (
        "GoDaddy renews today",
        "₹999 to renew with GoDaddy.",
    )
    # A local_only account: nothing about who or how much.
    assert dn.bill_text(_bill(), dn.TODAY, private=True) == (
        "A bill is due today",
        "Details on the dashboard.",
    )


def test_task_wording():
    task = {"title": "Call the plumber", "flags": {"list": "Home", "due": "2026-10-19"}}
    assert dn.task_text(task, dn.TODAY) == ("Due today: Call the plumber", "On your Home list.")
    assert dn.task_text(task, dn.OVERDUE) == (
        "Overdue: Call the plumber",
        "It was due Mon 19 Oct, on your Home list.",
    )
    assert dn.task_text({"title": "Pay rent", "flags": {}}, dn.TOMORROW) == (
        "Due tomorrow: Pay rent",
        "On your to-do list.",
    )
    assert dn.task_text(task, dn.TODAY, private=True)[0] == "A to-do is due today"


def test_document_wording():
    assert dn.document_text("Passport", TODAY + timedelta(days=7), TODAY) == (
        "Passport expires in 7 days",
        "On 28 Oct 2026. Start the renewal now if it needs an appointment or paperwork.",
    )
    assert dn.document_text("Passport", TODAY + timedelta(days=1), TODAY)[0] == (
        "Passport expires tomorrow"
    )
    assert dn.document_text("Passport", TODAY, TODAY)[0] == "Passport expires today"


def test_reminder_wording():
    now = datetime(2026, 10, 21, 4, 0, tzinfo=UTC)  # 09:30 IST
    at = datetime(2026, 10, 21, 3, 30, tzinfo=UTC)  # 09:00 IST
    assert dn.reminder_text("Pay TNEB ₹1,240\nfrom the app", at, now, IST) == (
        "Pay TNEB ₹1,240",
        "Reminder for 09:00.",
    )
    yesterday = at - timedelta(days=1)
    assert dn.reminder_text("", yesterday, now, IST) == (
        "Reminder",
        "Reminder for Tue 20 Oct 09:00.",
    )


def _bill_row(bill, exposure="standard"):
    return {"id": str(uuid.uuid4()), "bill": bill, "account_exposure": exposure}


def test_bill_items():
    rows = [
        _bill_row(_bill(due="2026-10-21")),
        _bill_row(_bill(payee="Airtel", due="2026-10-22")),
        _bill_row(_bill(payee="LIC", due="2026-10-25")),  # later this week: not yet
    ]
    morning = dn.bill_items(rows, TODAY, 9)
    assert [(i.key, i.priority) for i in morning] == [("bill:tneb:2026-10-21:today", "important")]
    evening = dn.bill_items(rows, TODAY, 19)
    assert [(i.key, i.priority, i.title) for i in evening] == [
        ("bill:tneb:2026-10-21:today", "important", "TNEB bill due today"),
        ("bill:airtel:2026-10-22:tomorrow", "info", "Airtel bill due tomorrow"),
    ]
    assert evening[0].source_id == rows[0]["id"]
    assert dn.bill_items(rows, TODAY, 23) == []  # night: quiet


def test_bill_key_follows_the_payee_not_the_email():
    # A statement and a reminder email about one bill must not notify twice.
    a = dn.bill_items([_bill_row(_bill(payee="TNEB Ltd"))], TODAY, 19)
    b = dn.bill_items([_bill_row(_bill(payee="TNEB"))], TODAY, 19)
    assert a[0].key == b[0].key


def _task(due, **flags):
    return {
        "id": str(uuid.uuid4()),
        "title": "File GST return",
        "account_exposure": "standard",
        "flags": {"status": "needsAction", "due": due, **flags},
    }


def test_task_items():
    rows = [
        _task("2026-10-21"),
        _task("2026-10-20"),
        _task("2026-10-21", status="completed"),
        _task("2026-10-21", parent="list:abc"),
        _task(None),
        _task("2026-11-30"),
    ]
    items = dn.task_items(rows, TODAY, 9)
    assert [i.key for i in items] == [
        f"task:{rows[0]['id']}:2026-10-21:today",
        f"task:{rows[1]['id']}:2026-10-20:overdue",
    ]
    assert {i.priority for i in items} == {"important"}


def _doc(days, sent=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        title="Car insurance",
        expires_on=TODAY + timedelta(days=days),
        reminders_sent=sent or [],
    )


def test_document_items():
    docs = [_doc(7), _doc(30, ["30"]), _doc(90), _doc(0)]
    items = dn.document_items(docs, TODAY, 9)
    assert [(i.lead, i.priority) for i in items] == [("7", "info"), ("1", "important")]
    assert items[0].key == f"document:{docs[0].id}:2026-10-28:7"
    assert items[0].document is docs[0]
    assert dn.document_items(docs, TODAY, 6) == []


def test_reminder_items():
    now = datetime(2026, 10, 21, 4, 0, tzinfo=UTC)
    it = SimpleNamespace(
        id=uuid.uuid4(), content="Call the bank", trigger_time=now - timedelta(minutes=10)
    )
    (item,) = dn.reminder_items(
        [it, SimpleNamespace(id=uuid.uuid4(), content="x", trigger_time=None)], now, IST
    )
    assert item.key == f"reminder:{it.id}:2026-10-21T03:50:00+00:00:now"
    assert item.priority == "important" and item.title == "Call the bank"


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _Session:
    def __init__(self, existing=()):
        self.existing = list(existing)
        self.added = []

    async def execute(self, _stmt):
        return _Result(self.existing)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


def _item(key, priority="info", document=None, lead="today"):
    return dn.DueItem(
        kind="document" if document else "task",
        key=key,
        lead=lead,
        title=f"title {key}",
        body="body",
        priority=priority,
        source_id=str(uuid.uuid4()),
        document=document,
    )


@pytest.mark.asyncio
async def test_write_new_skips_existing_keys_and_duplicates():
    now = datetime(2026, 10, 21, 4, 0, tzinfo=UTC)
    session = _Session(existing=["a"])
    written = await dn.write_new(
        session, "t1", [_item("a"), _item("b"), _item("b"), _item("c", "important")], now
    )
    assert written == ["c", "b"]  # important first; "a" already exists
    n = session.added[0]
    assert n.tenant_id == "t1" and n.priority == "important" and n.source_type == dn.SOURCE_TYPE
    assert n.extra_metadata["dedup_key"] == "c" and n.extra_metadata["item"] == "task"
    assert n.is_delivered is True and n.delivered_at == now


@pytest.mark.asyncio
async def test_write_new_caps_a_run_and_records_document_leads():
    now = datetime(2026, 10, 21, 4, 0, tzinfo=UTC)
    doc = _doc(7, ["60", "30"])
    items = [_item("doc", document=doc, lead="7")]
    items += [_item(f"k{i}") for i in range(dn.MAX_PER_RUN + 5)]
    session = _Session()
    written = await dn.write_new(session, "t1", items, now)
    assert len(written) == dn.MAX_PER_RUN and written[0] == "doc"
    assert doc.reminders_sent == ["30", "60", "7"]  # the daily sweep now skips this one
    assert await dn.write_new(session, "t1", [], now) == []


@pytest.mark.asyncio
async def test_worker_respects_the_quiet_setting(monkeypatch):
    from life_graph.config import settings
    from life_graph.workers.due_notifications import write_due_notifications

    monkeypatch.setattr(settings, "phone_due_notifications", False)
    assert (await write_due_notifications({}))["status"] == "skipped"


def test_cron_is_scheduled():
    from life_graph.workers.settings import WorkerSettings

    name = "life_graph.workers.due_notifications.write_due_notifications"
    assert name in WorkerSettings.functions
    assert any(job.name == f"cron:{name}" for job in WorkerSettings.cron_jobs)
