"""scripts/shadow_context_structure.py against a real Postgres (ADR M8 ingestion §6.2).

Seeds two tenants with shadow traces, memories, typed links, decisions and
contradiction approvals, then runs the script's queries inside its read-only
transaction: tenant A's counts are exact, tenant B's rows never count, no
ref or content string reaches the output, and a write in that transaction
is refused.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, text

from life_graph.models.db import AgentTask, Approval, Decision, Memory, MemoryLink
from life_graph.storage.database import async_session, engine
from scripts import shadow_context_structure as scs
from tests.integration.conftest import skip_on_db_error

NOW = datetime.now(UTC)
SINCE = NOW - timedelta(days=7)
SECRET = "Anu moved to Coimbatore"


def _tenant(tag: str) -> str:
    return f"shadowcs_{tag}_{uuid.uuid4().hex[:8]}"


def _mem(tenant: str, content: str, *, days_ago: float = 1, **kw) -> Memory:
    when = NOW - timedelta(days=days_ago)
    return Memory(
        id=uuid.uuid4(),
        tenant_id=tenant,
        content=content,
        content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
        importance=0.7,
        confidence=0.9,
        status=kw.pop("status", "active"),
        trust_tier="self",
        source_type="chat",
        properties=kw.pop("properties", {}),
        created_at=when,
        updated_at=when,
        valid_from=when,
        **kw,
    )


def _trace(mem_ids: list[uuid.UUID], dec_id: uuid.UUID) -> dict:
    items = [
        {
            "ref": f"memory:{m}",
            "dimension": "facts",
            "origin": "owner_said",
            "confirmed": True,
            "evidence": "direct",
            "status": "active",
            "reason": "matched",
            "freshness": "fresh",
            "world_time_known": i == 0,
            "fp": "deadbeefcafe0123",
            "rec": NOW.isoformat(),
            "due": None,
        }
        for i, m in enumerate(mem_ids)
    ]
    items.append(
        {
            **items[0],
            "ref": f"decision:{dec_id}",
            "status": "candidate",
            "confirmed": False,
            "world_time_known": False,
        }
    )
    return {
        "context_snapshot": {
            "v": 2,
            "reference_time": NOW.isoformat(),
            "sources": ["memories"],
            "items": items,
            "conflicts": [
                {
                    "kind": "pending_contradiction",
                    "refs": [items[0]["ref"], items[1]["ref"]],
                    "statuses": ["active"],
                    "approval": None,
                }
            ],
            "relations": [
                {
                    "from": f"memory:{mem_ids[0]}",
                    "to": f"memory:{mem_ids[1]}",
                    "type": "BECAUSE",
                    "strength": 0.9,
                }
            ],
            "exclusions": {},
            "insufficient": False,
            "abstain": False,
            "abstention_reason": None,
            "timings_ms": {"embed": 12.0, "retrieve": 40.0, "total": 80.0},
            "ms": 85,
        },
        "context_changes": {
            "window": {"from": None, "to": NOW.isoformat()},
            "baseline": {"task": str(uuid.uuid4())},
            "changes": [
                {
                    "kind": "added",
                    "ref": f"memory:{mem_ids[1]}",
                    "acknowledged": False,
                    "reason": SECRET,
                }
            ],
            "suppressed": {"duplicate": 2},
            "insufficient": False,
            "explanation": SECRET,
            "read_failed": False,
            "ms": 15,
        },
    }


async def _seed(tenant: str) -> list[uuid.UUID]:
    a = _mem(
        tenant,
        SECRET,
        properties={"world_time": {"precision": "month", "rule": "x", "source": "content"}},
    )
    b = _mem(tenant, "school changed", properties={"valid_until_by": "supersession"})
    old = _mem(tenant, "old fact", days_ago=30)
    dec = Decision(id=uuid.uuid4(), tenant_id=tenant, title=SECRET, status="candidate")
    async with async_session() as s:
        for row in (a, b, old, dec):
            s.add(row)
            await s.flush()
        s.add(
            MemoryLink(
                id=uuid.uuid4(),
                tenant_id=tenant,
                source_memory_id=a.id,
                target_memory_id=b.id,
                link_type="BECAUSE",
                strength=0.9,
                properties={"why": "extraction:because"},
            )
        )
        s.add(
            MemoryLink(
                id=uuid.uuid4(),
                tenant_id=tenant,
                source_memory_id=a.id,
                target_memory_id=b.id,
                link_type="ASSOCIATED",
                strength=0.5,
                properties={},
            )
        )
        s.add(
            Approval(
                tenant_id=tenant,
                kind="contradiction",
                source="judgment",
                source_ref=f"{a.id}|{b.id}",
                title=SECRET,
                payload={"applied": False, "confidence": "low", "not_queued": 2},
            )
        )
        s.add(
            AgentTask(
                id=uuid.uuid4(),
                tenant_id=tenant,
                agent_name="jarvis",
                status="completed",
                input={"message": SECRET},
                result={"response": SECRET, "trace": _trace([a.id, b.id], dec.id)},
                created_at=NOW - timedelta(hours=2),
            )
        )
        # Before --since: never counted.
        s.add(
            AgentTask(
                id=uuid.uuid4(),
                tenant_id=tenant,
                agent_name="jarvis",
                status="completed",
                input={"message": "x"},
                result={"response": "x", "trace": _trace([a.id, b.id], dec.id)},
                created_at=NOW - timedelta(days=20),
            )
        )
        await s.commit()
    return [a.id, b.id]


async def _cleanup(*tenants: str) -> None:
    async with async_session() as s:
        for t in tenants:
            await s.execute(text("DELETE FROM life_graph.decisions WHERE tenant_id = :t"), {"t": t})
            for model in (AgentTask, Approval, MemoryLink, Memory):
                await s.execute(delete(model).where(model.tenant_id == t))
        await s.commit()


@pytest.mark.asyncio
@skip_on_db_error
async def test_counts_are_tenant_scoped_and_label_only():
    ta, tb = _tenant("a"), _tenant("b")
    try:
        refs = await _seed(ta)
        await _seed(tb)
        async with scs.read_only(engine) as conn:
            raw = await scs.collect(conn, ta, SINCE)
        s = scs.summarise(raw, tenant=ta, since=SINCE)

        sn, ch, ing = s["snapshot"], s["changes"], s["ingestion"]
        assert sn["turns_with_snapshot"] == 1  # the 20-day-old turn and tenant B's are out
        assert sn["memory_items"] == 2
        assert sn["world_time_known"] == 1
        assert sn["world_time_known_share"] == 0.5
        assert sn["items_by_kind"] == {
            "decision": {"n": 1, "world_time_known": 0},
            "memory": {"n": 2, "world_time_known": 1},
        }
        assert sn["relation_types"] == {"BECAUSE": 1}
        assert sn["conflict_kinds"] == {"pending_contradiction": 1}
        assert sn["decision_items"] == {"candidate": {"n": 1, "confirmed": 0}}
        assert sn["ms"]["p50"] == 85.0
        assert sn["timings_ms"]["retrieve"]["p50"] == 40.0
        assert ch["turns_compared"] == 1
        assert ch["baseline_found_rate"] == 1.0
        assert ch["kinds"] == {"added": {"n": 1, "acknowledged": 0}}
        assert ch["suppressed"] == {"duplicate": 2}
        assert ing["memories_created"] == 2  # the 30-day-old memory is out
        assert ing["with_world_time"] == 1
        assert ing["world_time_precision"] == {"month": 1}
        assert ing["valid_until_by_supersession"] == 1
        assert ing["typed_links_by_type"] == {"BECAUSE": 1}
        assert ing["decisions_by_status"] == {"candidate": {"n": 1, "created_since": 1}}
        assert ing["pending_contradictions_by_confidence"] == {
            "low": {"pending": 1, "applied": 0, "created_since": 1, "not_queued": 2}
        }

        out = json.dumps(s, default=str) + scs.render(s)
        for leak in (SECRET, "deadbeef", tb, *(str(r) for r in refs)):
            assert leak not in out
    finally:
        await _cleanup(ta, tb)


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_transaction_is_read_only():
    async with scs.read_only(engine) as conn:
        assert (await conn.execute(text("SHOW transaction_read_only"))).scalar() == "on"
        with pytest.raises(Exception, match="read-only"):
            await conn.execute(text("DELETE FROM agent_tasks WHERE tenant_id = 'nobody'"))
