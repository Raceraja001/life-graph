#!/usr/bin/env python3
"""Synthetic evaluation of M8 change detection (services/memory/changes.py).

Each case in `evals/context_changes/cases.json` is seeded into a throwaway
tenant (``m3eval_<hex>``, the production retrieval arm's pattern and cleanup),
plus a second throwaway tenant for the isolation cases. A case says which
records the earlier turn's snapshot held, what happened to the rows since, and
which records this turn's snapshot holds. The harness then:

1. seeds the rows; builds the earlier snapshot from them with Stage 1's own
   item builders at the earlier reference time and keeps its compact form in
   an earlier turn's trace (``agent_tasks.result.trace.context_snapshot``);
2. applies the case's changes to the rows;
3. builds this turn's snapshot from the live rows, and runs the shipped path:
   find_baseline (the trace), resolve_refs (the re-read), compare_context;
4. moves the baseline forward (this turn's compact becomes the next turn's
   baseline) and compares again: nothing reported the first time may repeat.

No embedding and no search: snapshots are built from the rows directly, so the
eval measures the comparison, not retrieval. Every chat-model client and the
embedder raise while it runs. Synthetic data only; every row is deleted again,
also on failure.

Reported per kind and per noise category, never as one score (spec section 8):

* must_detect: missed (an expected change not reported), per kind;
* must_stay_silent: false_positives (any change not flagged acknowledged);
* unexpected_rate: reported changes not in the case's labels / all reported;
* repeats after the baseline moves; changes without evidence or reason;
* cross_tenant: the other tenant's ids or fingerprints in a result;
* model_calls; determinism_failures (two runs, byte-identical);
* suppressed counts per noise reason;
* latency p50/p95 (ms) of baseline read + re-read + comparison;
* "as-of recompute (c)": whether ADR §6 option (c) could have seen each kind
  on today's data, from the ADR's table (for the record; not run).

`--verify` exits non-zero when a target is missed: 0 missed, 0 silent false
positives, unexpected_rate <= 0.05, 0 repeats, 0 coverage gaps, 0 cross-tenant,
0 model calls, 0 determinism failures, every kind covered by at least two
must-detect cases, at least 40 + 20 cases, latency p95 <= --latency-p95-ms
(default 50), and no rows left behind.

Needs Postgres. By default it uses the integration test database (the
configured name with `_test` appended), as scripts/eval_context_snapshot.py:

    set -a; . <(grep -E '^LIFE_GRAPH_(DATABASE_URL|DATABASE_URL_SYNC|REDIS_URL)=' .env); set +a
    python scripts/eval_context_changes.py --verify
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES_PATH = ROOT / "evals" / "context_changes" / "cases.json"
MIN_DETECT, MIN_SILENT, MIN_PER_KIND = 40, 20, 2
UNEXPECTED_MAX = 0.05
#: What ADR §6 option (c) (recompute "as of" the last turn) could see, by kind.
AS_OF_RECOMPUTE = {
    "added": "yes",
    "deleted": "no",
    "rejected": "only with a named reviewer",
    "archived": "only with a named reviewer",
    "expired": "in theory",
    "discarded": "partly",
    "disputed": "no",
    "superseded": "partly",
    "confirmed": "no",
    "edited": "no",
    "decision_status": "partly",
    "decision_superseded": "partly",
    "decision_review_due": "yes",
    "intention_completed": "partly",
    "intention_expired": "partly",
    "intention_dismissed": "partly",
    "intention_approaching": "yes",
    "conflict_appeared": "partly",
    "conflict_resolved": "partly",
    "became_stale": "yes",
    "reconfirmed": "yes",
}


def _with_suffix(url: str, suffix: str) -> str:
    head, sep, tail = url.rpartition("/")
    if not sep or not tail:
        return url
    name, qmark, query = tail.partition("?")
    if not name or name.endswith(suffix):
        return url
    return f"{head}/{name}{suffix}{qmark}{query}"


def _point_at_test_database(suffix: str) -> None:
    from life_graph.config import settings

    if suffix:
        settings.database_url = _with_suffix(settings.database_url, suffix)
        settings.database_url_sync = _with_suffix(settings.database_url_sync, suffix)


# ── Seeding ───────────────────────────────────────────────────


def _hours(now: datetime, value: float | None) -> datetime | None:
    return None if value is None else now + timedelta(hours=float(value))


def _timed(spec: dict[str, Any], now: datetime) -> dict[str, Any]:
    """``<column>_h`` keys as datetimes (hours from now; negative is past)."""
    return {k[:-2]: _hours(now, v) for k, v in spec.items() if k.endswith("_h")}


def _memory_props(spec: dict[str, Any], now: datetime, turns: dict[str, str]) -> dict[str, Any]:
    from life_graph.core import evidence as ev

    props = dict(spec.get("properties") or {})
    if spec.get("review"):
        r = spec["review"]
        props["review"] = {"action": r.get("action", "approve"), "by": r["by"]}
        props["review"]["at"] = _hours(now, r["at_h"]).isoformat()
    if "superseded_at_h" in spec:
        props["superseded_at"] = _hours(now, spec["superseded_at_h"]).isoformat()
    if spec.get("owner_confirmed"):
        props[ev.OWNER_CONFIRMED] = {"by": "owner", "at": now.isoformat()}
    if spec.get("task") in turns:
        props["task_id"] = turns[spec["task"]]
    if "disputed_h" in spec:
        # What api/jarvis.py memory_was_wrong merges in (D13).
        at = _hours(now, spec["disputed_h"]).isoformat()
        props["disputed"] = {"at": at, "task_id": None, "note": None}
    return props


def _new_memory(tenant: str, spec: dict[str, Any], now: datetime, turns: dict[str, str]) -> Any:
    from life_graph.models.db import Memory

    t = _timed(spec, now)
    created = t.get("created_at") or now - timedelta(days=10)
    return Memory(
        id=uuid.uuid4(),
        tenant_id=tenant,
        content=spec["content"],
        content_hash=hashlib.sha256(f"{spec['content']}{uuid.uuid4()}".encode()).hexdigest(),
        properties=_memory_props(spec, now, turns),
        tags=spec.get("tags"),
        importance=0.6,
        confidence=0.9,
        source_type=spec.get("source_type", "chat"),
        trust_tier=spec.get("trust_tier", "self"),
        extraction_tier=spec.get("extraction_tier"),
        status=spec.get("status", "active"),
        created_at=created,
        updated_at=t.get("updated_at") or created,
        valid_from=created,
        valid_until=t.get("valid_until"),
        last_reinforced=t.get("last_reinforced"),
    )


def _new_decision(tenant: str, spec: dict[str, Any], now: datetime) -> Any:
    from life_graph.models.db import Decision

    t = _timed(spec, now)
    return Decision(
        id=uuid.uuid4(),
        tenant_id=tenant,
        title=spec["title"],
        reasoning=spec.get("reasoning"),
        status=spec.get("status", "candidate"),
        source=spec.get("source", "conversation"),
        created_at=t.get("created_at") or now - timedelta(days=10),
        decided_at=t.get("decided_at"),
        review_at=t.get("review_at"),
        reviewed_at=t.get("reviewed_at"),
    )


def _new_intention(tenant: str, spec: dict[str, Any], now: datetime) -> Any:
    from life_graph.models.db import Intention

    t = _timed(spec, now)
    return Intention(
        id=uuid.uuid4(),
        tenant_id=tenant,
        content=spec["content"],
        trigger_type=spec.get("trigger_type", "nudge"),
        status=spec.get("status", "pending"),
        created_at=t.get("created_at") or now - timedelta(days=10),
        trigger_time=t.get("trigger_time"),
        expires_at=t.get("expires_at"),
        completed_at=t.get("completed_at"),
    )


class World:
    """One case's tenant: its rows by key, and where they live."""

    def __init__(self, tenant: str, now: datetime) -> None:
        self.tenant = tenant
        self.now = now
        self.rows: dict[str, Any] = {}
        self.kind: dict[str, str] = {}
        self.turns: dict[str, str] = {}

    def ref(self, key: str) -> str:
        return f"{self.kind[key]}:{self.rows[key].id}"

    async def seed(self, spec: dict[str, Any]) -> None:
        from life_graph.models.db import Approval
        from life_graph.storage.database import async_session

        async with async_session() as s:
            for m in spec.get("memories", []):
                self._put(s, m["key"], "memory", _new_memory(self.tenant, m, self.now, self.turns))
            for d in spec.get("decisions", []):
                self._put(s, d["key"], "decision", _new_decision(self.tenant, d, self.now))
            for i in spec.get("intentions", []):
                self._put(s, i["key"], "intention", _new_intention(self.tenant, i, self.now))
            await s.flush()
            for group in ("memories", "decisions"):
                for row in spec.get(group, []):
                    if row.get("superseded_by"):
                        self.rows[row["key"]].superseded_by = self.rows[row["superseded_by"]].id
            for a in spec.get("approvals", []):
                t = _timed(a, self.now)
                old, new = str(self.rows[a["old"]].id), str(self.rows[a["new"]].id)
                row = Approval(
                    tenant_id=self.tenant,
                    kind="contradiction",
                    source="judgment",
                    source_ref=f"{old}|{new}",
                    title="Review a suspected contradiction",
                    payload={"memory_id_old": old, "memory_id_new": new, "applied": False},
                    status=a.get("status", "pending"),
                    created_at=t.get("created_at") or self.now - timedelta(days=10),
                )
                self._put(s, a["key"], "approval", row)
            await s.commit()

    def _put(self, s: Any, key: str, kind: str, row: Any) -> None:
        s.add(row)
        self.rows[key] = row
        self.kind[key] = kind

    async def mutate(self, ops: list[dict[str, Any]]) -> None:
        from life_graph.storage.database import async_session

        async with async_session() as s:
            for op in ops:
                await self._apply(s, op)
                await s.flush()
            await s.commit()

    async def _apply(self, s: Any, op: dict[str, Any]) -> None:
        from life_graph.models.db import Approval, Decision, Intention, Memory

        model = {"memory": Memory, "decision": Decision, "intention": Intention}
        model["approval"] = Approval
        key = op["key"]
        row = await s.get(model[self.kind[key]], self.rows[key].id)
        if op["op"] == "delete":
            if self.kind[key] == "memory":
                from sqlalchemy import update

                await s.execute(
                    update(Memory).where(Memory.superseded_by == row.id).values(superseded_by=None)
                )
            await s.delete(row)
            return
        fields = dict(op.get("set") or {})
        for name, value in _timed(fields, self.now).items():
            if name not in ("superseded_at", "disputed"):  # memory properties, set below
                setattr(row, name, value)
        for name, value in fields.items():
            if name.endswith("_h") or name in ("review", "owner_confirmed", "task"):
                continue
            if name == "superseded_by":
                value = self.rows[value].id
            elif name == "properties":
                value = {**(row.properties or {}), **value}
            setattr(row, name, value)
        if self.kind[key] == "memory" and any(
            k in fields
            for k in ("review", "owner_confirmed", "task", "superseded_at_h", "disputed_h")
        ):
            extra = _memory_props(fields, self.now, self.turns)
            row.properties = {**(row.properties or {}), **extra}
        self.rows[key] = row

    async def live(self, key: str) -> Any:
        from life_graph.models.db import Approval, Decision, Intention, Memory
        from life_graph.storage.database import async_session

        model = {
            "memory": Memory,
            "decision": Decision,
            "intention": Intention,
            "approval": Approval,
        }
        async with async_session() as s:
            return await s.get(model[self.kind[key]], self.rows[key].id)


