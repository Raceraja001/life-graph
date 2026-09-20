"""Contacts connector (docs/specs/connector-contacts.md): parsers, the Google
source against a fake People API, and the per-account cloud visibility rules.

Database-backed behaviour (imports, lookups by address, the brief) is exercised
end to end against a copy of the database; these tests pin the pure rules.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from life_graph.config import settings
from life_graph.connectors import google_oauth
from life_graph.connectors.base import (
    AUTH_OAUTH,
    Account,
    ConnectorError,
    ReauthRequiredError,
)
from life_graph.connectors.exposure import (
    EXPOSURE_LOCAL_ONLY,
    MASK,
    person_line,
    person_name,
    view_items,
)
from life_graph.connectors.locality import CLOUD, LOCAL

NOW = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)

# ── vCard ────────────────────────────────────────────────────

GOOGLE_EXPORT = (
    "BEGIN:VCARD\r\n"
    "VERSION:3.0\r\n"
    "FN:Arun Kumar\r\n"
    "N:Kumar;Arun;;;\r\n"
    "EMAIL;TYPE=INTERNET;TYPE=WORK:Arun.Kumar@Acme.test\r\n"
    "EMAIL;TYPE=INTERNET:arun@home.test\r\n"
    "TEL;TYPE=CELL:+91 98765 43210\r\n"
    "ORG:Acme Ltd\r\n"
    "TITLE:CFO\r\n"
    "BDAY:1980-09-21\r\n"
    "ADR;TYPE=HOME:;;12 MG Road;Bengaluru;;560001;India\r\n"
    "NOTE:Met at the expo\\, prefers calls.\\nAadhaar 1234 5678 9012\r\n"
    "CATEGORIES:myContacts,starred,Vendors\r\n"
    "item1.X-ABRELATEDNAMES:Meera\r\n"
    "UID:abc-123\r\n"
    "END:VCARD\r\n"
    "BEGIN:VCARD\r\n"
    "VERSION:3.0\r\n"
    "FN:Priya\r\n"
    "  Sharma\r\n"
    "EMAIL:priya@x.test\r\n"
    "BDAY:--02-29\r\n"
    "END:VCARD\r\n"
)


def test_vcard_google_export():
    from plugins.contacts.vcard import parse_vcards

    arun, priya = parse_vcards(GOOGLE_EXPORT)
    assert arun.kind == "contact" and arun.external_id == "vcard:abc-123"
    assert arun.title == "Arun Kumar" and arun.direction == "own"
    assert arun.emails == ["arun.kumar@acme.test", "arun@home.test"]
    assert arun.flags == {
        "org": "Acme Ltd",
        "job_title": "CFO",
        "birthday": "09-21",
        "groups": ["Vendors"],
        "starred": True,
    }
    private = json.loads(arun.detail)
    assert private["phones"] == ["+91 98765 43210 (cell)"]
    assert private["addresses"] == ["12 MG Road, Bengaluru, 560001, India (home)"]
    assert private["notes"].startswith("Met at the expo, prefers calls.\nAadhaar")
    assert private["relations"] == ["Meera"] and private["birth_year"] == 1980
    # Folded line; a February 29 birthday without a year.
    assert priya.title == "Priya Sharma" and priya.flags["birthday"] == "02-29"
    assert priya.external_id.startswith("vcard:h:")


def test_vcard_21_quoted_printable_and_40():
    from plugins.contacts.vcard import parse_vcards

    text = (
        "BEGIN:VCARD\nVERSION:2.1\n"
        "N;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:Sh=C3=A9th;Ren=\n"
        "=C3=A9e;;;\n"
        "TEL;CELL;PREF:+911234567890\n"
        "END:VCARD\n"
        "BEGIN:VCARD\nVERSION:4.0\n"
        'FN:Kai "K" Lee\n'
        "EMAIL;PREF=1:kai@x.test\n"
        "BDAY:19900314\n"
        "END:VCARD\n"
    )
    renee, kai = parse_vcards(text)
    assert renee.title == "Renée Shéth"
    assert json.loads(renee.detail)["phones"] == ["+911234567890 (cell)"]
    assert kai.title == 'Kai "K" Lee' and kai.flags["birthday"] == "03-14"


def test_vcard_ids_are_stable_and_empty_cards_skipped():
    from plugins.contacts.vcard import parse_vcards

    card = "BEGIN:VCARD\nFN:Anon\nEMAIL:a@x.test\nEND:VCARD\n"
    first, second = parse_vcards(card)[0], parse_vcards(card)[0]
    assert first.external_id == second.external_id
    assert parse_vcards("BEGIN:VCARD\nVERSION:3.0\nEND:VCARD\n") == []
    # Nothing but an address: the address is the name.
    assert parse_vcards("BEGIN:VCARD\nEMAIL:x@y.test\nEND:VCARD\n")[0].title == "x@y.test"


def test_vcard_rejects_other_files():
    from plugins.contacts.vcard import parse_vcards

    with pytest.raises(ConnectorError, match="not a vCard"):
        parse_vcards("name,email\nArun,a@x.test\n")


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("1980-09-21", (1980, 9, 21)),
        ("19800921", (1980, 9, 21)),
        ("--0921", (None, 9, 21)),
        ("--09-21", (None, 9, 21)),
        ("1604-09-21", (None, 9, 21)),
        ("1980-09-21T00:00:00Z", (1980, 9, 21)),
        ("sometime", (None, None, None)),
    ],
)
def test_vcard_birthday_formats(raw, want):
    from plugins.contacts.vcard import _birthday

    assert _birthday(raw) == want


# ── Google People API (fake) ─────────────────────────────────


def _person(rid, name, email, **extra):
    return {
        "resourceName": rid,
        "names": [{"displayName": name, "metadata": {"primary": True}}],
        "emailAddresses": [{"value": email}],
        **extra,
    }


def _account():
    return Account(
        id="acc-c",
        tenant_id="raja",
        connector="contacts",
        account_key="google",
        display_name="Google",
        auth_method=AUTH_OAUTH,
    )


class FakePeople:
    """Serves connections + otherContacts pages, sync tokens, and scripted errors."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.expired = False
        self.error: tuple[int, dict] | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.method == "GET"
        if self.error:
            return httpx.Response(self.error[0], json=self.error[1])
        params = dict(request.url.params)
        incremental = "syncToken" in params
        if incremental and self.expired:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "status": "FAILED_PRECONDITION",
                        "message": "Sync token is expired.",
                        "details": [{"reason": "EXPIRED_SYNC_TOKEN"}],
                    }
                },
            )
        if request.url.path.endswith("/people/me/connections"):
            if incremental:
                return httpx.Response(
                    200,
                    json={
                        "connections": [
                            {"resourceName": "people/c2", "metadata": {"deleted": True}},
                            _person("people/c3", "New Person", "new@x.test"),
                        ],
                        "nextSyncToken": "conn-2",
                    },
                )
            if params.get("pageToken") != "p2":
                return httpx.Response(
                    200,
                    json={
                        "connections": [
                            _person(
                                "people/c1",
                                "Arun Kumar",
                                "Arun@Acme.test",
                                organizations=[{"name": "Acme", "title": "CFO"}],
                                birthdays=[{"date": {"month": 9, "day": 21}}],
                                phoneNumbers=[
                                    {"value": "+91 98765 43210", "formattedType": "Mobile"}
                                ],
                                memberships=[
                                    {
                                        "contactGroupMembership": {
                                            "contactGroupResourceName": "contactGroups/starred"
                                        }
                                    }
                                ],
                            )
                        ],
                        "nextPageToken": "p2",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "connections": [_person("people/c2", "Old Friend", "old@x.test")],
                    "nextSyncToken": "conn-1",
                },
            )
        assert request.url.path.endswith("/otherContacts")
        return httpx.Response(
            200,
            json={
                "otherContacts": []
                if incremental
                else [_person("otherContacts/o1", "", "vendor@shop.test")],
                "nextSyncToken": "other-2" if incremental else "other-1",
            },
        )


