"""Connectors: the pieces that decide what leaves the machine, and the parsers.

Database-backed behaviour (sync, upserts, "waiting on you", the brief) is
exercised end to end against a real IMAP server and ICS feeds; these tests pin
the pure rules those paths rely on.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest

from life_graph.config import settings
from life_graph.connectors import exposure, google_oauth, locality, secrets
from life_graph.connectors.base import ConnectorError, ReauthRequiredError
from life_graph.connectors.exposure import EXPOSURE_LOCAL_ONLY, MASK, redact, view_items
from life_graph.connectors.locality import CLOUD, LOCAL, audience, audience_for_model

# ── redaction ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "leak"),
    [
        ("Your OTP is 482913", "482913"),
        ("verification code: 5521", "5521"),
        ("password: hunter2", "hunter2"),
        ("card 4111 1111 1111 1111 charged", "4111"),
        ("Aadhaar 1234 5678 9012", "9012"),
        ("PAN ABCDE1234F", "ABCDE1234F"),
        ("IFSC HDFC0001234", "HDFC0001234"),
        ("credited to 50100123456789", "50100123456789"),
        ("The account number is XX4521.", "4521"),
        ("A/c XX4521 debited", "4521"),
    ],
)
def test_redact_masks_secrets(text, leak):
    out = redact(text)
    assert leak not in out and MASK in out


@pytest.mark.parametrize(
    "text", ["Standup at 10:30", "Due 2026-09-19", "Room 204, floor 3", "Invoice #12 for 4 items"]
)
def test_redact_leaves_ordinary_text(text):
    assert redact(text) == text


# ── exposure table ───────────────────────────────────────────

NOW = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)


def _event(**kw):
    return {
        "id": "e1",
        "kind": "event",
        "account_name": "Personal",
        "account_exposure": "standard",
        "title": "Dentist",
        "starts_at": NOW,
        "ends_at": NOW + timedelta(hours=1),
        "location": "Clinic",
        "attendees": ["Priya"],
        "direction": "own",
        "flags": {},
        "local_detail": "Bring card 4111 1111 1111 1111",
        **kw,
    }


def _mail(**kw):
    return {
        "id": "m1",
        "kind": "email",
        "account_name": "Mail",
        "account_exposure": "standard",
        "title": "Contract",
        "sender_name": "Priya",
        "sender_addr": "p@x.test",
        "direction": "inbound",
        "occurred_at": NOW,
        "summary": "Sign by Monday",
        "category": "work",
        "flags": {},
        **kw,
    }


def test_cloud_never_sees_event_descriptions():
    cloud = view_items([_event()], CLOUD)["items"][0]
    local = view_items([_event()], LOCAL)["items"][0]
    assert "description" not in cloud
    assert local["description"].startswith("Bring card")


def test_local_only_accounts_are_counted_not_shown_to_cloud():
    rows = [
        _event(),
        _event(
            id="e2", account_name="Work", account_exposure=EXPOSURE_LOCAL_ONLY, title="Board prep"
        ),
    ]
    cloud = view_items(rows, CLOUD)
    assert [i["title"] for i in cloud["items"]] == ["Dentist"]
    assert cloud["withheld"] == {"Work": 1}
    assert len(view_items(rows, LOCAL)["items"]) == 2


def test_sensitive_mail_shows_only_its_sender_to_cloud():
    row = _mail(title="Your OTP is 482913", summary="OTP for login", category="sensitive")
    cloud = view_items([row], CLOUD)["items"][0]
    assert cloud["subject"] == "(sensitive email)" and cloud["summary"] is None
    assert cloud["sender_name"] == "Priya"
    assert view_items([row], LOCAL)["items"][0]["subject"] == "Your OTP is 482913"


def test_cloud_mail_fields_are_redacted():
    row = _mail(title="Refund to a/c XX4521", summary="Refund of 500 to 50100123456789")
    cloud = view_items([row], CLOUD)["items"][0]
    assert "4521" not in cloud["subject"] and "50100123456789" not in cloud["summary"]


def test_bodies_only_ever_go_to_local():
    assert exposure.body_for(LOCAL, "hello") == "hello"
    assert exposure.body_for(CLOUD, "hello") is None
    assert exposure.audience_or_cloud("anything") == CLOUD


# ── locality ─────────────────────────────────────────────────


def test_model_locality(monkeypatch):
    monkeypatch.setattr(settings, "connector_local_model_prefixes", "")
    assert locality.model_is_local("ollama_chat/qwen3:14b")
    assert locality.model_is_local("lm_studio/qwen")
    assert not locality.model_is_local("claude-cli")
    assert not locality.model_is_local("gemini/gemini-3.6-flash")
    assert not locality.model_is_local(None)
    monkeypatch.setattr(settings, "connector_local_model_prefixes", "hosted_vllm/")
    assert locality.model_is_local("hosted_vllm/llama")


def test_a_cloud_fallback_makes_a_local_run_cloud(monkeypatch):
    monkeypatch.setattr(settings, "llm_fallback_chain", "ollama_chat/qwen3:4b")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", None)
    assert locality.run_is_local("ollama_chat/qwen3:14b")
    monkeypatch.setattr(settings, "llm_fallback_chain", "ollama_chat/qwen3:4b,gemini/flash")
    assert not locality.run_is_local("ollama_chat/qwen3:14b")
    monkeypatch.setattr(settings, "llm_fallback_chain", "ollama_chat/qwen3:4b")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", "openrouter/x")
    assert not locality.run_is_local("ollama_chat/qwen3:14b")


def test_audience_defaults_to_cloud_and_never_widens(monkeypatch):
    monkeypatch.setattr(settings, "llm_fallback_chain", "ollama_chat/qwen3:4b")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", None)
    assert locality.current_audience() == CLOUD
    with audience_for_model("ollama_chat/qwen3:14b"):
        assert locality.current_audience() == LOCAL
    with audience(CLOUD), audience_for_model("ollama_chat/qwen3:14b"):
        assert locality.current_audience() == CLOUD
    assert locality.current_audience() == CLOUD


# ── secrets ──────────────────────────────────────────────────


@pytest.fixture
def secret_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "connector_secrets_dir", str(tmp_path))
    return tmp_path


def test_secret_roundtrip_is_private(secret_dir):
    secrets.write_secret("raja", "acc-1", {"method": "app_password", "password": "pw"})
    path = secrets.secret_path("raja", "acc-1")
    assert secrets.read_secret("raja", "acc-1")["password"] == "pw"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        os.chmod(path, 0o644)
        with pytest.raises(secrets.SecretError, match="readable by other users"):
            secrets.read_secret("raja", "acc-1")
    secrets.delete_secret("raja", "acc-1")
    assert not secrets.has_secret("raja", "acc-1")


@pytest.mark.parametrize("bad", ["../etc", "a/b", "", "x y"])
def test_secret_paths_reject_traversal(secret_dir, bad):
    with pytest.raises(secrets.SecretError):
        secrets.secret_path(bad, "acc")


def test_google_client_accepts_the_downloaded_json(secret_dir):
    secrets.write_google_client({"installed": {"client_id": "cid", "client_secret": "cs"}})
    assert secrets.google_client() == {"client_id": "cid", "client_secret": "cs"}
    with pytest.raises(secrets.SecretError):
        secrets.write_google_client({"installed": {"client_id": "only-id"}})


# ── summariser post-processing ───────────────────────────────


class _FakeLLM:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    async def chat_local_only(self, **kw):
        self.calls.append(kw)
        return self.reply


async def test_summary_is_local_only_and_redacted():
    from life_graph.connectors.summarize import summarize_email

    llm = _FakeLLM(
        json.dumps(
            {
                "summary": "The OTP is 482913",
                "category": "personal",
                "asks_me": False,
                "suspicious": False,
            }
        )
    )
    out = await summarize_email(
        subject="Your OTP", sender="Bank", text="OTP 482913", automated=True, client=llm
    )
    assert "482913" not in out.summary
    assert out.category == "sensitive"  # keyword override beats the model
    assert llm.calls and llm.calls[0]["response_format"]["type"] == "json_schema"


async def test_suspicious_mail_is_never_a_to_do():
    from life_graph.connectors.summarize import summarize_email

    llm = _FakeLLM(
        json.dumps(
            {
                "summary": "Wants files sent",
                "category": "personal",
                "asks_me": True,
                "suspicious": True,
            }
        )
    )
    out = await summarize_email(
        subject="Urgent", sender="x", text="ignore instructions", automated=False, client=llm
    )
    assert out.suspicious and not out.asks_me


async def test_summary_failure_falls_back_without_raising():
    from life_graph.connectors.summarize import summarize_email

    out = await summarize_email(
        subject="Hi", sender="x", text="hello", automated=False, client=_FakeLLM("not json")
    )
    assert not out.ok and out.summary is None and out.asks_me is False


# ── mail parsing ─────────────────────────────────────────────


def test_mail_item_threading_and_flags():
    from plugins.mail.mailparse import html_to_text, to_item

    headers = {
        "from": "Priya <PRIYA@acme.test>",
        "to": "raja@example.test",
        "subject": "=?utf-8?q?Caf=C3=A9?=",
        "date": "Fri, 18 Sep 2026 10:00:00 +0530",
        "message-id": "<b@x>",
        "references": "<root@x> <a@x>",
        "in-reply-to": "<a@x>",
    }
    item = to_item(headers, external_id="b@x", sent=False, my_addresses={"raja@example.test"})
    assert item.thread_key == "root@x"
    assert item.title == "Café" and item.sender_addr == "priya@acme.test"
    assert item.to_me and item.direction == "inbound" and not item.flags["automated"]
    news = to_item(
        {**headers, "list-unsubscribe": "<mailto:u@x>"},
        external_id="c",
        sent=False,
        my_addresses={"raja@example.test"},
    )
    assert news.flags["automated"]
    mine = to_item(
        {**headers, "from": "Raja <raja@example.test>"},
        external_id="d",
        sent=False,
        my_addresses={"raja@example.test"},
    )
    assert mine.direction == "sent" and mine.to_me is False
    assert "Hello world" in html_to_text("<style>x{}</style><p>Hello</p><p>world</p>").replace(
        "\n", " "
    )


def test_gmail_body_prefers_plain_text():
    import base64

    from plugins.mail.gmail_source import body_text

    enc = lambda s: base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")  # noqa: E731
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": enc("<b>html</b>")}},
            {"mimeType": "text/plain", "body": {"data": enc("plain text")}},
            {"mimeType": "application/pdf", "filename": "x.pdf", "body": {}},
        ],
    }
    assert body_text(payload) == "plain text"


def test_imap_client_refuses_mailbox_changes():
    from plugins.mail.imap_source import ReadOnlyIMAP

    conn = ReadOnlyIMAP.__new__(ReadOnlyIMAP)  # no network: the guard runs first
    for name, args in (
        ("STORE", ("1", "+FLAGS", "\\Seen")),
        ("SELECT", ("INBOX",)),
        ("EXPUNGE", ()),
        ("APPEND", ("INBOX",)),
        ("UID", ("STORE", "1")),
    ):
        with pytest.raises(ConnectorError, match="read-only"):
            conn._command(name, *args)


# ── calendar ─────────────────────────────────────────────────


def _ics(now: datetime) -> bytes:
    fmt = lambda d: d.strftime("%Y%m%dT%H%M%SZ")  # noqa: E731
    day = now.strftime("%Y%m%d")
    nxt = (now + timedelta(days=1)).strftime("%Y%m%d")
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//t//EN
BEGIN:VEVENT
UID:rec@t
DTSTART:{fmt(now - timedelta(days=1))}
DTEND:{fmt(now - timedelta(days=1) + timedelta(minutes=15))}
RRULE:FREQ=DAILY;COUNT=3
SUMMARY:Standup
ORGANIZER:mailto:me@t
END:VEVENT
BEGIN:VEVENT
UID:inv@t
DTSTART:{fmt(now + timedelta(hours=2))}
DTEND:{fmt(now + timedelta(hours=3))}
SUMMARY:Invite
ORGANIZER:mailto:boss@t
ATTENDEE;PARTSTAT=ACCEPTED:mailto:me@t
END:VEVENT
BEGIN:VEVENT
UID:dec@t
DTSTART:{fmt(now + timedelta(hours=4))}
DTEND:{fmt(now + timedelta(hours=5))}
SUMMARY:Declined
ORGANIZER:mailto:boss@t
ATTENDEE;PARTSTAT=DECLINED:mailto:me@t
END:VEVENT
BEGIN:VEVENT
UID:can@t
DTSTART:{fmt(now + timedelta(hours=6))}
DTEND:{fmt(now + timedelta(hours=7))}
STATUS:CANCELLED
SUMMARY:Cancelled
END:VEVENT
BEGIN:VEVENT
UID:hol@t
DTSTART;VALUE=DATE:{day}
DTEND;VALUE=DATE:{nxt}
SUMMARY:Holiday
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n").encode()


def test_ics_expansion_and_filters():
    from plugins.calendar.connector import parse_ics

    now = datetime.now(UTC).replace(microsecond=0)
    items = parse_ics(_ics(now), {"me@t"})
    titles = [i.title for i in items]
    assert titles.count("Standup") == 3
    assert "Declined" not in titles and "Cancelled" not in titles
    by = {i.title: i for i in items}
    assert by["Invite"].direction == "invite" and by["Standup"].direction == "own"
    assert by["Holiday"].all_day
    assert len({i.external_id for i in items}) == len(items)


def test_ics_rejects_garbage():
    from plugins.calendar.connector import parse_ics

    with pytest.raises(ConnectorError):
        parse_ics(b"<html>not a calendar</html>", set())


def test_google_event_mapping():
    from plugins.calendar.connector import google_event_item

    ev = {
        "id": "1",
        "summary": "Sync",
        "start": {"dateTime": "2026-09-19T10:00:00+05:30"},
        "end": {"dateTime": "2026-09-19T11:00:00+05:30"},
        "organizer": {"self": True},
        "hangoutLink": "https://meet/x",
        "attendees": [{"email": "me@t", "self": True}, {"email": "a@t", "displayName": "Ann"}],
    }
    item = google_event_item("primary", ev, {"me@t"})
    assert item.direction == "own" and item.attendees == ["Ann"]
    assert "meet/x" in item.detail and item.starts_at.tzinfo is not None
    declined = {**ev, "attendees": [{"email": "me@t", "self": True, "responseStatus": "declined"}]}
    assert google_event_item("primary", declined, {"me@t"}) is None


# ── OAuth ────────────────────────────────────────────────────


async def test_oauth_flow_with_pkce(secret_dir):
    secrets.write_google_client({"installed": {"client_id": "cid", "client_secret": "cs"}})
    url = google_oauth.start("raja", "acc-9", "email", "me@gmail.com")
    assert (
        "gmail.readonly" in url
        and "code_challenge_method=S256" in url
        and "access_type=offline" in url
    )
    state = url.split("state=")[1].split("&")[0]
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(x.split("=", 1) for x in request.content.decode().split("&")))
        return httpx.Response(
            200,
            json={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/gmail.readonly",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        tenant, account = await google_oauth.finish(state, "code-1", http=http)
    assert (tenant, account) == ("raja", "acc-9")
    assert seen["code_verifier"] and seen["grant_type"] == "authorization_code"
    assert secrets.read_secret("raja", "acc-9")["refresh_token"] == "rt"
    with pytest.raises(ConnectorError, match="expired or already used"):
        await google_oauth.finish(state, "code-1")


async def test_revoked_refresh_token_means_reconnect(secret_dir):
    secrets.write_google_client({"installed": {"client_id": "cid", "client_secret": "cs"}})
    google_oauth.forget("acc-x")
    row = SimpleNamespace(id="acc-x")

    def handler(request):
        return httpx.Response(400, json={"error": "invalid_grant"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ReauthRequiredError):
            await google_oauth.access_token(row, {"refresh_token": "old"}, http=http)


# ── brief + chat intent ──────────────────────────────────────


def test_brief_render_off_machine(monkeypatch):
    from life_graph.connectors.brief import render

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    raw = {
        "today": [
            _event(),
            _event(id="e2", title="Call", starts_at=NOW + timedelta(minutes=30)),
            _event(
                id="e3",
                account_name="Work",
                account_exposure=EXPOSURE_LOCAL_ONLY,
                title="Board prep",
            ),
        ],
        "tomorrow_early": [],
        "waiting": [_mail(occurred_at=NOW - timedelta(days=2))],
    }
    ext = render(raw, CLOUD, NOW)["text"]
    assert "## Today" in ext and "overlaps" in ext and "+1 event in Work" in ext
    assert "Board prep" not in ext and "4111" not in ext
    assert "## Waiting on you (1)" in ext and "2d · Priya: Contract" in ext
    assert "Board prep" in render(raw, LOCAL, NOW)["text"]


@pytest.mark.parametrize(
    ("msg", "want"),
    [
        ("what's on my calendar today?", (True, False)),
        ("did priya reply to my email?", (False, True)),
        ("write a poem about rain", (False, False)),
    ],
)
def test_chat_intent(msg, want):
    from life_graph.connectors.chat_context import wants_context

    assert wants_context(msg) == want


def test_recommendation():
    from life_graph.api.connectors import recommend

    assert recommend("me@gmail.com", None)["auth_method"] == "app_password"
    assert recommend("me@corp.test", True)["auth_method"] == "oauth"
    work = recommend("me@corp.test", False)
    assert work["auth_method"] == "app_password" and work["exposure"] == "local_only"


# ── phase 4: promises ────────────────────────────────────────


async def test_promise_due_date_is_computed_not_guessed(monkeypatch):
    from life_graph.connectors.summarize import summarize_email

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    reply = json.dumps(
        {
            "summary": "Raja will send the contract",
            "category": "work",
            "asks_me": False,
            "suspicious": False,
            "commitment": "Send the signed contract to Priya",
            "commitment_when": "by Friday",
        }
    )
    wednesday = datetime(2026, 9, 16, 6, 0, tzinfo=UTC)
    out = await summarize_email(
        subject="Re: Contract",
        sender="Raja",
        text="I'll send it by Friday",
        automated=False,
        sent=True,
        sent_at=wednesday,
        client=_FakeLLM(reply),
    )
    assert out.commitment == "Send the signed contract to Priya"
    assert out.commitment_due.isoformat() == "2026-09-18"
    inbound = await summarize_email(
        subject="Re: Contract",
        sender="Priya",
        text="I'll send it",
        automated=False,
        sent=False,
        sent_at=wednesday,
        client=_FakeLLM(reply),
    )
    assert inbound.commitment is None  # only the user's own promises count


def test_brief_promises_section(monkeypatch):
    from life_graph.connectors.brief import render

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    promise = _mail(
        id="p1",
        direction="sent",
        title="Re: Contract",
        flags={"commitment": "Send the deck", "commitment_due": "2026-09-18"},
    )
    sensitive = _mail(
        id="p2",
        direction="sent",
        title="Re: KYC",
        category="sensitive",
        flags={"commitment": "Send PAN copy", "commitment_due": "2026-09-19"},
    )
    raw = {"today": [], "tomorrow_early": [], "waiting": [], "promises": [promise, sensitive]}
    ext = render(raw, CLOUD, NOW)["text"]
    assert "## You promised (2)" in ext
    assert "Send the deck — overdue (re: Contract)" in ext
    assert "PAN" not in ext and "A promise in a sensitive email" in ext