async def _snapshot(world: World, keys: list[str], conflicts: list[dict], at: datetime) -> Any:
    from life_graph.services.memory import snapshot as snap
    from life_graph.services.memory.snapshot import (
        DEFAULT_BUDGET,
        ConflictSide,
        ContextConflict,
        ContextSnapshot,
        SourceRef,
    )

    build = {
        "memory": snap.memory_item,
        "decision": snap.decision_item,
        "intention": snap.intention_item,
    }
    items = []
    for key in keys:
        row = await world.live(key)
        items.append(build[world.kind[key]](row, at, DEFAULT_BUDGET))
    out = []
    for c in conflicts:
        sides = []
        for key, role in zip(c["sides"], c.get("roles", ("existing", "proposed")), strict=False):
            row = await world.live(key)
            sides.append(
                ConflictSide(SourceRef(world.kind[key], str(row.id)), role, str(row.status))
            )
        approval = str(world.rows[c["approval"]].id) if c.get("approval") else None
        out.append(ContextConflict(c["kind"], tuple(sides), approval_id=approval))
    return ContextSnapshot(
        query="eval",
        purpose="conversation",
        as_of=None,
        reference_time=at.isoformat(),
        budget=DEFAULT_BUDGET,
        items=tuple(items),
        conflicts=tuple(out),
        insufficient=not items,
        sources=("memories", "decisions", "intentions"),
    )


