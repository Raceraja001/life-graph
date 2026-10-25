"""GET /jarvis/contacts and /jarvis/mail/waiting (services/jarvis_inbox.py):
the rows the app reads, local_only accounts kept off the phone, a failed read
as an empty list, and the device's tenant asked. No database: the store is faked."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from life_graph.connectors import store
from life_graph.services import jarvis_inbox as ji
from tests.unit.fakes import FakeSession, session_factory, sql

NOW = datetime(2026, 10, 25, 9, 42, tzinfo=UTC)


@pytest.fixture
def _no_db(monkeypatch):
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(FakeSession()))


def _contact(name, exposure="standard", *, phones=None, emails=None):
    return {
        "id": f"c-{name}",
        "kind": "contact",
        "account_name": "Google",
        "account_exposure": exposure,
        "account_cloud_fields": None,
        "title": name,
        "direction": "own",
        "emails": emails or [],
        "flags": {},
        "local_detail": json.dumps({"phones": phones or []}),
    }


def _mail(subject, sender, exposure="standard", *, addr="a@example.test"):
    return {
        "id": f"m-{len(subject)}",
        "kind": "email",
        "account_name": "Mail",
        "account_exposure": exposure,
        "title": subject,
        "summary": "Asks for the invoice",
        "sender_name": sender,
        "sender_addr": addr,
        "occurred_at": datetime(2026, 10, 23, 8, 0, tzinfo=UTC),
        "direction": "inbound",
        "category": None,
        "flags": {"needs_reply": True},
    }


@pytest.mark.asyncio
async def test_contacts_search_and_list(monkeypatch, _no_db):
    calls = []

    async def search(session, tenant_id, query, limit=10):
        calls.append(("search", tenant_id, query, limit))
        return [
            _contact("Murugan K", phones=["+91 98765 43210 (mobile)"], emails=["m@example.test"]),
            _contact("Hidden Person", "local_only", phones=["+91 1"]),
        ]

    async def listed(session, tenant_id, limit=100):
        calls.append(("list", tenant_id, limit))
        return [_contact("Amma")]

    monkeypatch.setattr(store, "search_contacts", search)
    monkeypatch.setattr(store, "list_contacts", listed)
    out = await ji.contacts("t-own", "  murugan ")
    assert out == [
        {
            "id": "c-Murugan K",
            "name": "Murugan K",
            "phone": "+91 98765 43210",
            "email": "m@example.test",
        }
    ]  # the local_only contact is not sent at all
    assert await ji.contacts("t-own", "") == [
        {"id": "c-Amma", "name": "Amma", "phone": None, "email": None}
    ]
    await ji.contacts("t-own", "a")  # one letter: too short to search, the list instead
    assert calls == [
        ("search", "t-own", "murugan", ji.MAX_SEARCH),
        ("list", "t-own", ji.MAX_CONTACTS),
        ("list", "t-own", ji.MAX_CONTACTS),
    ]


@pytest.mark.asyncio
async def test_contacts_failing_is_an_empty_list(monkeypatch, _no_db, caplog):
    async def boom(*_a, **_k):
        raise RuntimeError("Murugan's number")

    monkeypatch.setattr(store, "list_contacts", boom)
    caplog.set_level("DEBUG", logger=ji.__name__)
    assert await ji.contacts("t-own") == []
    assert "RuntimeError" in caplog.text and "Murugan" not in caplog.text


@pytest.mark.asyncio
async def test_list_contacts_is_this_tenants(monkeypatch):
    session = FakeSession([])
    await store.list_contacts(session, "t-own")
    text = sql(session.statements[0])
    assert "tenant_id = 't-own'" in text and "'contact'" in text


@pytest.mark.asyncio
async def test_mail_waiting_rows_and_local_only_masked(monkeypatch, _no_db):
    async def waiting(session, tenant_id, now=None, limit=20):
        assert (tenant_id, limit) == ("t-own", ji.MAX_WAITING)
        return [
            _mail("Invoice?", "Priya"),
            _mail("Lab results", "Dr Rao", "local_only", addr="lab@example.test"),
            _mail("Hello", None, addr="ravi@example.test"),
        ]

    async def people(session, tenant_id, addrs):
        assert tenant_id == "t-own" and "lab@example.test" in addrs
        return {
            "ravi@example.test": {"title": "Ravi", "account_exposure": "standard"},
            "a@example.test": {"title": "Secret name", "account_exposure": "local_only"},
        }

    monkeypatch.setattr(store, "waiting_on_me", waiting)
    monkeypatch.setattr(store, "people_by_address", people)
    out = await ji.mail_waiting("t-own", NOW)
    assert out[0] == {
        "id": "m-8",
        "from": "Priya",
        "subject": "Invoice?",
        "received_at": "2026-10-23T08:00:00+00:00",
        "needs_reply": True,
    }
    assert out[1]["from"] == "Someone" and out[1]["subject"] == "(no subject)"
    assert "Dr Rao" not in str(out) and "Lab results" not in str(out)
    assert out[2]["from"] == "Ravi"  # a name from a contact
    assert "Secret name" not in str(out)


@pytest.mark.asyncio
async def test_mail_waiting_failing_is_an_empty_list(monkeypatch, _no_db):
    async def boom(*_a, **_k):
        raise RuntimeError("down")

    monkeypatch.setattr(store, "waiting_on_me", boom)
    assert await ji.mail_waiting("t-own", NOW) == []


@pytest.mark.asyncio
async def test_endpoints_answer_for_the_requests_tenant(monkeypatch):
    from life_graph.api import jarvis
    from life_graph.core.tenant import tenant_scope

    asked = []

    async def contacts(tenant_id, q=""):
        asked.append(("contacts", tenant_id, q))
        return []

    async def waiting(tenant_id, now=None):
        asked.append(("mail", tenant_id))
        return []

    monkeypatch.setattr(ji, "contacts", contacts)
    monkeypatch.setattr(ji, "mail_waiting", waiting)
    with tenant_scope("t-own"):
        assert (await jarvis.contacts("amma"))["data"] == []
        assert (await jarvis.mail_waiting())["data"] == []
    assert asked == [("contacts", "t-own", "amma"), ("mail", "t-own")]
