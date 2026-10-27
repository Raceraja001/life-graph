"""Answer cards (services/jarvis_cards.py, api/jarvis.py): each card tool's
result as the app's cards, results cut at 2,000 characters read up to the
cut, local_only accounts masked, the chat stream's card events after the
existing ones, and the voice reply's cards from the run's own tool results."""

from __future__ import annotations

import asyncio
import json
import uuid
from types import SimpleNamespace

import pytest

from life_graph.services import jarvis_cards as jc
from life_graph.services.chat_stream import _trim

CARD_KEYS = {"kind", "id", "title", "subtitle", "amount", "when", "actions", "source"}


@pytest.fixture(autouse=True)
def _owner_in_india(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")


def _bills_result(*bills):
    return json.dumps({"today": "2026-10-25", "items": list(bills), "withheld": {}})


def _bill(payee, due, *, kind="bill", autopay=False, account="Gmail", amount=1240.0):
    return {
        "id": str(uuid.uuid4()),
        "account": account,
        "kind": kind,
        "payee": payee,
        "due": due,
        "autopay": autopay,
        "state": "open",
        "amount": amount,
        "currency": "INR",
        "subject": f"{payee} statement",
    }


def test_bill_cards():
    tneb = _bill("TNEB", "2026-10-26")
    airtel = _bill("Airtel", "2026-10-31", autopay=True)
    car = _bill("Car insurance", "2026-11-01", kind="renewal", amount=14200.0)
    out = jc.cards_for("bills_due", _bills_result(tneb, airtel, car), set())
    assert [set(c) for c in out] == [CARD_KEYS] * 3
    assert out[0] == {
        "kind": "bill",
        "id": tneb["id"],
        "title": "TNEB",
        "subtitle": "Due Mon 26 Oct",
        "amount": "₹1,240",
        "when": "2026-10-26",
        "actions": [{"id": "paid", "label": "Mark paid"}],
        "source": "email, Gmail",
    }
    assert out[1]["subtitle"] == "Due Sat 31 Oct · autopay" and out[1]["actions"] == []
    assert out[2]["subtitle"] == "Renews Sun 1 Nov" and out[2]["amount"] == "₹14,200"


def test_a_local_only_bill_card_shows_when_but_not_who_or_how_much():
    secret = _bill("HDFC Credit Card", "2026-10-26", account="Private mail")
    out = jc.cards_for("bills_due", _bills_result(secret), {"Private mail"})
    assert out[0]["title"] == "A bill" and out[0]["amount"] is None
    assert out[0]["when"] == "2026-10-26" and "HDFC" not in json.dumps(out)
    # Exposure not known: masked too.
    assert jc.cards_for("bills_due", _bills_result(secret), None)[0]["title"] == "A bill"


def test_event_cards_on_the_owners_clock():
    result = json.dumps(
        {
            "from": "2026-10-25",
            "days": 1,
            "timezone": "Asia/Kolkata",
            "items": [
                {
                    "id": "e1",
                    "kind": "event",
                    "account": "Work",
                    "title": "Dentist",
                    "starts_at": "2026-10-25T07:00:00+00:00",
                    "ends_at": "2026-10-25T08:00:00+00:00",
                    "all_day": False,
                    "location": "Anna Nagar",
                },
                {
                    "id": "e2",
                    "kind": "event",
                    "account": "Home",
                    "title": "Diwali",
                    "starts_at": "2026-10-25T18:30:00+00:00",
                    "ends_at": "2026-10-26T18:30:00+00:00",
                    "all_day": True,
                },
            ],
            "withheld": {},
        }
    )
    for tool in ("calendar_events", "calendar_next"):
        dentist, diwali = jc.cards_for(tool, result, {"Home"})
        assert dentist == {
            "kind": "event",
            "id": "e1",
            "title": "Dentist",
            "subtitle": "Sun 25 Oct, 12:30–13:30 · Anna Nagar",
            "amount": None,
            "when": "2026-10-25T07:00:00+00:00",
            "actions": [],
            "source": "Work calendar",
        }
        # Home is local_only: when, never what.
        assert diwali["title"] == "An event" and diwali["subtitle"] == "Mon 26 Oct, all day"


def test_person_card_from_memory_about():
    result = json.dumps(
        {
            "name": "murugan",
            "known": True,
            "id": "ent-1",
            "also_called": ["Murugan"],
            "memories": [
                {
                    "id": "m1",
                    "content": "Murugan fixed the pump.",
                    "created_at": "2026-10-20T10:00:00+00:00",
                },
                {
                    "id": "m2",
                    "content": "Murugan lives in Salem.",
                    "created_at": "2026-10-01T10:00:00+00:00",
                },
            ],
            "often_mentioned_with": ["Salem"],
        }
    )
    assert jc.cards_for("memory_about", result, set()) == [
        {
            "kind": "person",
            "id": "ent-1",
            "title": "Murugan",
            "subtitle": "Murugan fixed the pump.",
            "amount": None,
            "when": "2026-10-20T10:00:00+00:00",
            "actions": [],
            "source": "your memories, 2 noted",
        }
    ]
    unknown = json.dumps({"name": "zed", "known": False, "memories": []})
    assert jc.cards_for("memory_about", unknown, set()) == []


def test_app_down_cards_only_for_apps_that_are_down():
    result = json.dumps(
        {
            "apps": [
                {
                    "project": "uzhavu.race",
                    "status": "down",
                    "down_since": "2026-10-25T00:42:00+00:00",
                    "http_status": 502,
                    "error": None,
                },
                {"project": "life-graph", "status": "up"},
                {"project": "chit-fin", "status": "down", "error": "connection refused"},
            ],
            "lines": [],
        }
    )
    out = jc.cards_for("app_health", result, set())
    assert [(c["kind"], c["id"], c["subtitle"]) for c in out] == [
        ("app_down", "uzhavu.race", "Down · HTTP 502"),
        ("app_down", "chit-fin", "Down · connection refused"),
    ]
    assert out[0]["when"] == "2026-10-25T00:42:00+00:00" and out[0]["source"] == "uptime check"


def test_document_cards():
    result = json.dumps(
        {
            "today": "2026-10-25",
            "documents": [
                {"id": "d1", "title": "Passport", "expires_on": "2026-10-30", "days_left": 5},
                {"id": "d2", "title": "Licence", "expires_on": "2026-10-20", "days_left": -5},
                {
                    "title": "Warranty",
                    "expires_on": "2026-10-26",
                    "days_left": 1,
                },  # cloud view: no id
            ],
        }
    )
    out = jc.cards_for("documents_expiring", result, set())
    assert [(c["id"], c["subtitle"]) for c in out] == [
        ("d1", "Expires in 5 days, Fri 30 Oct"),
        ("d2", "Expired, Tue 20 Oct"),
        (None, "Expires tomorrow, Mon 26 Oct"),
    ]
    assert out[0]["source"] == "your documents" and out[0]["when"] == "2026-10-30"


def test_reminder_card():
    result = json.dumps(
        {
            "reminded": True,
            "id": "r1",
            "text": "Call Amma",
            "at": "2026-10-25T19:00:00+05:30",
            "when": "today at 7 pm",
        },
        ensure_ascii=False,
    )
    assert jc.cards_for("reminder_set", result, set()) == [
        {
            "kind": "reminder",
            "id": "r1",
            "title": "Call Amma",
            "subtitle": "today at 7 pm",
            "amount": None,
            "when": "2026-10-25T19:00:00+05:30",
            "actions": [{"id": "cancel", "label": "Cancel"}],
            "source": "a reminder you asked for",
        }
    ]
    assert jc.cards_for("reminder_set", json.dumps({"error": "no time"}), set()) == []


def test_at_most_five_cards_per_result():
    bills = [_bill(f"Payee {n}", "2026-10-26") for n in range(9)]
    assert len(jc.cards_for("bills_due", _bills_result(*bills), set())) == jc.MAX_CARDS


def test_a_result_cut_by_the_stream_is_read_up_to_the_cut():
    bills = [_bill(f"Payee number {n} with a long name", "2026-10-26") for n in range(30)]
    cut = _trim(_bills_result(*bills))
    assert cut.endswith("…")
    with pytest.raises(ValueError):
        json.loads(cut)
    out = jc.cards_for("bills_due", cut, set())
    assert [c["title"] for c in out] == [f"Payee number {n} with a long name" for n in range(5)]
    # A cut memory_about still has its name and id at the front.
    long = json.dumps(
        {
            "name": "murugan",
            "known": True,
            "id": "ent-1",
            "also_called": ["Murugan"],
            "memories": [
                {"id": str(n), "content": "x" * 300, "created_at": None} for n in range(20)
            ],
        }
    )
    person = jc.cards_for("memory_about", _trim(long), set())
    assert person[0]["id"] == "ent-1" and person[0]["title"] == "Murugan"


def test_garbage_and_other_tools_make_no_cards():
    assert jc.cards_for("bills_due", "not json at all", set()) == []
    assert jc.cards_for("bills_due", '{"error": "no tenant context"}', set()) == []
    assert jc.cards_for("email_search", _bills_result(_bill("X", "2026-10-26")), set()) == []
    assert (
        jc.cards_for("calendar_events", '{"items": [{"id": 1, "starts_at": "x"}]}', set())[0][
            "title"
        ]
        == "An event"
    )


def test_salvage_helpers():
    text = '{"a": 1, "items": [{"x": 1}, {"x": 2}, {"x": "cut'
    assert jc.salvage_list(text, "items") == [{"x": 1}, {"x": 2}]
    assert jc.salvage_list(text, "missing") == []
    assert jc.salvage_value(text, "a") == 1


# ── The chat stream ────────────────────────────────────────────────────────


class _Inner:
    def __init__(self, events):
        self.events = events

    @property
    async def body_iterator(self):
        for e in self.events:
            yield f"data: {json.dumps(e)}\n\n".encode()


@pytest.mark.asyncio
async def test_chat_stream_gains_card_events_after_the_existing_ones(monkeypatch):
    from life_graph.api import jarvis

    asked = []

    async def accounts(tenant_id):
        asked.append(tenant_id)
        return {"Private"}

    monkeypatch.setattr(jc, "local_only_accounts", accounts)
    reminder = json.dumps(
        {
            "reminded": True,
            "id": "r1",
            "text": "Call Amma",
            "at": "2026-10-25T19:00:00+05:30",
            "when": "today at 7 pm",
        }
    )
    inner = _Inner(
        [
            {"type": "start", "session_id": "s1"},
            {"type": "tool_result", "name": "reminder_set", "result": reminder},
            {
                "type": "tool_result",
                "name": "bills_due",
                "result": _bills_result(
                    _bill("TNEB", "2026-10-26"), _bill("HDFC", "2026-10-27", account="Private")
                ),
            },
            {"type": "tool_result", "name": "email_search", "result": "{}"},
            {"type": "assistant_delta", "text": "Done."},
            {"type": "done"},
        ]
    )
    frames = [f async for f in jarvis._app_frames(inner, "t-own")]
    events = [json.loads(f[6:]) for f in frames]
    assert [e["type"] for e in events] == ["reminded", "card", "card", "card", "token", "done"]
    assert events[0] == {
        "type": "reminded",
        "id": "r1",
        "text": "Call Amma",
        "at": "2026-10-25T19:00:00+05:30",
    }
    assert events[1]["card"]["kind"] == "reminder"
    assert [e["card"]["title"] for e in events[2:4]] == ["TNEB", "A bill"]
    assert asked == ["t-own"]  # read once per stream


@pytest.mark.asyncio
async def test_chat_stream_without_a_tenant_masks_bills(monkeypatch):
    from life_graph.api import jarvis

    inner = _Inner(
        [
            {
                "type": "tool_result",
                "name": "bills_due",
                "result": _bills_result(_bill("TNEB", "2026-10-26")),
            }
        ]
    )
    events = [json.loads(f[6:]) async for f in jarvis._app_frames(inner)]
    assert events[0]["card"]["title"] == "A bill"


@pytest.mark.asyncio
async def test_local_only_accounts_is_this_tenants(monkeypatch):
    from tests.unit.fakes import FakeSession, session_factory, sql

    session = FakeSession(["Private"])
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(session))
    assert await jc.local_only_accounts("t-own") == {"Private"}
    text = sql(session.statements[0])
    assert "tenant_id = 't-own'" in text and "'local_only'" in text

    class Broken:
        async def __aenter__(self):
            raise RuntimeError("down")

        async def __aexit__(self, *_a):
            return False

    monkeypatch.setattr("life_graph.storage.database.async_session", lambda: Broken())
    assert await jc.local_only_accounts("t-own") is None