async def _turn(
    tenant: str,
    session_id: Any,
    at: datetime,
    compact: dict | None,
    *,
    changes_trace: dict | None = None,
) -> str:
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    task = AgentTask(
        id=uuid.uuid4(),
        tenant_id=tenant,
        agent_name="jarvis",
        status="completed",
        session_id=session_id,
        input={"message": "eval"},
        result={"response": "ok", "trace": {"context_snapshot": compact}} if compact else {},
        created_at=at,
    )
    if changes_trace is not None:
        task.result = {
            **task.result,
            "trace": {**task.result["trace"], "context_changes": changes_trace},
        }
    async with async_session() as s:
        s.add(task)
        await s.commit()
    return str(task.id)


async def _conversation(tenant: str, at: datetime) -> Any:
    from life_graph.models.db import AgentSession
    from life_graph.storage.database import async_session

    conv = AgentSession(tenant_id=tenant, user_message="eval", routed_to="jarvis")
    conv.created_at = at
    async with async_session() as s:
        s.add(conv)
        await s.commit()
    return conv.id


async def _cleanup(tenant: str) -> int:
    from sqlalchemy import text

    from life_graph.evals import production_retrieval_arm as arm
    from life_graph.storage.database import async_session

    async with async_session() as s:
        await s.execute(
            text("DELETE FROM life_graph.decisions WHERE tenant_id = :t"), {"t": tenant}
        )
        await s.execute(
            text(
                "UPDATE memories SET superseded_by = NULL, supersedes = NULL WHERE tenant_id = :t"
            ),
            {"t": tenant},
        )
        await s.commit()
    return await arm.cleanup_tenant(tenant)


