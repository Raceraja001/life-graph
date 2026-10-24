"""The phone app's v3 endpoints, with a real device token through the real
middleware (life-graph-android docs/PLAN-v3.md): notification buttons that
mark a bill paid, a reminder done or snooze an item, the latest brief with its
audio, and reminders Jarvis sets, lists and cancels.
"""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"phone3_{uuid.uuid4().hex[:8]}"
OTHER = f"other_{TENANT}"
KEY = "svc-test-key"
OWNER = {"Authorization": f"Bearer {KEY}", "X-Tenant-ID": TENANT}
DAY = date(2026, 10, 21)


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    from life_graph.config import settings
    from life_graph.services import devices

    monkeypatch.setattr(settings, "service_api_keys", KEY)
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(devices, "pairing_limiter", devices.PairingLimiter())
    devices._cache.clear()


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _phone(client) -> dict:
    code = (await client.post("/api/v1/devices/codes", headers=OWNER)).json()["data"]["code"]
    resp = await client.post("/api/v1/devices/pair", json={"code": code, "name": "Pixel"})
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    from life_graph.connectors.tools import user_tz

    return datetime.combine(day, time(hour, minute), tzinfo=user_tz()).astimezone(UTC)


def _act(client, phone, notification_id, action):
    return client.post(
        f"/api/v1/jarvis/notifications/{notification_id}/action",
        headers=phone,
        json={"action": action},
    )


async def _intention(content, at, *, tenant=TENANT, status="pending", trigger_type="time"):
    from life_graph.models.db import Intention
    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = Intention(
            tenant_id=tenant,
            content=content,
            trigger_type=trigger_type,
            trigger_time=at,
            priority="normal",
            status=status,
        )
        s.add(row)
        await s.commit()
        return row.id


async def _notification(*, tenant=TENANT, source_type=None, meta=None, title="N", age_min=0):
    from life_graph.models.db import Notification
    from life_graph.storage.database import async_session

    async with async_session() as s:
        n = Notification(
            tenant_id=tenant,
            title=title,
            body=f"{title} body",
            priority="info",
            source_type=source_type,
            extra_metadata=meta or {},
        )
        n.created_at = datetime.now(UTC) - timedelta(minutes=age_min)
        s.add(n)
        await s.commit()
        return n.id


async def _get(model, ident):
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(model, ident)


async def _seed_due(evening: datetime) -> dict:
    """A bill from two emails, a to-do due today and a reminder just past."""
    from life_graph.connectors.models import ConnectorAccount, ConnectorItem
    from life_graph.storage.database import async_session

    bill = {
        "kind": "bill",
        "payee": "TNEB",
        "amount": 1240.0,
        "currency": "INR",
        "due": (DAY + timedelta(days=1)).isoformat(),
        "autopay": False,
        "state": "open",
    }
    async with async_session() as s:
        mail = ConnectorAccount(
            tenant_id=TENANT,
            connector="imap",
            account_key=f"{TENANT}@example.com",
            display_name="Mail",
            auth_method="app_password",
        )
        tasks = ConnectorAccount(
            tenant_id=TENANT,
            connector="tasks",
            account_key=f"{TENANT}-tasks",
            display_name="Google Tasks",
            auth_method="oauth",
        )
        s.add_all([mail, tasks])
        await s.flush()
        emails = [
            ConnectorItem(
                tenant_id=TENANT,
                account_id=mail.id,
                kind="email",
                external_id=f"bill-{n}",
                direction="inbound",
                title="Your electricity bill",
                trust_tier="external",
                occurred_at=evening - timedelta(days=days),
                flags={"bill": dict(bill)},
            )
            for n, days in ((1, 5), (2, 1))  # the statement, then a reminder email
        ]
        task = ConnectorItem(
            tenant_id=TENANT,
            account_id=tasks.id,
            kind="task",
            external_id="list:task-1",
            direction="own",
            title="File GST return",
            trust_tier="self",
            occurred_at=evening - timedelta(days=2),
            flags={"status": "needsAction", "due": DAY.isoformat(), "list": "Work"},
        )
        s.add_all([*emails, task])
        await s.commit()
        ids = {"emails": [e.id for e in emails], "task": task.id}
    ids["reminder"] = await _intention("Call the bank", evening - timedelta(minutes=10))
    return ids


