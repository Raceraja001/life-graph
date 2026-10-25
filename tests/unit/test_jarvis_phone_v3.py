"""The phone app's v3 pure parts (life-graph-android docs/PLAN-v3.md): reading a
reminder's time, the wording the phone shows, which buttons a notification
offers, taking an action, the "reminded" chat event, snoozing a due item, and
the brief's audio cache. The endpoints themselves are covered with a real
device token in tests/integration/test_jarvis_phone_v3.py.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from life_graph.services import due_notifications as dn
from life_graph.services import notification_actions as na
from life_graph.services.reminders import (
    NEED_A_TIME,
    WhenError,
    check_when,
    clock,
    parse_when,
    say_when,
)
from tests.unit.fakes import FakeSession, session_factory

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 25, 10, 0, tzinfo=IST).astimezone(UTC)  # Sun 10:00 in Chennai


def _local(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=IST)


# ── Reading the time ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("said", "want"),
    [
        ("6pm", _local(25, 18)),
        ("6 pm", _local(25, 18)),
        ("at 6:30 p.m.", _local(25, 18, 30)),
        ("at 6", _local(25, 18)),  # 6 am has passed: the next 6 o'clock
        ("at 11", _local(25, 11)),  # 11 am is still to come
        ("9am", _local(26, 9)),  # passed today, no day named: tomorrow
        ("tomorrow 9am", _local(26, 9)),
        ("tomorrow at 9 am", _local(26, 9)),
        ("9 am tomorrow", _local(26, 9)),
        ("18:30", _local(25, 18, 30)),
        ("at 07:15", _local(26, 7, 15)),  # 24-hour, passed: tomorrow
        ("tonight at 9", _local(25, 21)),
        ("today at 5 pm", _local(25, 17)),
        ("noon", _local(25, 12)),
        ("midnight", _local(26, 0)),
        ("in 2 hours", _local(25, 12)),
        ("in an hour", _local(25, 11)),
        ("in half an hour", _local(25, 10, 30)),
        ("in 45 minutes", _local(25, 10, 45)),
        ("in 3 days", _local(28, 10)),
        ("2026-10-25T18:00:00+05:30", _local(25, 18)),
        ("2026-10-25T12:30:00Z", _local(25, 18)),
        ("2026-10-25T18:00", _local(25, 18)),  # no offset: the owner's clock
    ],
)
def test_parse_when_reads_simple_times(said, want):
    got = parse_when(said, NOW, IST)
    assert got == want and got.tzinfo is not None


@pytest.mark.parametrize(
    ("said", "asks"),
    [
        ("", NEED_A_TIME),
        ("tomorrow", NEED_A_TIME),
        ("later", NEED_A_TIME),
        ("tomorrow morning", NEED_A_TIME),
        ("on Monday", NEED_A_TIME),
        ("13 pm", NEED_A_TIME),
        ("25:00", NEED_A_TIME),
        ("6:75 pm", NEED_A_TIME),
        ("in 2 fortnights", NEED_A_TIME),
        ("2026-13-45T10:00", NEED_A_TIME),
        ("tomorrow at 6", "Is that 6 am or 6 pm?"),
        ("today at 9 am", "already passed"),
        ("tomorrow midnight", "Midnight tonight"),
    ],
)
def test_parse_when_refuses_what_it_cannot_be_sure_of(said, asks):
    with pytest.raises(WhenError) as err:
        parse_when(said, NOW, IST)
    assert asks in str(err.value)


def test_check_when_wants_the_future_within_a_year():
    assert check_when(NOW + timedelta(minutes=5), NOW) is None
    assert "passed" in check_when(NOW - timedelta(minutes=1), NOW)
    assert "year" in check_when(NOW + timedelta(days=400), NOW)


def test_plain_words_for_a_time():
    assert clock(_local(25, 9)) == "9 am"
    assert clock(_local(25, 18, 30)) == "6:30 pm"
    assert clock(_local(25, 0, 5)) == "12:05 am"
    assert clock(_local(25, 12)) == "12 pm"
    assert say_when(_local(25, 18), NOW, IST) == "today at 6 pm"
    assert say_when(_local(26, 9), NOW, IST) == "tomorrow at 9 am"
    assert say_when(_local(28, 9), NOW, IST) == "on Wed 28 Oct at 9 am"


# ── Which buttons a notification offers ──────────────────────────────


def _due(item, **extra):
    return {"kind": "due_item", "item": item, "item_id": str(uuid.uuid4()), **extra}


def test_kind_comes_from_what_wrote_the_notification():
    assert na.kind_of("due_item", _due("bill")) == "bill"
    assert na.kind_of("due_item", _due("reminder")) == "reminder"
    assert na.kind_of("brief", {"kind": "daily_brief"}) == "brief"
    # Rows from before item_id was stored, and anything else: no buttons.
    assert na.kind_of("due_item", {"kind": "due_item", "item": "bill"}) == "other"
    assert na.kind_of("due_item", _due("weird")) == "other"
    assert na.kind_of(None, {}) == "other"
    assert na.kind_of("watcher", None) == "other"


def test_actions_per_kind_match_the_contract():
    def ids(kind):
        return [(a["id"], a["label"]) for a in na.actions_for(kind, {})]

    assert ids("bill") == [("paid", "Paid"), ("snooze_1d", "Tomorrow")]
    assert ids("reminder") == [
        ("done", "Done"),
        ("snooze_1h", "In 1 hour"),
        ("snooze_1d", "Tomorrow"),
    ]
    assert ids("task") == [("snooze_1d", "Tomorrow")]
    assert ids("document") == [] and ids("other") == []
    assert ids("brief") == [("listen", "Listen")]
    assert all(len(v) <= 3 for v in na.ACTIONS.values())


def test_buttons_go_once_used_except_listen():
    used = {"action": {"id": "paid", "at": "x"}}
    assert na.actions_for("bill", used) == []
    assert na.actions_for("brief", used) == [{"id": "listen", "label": "Listen"}]


def test_offered():
    assert na.offered("bill", "paid") and not na.offered("bill", "done")
    assert na.offered("reminder", "snooze_1h") and not na.offered("task", "snooze_1h")
    assert not na.offered("document", "paid") and not na.offered("other", "listen")
    assert not na.offered("bill", "rm -rf")


def test_snooze_until_and_the_result_sentences():
    tomorrow9 = na.snooze_until("snooze_1d", NOW, IST)
    assert tomorrow9 == _local(26, 9)
    assert na.snooze_until("snooze_1h", NOW, IST) == _local(25, 11)
    late = datetime(2026, 10, 25, 23, 30, tzinfo=IST)
    assert na.snooze_until("snooze_1d", late, IST) == _local(26, 9)

    def say(action, at=None):
        return na.result_for(action, at=at, now=NOW, tz=IST)

    assert say("paid") == "Marked paid."
    assert say("done") == "Done."
    assert say("listen") == "Open Jarvis to listen."
    assert say("snooze_1d", tomorrow9) == "I'll remind you tomorrow at 9 am."
    assert say("snooze_1h", _local(25, 11)) == "I'll remind you today at 11 am."


def test_notification_rows_carry_kind_and_actions():
    from life_graph.api.jarvis import _notification_row

    base = {"id": uuid.uuid4(), "title": "T", "body": "B", "priority": "high"}
    base["created_at"] = NOW
    bill = SimpleNamespace(**base, source_type="due_item", extra_metadata=_due("bill"))
    row = _notification_row(bill)
    assert row["kind"] == "bill" and row["priority"] == "important"
    assert [a["id"] for a in row["actions"]] == ["paid", "snooze_1d"]
    old = SimpleNamespace(**base)  # no source_type or metadata at all
    assert _notification_row(old)["kind"] == "other"
    assert _notification_row(old)["actions"] == []


# ── Taking an action ─────────────────────────────────────────────────


def _notification(meta, source_type="due_item"):
    return SimpleNamespace(
        id=uuid.uuid4(), source_type=source_type, extra_metadata=meta, is_read=False
    )


async def _perform(note, action, session=None):
    return await na.perform(session or FakeSession(), "t1", note, action, NOW, IST)


@pytest.mark.asyncio
async def test_an_action_not_offered_or_already_taken_is_refused():
    with pytest.raises(na.ActionRefusedError, match="isn't offered"):
        await _perform(_notification(_due("task")), "paid")
    with pytest.raises(na.ActionRefusedError, match="isn't offered"):
        await _perform(_notification({"kind": "due_item"}), "done")  # an old row
    done = _notification(_due("task", action={"id": "snooze_1d", "at": "x"}))
    with pytest.raises(na.ActionRefusedError, match="Already done"):
        await _perform(done, "snooze_1d")


@pytest.mark.asyncio
async def test_listen_changes_nothing_and_may_be_repeated():
    note = _notification({"kind": "daily_brief"}, source_type="brief")
    assert await _perform(note, "listen") == "Open Jarvis to listen."
    assert await _perform(note, "listen") == "Open Jarvis to listen."
    assert note.extra_metadata == {"kind": "daily_brief"} and note.is_read is False


@pytest.mark.asyncio
async def test_tomorrow_on_a_task_holds_it_back_and_frees_its_key():
    meta = _due("task", dedup_key="task:abc:2026-10-25:today", lead="today")
    note = _notification(meta)
    assert await _perform(note, "snooze_1d") == "I'll remind you tomorrow at 9 am."
    out = note.extra_metadata
    assert out["dedup_key"] == f"task:abc:2026-10-25:today:snoozed:{note.id}"
    assert out["snoozed_key"] == "task:abc:2026-10-25:today"
    assert out["snooze_prefix"] == "task:abc:2026-10-25"
    assert out["snoozed_until"] == "2026-10-26T03:30:00+00:00"
    assert out["action"]["id"] == "snooze_1d" and note.is_read is True


@pytest.mark.asyncio
async def test_done_and_snooze_on_a_reminder():
    def reminder(status="pending"):
        return SimpleNamespace(id=uuid.uuid4(), status=status, trigger_time=NOW, completed_at=None)

    it = reminder()
    note = _notification(_due("reminder"))
    assert await _perform(note, "done", FakeSession(it)) == "Done."
    assert it.status == "completed" and it.completed_at == NOW and note.is_read

    it = reminder()
    note = _notification(_due("reminder"))
    assert await _perform(note, "snooze_1h", FakeSession(it)) == "I'll remind you today at 11 am."
    assert it.trigger_time == _local(25, 11) and it.status == "pending"

    for status, words in (("completed", "Already done"), ("dismissed", "cancelled")):
        with pytest.raises(na.ActionRefusedError, match=words):
            await _perform(_notification(_due("reminder")), "done", FakeSession(reminder(status)))
    with pytest.raises(na.ActionNotFoundError):
        await _perform(_notification(_due("reminder")), "done", FakeSession(None))


@pytest.mark.asyncio
async def test_paid_marks_the_bill_and_its_other_emails(monkeypatch):
    from life_graph.connectors import bills

    calls = []

    async def mark_paid(session, tenant_id, item_id, paid_at):
        calls.append((tenant_id, item_id, paid_at))
        return 2

    monkeypatch.setattr(bills, "mark_paid", mark_paid)
    meta = _due("bill")
    note = _notification(meta)
    assert await _perform(note, "paid") == "Marked paid."
    assert calls == [("t1", meta["item_id"], NOW)] and note.is_read

    async def gone(*_a):
        return None

    monkeypatch.setattr(bills, "mark_paid", gone)
    with pytest.raises(na.ActionNotFoundError):
        await _perform(_notification(_due("bill")), "paid")


@pytest.mark.asyncio
async def test_mark_paid_closes_every_open_email_about_that_bill():
    from life_graph.connectors.bills import mark_paid

    def email(payee, state="open"):
        bill = {"kind": "bill", "payee": payee, "due": "2026-10-27", "state": state}
        return SimpleNamespace(id=uuid.uuid4(), flags={"bill": bill, "other": 1})

    first, again, someone_else = email("TNEB"), email("TNEB"), email("Airtel")
    session = FakeSession(first, [again, someone_else])
    assert await mark_paid(session, "t1", str(first.id), NOW) == 2
    assert first.flags["bill"]["state"] == "paid" and again.flags["bill"]["state"] == "paid"
    assert first.flags["other"] == 1 and first.flags["bill"]["paid_at"] == NOW.isoformat()
    assert someone_else.flags["bill"]["state"] == "open"
    assert await mark_paid(FakeSession(None), "t1", str(first.id), NOW) is None
    assert await mark_paid(FakeSession(), "t1", "not-a-uuid", NOW) is None
    not_a_bill = SimpleNamespace(id=uuid.uuid4(), flags={"bill": {"kind": "payment_done"}})
    assert await mark_paid(FakeSession(not_a_bill), "t1", str(not_a_bill.id), NOW) is None


# ── Snoozed items in the due-notification job ────────────────────────


def _item(key):
    return dn.DueItem(kind="task", key=key, lead="today", title="t", body="b", priority="info")


def test_snoozed_items_are_held_back_until_the_snooze_ends():
    assert dn.item_prefix("bill:tneb:2026-10-27:overdue") == "bill:tneb:2026-10-27"
    items = [_item("task:a:2026-10-25:today"), _item("task:b:2026-10-25:today")]
    kept = dn.drop_snoozed(items, {"task:a:2026-10-25"})
    assert [i.key for i in kept] == ["task:b:2026-10-25:today"]


@pytest.mark.asyncio
async def test_active_snoozes_reads_only_unexpired_ones():
    from tests.unit.fakes import sql

    session = FakeSession(["task:a:2026-10-25", None])
    assert await dn.active_snoozes(session, "t1", NOW) == {"task:a:2026-10-25"}
    text = sql(session.statements[0])
    assert "snoozed_until" in text and "'2026-10-25T04:30:00+00:00'" in text and "'t1'" in text


@pytest.mark.asyncio
async def test_a_due_notification_names_its_item():
    session = FakeSession()
    item = dn.DueItem(
        kind="reminder",
        key="k",
        lead="now",
        title="t",
        body="b",
        priority="important",
        source_id="abc",
    )
    await dn.write_new(session, "t1", [item], NOW)
    meta = session.added[0].extra_metadata
    assert meta["item"] == "reminder" and meta["item_id"] == "abc"
    assert na.kind_of(dn.SOURCE_TYPE, meta) == "reminder"


# ── The chat stream and the voice reply ──────────────────────────────


def test_a_reminder_reaches_the_app_as_a_reminded_event():
    from life_graph.api.jarvis import _app_event

    def event(result, name="reminder_set"):
        return _app_event({"type": "tool_result", "name": name, "result": result}, {})

    ok = json.dumps(
        {"reminded": True, "id": "r1", "text": "Call Murugan", "at": "2026-10-25T18:00:00+05:30"}
    )
    assert event(ok) == {
        "type": "reminded",
        "id": "r1",
        "text": "Call Murugan",
        "at": "2026-10-25T18:00:00+05:30",
    }
    for bad in ('{"error": "I need a clear time"}', '{"reminded": true}', "not json", None):
        assert event(bad) is None
    assert event(ok, name="bills_due") is None


# ── reminder_set ─────────────────────────────────────────────────────


@pytest.fixture
def _fake_db(monkeypatch):
    from life_graph.storage import database

    session = FakeSession()
    monkeypatch.setattr(database, "async_session", session_factory(session))
    return session


async def _set(text, at):
    from life_graph.core.task_context import TaskContext, _task_context_var
    from life_graph.tools.reminders import reminder_set

    run = uuid.uuid4()
    token = _task_context_var.set(TaskContext(task_id=run, tenant_id="t_rem"))
    try:
        return json.loads(await reminder_set(text, at)), run
    finally:
        _task_context_var.reset(token)


@pytest.mark.asyncio
async def test_reminder_set_creates_a_time_reminder_tagged_with_the_run(_fake_db):
    out, run = await _set("  Call   Murugan ", "in 2 hours")
    (row,) = _fake_db.added
    assert out["reminded"] is True and out["id"] == str(row.id) and out["text"] == "Call Murugan"
    assert row.tenant_id == "t_rem" and row.trigger_type == "time" and row.status == "pending"
    assert row.context_match == {"set_by": "jarvis", "task_id": str(run)}
    assert datetime.fromisoformat(out["at"]) == row.trigger_time
    assert out["when"].startswith(("today at", "tomorrow at"))
    assert _fake_db.commits == 1


@pytest.mark.asyncio
async def test_reminder_set_refuses_an_unclear_or_past_time(_fake_db):
    out, _ = await _set("Call Murugan", "sometime")
    assert out["error"] == NEED_A_TIME
    out, _ = await _set("Call Murugan", "2020-01-01T09:00:00+05:30")
    assert "passed" in out["error"]
    out, _ = await _set("", "6 pm")
    assert "What should the reminder say" in out["error"]
    assert _fake_db.added == []


@pytest.mark.asyncio
async def test_reminder_set_refuses_after_outside_content(_fake_db):
    from life_graph.core.run_taint import TAINTED_REFUSAL, tool_call_scope

    with tool_call_scope(True):
        out, _ = await _set("Pay 5000 to Acme", "in 1 hour")
    assert out == {"error": TAINTED_REFUSAL} and _fake_db.added == []


@pytest.mark.asyncio
async def test_after_outside_content_the_owner_asking_still_sets_a_reminder(_fake_db, monkeypatch):
    """Sharing a school circular and saying "remind me Friday" is the owner
    asking; the same words inside the shared text are not."""
    from unittest.mock import AsyncMock

    from life_graph.core.run_taint import TAINTED_REFUSAL, tool_call_scope
    from life_graph.tools import memory_search

    owner = AsyncMock(return_value="is this legit?")
    monkeypatch.setattr(memory_search, "_owner_message", owner)
    with tool_call_scope(True):
        out, _ = await _set("Pay the school fees", "in 1 hour")
    assert out == {"error": TAINTED_REFUSAL}

    owner.return_value = "remind me about this in an hour"
    with tool_call_scope(True):
        out, _ = await _set("Pay the school fees", "in 1 hour")
    assert out.get("reminded") is True and len(_fake_db.added) == 1


@pytest.mark.asyncio
async def test_reminder_set_without_a_tenant():
    from life_graph.tools.reminders import reminder_set

    assert "no tenant" in json.loads(await reminder_set("Call", "6 pm"))["error"]


def test_jarvis_holds_reminder_set_as_a_personal_tool():
    from life_graph.kernel.personas import _BUILTIN_PERSONAS
    from life_graph.services.lead import PERSONAL_TOOLS

    jarvis = next(p for p in _BUILTIN_PERSONAS if p["name"] == "jarvis")
    assert "reminder_set" in jarvis["allowed_tools"] and "reminder_set" in PERSONAL_TOOLS
    assert "reminder_set" in jarvis["system_prompt"]


# ── The brief's audio ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_spoken_brief_is_synthesised_once_per_brief(monkeypatch):
    from life_graph.api import jarvis
    from life_graph.services import assistant_chat

    said = []

    async def speak(text):
        said.append(text)
        return None if text == "down" else b"mp3"

    monkeypatch.setattr(assistant_chat, "speak", speak)
    monkeypatch.setattr(jarvis, "_brief_audio", {})
    assert await jarvis._brief_mp3("b1", "Good morning") == b"mp3"
    assert await jarvis._brief_mp3("b1", "Good morning") == b"mp3"
    assert said == ["Good morning"]
    assert await jarvis._brief_mp3("b2", "down") is None
    assert await jarvis._brief_mp3("b2", "down") is None  # a failure is tried again
    assert said == ["Good morning", "down", "down"]
    for i in range(jarvis.BRIEF_AUDIO_CACHE + 2):
        await jarvis._brief_mp3(f"x{i}", "hi")
    assert len(jarvis._brief_audio) == jarvis.BRIEF_AUDIO_CACHE


@pytest.mark.asyncio
async def test_slow_speech_returns_the_text_first_and_plays_on_the_next_tap(monkeypatch):
    """With the GPU busy, speech took over 60 s and the phone got nothing (2026-10-25)."""
    import asyncio

    from life_graph.api import jarvis
    from life_graph.services import assistant_chat

    said = []
    release = asyncio.Event()

    async def slow_speak(text):
        said.append(text)
        await release.wait()
        return b"mp3"

    monkeypatch.setattr(assistant_chat, "speak", slow_speak)
    monkeypatch.setattr(jarvis, "_brief_audio", {})
    monkeypatch.setattr(jarvis, "_brief_speaking", {})
    monkeypatch.setattr(jarvis, "BRIEF_AUDIO_WAIT_SECONDS", 0.05)

    assert await jarvis._brief_mp3("b9", "Good morning") is None  # text only, at once
    assert await jarvis._brief_mp3("b9", "Good morning") is None  # still speaking: not twice
    release.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert await jarvis._brief_mp3("b9", "Good morning") == b"mp3"
    assert said == ["Good morning"]