@pytest.fixture
def fake_people(monkeypatch):
    from plugins.contacts import google_source

    fake = FakePeople()
    real = httpx.AsyncClient

    def client(**kw):
        return real(transport=httpx.MockTransport(fake.handler), **kw)

    monkeypatch.setattr(google_source.httpx, "AsyncClient", client)
    return fake


async def test_google_full_then_incremental(fake_people):
    from plugins.contacts import google_source

    secret = {"access_token": "at"}
    items, deleted, cursor, complete = await google_source.sync(_account(), secret, {})
    assert complete and not deleted
    by_id = {i.external_id: i for i in items}
    assert set(by_id) == {"people/c1", "people/c2", "otherContacts/o1"}
    arun = by_id["people/c1"]
    assert arun.direction == "own" and arun.emails == ["arun@acme.test"]
    assert arun.flags == {"org": "Acme", "job_title": "CFO", "birthday": "09-21", "starred": True}
    assert json.loads(arun.detail) == {"phones": ["+91 98765 43210 (mobile)"]}
    other = by_id["otherContacts/o1"]
    assert other.direction == "inbound" and other.title == "vendor@shop.test"
    assert cursor == {"google": {"connections": "conn-1", "other": "other-1"}}
    assert all(r.headers["Authorization"] == "Bearer at" for r in fake_people.requests)

    items, deleted, cursor, complete = await google_source.sync(_account(), secret, cursor)
    assert not complete and deleted == ["people/c2"]
    assert [i.external_id for i in items] == ["people/c3"]
    assert cursor == {"google": {"connections": "conn-2", "other": "other-2"}}


