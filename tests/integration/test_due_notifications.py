"""Due items as phone notifications, against the database
(services/due_notifications.py).

A bill from mail, a to-do, a document and a timed reminder are seeded for one
tenant; a run writes one notification each, a second run at the same time
writes nothing, and the next morning only the new lead times are written.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"due_{uuid.uuid4().hex[:8]}"
DAY = date(2026, 10, 21)


def _at(day: date, hour: int) -> datetime:
    from life_graph.connectors.tools import user_tz

    return datetime.combine(day, time(hour), tzinfo=user_tz()).astimezone(UTC)


async def _seed(now: datetime) -> uuid.UUID:
    from life_graph.connectors.models import ConnectorAccount, ConnectorItem
    from life_graph.models.assistant import Document
    from life_graph.models.db import Intention
    from life_graph.storage.database import async_session

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
        s.add(
            ConnectorItem(
                tenant_id=TENANT,
                account_id=mail.id,
                kind="email",
                external_id="bill-1",
                direction="inbound",
                title="Your electricity bill",
                trust_tier="external",
                occurred_at=now - timedelta(days=5),
                flags={
                    "bill": {
                        "kind": "bill",
                        "payee": "TNEB",
                        "amount": 1240.0,
                        "currency": "INR",
                        "due": (DAY + timedelta(days=1)).isoformat(),
                        "autopay": False,
                        "state": "open",
                    }
                },
            )
        )
        s.add(
            ConnectorItem(
                tenant_id=TENANT,
                account_id=tasks.id,
                kind="task",
                external_id="list:task-1",
                direction="own",
                title="File GST return",
                trust_tier="self",
                occurred_at=now - timedelta(days=2),
                flags={"status": "needsAction", "due": DAY.isoformat(), "list": "Work"},
            )
        )
        doc = Document(
            tenant_id=TENANT,
            kind="insurance",
            title="Car insurance",
            expires_on=DAY + timedelta(days=7),
            reminders_sent=[],
        )
        s.add(doc)
        s.add(
            Intention(
                tenant_id=TENANT,
                content="Call the bank about the card",
                trigger_type="time",
                trigger_time=now - timedelta(minutes=10),
                priority="normal",
                status="pending",
            )
        )
        await s.commit()
        return doc.id


async def _rows():
    from sqlalchemy import select

    from life_graph.models.db import Notification
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return list(
            (
                await s.execute(
                    select(Notification).where(
                        Notification.tenant_id == TENANT,
                        Notification.source_type == "due_item",
                    )
                )
            )
            .scalars()
            .all()
        )


@pytest.mark.asyncio
@skip_on_db_error
async def test_due_items_are_written_once_per_lead_time():
    from life_graph.models.assistant import Document
    from life_graph.services import due_notifications
    from life_graph.storage.database import async_session

    evening = _at(DAY, 19)
    doc_id = await _seed(evening)

    written = await due_notifications.run_for_tenant(TENANT, evening)
    assert sorted(k.split(":")[0] for k in written) == ["bill", "document", "reminder", "task"]
    rows = {r.extra_metadata["item"]: r for r in await _rows()}
    assert rows["bill"].title == "TNEB bill due tomorrow"
    assert rows["bill"].body == "₹1,240 to TNEB."
    assert rows["bill"].priority == "info"
    assert rows["task"].title == "Due today: File GST return"
    assert rows["task"].priority == "important"
    assert rows["document"].title == "Car insurance expires in 7 days"
    assert rows["reminder"].title == "Call the bank about the card"
    assert all(r.is_delivered for r in rows.values())  # kept out of the next brief

    # Re-runs never duplicate.
    assert await due_notifications.run_for_tenant(TENANT, evening) == []
    assert await due_notifications.run_for_tenant(TENANT, evening + timedelta(minutes=15)) == []
    assert len(await _rows()) == 4

    # The daily sweep's ledger knows the 7-day notice went out.
    async with async_session() as s:
        assert "7" in (await s.get(Document, doc_id)).reminders_sent

    # Next morning: the bill is due today and the to-do overdue; nothing else.
    morning = _at(DAY + timedelta(days=1), 9)
    written = await due_notifications.run_for_tenant(TENANT, morning)
    assert sorted(f"{k.split(':')[0]}:{k.rsplit(':', 1)[1]}" for k in written) == [
        "bill:today",
        "task:overdue",
    ]
    assert f"bill:tneb:{(DAY + timedelta(days=1)).isoformat()}:today" in written
    assert await due_notifications.run_for_tenant(TENANT, morning) == []
    assert len(await _rows()) == 6

    # Another tenant sees none of it.
    assert await due_notifications.run_for_tenant(f"{TENANT}_other", morning) == []
