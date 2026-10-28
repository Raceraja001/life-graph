# tests for sweep_reminders
import uuid
from datetime import date, timedelta

import pytest

from life_graph.services.documents import (
    EXPIRED,
    Document,
    sweep_reminders,
)


# Dummy session factory and session
class DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def commit(self):
        pass


def dummy_session_factory():
    return DummySession()


# Dummy notifications object
class DummyNotifications:
    def __init__(self):
        self.calls = []

    async def create(
        self, tenant_id, title, body, priority, source_type, source_id, metadata, deliver_at_brief
    ):
        self.calls.append(
            {
                "tenant_id": tenant_id,
                "title": title,
                "body": body,
                "priority": priority,
                "source_type": source_type,
                "source_id": source_id,
                "metadata": metadata,
                "deliver_at_brief": deliver_at_brief,
            }
        )


# Helper to create a document


def make_doc(expires_on, reminders_sent=None):
    return Document(
        id=uuid.uuid4(),
        tenant_id="tenant1",
        title="Test Doc",
        kind="other",
        issuer=None,
        number_last4=None,
        holder=None,
        issued_on=None,
        expires_on=expires_on,
        notes=None,
        source="api",
        reminders_sent=reminders_sent or [],
        properties={},
    )


# Patch expiring to return our docs
async def expiring_stub(session, tenant_id, today, within_days):
    return docs


@pytest.mark.asyncio
async def test_no_thresholds():
    today = date.today()
    doc = make_doc(today + timedelta(days=90))  # days > 60, no threshold
    global docs
    docs = [doc]
    notifications = DummyNotifications()
    # Patch expiring
    import life_graph.services.documents as documents

    documents.expiring = expiring_stub
    sent = await sweep_reminders(dummy_session_factory, "tenant1", today, notifications)
    assert sent == 0
    assert len(notifications.calls) == 0


@pytest.mark.asyncio
async def test_threshold_already_sent():
    today = date.today()
    doc = make_doc(today + timedelta(days=45), reminders_sent=[str(60)])
    global docs
    docs = [doc]
    notifications = DummyNotifications()
    import life_graph.services.documents as documents

    documents.expiring = expiring_stub
    sent = await sweep_reminders(dummy_session_factory, "tenant1", today, notifications)
    assert sent == 0
    assert len(notifications.calls) == 0


@pytest.mark.asyncio
async def test_expired_document():
    today = date.today()
    doc = make_doc(today - timedelta(days=1), reminders_sent=[])
    global docs
    docs = [doc]
    notifications = DummyNotifications()
    import life_graph.services.documents as documents

    documents.expiring = expiring_stub
    sent = await sweep_reminders(dummy_session_factory, "tenant1", today, notifications)
    assert sent == 1
    call = notifications.calls[0]
    assert call["title"].startswith("Test Doc expired")
    assert call["priority"] == "important"
    assert call["deliver_at_brief"] is False
    # All thresholds should now be recorded
    assert set(doc.reminders_sent) == set(["60", "30", "7", "1", EXPIRED])


@pytest.mark.asyncio
async def test_near_threshold():
    today = date.today()
    doc = make_doc(today + timedelta(days=5), reminders_sent=[])
    global docs
    docs = [doc]
    notifications = DummyNotifications()
    import life_graph.services.documents as documents

    documents.expiring = expiring_stub
    sent = await sweep_reminders(dummy_session_factory, "tenant1", today, notifications)
    assert sent == 1
    call = notifications.calls[0]
    assert call["priority"] == "important"
    assert call["deliver_at_brief"] is False
    assert set(doc.reminders_sent) == {"7", "60", "30"}


@pytest.mark.asyncio
async def test_far_threshold():
    today = date.today()
    doc = make_doc(today + timedelta(days=45), reminders_sent=[])
    global docs
    docs = [doc]
    notifications = DummyNotifications()
    import life_graph.services.documents as documents

    documents.expiring = expiring_stub
    sent = await sweep_reminders(dummy_session_factory, "tenant1", today, notifications)
    assert sent == 1
    call = notifications.calls[0]
    assert call["priority"] == "info"
    assert call["deliver_at_brief"] is True
    assert set(doc.reminders_sent) == {"60"}


@pytest.mark.asyncio
async def test_no_expiry():
    today = date.today()
    doc = make_doc(expires_on=None)
    global docs
    docs = [doc]
    notifications = DummyNotifications()
    import life_graph.services.documents as documents

    documents.expiring = expiring_stub
    sent = await sweep_reminders(dummy_session_factory, "tenant1", today, notifications)
    assert sent == 0
    assert len(notifications.calls) == 0