async def test_google_expired_token_means_full_listing(fake_people):
    from plugins.contacts import google_source

    fake_people.expired = True
    cursor = {"google": {"connections": "old", "other": "old"}}
    items, deleted, new_cursor, complete = await google_source.sync(
        _account(), {"access_token": "at"}, cursor
    )
    assert complete and len(items) == 3 and not deleted
    assert new_cursor["google"]["connections"] == "conn-1"


async def test_google_api_disabled_is_not_a_reconnect(fake_people):
    from plugins.contacts import google_source

    fake_people.error = (
        403,
        {
            "error": {
                "status": "PERMISSION_DENIED",
                "message": "People API has not been used in project 1 before or it is disabled.",
                "details": [{"reason": "SERVICE_DISABLED"}],
            }
        },
    )
    with pytest.raises(ConnectorError, match="People API is not enabled") as err:
        await google_source.sync(_account(), {"access_token": "at"}, {})
    assert not isinstance(err.value, ReauthRequiredError)
    fake_people.error = (401, {"error": {"status": "UNAUTHENTICATED"}})
    with pytest.raises(ReauthRequiredError):
        await google_source.sync(_account(), {"access_token": "at"}, {})


def test_contacts_oauth_scopes_are_read_only():
    scopes = google_oauth.scopes_for("contacts")
    assert scopes and all(s.endswith(".readonly") for s in scopes)
    with pytest.raises(ConnectorError):
        google_oauth.scopes_for("nonexistent")


# ── account settings ─────────────────────────────────────────


def test_cloud_fields_setting():
    from plugins.contacts import CONNECTOR

    assert CONNECTOR.validate_settings("file", {})["cloud_fields"] == [
        "name",
        "org",
        "emails",
        "birthday",
    ]
    chosen = CONNECTOR.validate_settings("oauth", {"cloud_fields": ["phones", "name"]})
    assert chosen["cloud_fields"] == ["name", "phones"]
    assert CONNECTOR.validate_settings("oauth", {"cloud_fields": []})["cloud_fields"] == []
    with pytest.raises(ValueError, match="unknown"):
        CONNECTOR.validate_settings("oauth", {"cloud_fields": ["birth_year"]})
    with pytest.raises(ValueError):
        CONNECTOR.validate_settings("oauth", {"username": "not-an-address"})