# ── Model guard ───────────────────────────────────────────────


@contextlib.contextmanager
def _no_models(counter: list[int]):
    """Every chat-model client and the embedder count a call and raise."""
    from life_graph import runtime
    from life_graph.services.llm import client as llm_client
    from life_graph.services.llm import resilient
    from life_graph.services.memory import retrieval

    def boom(*a, **kw):
        counter.append(1)
        raise RuntimeError("model call during change detection")

    saved = [
        (llm_client.LMStudioClient, "__init__", llm_client.LMStudioClient.__init__),
        (resilient.ResilientLLM, "__init__", resilient.ResilientLLM.__init__),
        (runtime, "get_lm_client", runtime.get_lm_client),
        (runtime, "get_memory_manager", runtime.get_memory_manager),
        (retrieval, "judge", retrieval.judge),
    ]
    for owner, name, _ in saved:
        setattr(owner, name, boom)
    try:
        yield
    finally:
        for owner, name, value in saved:
            setattr(owner, name, value)


# ── One case ──────────────────────────────────────────────────


async def _setup(case: dict, world: World, other: World) -> tuple[Any, str, Any]:
    """Seeds, the earlier turn, the changes and this turn; (current snapshot, turn id, conv)."""
    now = world.now
    prev_at = now - timedelta(hours=float(case.get("window_hours", 24)))
    mode = case.get("baseline", "same")
    conv = await _conversation(world.tenant, prev_at - timedelta(minutes=1))
    world.turns["current"] = str(uuid.uuid4())
    await world.seed(case.get("seed", {}))
    await other.seed(case.get("other_seed", {}))
    prev = await _snapshot(
        world, case.get("previous", []), case.get("previous_conflicts", []), prev_at
    )
    compact: dict | None = prev.compact()
    if mode == "error":
        compact = {"error": "TimeoutError", "ms": 1000}
    elif mode == "v1":
        compact = {k: v for k, v in compact.items() if k not in ("v", "reference_time")}
    if mode in ("same", "error", "v1"):
        await _turn(world.tenant, conv, prev_at, compact)
    elif mode == "other_conversation":
        await _turn(world.tenant, await _conversation(world.tenant, prev_at), prev_at, compact)
    elif mode == "old":
        old_at = now - timedelta(days=40)
        await _turn(
            world.tenant,
            conv,
            old_at,
            (await _snapshot(world, case.get("previous", []), [], old_at)).compact(),
        )
    elif mode == "other_tenant":
        # The other tenant's turn, in this very conversation, newer than anything of ours.
        await _turn(other.tenant, conv, prev_at, compact)
    # mode "none": no earlier turn at all.
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        s.add(
            AgentTask(
                id=uuid.UUID(world.turns["current"]),
                tenant_id=world.tenant,
                agent_name="jarvis",
                status="running",
                session_id=conv,
                input={"message": "eval"},
                created_at=now,
            )
        )
        await s.commit()
    await world.mutate(case.get("mutate", []))
    if case.get("failed_turn"):
        # A turn between the two whose comparison timed out: its snapshot was
        # taken after the changes, so using it as the baseline would lose them.
        mid = now - timedelta(hours=1)
        mid_snap = await _snapshot(world, case.get("current", []), [], mid)
        await _turn(
            world.tenant,
            conv,
            mid,
            mid_snap.compact(),
            changes_trace={"error": "TimeoutError", "ms": 1000},
        )
    cur = await _snapshot(world, case.get("current", []), case.get("current_conflicts", []), now)
    return cur, world.turns["current"], conv


