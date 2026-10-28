"""Tests for the mail_row function in life_graph/services/jarvis_inbox.py."""

from datetime import UTC, datetime

from life_graph.services.jarvis_inbox import mail_row


def test_mail_row_all_fields_present():
    """Test mail_row when all fields are present in the input."""
    mail = {
        "id": "m-123",
        "sender_name": "John Doe",
        "sender_addr": "john@example.com",
        "subject": "Meeting tomorrow",
        "date": datetime(2026, 10, 25, 9, 42, tzinfo=UTC),
        "needs_reply": True,
    }

    result = mail_row(mail)

    assert result["id"] == "m-123"
    assert result["from"] == "John Doe"
    assert result["subject"] == "Meeting tomorrow"
    assert result["received_at"] == datetime(2026, 10, 25, 9, 42, tzinfo=UTC)
    assert result["needs_reply"] is True


def test_mail_row_missing_sender_name_and_addr():
    """Test mail_row when sender_name and sender_addr are missing."""
    mail = {
        "id": "m-456",
        "subject": "No sender info",
        "date": datetime(2026, 10, 25, 9, 42, tzinfo=UTC),
        "needs_reply": False,
    }

    result = mail_row(mail)

    assert result["id"] == "m-456"
    assert result["from"] == "Someone"  # default value
    assert result["subject"] == "No sender info"
    assert result["received_at"] == datetime(2026, 10, 25, 9, 42, tzinfo=UTC)
    assert result["needs_reply"] is False


def test_mail_row_missing_subject():
    """Test mail_row when subject is missing."""
    mail = {
        "id": "m-789",
        "sender_name": "Jane Smith",
        "date": datetime(2026, 10, 25, 9, 42, tzinfo=UTC),
        "needs_reply": True,
    }

    result = mail_row(mail)

    assert result["id"] == "m-789"
    assert result["from"] == "Jane Smith"
    assert result["subject"] == "(no subject)"  # default value
    assert result["received_at"] == datetime(2026, 10, 25, 9, 42, tzinfo=UTC)
    assert result["needs_reply"] is True
