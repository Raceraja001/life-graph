"""Batch and stale approval decisions land in audit_log, on Postgres.

Only ApprovalService.resolve wrote an ``approval_decision`` row; a batch
resolve and the stale sweep wrote none. These tests go through the real
services and read the rows back from the table the audit API reads.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"test_approval_audit_rows_{uuid.uuid4().hex[:8]}"


async def _seed(created_at: datetime | None = None) -> str:
    """One pending queue entry with no feed copy and no action. Returns its id."""
    from life_graph.autonomy.models import ApprovalQueueEntry
    from life_graph.storage.database import async_session

    async with async_session() as s:
        entry = ApprovalQueueEntry(
            tenant_id=TENANT,
            agent_id="ops",
            action_name=f"noop_{uuid.uuid4().hex[:8]}",
            action_command="true",
            risk_level="moderate",
            category="pipeline",
            trigger_type="manual",
            trigger_detail="audit rows test",
            status="pending",
            **({"created_at": created_at} if created_at else {}),
        )
        s.add(entry)
        await s.commit()
        return str(entry.id)


async def _audit_rows(approval_id: str) -> list:
    from life_graph.autonomy.models import AuditLogEntry
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return (
            (
                await s.execute(
                    select(AuditLogEntry).where(
                        AuditLogEntry.tenant_id == TENANT, AuditLogEntry.approval_id == approval_id
                    )
                )
            )
            .scalars()
            .all()
        )


def _queue():
    from life_graph.runtime import get_approval_service

    return get_approval_service()


@skip_on_db_error
async def test_a_batch_reject_leaves_an_audit_row_per_entry():
    ids = [await _seed(), await _seed()]

    out = await _queue().batch_resolve(TENANT, {"approval_ids": ids}, "reject", "no", "owner")

    assert sorted(out["resolved_ids"]) == sorted(ids)
    for entry_id in ids:
        (row,) = await _audit_rows(entry_id)
        assert (row.action_type, row.result) == ("approval_decision", "rejected")
        assert row.classification_reasoning["resolved_by"] == "owner"


@skip_on_db_error
async def test_the_stale_sweep_leaves_an_expired_audit_row():
    entry_id = await _seed(created_at=datetime.now(UTC) - timedelta(days=30))

    assert await _queue().expire_stale(14) >= 1

    (row,) = await _audit_rows(entry_id)
    assert (row.action_type, row.result) == ("approval_decision", "expired")
    assert row.classification_reasoning["resolved_by"] == "system"