async def _compare(snap: Any, task_id: str, now: datetime) -> tuple[Any, float]:
    from life_graph.services.memory import changes

    t0 = time.perf_counter()
    found = await changes.find_baseline(uuid.UUID(task_id))
    resolved = None
    if found.baseline is not None:
        refs, approvals = changes.refs_to_resolve(found.baseline, snap)
        resolved = await changes.resolve_refs(refs, approvals)
    result = changes.compare_context(
        found.baseline, snap, resolved, now, conversation_tasks=found.conversation_tasks
    )
    return result, (time.perf_counter() - t0) * 1000.0


def _label_ref(world: World, case: dict, label: dict) -> str:
    from life_graph.services.memory.changes import conflict_key

    if label["ref"].startswith("conflict:"):
        name = label["ref"].split(":", 1)[1]
        spec = next(
            c
            for c in [*case.get("current_conflicts", []), *case.get("previous_conflicts", [])]
            if c.get("name") == name
        )
        return conflict_key(spec["kind"], [world.ref(k) for k in spec["sides"]])
    return world.ref(label["ref"])


def _score(case: dict, world: World, other: World, result: Any, again: Any) -> dict:
    labels = {(lab["kind"], _label_ref(world, case, lab)): lab for lab in case.get("changes", [])}
    got = {(c.kind, c.ref): c for c in result.changes}
    detect = case["expect"] == "detect"
    missed = [k for k in labels if k not in got]
    ack_wrong = [
        k
        for k, lab in labels.items()
        if k in got and "acknowledged" in lab and got[k].acknowledged != lab["acknowledged"]
    ]
    unexpected = [k for k in got if k not in labels]
    silent_fp = (
        [k for k, c in got.items() if not c.acknowledged and k not in labels] if not detect else []
    )
    blob = json.dumps(result.to_dict())
    foreign = [str(r.id) for r in other.rows.values()]
    first_keys = {c.key for c in result.changes}
    return {
        "detect": detect,
        "labels": len(labels),
        "kinds": sorted({k for k, _ in labels}),
        "found_kinds": sorted({key[0] for key in labels if key in got}),
        "missed": len(missed),
        "missed_detail": [f"{k}" for k, _ in missed],
        "acknowledged_wrong": len(ack_wrong),
        "reported": len(got),
        "unexpected": len(unexpected),
        "unexpected_detail": sorted(k for k, _ in unexpected),
        "false_positives": len(silent_fp),
        "repeats": sum(1 for c in again.changes if c.key in first_keys),
        "coverage_gaps": sum(1 for c in result.changes if not c.evidence or not c.reason),
        "cross_tenant": sum(1 for oid in foreign if oid in blob),
        "insufficient_wrong": int(result.insufficient != bool(case.get("insufficient", False))),
        "suppressed": dict(result.suppressed),
    }