@pytest.mark.asyncio
@skip_on_db_error
async def test_buttons_on_due_items_mark_paid_and_snooze(client, monkeypatch):
    from life_graph.connectors.bills import bills_due
    from life_graph.connectors.models import ConnectorItem
    from life_graph.models.db import Intention, Notification
    from life_graph.services import due_notifications
    from life_graph.services import notification_actions as na
    from life_graph.storage.database import async_session

    evening = _at(DAY, 19)
    ids = await _seed_due(evening)
    written = await due_notifications.run_for_tenant(TENANT, evening)
    assert sorted(k.split(":")[0] for k in written) == ["bill", "reminder", "task"]

    phone = await _phone(client)
    listed = (await client.get("/api/v1/jarvis/notifications", headers=phone)).json()["data"]
    titles = {"TNEB bill due tomorrow", "Due today: File GST return", "Call the bank"}
    by_kind = {n["kind"]: n for n in listed if n["title"] in titles}
    assert set(by_kind) == {"bill", "task", "reminder"}
    assert [a["id"] for a in by_kind["bill"]["actions"]] == ["paid", "snooze_1d"]
    assert [a["id"] for a in by_kind["task"]["actions"]] == ["snooze_1d"]
    assert [a["id"] for a in by_kind["reminder"]["actions"]] == ["done", "snooze_1h", "snooze_1d"]
    assert by_kind["bill"]["actions"][0] == {"id": "paid", "label": "Paid"}

    monkeypatch.setattr(na, "utcnow", lambda: evening)

    # Paid: every open email about the bill is closed, so it is no longer due.
    paid = await _act(client, phone, by_kind["bill"]["id"], "paid")
    assert paid.status_code == 200
    assert paid.json()["data"] == {
        "id": by_kind["bill"]["id"],
        "action": "paid",
        "result": "Marked paid.",
    }
    for email_id in ids["emails"]:
        assert (await _get(ConnectorItem, email_id)).flags["bill"]["state"] == "paid"
    async with async_session() as s:
        assert await bills_due(s, TENANT, DAY) == []
    note = await _get(Notification, uuid.UUID(by_kind["bill"]["id"]))
    assert note.is_read and note.extra_metadata["action"]["id"] == "paid"
    again = await _act(client, phone, by_kind["bill"]["id"], "paid")
    assert again.status_code == 409 and "Already done" in again.text

    # Tomorrow on the to-do; an hour on the reminder.
    snoozed = await _act(client, phone, by_kind["task"]["id"], "snooze_1d")
    assert snoozed.json()["data"]["result"] == "I'll remind you tomorrow at 9 am."
    later = await _act(client, phone, by_kind["reminder"]["id"], "snooze_1h")
    assert later.json()["data"]["result"] == "I'll remind you today at 8 pm."
    assert (await _get(Intention, ids["reminder"])).trigger_time == evening + timedelta(hours=1)

    # An hour on: only the reminder comes back (its new time is a new key).
    written = await due_notifications.run_for_tenant(TENANT, evening + timedelta(minutes=61))
    assert [k.split(":")[0] for k in written] == ["reminder"]

    # Next morning: the to-do (now overdue) waits for 09:00; the paid bill never returns.
    assert await due_notifications.run_for_tenant(TENANT, _at(DAY + timedelta(days=1), 8, 30)) == []
    written = await due_notifications.run_for_tenant(TENANT, _at(DAY + timedelta(days=1), 9, 5))
    assert written == [f"task:{ids['task']}:{DAY.isoformat()}:overdue"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_action_is_taken_once_and_only_on_your_own(client):
    from life_graph.models.db import Intention, Notification

    phone = await _phone(client)
    it = await _intention("Take the medicine", datetime.now(UTC) - timedelta(minutes=5))
    meta = {"kind": "due_item", "item": "reminder", "item_id": str(it), "dedup_key": f"r:{it}"}
    nid = await _notification(source_type="due_item", meta=meta, title="Take the medicine")

    wrong = await _act(client, phone, nid, "paid")
    assert wrong.status_code == 409
    done = await _act(client, phone, nid, "done")
    assert done.status_code == 200 and done.json()["data"]["result"] == "Done."
    row = await _get(Intention, it)
    assert row.status == "completed" and row.completed_at is not None
    assert (await _get(Notification, nid)).is_read
    assert (await _act(client, phone, nid, "done")).status_code == 409

    # Someone else's notification, an unknown id, not an id: 404.
    theirs = await _notification(tenant=OTHER, source_type="due_item", meta=meta)
    assert (await _act(client, phone, theirs, "done")).status_code == 404
    assert (await _act(client, phone, uuid.uuid4(), "done")).status_code == 404
    assert (await _act(client, phone, "not-an-id", "done")).status_code == 404

    # A notification of ours that points at someone else's reminder: 404.
    their_it = await _intention("Theirs", datetime.now(UTC), tenant=OTHER)
    sneaky = {**meta, "item_id": str(their_it), "dedup_key": "r:x"}
    nid2 = await _notification(source_type="due_item", meta=sneaky)
    assert (await _act(client, phone, nid2, "done")).status_code == 404
    assert (await _get(Intention, their_it)).status == "pending"

    # A row written before item_id was stored: kind "other", no buttons.
    old = await _notification(
        source_type="due_item", meta={"kind": "due_item", "item": "bill"}, title="Old bill"
    )
    listed = (await client.get("/api/v1/jarvis/notifications", headers=phone)).json()["data"]
    row = next(n for n in listed if n["id"] == str(old))
    assert row["kind"] == "other" and row["actions"] == []
    assert (await _act(client, phone, old, "paid")).status_code == 409


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_latest_brief_is_spoken_once(client, monkeypatch):
    from life_graph.api import jarvis
    from life_graph.services import assistant_chat

    phone = await _phone(client)
    none_yet = await client.get("/api/v1/jarvis/brief/latest", headers=phone)
    assert none_yet.status_code == 404

    said = []

    async def speak(text):
        said.append(text)
        return b"ID3-mp3"

    monkeypatch.setattr(assistant_chat, "speak", speak)
    monkeypatch.setattr(jarvis, "_brief_audio", {})
    brief = {"kind": "daily_brief"}
    await _notification(source_type="brief", meta=brief, title="Daily Brief — old", age_min=60)
    newest = await _notification(source_type="brief", meta=brief, title="Daily Brief — new")
    await _notification(tenant=OTHER, source_type="brief", meta=brief, title="Not yours")

    first = (await client.get("/api/v1/jarvis/brief/latest", headers=phone)).json()["data"]
    assert first["id"] == str(newest) and first["title"] == "Daily Brief — new"
    assert first["text"] == "Daily Brief — new body" and first["created_at"]
    assert base64.b64decode(first["audio_base64"]) == b"ID3-mp3"
    again = (await client.get("/api/v1/jarvis/brief/latest", headers=phone)).json()["data"]
    assert again["audio_base64"] == first["audio_base64"] and len(said) == 1

    listed = (await client.get("/api/v1/jarvis/notifications", headers=phone)).json()["data"]
    row = next(n for n in listed if n["id"] == str(newest))
    assert row["kind"] == "brief" and row["actions"] == [{"id": "listen", "label": "Listen"}]
    for _ in range(2):  # Listen only opens the app: it may be tapped again
        listen = await _act(client, phone, newest, "listen")
        assert listen.json()["data"]["result"] == "Open Jarvis to listen."
    assert (await _act(client, phone, newest, "paid")).status_code == 409

    async def silent(text):
        return None

    monkeypatch.setattr(assistant_chat, "speak", silent)
    monkeypatch.setattr(jarvis, "_brief_audio", {})
    quiet = (await client.get("/api/v1/jarvis/brief/latest", headers=phone)).json()["data"]
    assert quiet["audio_base64"] is None and quiet["text"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_reminders_are_listed_soonest_first_and_cancelled(client):
    from life_graph.models.db import Intention

    phone = await _phone(client)
    now = datetime.now(UTC)
    late = await _intention("Water the plants", now + timedelta(hours=2))
    soon = await _intention("Call Murugan", now + timedelta(hours=1))
    done = await _intention("Done already", now + timedelta(hours=3), status="completed")
    await _intention("Context one", None, trigger_type="context")
    theirs = await _intention("Theirs", now + timedelta(minutes=30), tenant=OTHER)

    listed = (await client.get("/api/v1/jarvis/reminders", headers=phone)).json()["data"]
    mine = [r for r in listed if r["id"] in {str(late), str(soon)}]
    assert [r["text"] for r in mine] == ["Call Murugan", "Water the plants"]
    assert all(r["status"] == "pending" for r in listed)
    assert datetime.fromisoformat(mine[0]["at"]) == now + timedelta(hours=1)
    assert str(theirs) not in {r["id"] for r in listed}
    assert str(done) not in {r["id"] for r in listed}

    cancel = await client.post(f"/api/v1/jarvis/reminders/{soon}/cancel", headers=phone)
    assert cancel.json()["data"] == {"id": str(soon), "status": "cancelled"}
    assert (await _get(Intention, soon)).status == "dismissed"  # kept, never deleted
    listed = (await client.get("/api/v1/jarvis/reminders", headers=phone)).json()["data"]
    assert str(soon) not in {r["id"] for r in listed}
    repeat = await client.post(f"/api/v1/jarvis/reminders/{soon}/cancel", headers=phone)
    assert repeat.status_code == 200 and repeat.json()["data"]["status"] == "cancelled"

    finished = await client.post(f"/api/v1/jarvis/reminders/{done}/cancel", headers=phone)
    assert finished.status_code == 409
    for bad in (theirs, uuid.uuid4(), "nope"):
        resp = await client.post(f"/api/v1/jarvis/reminders/{bad}/cancel", headers=phone)
        assert resp.status_code == 404
    assert (await _get(Intention, theirs)).status == "pending"


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_reminder_jarvis_sets_is_listed_and_in_the_voice_reply(client):
    import json

    from life_graph.api.jarvis import _reminded_in
    from life_graph.core.run_taint import tool_call_scope
    from life_graph.core.task_context import TaskContext, _task_context_var
    from life_graph.tools.reminders import reminder_set

    run = uuid.uuid4()
    token = _task_context_var.set(TaskContext(task_id=run, tenant_id=TENANT))
    try:
        out = json.loads(await reminder_set("Call Murugan", "in 2 hours"))
        with tool_call_scope(True):  # after an email or web page: refused
            refused = json.loads(await reminder_set("Pay Acme", "in 1 hour"))
    finally:
        _task_context_var.reset(token)
    assert out["reminded"] is True and "error" in refused

    voice = await _reminded_in(TENANT, run)
    assert voice == [{"id": out["id"], "text": "Call Murugan", "at": out["at"]}]
    assert await _reminded_in(OTHER, run) == []

    phone = await _phone(client)
    listed = (await client.get("/api/v1/jarvis/reminders", headers=phone)).json()["data"]
    assert out["id"] in {r["id"] for r in listed}
    assert "Pay Acme" not in {r["text"] for r in listed}