# ── The voice reply ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_voice_reply_cards_from_the_runs_own_tool_results(monkeypatch):
    from life_graph.api import dependencies, jarvis
    from life_graph.services.chat_stream import get_chat_stream_bus

    bus = get_chat_stream_bus()
    task_id = str(uuid.uuid4())
    reminder = json.dumps(
        {
            "reminded": True,
            "id": "r1",
            "text": "Call Amma",
            "at": "2026-10-25T19:00:00+05:30",
            "when": "today at 7 pm",
        }
    )

    class PM:
        async def spawn(self, **kw):
            return {"task_id": task_id}

    async def settled(tenant_id, tid):
        meta = {"task_id": task_id, "agent_name": "jarvis"}
        bus.publish(
            task_id,
            {
                **meta,
                "depth": 0,
                "event": {"type": "tool_result", "name": "reminder_set", "result": reminder},
            },
        )
        # A delegated child's call: not the answer's card.
        bus.publish(
            task_id,
            {
                **meta,
                "depth": 1,
                "event": {"type": "tool_result", "name": "reminder_set", "result": reminder},
            },
        )
        bus.publish(task_id, {**meta, "depth": 0, "event": {"type": "token", "content": "Set."}})
        await asyncio.sleep(0)
        return SimpleNamespace(
            id=uuid.UUID(task_id), status="completed", session_id=None, result={"response": "Set."}
        )

    async def nothing(*_a, **_k):
        return []

    async def start(*_a, **_k):
        return uuid.uuid4()

    async def accounts(tenant_id):
        return set()

    monkeypatch.setattr(dependencies, "get_process_manager", lambda: PM())
    monkeypatch.setattr("life_graph.api.kernel._start_chat_session", start)
    monkeypatch.setattr(jarvis, "_settled", settled)
    monkeypatch.setattr(jarvis, "_saved_in", nothing)
    monkeypatch.setattr(jarvis, "_reminded_in", nothing)
    monkeypatch.setattr(jc, "local_only_accounts", accounts)
    turn = await jarvis._answer("t-own", "remind me", None)
    assert [c["kind"] for c in turn["cards"]] == ["reminder"]
    assert turn["cards"][0]["id"] == "r1"
    # The bus key is freed: no subscriber left, no buffer kept.
    assert bus.buffer_len(task_id) == 0 and not bus._subscribers.get(task_id)


def test_approval_cards_say_what_deciding_does():
    result = json.dumps(
        {
            "total": 3,
            "items": [
                {"id": "a1", "kind": "driver_pr", "title": "Open PR: Tests for day_row", "verified": True, "files": 1},
                {"id": "a2", "kind": "model_adoption", "title": "Adopt MiniMax M3.1 Flash", "summary": "6/6 evals"},
                {"id": "a3", "kind": "something_new", "title": "Review this"},
            ],
        }
    )
    cards = jc.cards_for("approvals_waiting", result, set())
    assert [(c["kind"], c["id"], c["subtitle"]) for c in cards] == [
        ("approval", "a1", "checks passed · 1 file"),
        ("approval", "a2", "6/6 evals"),
        ("approval", "a3", ""),
    ]
    assert [[a["label"] for a in c["actions"]] for c in cards] == [
        ["Open PR", "Reject"],
        ["Adopt", "Not now"],
        ["Approve", "Reject"],
    ]
    assert jc.cards_for("approvals_waiting", json.dumps({"error": "x"}), set()) == []