async def _run_case(case: dict, repeat: int, model_calls: list[int]) -> tuple[dict, list[float]]:
    from life_graph.core.tenant import tenant_scope
    from life_graph.evals import production_retrieval_arm as arm

    now = datetime.now(UTC).replace(microsecond=0)
    world, other = World(arm.new_tenant(), now), World(arm.new_tenant(), now)
    latencies: list[float] = []
    try:
        snap, task_id, conv = await _setup(case, world, other)
        dumps = []
        with _no_models(model_calls), tenant_scope(world.tenant):
            for _ in range(max(2, repeat)):
                result, ms = await _compare(snap, task_id, now)
                latencies.append(ms)
                dumps.append(json.dumps(result.to_dict()))
        # The baseline moves: this turn's snapshot is the next turn's baseline.
        later = now + timedelta(minutes=5)
        from life_graph.models.db import AgentTask
        from life_graph.storage.database import async_session

        async with async_session() as s:
            row = await s.get(AgentTask, uuid.UUID(task_id))
            row.result = {"response": "ok", "trace": {"context_snapshot": snap.compact()}}
            await s.commit()
        next_id = await _turn(world.tenant, conv, later, None)
        next_snap = await _snapshot(
            world, case.get("current", []), case.get("current_conflicts", []), later
        )
        with _no_models(model_calls), tenant_scope(world.tenant):
            again, _ = await _compare(next_snap, next_id, later)
        row_out = _score(case, world, other, result, again)
        row_out["determinism_failures"] = int(len(set(dumps)) != 1)
    finally:
        left = await _cleanup(world.tenant) + await _cleanup(other.tenant)
    row_out["rows_left"] = left
    return row_out, latencies


# ── Report ────────────────────────────────────────────────────


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return round(ordered[idx], 2)


def _summary(rows: list[dict]) -> dict:
    reported = sum(r["reported"] for r in rows)
    keys = (
        "missed",
        "false_positives",
        "unexpected",
        "repeats",
        "coverage_gaps",
        "cross_tenant",
        "determinism_failures",
        "acknowledged_wrong",
        "insufficient_wrong",
    )
    out = {"cases": len(rows), "reported": reported} | {k: sum(r[k] for r in rows) for k in keys}
    out["unexpected_rate"] = round(out["unexpected"] / reported, 4) if reported else 0.0
    return out


async def run(cases_path: Path, repeat: int) -> dict:
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    rows: dict[str, dict] = {}
    latencies: list[float] = []
    model_calls: list[int] = []
    for case in data["cases"]:
        row, lat = await _run_case(case, repeat, model_calls)
        rows[case["id"]] = row | {"category": case["category"], "p50_ms": _pct(lat, 0.5)}
        latencies += lat
    by_kind: dict[str, dict[str, int]] = {}
    for r in rows.values():
        if r["detect"]:
            for k in r["kinds"]:
                entry = by_kind.setdefault(k, {"cases": 0, "found": 0})
                entry["cases"] += 1
                entry["found"] += int(k in r["found_kinds"])
    for k, entry in by_kind.items():
        entry["as_of_recompute_could_see"] = AS_OF_RECOMPUTE.get(k, "?")
    suppressed: dict[str, int] = {}
    for r in rows.values():
        for k, n in r["suppressed"].items():
            suppressed[k] = suppressed.get(k, 0) + n
    detect = [r for r in rows.values() if r["detect"]]
    silent = [r for r in rows.values() if not r["detect"]]
    return {
        "benchmark": "life_graph_context_changes_v1",
        "cases_file": str(cases_path.relative_to(ROOT)),
        "cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "method": "snapshots built from rows with Stage 1 item builders; no embedding, no model",
        "must_detect": _summary(detect),
        "must_stay_silent": _summary(silent),
        "overall": _summary(list(rows.values())),
        "by_kind": dict(sorted(by_kind.items())),
        "by_category": {
            cat: _summary([r for r in rows.values() if r["category"] == cat])
            for cat in sorted({r["category"] for r in rows.values()})
        },
        "suppressed": dict(sorted(suppressed.items())),
        "model_calls": len(model_calls),
        "latency_ms": {
            "runs": len(latencies),
            "p50": _pct(latencies, 0.5),
            "p95": _pct(latencies, 0.95),
            "max": round(max(latencies), 2) if latencies else 0.0,
        },
        "rows_left_after_cleanup": sum(r["rows_left"] for r in rows.values()),
        "cases": {
            cid: {
                k: r[k]
                for k in (
                    "category",
                    "missed_detail",
                    "unexpected_detail",
                    "false_positives",
                    "p50_ms",
                )
            }
            for cid, r in rows.items()
        },
    }


