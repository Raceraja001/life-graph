"""Change detection against a real Postgres (services/memory/changes.py).

resolve_refs reads live rows by id (delete, reject, supersede along a chain,
decision supersede, intention complete); find_baseline picks the same
conversation first, skips error traces and every version of a regenerated
turn; and the tenant negative tests: tenant B's turn is never tenant A's
baseline, even with A's conversation id, and B's row id inside A's baseline
reads as a plain ``deleted`` with nothing of B in the result.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, text

from life_graph.core.tenant import tenant_scope
from life_graph.models.db import AgentSession, AgentTask, Approval, Decision, Intention, Memory
from life_graph.services.memory import snapshot
from life_graph.services.memory.changes import (
    Baseline,
    compare_context,
    detect,
    find_baseline,
    refs_to_resolve,
    resolve_refs,
)
from life_graph.services.memory.snapshot import DEFAULT_BUDGET, ContextSnapshot
from life_graph.storage.database import async_session
from life_graph.storage.postgres import PostgresMemoryStore
from tests.integration.conftest import skip_on_db_error

NOW = datetime.now(UTC)


def _tenant(tag: str) -> str:
    return f"ctxchg_{tag}_{uuid.uuid4().hex[:8]}"


def _mem(tenant: str, content: str, *, days_ago: float = 3, **kw) -> Memory:
    when = NOW - timedelta(days=days_ago)
    return Memory(
        id=uuid.uuid4(),
        tenant_id=tenant,
        content=content,
        content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
        importance=0.7,
        confidence=0.9,
        status=kw.pop("status", "active"),
        trust_tier=kw.pop("trust_tier", "self"),
        source_type=kw.pop("source_type", "chat"),
        properties=kw.pop("properties", {}),
        created_at=when,
        updated_at=when,
        valid_from=when,
        **kw,
    )


async def _add(*rows) -> None:
    async with async_session() as s:
        for r in rows:
            s.add(r)
            await s.flush()
        await s.commit()


async def _cleanup(*tenants: str) -> None:
    async with async_session() as s:
        for t in tenants:
            await s.execute(text("DELETE FROM life_graph.decisions WHERE tenant_id = :t"), {"t": t})
            for model in (AgentTask, AgentSession, Approval, Intention):
                await s.execute(delete(model).where(model.tenant_id == t))
            await s.execute(
                text(
                    "UPDATE memories SET superseded_by = NULL, supersedes = NULL WHERE tenant_id = :t"
                ),
                {"t": t},
            )
            await s.execute(delete(Memory).where(Memory.tenant_id == t))
        await s.commit()


def _snap_of(memories, at: datetime) -> ContextSnapshot:
    items = tuple(snapshot.memory_item(m, at, DEFAULT_BUDGET) for m in memories)
    return ContextSnapshot(
        query="q",
        purpose="conversation",
        as_of=None,
        reference_time=at.isoformat(),
        budget=DEFAULT_BUDGET,
        items=items,
        insufficient=not items,
        sources=("memories", "decisions", "intentions"),
    )


async def _turn(tenant, session_id, *, at, compact=None, **kw) -> AgentTask:
    task = AgentTask(
        id=uuid.uuid4(),
        tenant_id=tenant,
        agent_name="jarvis",
        status=kw.pop("status", "completed"),
        session_id=session_id,
        input=kw.pop("input", {"message": "x"}),
        result={"response": "ok", "trace": {"context_snapshot": compact}} if compact else {},
        created_at=at,
    )
    await _add(task)
    return task


async def _conversation(tenant: str) -> uuid.UUID:
    conv = AgentSession(tenant_id=tenant, user_message="m", routed_to="jarvis")
    await _add(conv)
    return conv.id


# ── resolve_refs ──────────────────────────────────────────────


@skip_on_db_error
async def test_resolve_refs_reads_live_state_by_id():
    tenant = _tenant("res")
    try:
        rejected = _mem(tenant, "a fact later rejected", status="rejected")
        c = _mem(tenant, "the newest value")
        b = _mem(tenant, "a middle value", status="superseded")
        a = _mem(tenant, "the first value", status="superseded")
        await _add(rejected, c, b, a)
        async with async_session() as s:
            (await s.get(Memory, b.id)).superseded_by = c.id
            (await s.get(Memory, a.id)).superseded_by = b.id
            await s.commit()
        d_new = Decision(id=uuid.uuid4(), tenant_id=tenant, title="use Postgres", status="decided")
        d_old = Decision(id=uuid.uuid4(), tenant_id=tenant, title="use MySQL", status="superseded")
        done = Intention(id=uuid.uuid4(), tenant_id=tenant, content="renew", status="completed")
        await _add(d_new, d_old, done)
        async with async_session() as s:
            (await s.get(Decision, d_old.id)).superseded_by = d_new.id
            await s.commit()
        gone = f"memory:{uuid.uuid4()}"
        refs = [
            f"memory:{rejected.id}",
            f"memory:{a.id}",
            f"decision:{d_old.id}",
            f"intention:{done.id}",
            gone,
            "memory:not-a-uuid",
        ]
        with tenant_scope(tenant):
            rows = await resolve_refs(refs)
        assert rows[f"memory:{rejected.id}"].status == "rejected"
        assert rows[gone].missing and rows["memory:not-a-uuid"].missing
        # The chain is followed: B and C were read although only A was asked for.
        assert rows[f"memory:{a.id}"].superseded_by == str(b.id)
        assert rows[f"memory:{b.id}"].superseded_by == str(c.id)
        assert rows[f"memory:{c.id}"].status == "active"
        assert rows[f"decision:{d_old.id}"].superseded_by == str(d_new.id)
        assert rows[f"intention:{done.id}"].status == "completed"
        assert rows[f"memory:{a.id}"].fp == snapshot.fingerprint(a.id, "the first value")
    finally:
        await _cleanup(tenant)


@skip_on_db_error
async def test_another_tenants_row_resolves_to_missing_and_reads_as_a_plain_delete():
    mine, theirs = _tenant("a"), _tenant("b")
    try:
        own = _mem(mine, "my own fact")
        foreign = _mem(theirs, "SECRET-B a fact of tenant B")
        await _add(own, foreign)
        # A baseline holding B's id (forged or stale) ...
        prev = _snap_of([own, foreign], NOW - timedelta(hours=2))
        base = Baseline.from_compact(prev.compact(), task_id="t")
        # ... while B's row changes: none of its live state may reach A.
        async with async_session() as s:
            row = await s.get(Memory, foreign.id)
            row.status = "archived"
            row.content = "SECRET-B rewritten"
            await s.commit()
        ref = f"memory:{foreign.id}"
        with tenant_scope(mine):
            rows = await resolve_refs([ref, f"memory:{own.id}"])
        assert rows[ref].missing is True and rows[ref].status == "" and rows[ref].fp == ""
        result = compare_context(base, _snap_of([own], NOW), rows, NOW)
        # ... reports only a plain "deleted".
        assert [(c.kind, c.ref) for c in result.changes] == [("deleted", ref)]
        blob = json.dumps(result.to_dict())
        assert "SECRET-B" not in blob and "archived" not in blob
        assert snapshot.fingerprint(foreign.id, "SECRET-B rewritten") not in blob
    finally:
        await _cleanup(mine, theirs)


# ── find_baseline ─────────────────────────────────────────────


def _compact(at: datetime, memories=()) -> dict:
    return _snap_of(list(memories), at).compact()


@skip_on_db_error
async def test_the_baseline_is_the_latest_usable_turn_of_the_same_conversation():
    tenant = _tenant("base")
    try:
        conv = await _conversation(tenant)
        t = NOW - timedelta(hours=5)
        older = await _turn(tenant, conv, at=t, compact=_compact(t))
        good = await _turn(
            tenant, conv, at=t + timedelta(hours=1), compact=_compact(t + timedelta(hours=1))
        )
        await _turn(
            tenant, conv, at=t + timedelta(hours=2), compact={"error": "TimeoutError", "ms": 1000}
        )
        await _turn(tenant, conv, at=t + timedelta(hours=3), compact={"items": []})  # format 1
        current = await _turn(tenant, conv, at=t + timedelta(hours=4))
        with tenant_scope(tenant):
            found = await find_baseline(current.id)
        assert found.baseline is not None
        assert found.baseline.task_id == str(good.id) and found.baseline.same_conversation
        assert (
            str(older.id) in found.conversation_tasks
            and str(current.id) in found.conversation_tasks
        )
    finally:
        await _cleanup(tenant)


@skip_on_db_error
async def test_a_regenerated_turn_uses_the_baseline_of_the_turn_it_replaces():
    tenant = _tenant("regen")
    try:
        conv = await _conversation(tenant)
        t = NOW - timedelta(hours=5)
        before = await _turn(tenant, conv, at=t, compact=_compact(t))
        replaced = await _turn(
            tenant, conv, at=t + timedelta(hours=1), compact=_compact(t + timedelta(hours=1))
        )
        first_try = await _turn(
            tenant,
            conv,
            at=t + timedelta(hours=2),
            compact=_compact(t + timedelta(hours=2)),
            input={"message": "x", "regenerates": str(replaced.id)},
        )
        again = await _turn(
            tenant,
            conv,
            at=t + timedelta(hours=3),
            input={"message": "x", "regenerates": str(replaced.id)},
        )
        with tenant_scope(tenant):
            found = await find_baseline(again.id)
        assert found.baseline is not None and found.baseline.task_id == str(before.id)
        assert str(first_try.id) != found.baseline.task_id
    finally:
        await _cleanup(tenant)


@skip_on_db_error
async def test_another_tenants_turn_is_never_the_baseline_even_in_the_same_conversation():
    mine, theirs = _tenant("a"), _tenant("b")
    try:
        conv = await _conversation(mine)
        t = NOW - timedelta(hours=3)
        # Tenant B's newer turn carries A's conversation id.
        await _turn(
            theirs, conv, at=t + timedelta(hours=1), compact=_compact(t + timedelta(hours=1))
        )
        other_conv = await _conversation(theirs)
        await _turn(theirs, other_conv, at=t + timedelta(hours=1), compact=_compact(t))
        current = await _turn(mine, conv, at=t + timedelta(hours=2))
        with tenant_scope(mine):
            found = await find_baseline(current.id)
        assert found.baseline is None
        assert found.conversation_tasks == frozenset({str(current.id)})
        # And B cannot look up from A's turn at all.
        with tenant_scope(theirs):
            assert (await find_baseline(current.id)).baseline is None
    finally:
        await _cleanup(mine, theirs)


@skip_on_db_error
async def test_without_one_in_the_conversation_a_recent_turn_of_the_tenant_is_used():
    tenant = _tenant("wide")
    try:
        here, there = await _conversation(tenant), await _conversation(tenant)
        t = NOW - timedelta(days=2)
        elsewhere = await _turn(tenant, there, at=t, compact=_compact(t))
        await _turn(
            tenant, there, at=NOW - timedelta(days=40), compact=_compact(NOW - timedelta(days=40))
        )
        current = await _turn(tenant, here, at=NOW - timedelta(minutes=1))
        with tenant_scope(tenant):
            found = await find_baseline(current.id)
        assert found.baseline is not None and found.baseline.task_id == str(elsewhere.id)
        assert found.baseline.same_conversation is False
    finally:
        await _cleanup(tenant)


# ── The trace baseline, end to end ────────────────────────────


@skip_on_db_error
async def test_detect_compares_with_the_previous_turns_trace():
    tenant = _tenant("e2e")
    try:
        kept = _mem(tenant, "the car insurance renews in March")
        dropped = _mem(tenant, "the old router password rotates monthly")
        await _add(kept, dropped)
        conv = await _conversation(tenant)
        t = NOW - timedelta(hours=1)
        await _turn(tenant, conv, at=t, compact=_compact(t, [kept, dropped]))
        # Since then: one memory edited in place (a real word), one rejected.
        async with async_session() as s:
            row = await s.get(Memory, kept.id)
            row.content = "The car insurance renews in April"
            row.updated_at = NOW - timedelta(minutes=5)
            gone = await s.get(Memory, dropped.id)
            gone.status = "rejected"
            await s.commit()
        current = await _turn(tenant, conv, at=NOW - timedelta(minutes=1))
        async with async_session() as s:
            live = await s.get(Memory, kept.id)
        snap = _snap_of([live], NOW)
        with tenant_scope(tenant):
            result = await detect(snap, current.id, now=NOW)
            refs, _ = refs_to_resolve(None, snap)
        assert result.insufficient is False
        assert sorted((c.kind, c.ref) for c in result.changes) == [
            ("edited", f"memory:{kept.id}"),
            ("rejected", f"memory:{dropped.id}"),
        ]
        assert result.baseline["same_conversation"] is True
        assert "insurance" not in json.dumps(result.trace())
        assert refs == [f"memory:{kept.id}"]
    finally:
        await _cleanup(tenant)


@skip_on_db_error
async def test_a_turn_whose_comparison_failed_is_not_the_baseline():
    tenant = _tenant("fail")
    try:
        conv = await _conversation(tenant)
        t = NOW - timedelta(hours=4)
        good = await _turn(tenant, conv, at=t, compact=_compact(t))
        failed = AgentTask(
            id=uuid.uuid4(),
            tenant_id=tenant,
            agent_name="jarvis",
            status="completed",
            session_id=conv,
            input={"message": "x"},
            result={
                "response": "ok",
                "trace": {
                    "context_snapshot": _compact(t + timedelta(hours=1)),
                    "context_changes": {"error": "TimeoutError", "ms": 1000},
                },
            },
            created_at=t + timedelta(hours=1),
        )
        await _add(failed)
        current = await _turn(tenant, conv, at=t + timedelta(hours=3))
        with tenant_scope(tenant):
            found = await find_baseline(current.id)
        # The window reaches back past the failed turn, so nothing is lost.
        assert found.baseline is not None and found.baseline.task_id == str(good.id)
    finally:
        await _cleanup(tenant)


@skip_on_db_error
async def test_a_temporary_chat_is_never_a_baseline():
    tenant = _tenant("temp")
    try:
        here = await _conversation(tenant)
        temp = AgentSession(
            tenant_id=tenant, user_message="m", routed_to="jarvis", context={"temporary": True}
        )
        await _add(temp)
        t = NOW - timedelta(hours=3)
        # A temporary chat's turn, by its input and by its conversation.
        await _turn(
            tenant,
            temp.id,
            at=t + timedelta(hours=1),
            compact=_compact(t),
            input={"message": "x", "temporary": True},
        )
        await _turn(tenant, temp.id, at=t + timedelta(hours=1, minutes=5), compact=_compact(t))
        current = await _turn(tenant, here, at=t + timedelta(hours=2))
        with tenant_scope(tenant):
            assert (await find_baseline(current.id)).baseline is None
        # A later turn of the temporary chat itself does not compare with it either.
        later = await _turn(
            tenant, temp.id, at=t + timedelta(hours=2), input={"message": "x", "temporary": True}
        )
        with tenant_scope(tenant):
            assert (await find_baseline(later.id)).baseline is None
        # An ordinary conversation still is.
        plain = await _turn(tenant, await _conversation(tenant), at=t, compact=_compact(t))
        with tenant_scope(tenant):
            found = await find_baseline(current.id)
        assert found.baseline is not None and found.baseline.task_id == str(plain.id)
    finally:
        await _cleanup(tenant)


@skip_on_db_error
async def test_a_memory_used_since_the_last_turn_is_not_an_edit():
    """D9: touch / touch_many count the access but leave updated_at alone,
    so a memory recalled last turn is not a ``cosmetic`` edit this turn."""
    tenant = _tenant("used")
    try:
        used = _mem(tenant, "the team standup is at 9:30")
        stamp = used.updated_at
        await _add(used)
        conv = await _conversation(tenant)
        t = NOW - timedelta(hours=1)
        await _turn(tenant, conv, at=t, compact=_compact(t, [used]))
        store = PostgresMemoryStore()
        with tenant_scope(tenant):
            assert await store.touch_many([used.id]) == 1
            await store.touch(used.id)
        async with async_session() as s:
            live = await s.get(Memory, used.id)
        assert live.access_count == 2 and live.last_accessed is not None
        assert live.updated_at == stamp
        later = datetime.now(UTC)
        current = await _turn(tenant, conv, at=later - timedelta(seconds=1))
        snap = _snap_of([live], later)
        with tenant_scope(tenant):
            result = await detect(snap, current.id, now=later)
        assert result.insufficient is False
        assert result.changes == ()
        assert "cosmetic" not in dict(result.suppressed)
    finally:
        await _cleanup(tenant)
