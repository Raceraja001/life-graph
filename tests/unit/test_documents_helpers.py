import re
from datetime import UTC, date, datetime

from life_graph.services.documents import (
    EXPIRED,
    date_after_keyword,
    reminder_text,
)


# Helper to create a simple Document-like object
class DummyDoc:
    def __init__(self, title: str, expires_on: date):
        self.title = title
        self.expires_on = expires_on


# ---------- date_after_keyword tests ----------


def test_date_after_keyword_found():
    text = "The expiry date is 2024-12-31. Please renew soon."
    pattern = re.compile(r"expiry date", re.I)
    now = datetime(2024, 1, 1, tzinfo=UTC)
    result = date_after_keyword(text, pattern, now)
    assert result == date(2024, 12, 31)


def test_date_after_keyword_no_keyword():
    text = "No dates mentioned here."
    pattern = re.compile(r"expiry date", re.I)
    now = datetime(2024, 1, 1, tzinfo=UTC)
    result = date_after_keyword(text, pattern, now)
    assert result is None


def test_date_after_keyword_no_date_within_window():
    text = "The expiry date will be announced soon."
    pattern = re.compile(r"expiry date", re.I)
    now = datetime(2024, 1, 1, tzinfo=UTC)
    result = date_after_keyword(text, pattern, now)
    assert result is None


def test_date_after_keyword_multiple_keywords():
    text = "Expiry date: 2024-12-31. Renewal date: 2025-01-15."
    pattern = re.compile(r"expiry date|renewal date", re.I)
    now = datetime(2024, 1, 1, tzinfo=UTC)
    result = date_after_keyword(text, pattern, now)
    # Should pick the first date after the first matched keyword
    assert result == date(2024, 12, 31)


# ---------- reminder_text tests ----------


def test_reminder_text_normal():
    today = date(2024, 12, 20)
    expires = date(2024, 12, 31)
    doc = DummyDoc("Test Document", expires)
    title, body = reminder_text(doc, today, key="")
    assert title == "Test Document expires in 11 days (31 Dec 2024)"
    assert body == "Start the renewal now if it needs an appointment or paperwork."


def test_reminder_text_single_day():
    today = date(2024, 12, 30)
    expires = date(2024, 12, 31)
    doc = DummyDoc("Test Document", expires)
    title, body = reminder_text(doc, today, key="")
    assert title == "Test Document expires in 1 day (31 Dec 2024)"


def test_reminder_text_expired():
    today = date(2025, 1, 2)
    expires = date(2025, 1, 1)
    doc = DummyDoc("Expired Doc", expires)
    title, body = reminder_text(doc, today, key=EXPIRED)
    assert title == "Expired Doc expired on 01 Jan 2025"
    assert body == "Renew or replace it, then update the expiry date."
