"""ADR M8 §5.2 step 5 against Postgres: the world-change end, its undo on
both undo paths, and the low tier's daily cap (services/memory/supersession.py).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.config import settings
from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = f"suptier_{uuid.uuid4().hex[:8]}"
OTHER = f"suptieo_{uuid.uuid4().hex[:8]}"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "supersession-tiers-user"}
JAN = datetime(2026, 1, 1, tzinfo=UTC)
MARCH = datetime(2026, 3, 1, tzinfo=UTC)


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=HEADERS) as c:
        yield c


async def _seed(content: str, *, status="active", tenant=TENANT, **cols) -> str:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
            importance=0.6,
            tags=["test"],
            status=status,
            trust_tier="self",
            source_type="test",
            **cols,
        )
        s.add(m)
        await s.commit()
        return str(m.id)


async def _memory(mem_id: str):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, uuid.UUID(mem_id))


async def _approval(old_id: str, new_id: str, *, applied: bool, **extra) -> str:
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as s:
        ap = Approval(
            tenant_id=TENANT,
            kind="contradiction",
            source="judgment",
            source_ref=f"{old_id}|{new_id}",
            title="Review a contradiction",
            detail="test",
            status="pending",
            payload={
                "memory_id_old": old_id,
                "memory_id_new": new_id,
                "applied": applied,
                **extra,
            },
        )
        s.add(ap)
        await s.commit()
        return str(ap.id)


async def _moved_pair() -> tuple[str, str]:
    """An old city since January, a new one since March (a world change)."""
    uniq = uuid.uuid4().hex[:6]
    old_id = await _seed(f"tierx lives in Chennai {uniq}", valid_from=JAN, created_at=JAN)
    new_id = await _seed(
        f"tierx lives in Coimbatore {uniq}",
        valid_from=MARCH,
        properties={"world_time": {"precision": "month", "rule": "since", "source": "content"}},
    )
    return old_id, new_id


@skip_on_db_error
async def test_high_tier_world_end_and_the_approvals_undo(client: AsyncClient):
    from life_graph.core.memory_manager import MemoryManager
    from life_graph.core.tenant import tenant_scope
    from life_graph.storage.postgres import PostgresMemoryStore

    old_id, new_id = await _moved_pair()
    mgr = MemoryManager(
        store=PostgresMemoryStore(), extractor=None, tagger=None, contradiction_detector=None
    )
    with tenant_scope(TENANT):
        await mgr.supersede(old_id, new_id, "test", world_change=True)
    old = await _memory(old_id)
    assert old.status == "superseded"
    assert old.valid_until == MARCH
    assert old.properties["valid_until_by"] == "supersession"

    # One tap undoes it: the approvals undo (one pair) clears the end too.
    ap_id = await _approval(old_id, new_id, applied=True, confidence="high")
    resp = await client.post(f"/api/v1/approvals/{ap_id}/reject")
    assert resp.status_code == 200, resp.text
    old, new = await _memory(old_id), await _memory(new_id)
    assert old.status == "active" and old.valid_until is None
    assert "valid_until_by" not in (old.properties or {})
    assert new.supersedes is None


@skip_on_db_error
async def test_a_correction_gets_no_world_end():
    from life_graph.core.memory_manager import MemoryManager
    from life_graph.core.tenant import tenant_scope
    from life_graph.storage.postgres import PostgresMemoryStore

    old_id = await _seed("tierx lives in Adyar", valid_from=JAN, created_at=JAN)
    new_id = await _seed(
        "tierx lives in Anna Nagar",
        valid_from=MARCH,
        properties={"correction": True, "world_time": {"rule": "since"}},
    )
    mgr = MemoryManager(
        store=PostgresMemoryStore(), extractor=None, tagger=None, contradiction_detector=None
    )
    with tenant_scope(TENANT):
        await mgr.supersede(old_id, new_id, "test", world_change=True)
    old = await _memory(old_id)
    assert old.status == "superseded" and old.valid_until is None


@skip_on_db_error
async def test_the_owners_keep_ends_the_old_fact_only_with_the_flag(
    client: AsyncClient, monkeypatch
):
    old_id, new_id = await _moved_pair()
    ap_id = await _approval(old_id, new_id, applied=False, confidence="medium")
    monkeypatch.setattr(settings, "ingest_supersession_tiers", False)
    resp = await client.post(f"/api/v1/approvals/{ap_id}/approve")
    assert resp.status_code == 200, resp.text
    old = await _memory(old_id)
    assert old.status == "superseded" and old.valid_until is None  # today's behaviour

    old_id, new_id = await _moved_pair()
    ap_id = await _approval(old_id, new_id, applied=False, confidence="medium")
    monkeypatch.setattr(settings, "ingest_supersession_tiers", True)
    resp = await client.post(f"/api/v1/approvals/{ap_id}/approve")
    assert resp.status_code == 200, resp.text
    old = await _memory(old_id)
    assert old.status == "superseded" and old.valid_until == MARCH


@skip_on_db_error
async def test_restore_replaced_by_clears_only_its_own_valid_until():
    from life_graph.services.memory import supersession
    from life_graph.storage.database import async_session

    new_id = await _seed("tierx the saved one")
    ours = await _seed(
        "tierx ended by supersession",
        status="superseded",
        superseded_by=uuid.UUID(new_id),
        valid_until=MARCH,
        properties={"valid_until_by": "supersession", "superseded_at": "x"},
    )
    owners = await _seed(
        "tierx ended by the owner's deny",
        status="superseded",
        superseded_by=uuid.UUID(new_id),
        valid_until=MARCH,
        properties={"superseded_at": "x"},
    )
    async with async_session() as s:
        await supersession.restore_replaced_by(s, TENANT, uuid.UUID(new_id))
        await s.commit()

    a, b = await _memory(ours), await _memory(owners)
    assert a.status == "active" and a.valid_until is None and a.properties == {}
    assert b.status == "active" and b.valid_until == MARCH and b.properties == {}


@skip_on_db_error
async def test_low_tier_is_capped_per_tenant_per_day():
    from sqlalchemy import select

    from life_graph.models.db import Approval
    from life_graph.services.memory import supersession
    from life_graph.storage.database import async_session

    new_id = str(uuid.uuid4())
    queued = [
        await supersession.file_possible_update(TENANT, str(uuid.uuid4()), new_id, "why")
        for _ in range(supersession.LOW_TIER_DAILY_CAP + 2)
    ]
    # Another tenant's items never count against this one.
    assert await supersession.file_possible_update(OTHER, str(uuid.uuid4()), new_id, "why")

    assert queued == [True] * supersession.LOW_TIER_DAILY_CAP + [False, False]
    async with async_session() as s:
        rows = (
            (
                await s.execute(
                    select(Approval).where(
                        Approval.tenant_id == TENANT,
                        Approval.payload["confidence"].astext == "low",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == supersession.LOW_TIER_DAILY_CAP
    assert all(r.payload["applied"] is False for r in rows)
    assert all(r.title == "Possible update to review" for r in rows)
    assert sum(int(r.payload.get("not_queued", 0)) for r in rows) == 2


@skip_on_db_error
async def test_keeping_the_new_memory_never_applies_a_low_item(client: AsyncClient):
    old_id = await _seed("tierx Anu's school is Chettinad Vidyashram")
    new_id = await _seed("tierx Anu's school is Vidya Mandir", status="pending")
    await _approval(old_id, new_id, applied=False, confidence="low")

    resp = await client.post(f"/api/v1/memories/{new_id}/approve")
    assert resp.status_code == 200, resp.text

    assert (await _memory(old_id)).status == "active"
    assert (await _memory(new_id)).status == "active"