def failures(report: dict, latency_p95_ms: float) -> list[str]:
    from life_graph.services.memory.changes import KINDS

    fails: list[str] = []
    d, s, o = report["must_detect"], report["must_stay_silent"], report["overall"]
    if d["cases"] < MIN_DETECT or s["cases"] < MIN_SILENT:
        fails.append(f"too few cases: {d['cases']} detect / {s['cases']} silent")
    if o["missed"]:
        fails.append(f"missed = {o['missed']} (target 0; must_detect {d['missed']})")
    if s["false_positives"]:
        fails.append(f"must_stay_silent.false_positives = {s['false_positives']} (target 0)")
    if o["unexpected_rate"] > UNEXPECTED_MAX:
        fails.append(f"unexpected_rate = {o['unexpected_rate']} > {UNEXPECTED_MAX}")
    for key in (
        "repeats",
        "coverage_gaps",
        "cross_tenant",
        "determinism_failures",
        "acknowledged_wrong",
        "insufficient_wrong",
    ):
        if o[key]:
            fails.append(f"{key} = {o[key]} (target 0)")
    for kind in KINDS:
        n = report["by_kind"].get(kind, {}).get("cases", 0)
        if n < MIN_PER_KIND:
            fails.append(f"kind {kind}: {n} must-detect cases (need {MIN_PER_KIND})")
    if report["model_calls"]:
        fails.append(f"model_calls = {report['model_calls']} (target 0)")
    if report["latency_ms"]["p95"] > latency_p95_ms:
        fails.append(f"latency p95 {report['latency_ms']['p95']} ms > {latency_p95_ms} ms")
    if report["rows_left_after_cleanup"]:
        fails.append(f"{report['rows_left_after_cleanup']} throwaway rows left behind")
    return fails


def _print(report: dict) -> None:
    print(f"Context change eval ({report['method']})")
    head = f"{'set':<18} {'n':>3} {'rep':>4} {'miss':>4} {'fp':>3} {'unexp':>5} {'rpt':>3} {'cov':>3} {'xten':>4} {'det':>3}"
    print(head)
    print("-" * len(head))
    for name in ("must_detect", "must_stay_silent", "overall"):
        e = report[name]
        print(
            f"{name:<18} {e['cases']:>3} {e['reported']:>4} {e['missed']:>4} {e['false_positives']:>3} "
            f"{e['unexpected']:>5} {e['repeats']:>3} {e['coverage_gaps']:>3} {e['cross_tenant']:>4} "
            f"{e['determinism_failures']:>3}"
        )
    print(f"\n{'kind':<24} {'cases':>5} {'found':>5}  as-of recompute (c) could see")
    for kind, e in report["by_kind"].items():
        print(f"{kind:<24} {e['cases']:>5} {e['found']:>5}  {e['as_of_recompute_could_see']}")
    print("\nsuppressed: " + ", ".join(f"{k} {v}" for k, v in report["suppressed"].items()))
    lat = report["latency_ms"]
    print(
        f"model calls {report['model_calls']}; latency over {lat['runs']} runs: "
        f"p50 {lat['p50']} ms, p95 {lat['p95']} ms, max {lat['max']} ms"
    )
    for cid, c in report["cases"].items():
        if c["missed_detail"] or c["unexpected_detail"] or c["false_positives"]:
            print(f"  {cid}: missed {c['missed_detail']} unexpected {c['unexpected_detail']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--output", type=Path, default=None, help="Write the report JSON here")
    parser.add_argument("--repeat", type=int, default=3, help="Comparisons per case (min 2)")
    parser.add_argument("--verify", action="store_true", help="Exit non-zero on a missed target")
    parser.add_argument("--latency-p95-ms", type=float, default=50.0)
    parser.add_argument(
        "--db-suffix",
        default=os.environ.get("LIFE_GRAPH_TEST_DATABASE_SUFFIX", "_test"),
        help='Suffix for the database name (default "_test"; "" uses the configured DB)',
    )
    args = parser.parse_args()
    _point_at_test_database(args.db_suffix)
    logging.getLogger("life_graph").setLevel(logging.ERROR)

    report = asyncio.run(run(args.cases, args.repeat))
    _print(report)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    fails = failures(report, args.latency_p95_ms)
    if fails:
        print("FAIL:\n  " + "\n  ".join(fails), file=sys.stderr)
        return 1 if (args.verify or report["rows_left_after_cleanup"]) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
