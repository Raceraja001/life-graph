"""Bills & renewals from mail (docs/specs/bills-from-mail.md): the deterministic
parsing, payee matching, what leaves the machine, the brief lines, and the
summariser wiring (with a fake local model)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from life_graph.config import settings
from life_graph.connectors import bills
from life_graph.connectors.exposure import EXPOSURE_LOCAL_ONLY, view_bills
from life_graph.connectors.locality import CLOUD, LOCAL

RECEIVED = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("words", "want"),
    [
        ("Due Date: 25-09-2026", date(2026, 9, 25)),
        ("05/10/2026", date(2026, 10, 5)),  # day first
        ("05.10.26", date(2026, 10, 5)),
        ("2026-10-03", date(2026, 10, 3)),
        ("25 Sep 2026", date(2026, 9, 25)),
        ("25th September", date(2026, 9, 25)),
        ("Sep 25, 2026", date(2026, 9, 25)),
        ("renews on 3 Oct", date(2026, 10, 3)),
        ("was due on 17 Sep", date(2026, 9, 17)),  # an overdue reminder stays in the past
        ("15 Jan", date(2027, 1, 15)),  # far enough back → next year
        ("", None),
        ("soon", None),
        ("31-02-2026", None),
    ],
)
def test_parse_due(words, want):
    assert bills.parse_due(words, RECEIVED) == want


@pytest.mark.parametrize(
    ("words", "want"),
    [
        ("Rs. 2,345.00", (2345.0, "INR")),
        ("₹1,23,456", (123456.0, "INR")),
        ("INR 499", (499.0, "INR")),
        ("$12.99", (12.99, "USD")),
        ("1,299", (1299.0, "INR")),
        ("", (None, None)),
        ("nil", (None, None)),
    ],
)
def test_parse_amount(words, want):
    assert bills.parse_amount(words) == want


def test_payee_matching():
    assert bills.same_payee("HDFC credit card", "HDFC Bank")
    assert bills.same_payee("BESCOM electricity", "Bescom")
    assert not bills.same_payee("HDFC credit card", "ICICI credit card")
    assert not bills.same_payee("Electricity bill", "Electricity")  # only generic words
    assert bills.payee_key("example.com domain") == frozenset({"example.com"})


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("LIC of India policy no. [redacted]", "LIC of India"),
        ("HDFC card ending 4521", "HDFC"),
        ("BESCOM consumer 7654321098", "BESCOM"),
        ("HDFC credit card", "HDFC credit card"),  # "card" alone is part of the name
        ("Airtel broadband", "Airtel broadband"),
        ("  one two three four five six seven  ", "one two three four five six"),
    ],
)
def test_clean_payee(raw, want):
    assert bills.clean_payee(raw) == want


def test_from_fields():
    bill = bills.from_fields(
        kind="bill",
        payee="  BESCOM   electricity ",
        amount="Rs. 1,240.00",
        due="Due by 25-09-2026",
        autopay=False,
        received=RECEIVED,
    )
    assert bill == {
        "kind": "bill",
        "payee": "BESCOM electricity",
        "amount": 1240.0,
        "currency": "INR",
        "due": "2026-09-25",
        "autopay": False,
        "state": "open",
    }
    done = bills.from_fields(
        kind="payment_done", payee="BESCOM", amount="", due="", autopay=False, received=RECEIVED
    )
    assert done["state"] == "confirmation" and done["due"] is None
    assert (
        bills.from_fields(
            kind="none", payee="x", amount="", due="", autopay=False, received=RECEIVED
        )
        is None
    )
    assert (
        bills.from_fields(
            kind="bill", payee="", amount="", due="", autopay=False, received=RECEIVED
        )
        is None
    )


def test_rereading_keeps_what_the_user_did():
    new = {"kind": "bill", "payee": "x", "state": "open"}
    assert bills.merge_state(new, {"state": "paid"})["state"] == "paid"
    assert bills.merge_state(new, {"state": "open"})["state"] == "open"
    assert bills.merge_state(new, None) is new


# ── exposure + brief ─────────────────────────────────────────


def _row(id_, payee, due, kind="bill", amount=2345.0, autopay=False, **kw):
    return {
        "id": id_,
        "account_name": "Mail",
        "account_exposure": "standard",
        "title": f"Your {payee} statement",
        "bill": {
            "kind": kind,
            "payee": payee,
            "amount": amount,
            "currency": "INR",
            "due": due,
            "autopay": autopay,
            "state": "open",
        },
        **kw,
    }


ROWS = [
    _row("b1", "BESCOM electricity", "2026-09-17"),
    _row("b2", "HDFC credit card", "2026-09-26", amount=18250.5),
    _row("b3", "Airtel broadband", "2026-09-29", autopay=True, amount=999.0),
    _row("b4", "example.com domain", "2026-10-04", kind="renewal", amount=None),
]


def test_amounts_never_leave_the_machine(monkeypatch):
    monkeypatch.setattr(settings, "connector_bills_cloud", "details")
    cloud = view_bills(ROWS, CLOUD)
    assert len(cloud["items"]) == 4 and not cloud["withheld"]
    assert all("amount" not in b and "subject" not in b for b in cloud["items"])
    assert "18250" not in json.dumps(cloud)
    local = view_bills(ROWS, LOCAL)
    assert local["items"][1]["amount"] == 18250.5
    monkeypatch.setattr(settings, "connector_bills_cloud", "counts")
    assert view_bills(ROWS, CLOUD) == {"items": [], "withheld": {"Mail": 4}}
    monkeypatch.setattr(settings, "connector_bills_cloud", "details")
    hidden = view_bills(
        [_row("b9", "Payroll", "2026-09-26", account_exposure=EXPOSURE_LOCAL_ONLY)], CLOUD
    )
    assert hidden == {"items": [], "withheld": {"Mail": 1}}


def test_brief_bills_section(monkeypatch):
    from life_graph.connectors.brief import render

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(settings, "connector_bills_cloud", "details")
    raw = {"today": [], "tomorrow_early": [], "waiting": [], "promises": [], "bills": ROWS}
    text = render(raw, CLOUD, RECEIVED)["text"]
    assert "## Bills & renewals" in text
    assert "- Overdue: BESCOM electricity (due Thu 17 Sep)" in text
    assert "- HDFC credit card — due Sat 26 Sep" in text
    assert "- Airtel broadband — due Tue 29 Sep (autopay)" in text
    assert "- example.com domain — renews Sun 04 Oct" in text
    assert "₹" not in text and "18,250" not in text
    local = render(raw, LOCAL, RECEIVED)["text"]
    assert "- HDFC credit card — due Sat 26 Sep — ₹18,250.50" in local


# ── summariser wiring ────────────────────────────────────────


class _FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def chat_local_only(self, **kw):
        assert "bill_kind" in kw["response_format"]["json_schema"]["schema"]["properties"]
        return json.dumps(self.payload)


def _answer(**kw):
    base = {
        "summary": "Electricity bill.",
        "category": "transactional",
        "asks_me": False,
        "suspicious": False,
        "commitment": "",
        "commitment_when": "",
        "bill_kind": "bill",
        "bill_payee": "BESCOM electricity",
        "bill_amount": "Rs. 1,240.00",
        "bill_due": "25-09-2026",
        "bill_autopay": False,
    }
    return {**base, **kw}


async def test_summary_carries_the_bill(monkeypatch):
    from life_graph.connectors.summarize import summarize_email

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    s = await summarize_email(
        subject="Your BESCOM bill",
        sender="BESCOM",
        text="Amount due Rs. 1,240.00 by 25-09-2026",
        automated=True,
        sent_at=RECEIVED,
        client=_FakeLLM(_answer()),
    )
    assert s.bill["due"] == "2026-09-25" and s.bill["amount"] == 1240.0


async def test_phishing_and_sent_mail_are_never_bills():
    from life_graph.connectors.summarize import summarize_email

    scam = await summarize_email(
        subject="URGENT: electricity cut tonight",
        sender="bescom-alerts@evil.test",
        text="Pay now at http://evil.test or power is cut",
        automated=False,
        sent_at=RECEIVED,
        client=_FakeLLM(_answer(suspicious=True)),
    )
    assert scam.bill is None
    mine = await summarize_email(
        subject="Re: rent",
        sender="me",
        text="I paid the rent",
        automated=False,
        sent=True,
        sent_at=RECEIVED,
        client=_FakeLLM(_answer()),
    )
    assert mine.bill is None


@pytest.mark.parametrize(
    ("sender", "text", "scam"),
    [
        ("noreply@bescom.co.in", "Bill Amount Rs 1,240 due 25-09-2026", False),
        ("bescom-update@secure-billpay.xyz", "Your bill is pending", True),
        ("landlord.ramesh@gmail.com", "Rent for October: Rs 25,000 by 5th", False),
        ("noreply@bescom.co.in", "Pay now at http://bit.ly/bescom-pay", True),
        ("noreply@bescom.co.in", "Connection will be disconnected tonight at 9.30 pm", True),
        ("noreply@bescom.co.in", "Please call our electricity officer 98765", True),
        (None, "Your statement is ready", False),
    ],
)
def test_scam_signs(sender, text, scam):
    assert bills.looks_like_scam(sender, text) is scam


async def test_a_scam_bill_the_model_missed_is_dropped():
    """The local model did not flag this one in testing; the deterministic check does."""
    from life_graph.connectors.summarize import summarize_email

    s = await summarize_email(
        subject="URGENT: Electricity will be disconnected tonight",
        sender="BESCOM Update",
        sender_addr="bescom-update@secure-billpay.xyz",
        text="Your connection will be disconnected tonight. Pay Rs 500 at http://bit.ly/x",
        automated=False,
        sent_at=RECEIVED,
        client=_FakeLLM(_answer(suspicious=False)),
    )
    assert s.bill is None and s.suspicious is True and s.asks_me is False


def test_bill_intent():
    from life_graph.connectors.chat_context import wants_bills

    assert wants_bills("what bills are due this week?")
    assert wants_bills("when does my insurance renew")
    assert not wants_bills("write a poem about rain")
