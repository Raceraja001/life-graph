"""The decision lifecycle against a real Postgres (services/decision_lifecycle.py).

Owner moves write status, their timestamp and the trail; a supersede writes
``superseded_at`` (migration 063). With ``settings.decision_lifecycle`` on, a
capture links its decision to the decision memory of the same message, an
applied memory supersede supersedes the old memory's candidate, and the
memory undo takes it back. Two tenants with the same titles and the same
links never touch each other. Failure mining reads decided-then-superseded
decisions only. (docs/design/adr-m8-ingestion-structure.md §5.4, §5.5)
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text

from life_graph.config import settings
from life_graph.core.errors import ForbiddenError, NotFoundError
from life_graph.models.db import Decision, Memory
from life_graph.services import decision_lifecycle as lc
from life_graph.services.failure_mining import FailurePatternMiner
from life_graph.services.judgment import JudgmentService
from life_graph.services.memory import supersession
from life_graph.storage.database import async_session
from tests.integration.conftest import skip_on_db_error


def _tenant(tag: str) -> str:
    return f"declife_{tag}_{uuid.uuid4().hex[:8]}"


async def _decision(tenant: str, title: str, status: str = "candidate", **props) -> uuid.UUID:
    async with async_session() as s:
        row = await JudgmentService(s).create_decision(tenant, title, status=status)
        if props:
            row.properties = {**(row.properties or {}), **props}
        await s.commit()
        return row.id


async def _memory(tenant: str, content: str, **kw) -> uuid.UUID:
    now = datetime.now(UTC)
    m = Memory(
        id=uuid.uuid4(),
        tenant_id=tenant,
        content=content,
        content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
        importance=0.7,
        confidence=0.9,
        status=kw.pop("status", "active"),
        trust_tier="self",
        source_type="chat",
        properties=kw.pop("properties", {"fact_type": "decision"}),
        created_at=now,
        updated_at=now,
        valid_from=now,
        **kw,
    )
    async with async_session() as s:
        s.add(m)
        await s.commit()
    return m.id


async def _get(decision_id: uuid.UUID) -> Decision:
    async with async_session() as s:
        return (await s.execute(select(Decision).where(Decision.id == decision_id))).scalar_one()


async def _get_memory(memory_id: uuid.UUID) -> Memory:
    async with async_session() as s:
        return (await s.execute(select(Memory).where(Memory.id == memory_id))).scalar_one()


async def _cleanup(*tenants: str) -> None:
    async with async_session() as s:
        for t in tenants:
            await s.execute(
                text("UPDATE life_graph.decisions SET superseded_by = NULL WHERE tenant_id = :t"),
                {"t": t},
            )
            await s.execute(text("DELETE FROM life_graph.decisions WHERE tenant_id = :t"), {"t": t})
            await s.execute(
                text(
                    "UPDATE memories SET superseded_by = NULL, supersedes = NULL WHERE tenant_id = :t"
                ),
                {"t": t},
            )
            await s.execute(text("DELETE FROM memories WHERE tenant_id = :t"), {"t": t})
        await s.commit()


@skip_on_db_error
async def test_owner_confirm_then_supersede_writes_the_columns_and_the_trail():
    a = _tenant("a")
    try:
        old = await _decision(a, "Use Postgres 15")
        new = await _decision(a, "Use Postgres 17", status="decided")
        async with async_session() as s:
            await JudgmentService(s).move_decision(a, old, "decided", by="owner", owner=True)
            await s.commit()
        async with async_session() as s:
            await JudgmentService(s).supersede_decision(a, old, new, by="phone:d1", owner=True)
            await s.commit()

        row = await _get(old)
        assert row.status == "superseded" and row.superseded_by == new
        assert row.superseded_at is not None and row.decided_at is not None
        trail = row.properties["lifecycle"]
        assert [(e["from"], e["to"], e["by"]) for e in trail] == [
            ("candidate", "decided", "owner"),
            ("decided", "superseded", "phone:d1"),
        ]
    finally:
        await _cleanup(a)


@skip_on_db_error
async def test_a_refused_move_writes_nothing():
    a = _tenant("a")
    try:
        d = await _decision(a, "Buy a car")
        async with async_session() as s:
            with pytest.raises(ForbiddenError):
                await JudgmentService(s).move_decision(
                    a, d, "decided", by="service-key:x", owner=False
                )
            await s.commit()
        row = await _get(d)
        assert row.status == "candidate" and row.decided_at is None
        assert "lifecycle" not in row.properties
    finally:
        await _cleanup(a)


@skip_on_db_error
async def test_a_move_cannot_reach_another_tenant():
    a, b = _tenant("a"), _tenant("b")
    try:
        theirs = await _decision(b, "Buy a car")
        async with async_session() as s:
            with pytest.raises(NotFoundError):
                await JudgmentService(s).move_decision(a, theirs, "decided", by="owner", owner=True)
            await s.commit()
        assert (await _get(theirs)).status == "candidate"
    finally:
        await _cleanup(a, b)


@skip_on_db_error
async def test_a_capture_links_its_decision_to_the_decision_memory(monkeypatch):
    monkeypatch.setattr(settings, "decision_lifecycle", True)
    a = _tenant("a")
    capture = uuid.uuid4()
    try:
        memory_id = await _memory(a, "I decided to move to Chennai", capture_event_id=capture)
        async with async_session() as s:
            d = await JudgmentService(s).create_decision(
                a, "move to Chennai", status="candidate", capture_event_id=capture
            )
            assert await lc.link_capture_memory(s, a, d, capture) is True
            await s.commit()
            decision_id = d.id
        assert (await _get(decision_id)).properties["memory_id"] == str(memory_id)
        assert (await _get_memory(memory_id)).properties["decision_id"] == str(decision_id)
    finally:
        await _cleanup(a)


async def _mirror(tenant: str, old_m: uuid.UUID, new_m: uuid.UUID) -> bool:
    async with async_session() as s:
        old, new = await supersession.load(s, tenant, old_m, new_m, lock=True)
        assert supersession.apply(tenant, old, new, why="test")
        moved = await supersession.mirror_decisions(s, tenant, old, new)
        await s.commit()
    return moved


@skip_on_db_error
async def test_the_mirror_follows_the_memory_supersede_and_its_undo(monkeypatch):
    monkeypatch.setattr(settings, "decision_lifecycle", True)
    a, b = _tenant("a"), _tenant("b")
    try:
        old_m = await _memory(a, "School is Anna Nagar")
        new_m = await _memory(a, "School is Adyar")
        old_d = await _decision(a, "School: Anna Nagar", memory_id=str(old_m))
        new_d = await _decision(a, "School: Adyar", memory_id=str(new_m))
        # Tenant B: same titles, and links naming A's memories. Never touched.
        b_d = await _decision(b, "School: Anna Nagar", memory_id=str(old_m))

        assert await _mirror(a, old_m, new_m) is True
        row = await _get(old_d)
        assert row.status == "superseded" and row.superseded_by == new_d
        assert row.superseded_at is not None
        entry = row.properties["lifecycle"][-1]
        assert entry["by"] == lc.MIRROR_BY and entry["memory_old"] == str(old_m)
        assert (await _get(new_d)).status == "candidate"
        assert (await _get(b_d)).status == "candidate"

        async with async_session() as s:
            old, new = await supersession.load(s, a, old_m, new_m)
            assert supersession.undo(a, old, new)
            moved = await supersession.undo_decision_mirror(s, a, old_id=old_m, new_id=new_m)
            await s.commit()
        assert moved == 1
        row = await _get(old_d)
        assert row.status == "candidate" and row.superseded_by is None
        assert row.superseded_at is None
        assert row.properties["lifecycle"][-1]["by"] == lc.MIRROR_UNDO_BY
    finally:
        await _cleanup(a, b)


@skip_on_db_error
async def test_the_mirror_never_moves_a_decided_decision(monkeypatch):
    monkeypatch.setattr(settings, "decision_lifecycle", True)
    a = _tenant("a")
    try:
        old_m = await _memory(a, "Car: Swift")
        new_m = await _memory(a, "Car: Nexon")
        old_d = await _decision(a, "Car: Swift", status="decided", memory_id=str(old_m))
        await _decision(a, "Car: Nexon", memory_id=str(new_m))

        assert await _mirror(a, old_m, new_m) is False
        assert (await _get(old_d)).status == "decided"
    finally:
        await _cleanup(a)


@skip_on_db_error
async def test_flag_off_the_mirror_does_nothing(monkeypatch):
    monkeypatch.setattr(settings, "decision_lifecycle", False)
    a = _tenant("a")
    try:
        old_m = await _memory(a, "Gym: mornings")
        new_m = await _memory(a, "Gym: evenings")
        old_d = await _decision(a, "Gym: mornings", memory_id=str(old_m))
        await _decision(a, "Gym: evenings", memory_id=str(new_m))

        assert await _mirror(a, old_m, new_m) is False
        assert (await _get(old_d)).status == "candidate"
    finally:
        await _cleanup(a)


@skip_on_db_error
async def test_failure_mining_reads_decided_then_superseded_only():
    a = _tenant("a")
    try:
        decided = await _decision(a, "Quit the job", status="decided")
        candidate = await _decision(a, "Maybe a side project")
        newer = await _decision(a, "Stay in the job", status="decided")
        discarded = await _decision(a, "Not a decision")
        async with async_session() as s:
            await s.execute(
                text(
                    "UPDATE life_graph.decisions SET status = 'superseded', superseded_by = :n"
                    " WHERE id IN (:d, :c)"
                ),
                {"n": newer, "d": decided, "c": candidate},
            )
            await s.execute(
                text("UPDATE life_graph.decisions SET status = 'discarded' WHERE id = :x"),
                {"x": discarded},
            )
            await s.commit()

        found = {f["decision_id"] for f in await FailurePatternMiner().gather_failures(a)}
        assert found == {str(decided)}
    finally:
        await _cleanup(a)