def test_contacts_connector_is_discovered():
    from life_graph.connectors.runtime import ConnectorRuntime, discover

    catalogue = {c["name"]: c for c in ConnectorRuntime(discover()).catalogue()}
    contacts = catalogue["contacts"]
    assert contacts["auth_methods"] == ["oauth", "file"]
    assert {o["name"] for o in contacts["cloud_field_options"] if not o["default"]} == {
        "phones",
        "addresses",
        "notes",
    }


# ── exposure ─────────────────────────────────────────────────


def _contact(**kw):
    return {
        "id": "c1",
        "kind": "contact",
        "account_name": "Google",
        "account_exposure": "standard",
        "account_cloud_fields": None,
        "title": "Arun Kumar",
        "direction": "own",
        "emails": ["arun@acme.test"],
        "flags": {"org": "Acme", "job_title": "CFO", "birthday": "09-21"},
        "local_detail": json.dumps(
            {
                "phones": ["+91 98765 43210 (mobile)"],
                "addresses": ["12 MG Road"],
                "notes": "PAN ABCDE1234F",
                "relations": ["Meera (spouse)"],
                "birth_year": 1980,
            }
        ),
        **kw,
    }


def test_contact_default_cloud_view():
    cloud = view_items([_contact()], CLOUD)["items"][0]
    assert cloud["name"] == "Arun Kumar" and cloud["org"] == "Acme" and cloud["job_title"] == "CFO"
    assert cloud["emails"] == ["arun@acme.test"] and cloud["birthday"] == "09-21"
    text = json.dumps(cloud)
    for private in ("98765", "MG Road", "ABCDE1234F", "Meera", "1980"):
        assert private not in text
    local = view_items([_contact()], LOCAL)["items"][0]
    assert local["phones"] and local["notes"] == "PAN ABCDE1234F" and local["birth_year"] == 1980


def test_contact_cloud_fields_are_per_account():
    opted = _contact(account_cloud_fields=["name", "phones", "notes"])
    cloud = view_items([opted], CLOUD)["items"][0]
    assert cloud["phones"] == ["+91 98765 43210 (mobile)"]
    assert "ABCDE1234F" not in cloud["notes"] and MASK in cloud["notes"]  # still redacted
    assert "org" not in cloud and "emails" not in cloud and "birthday" not in cloud
    assert "relations" not in cloud and "birth_year" not in cloud  # never configurable

    nameless = view_items([_contact(account_cloud_fields=["emails"])], CLOUD)
    assert nameless == {"items": [], "withheld": {"Google": 1}}
    local_only = view_items([_contact(account_exposure=EXPOSURE_LOCAL_ONLY)], CLOUD)
    assert local_only == {"items": [], "withheld": {"Google": 1}}


def test_names_resolved_within_each_contacts_visibility():
    contact = _contact()
    assert person_name(contact, CLOUD) == "Arun Kumar"
    assert person_line(contact, CLOUD) == "Arun Kumar — Acme, CFO"
    assert person_line(_contact(account_cloud_fields=["name"]), CLOUD) == "Arun Kumar"
    hidden = _contact(account_exposure=EXPOSURE_LOCAL_ONLY)
    assert person_name(hidden, CLOUD) is None and person_name(hidden, LOCAL) == "Arun Kumar"

    people = {"arun@acme.test": contact}
    bare = {
        "id": "m1",
        "kind": "email",
        "account_name": "Mail",
        "account_exposure": "standard",
        "title": "Invoice",
        "sender_name": None,
        "sender_addr": "arun@acme.test",
        "direction": "inbound",
        "occurred_at": NOW,
        "summary": None,
        "category": "work",
        "flags": {},
    }
    assert view_items([bare], CLOUD, people)["items"][0]["sender_name"] == "Arun Kumar"
    # A suspicious sender never borrows a trusted contact's name.
    spoof = {**bare, "flags": {"suspicious": True}}
    assert view_items([spoof], LOCAL, people)["items"][0]["sender_name"] is None
    # Attendees shown as bare addresses get names too.
    event = {
        "id": "e1",
        "kind": "event",
        "account_name": "Cal",
        "account_exposure": "standard",
        "title": "Review",
        "starts_at": NOW,
        "ends_at": NOW,
        "location": None,
        "attendees": ["arun@acme.test", "Ann"],
        "direction": "own",
        "flags": {},
    }
    assert view_items([event], CLOUD, people)["items"][0]["attendees"] == ["Arun Kumar", "Ann"]
    hidden_people = {"arun@acme.test": hidden}
    assert view_items([event], CLOUD, hidden_people)["items"][0]["attendees"][0] == "arun@acme.test"


# ── addresses on mail and events ─────────────────────────────


def test_mail_and_events_record_who_is_involved():
    from plugins.calendar.connector import google_event_item
    from plugins.mail.mailparse import to_item

    mine = {"raja@example.test"}
    mail = to_item(
        {
            "from": "Priya <PRIYA@acme.test>",
            "to": "raja@example.test, Ann <ann@acme.test>",
            "cc": "boss@acme.test",
            "subject": "Plan",
            "date": "Fri, 18 Sep 2026 10:00:00 +0530",
        },
        external_id="1",
        sent=False,
        my_addresses=mine,
    )
    assert mail.emails == ["priya@acme.test", "ann@acme.test", "boss@acme.test"]
    ev = google_event_item(
        "primary",
        {
            "id": "1",
            "summary": "Sync",
            "start": {"dateTime": "2026-09-19T10:00:00+05:30"},
            "end": {"dateTime": "2026-09-19T11:00:00+05:30"},
            "organizer": {"email": "Lead@Acme.test"},
            "attendees": [
                {"email": "me@t", "self": True},
                {"email": "A@t", "displayName": "Ann"},
            ],
        },
        {"me@t"},
    )
    assert ev.emails == ["a@t", "lead@acme.test"]


# ── birthdays ────────────────────────────────────────────────


def test_birthday_window_wraps_year_and_leap_day():
    from life_graph.connectors.store import _month_days

    window = _month_days(date(2026, 12, 30), 4)
    assert list(window) == ["12-30", "12-31", "01-01", "01-02"]
    assert window["01-02"] == date(2027, 1, 2)
    feb = _month_days(date(2027, 2, 27), 3)
    assert feb["02-29"] == date(2027, 2, 28)
    assert "02-29" in _month_days(date(2028, 2, 29), 1)


def test_brief_birthdays_follow_each_accounts_visibility(monkeypatch):
    from life_graph.connectors.brief import render

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    today = NOW.date()
    raw = {
        "today": [],
        "tomorrow_early": [],
        "waiting": [],
        "promises": [],
        "birthdays": [
            {**_contact(), "birthday_on": today},
            {
                **_contact(id="c2", title="Meena", flags={"birthday": "09-21"}),
                "birthday_on": today + timedelta(days=2),
            },
            {
                **_contact(id="c3", title="Work Friend", account_name="Work"),
                "account_exposure": EXPOSURE_LOCAL_ONLY,
                "birthday_on": today + timedelta(days=1),
            },
            {
                **_contact(id="c4", title="No Dates", account_name="Quiet"),
                "account_cloud_fields": ["name"],
                "birthday_on": today,
            },
        ],
        "people": {},
    }
    cloud = render(raw, CLOUD, NOW)
    text = cloud["text"]
    assert "## Birthdays" in text and "- Arun Kumar — today" in text
    assert "- Meena — Mon 21 Sep" in text
    assert "Work Friend" not in text and "+1 in Work" in text
    assert "No Dates" not in text and "+1 in Quiet" in text
    local = render(raw, LOCAL, NOW)
    assert "- Work Friend — tomorrow" in local["text"] and "- No Dates — today" in local["text"]
    assert [c["on"] for c in local["birthdays"]["items"]][:1] == [today.isoformat()]


# ── chat intent ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("msg", "want"),
    [
        ("who is Arun Kumar?", True),
        ("what's Priya's phone number", True),
        ("any birthdays this week?", True),
        ("write a poem about rain", False),
    ],
)
def test_contact_intent(msg, want):
    from life_graph.connectors.chat_context import wants_contacts

    assert wants_contacts(msg) is want
