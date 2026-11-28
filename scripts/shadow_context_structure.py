"""Shadow check of context structure: label counts from the M8 shadow traces.

ADR ``docs/design/adr-m8-ingestion-structure.md`` §6.2, step 10 of §8.1.
Each personal local Jarvis turn keeps a compact context snapshot (refs and
labels, no content) at ``agent_tasks.result->'trace'->'context_snapshot'``
and, when comparing, the change list at ``...->'context_changes'``. This
script counts their labels for one tenant, before and after each ingestion
flag goes on, next to the ingestion side (world time, supersession ends,
typed links, decisions, pending contradiction approvals).

    PYTHONPATH=. python scripts/shadow_context_structure.py --tenant raja
        [--since 7 | 14d | 2026-11-20] [--json]

Rules it keeps (D30):
- one ``SET TRANSACTION READ ONLY`` transaction, rolled back at the end;
  it writes nothing;
- every query is filtered on ``tenant_id = :tenant``;
- it prints counts, rates and percentiles only. No ref, fingerprint, id,
  content or other string of a trace or a row is printed: a label is shown
  only when it is in the code's own vocabulary (:data:`VOCAB`), anything
  else is counted as ``other``.

The database is LIFE_GRAPH_DATABASE_URL (``life_graph.storage.database``):
run it from the copy whose ``.env`` you mean.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import AsyncIterator, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from life_graph.extraction import world_time
from life_graph.models.schemas import DECISION_STATUSES
from life_graph.services.memory import changes, snapshot, supersession, typed_links
from life_graph.services.memory.links import VALID_LINK_TYPES

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

#: Shown for a label that is not in the code's vocabulary.
OTHER = "other"
#: Shown for a missing (null) label.
UNSET = "unset"

#: The only label values this script ever prints, per label.
VOCAB: dict[str, frozenset[str]] = {
    "ref_kind": frozenset({"memory", "decision", "intention"}),
    "relation_type": frozenset(VALID_LINK_TYPES),
    # snapshot.ContextConflict.kind
    "conflict_kind": frozenset(
        {"supersession", "pending_contradiction", "decision_supersession", "linked_contradiction"}
    ),
    "decision_status": frozenset(DECISION_STATUSES),
    "abstention_reason": frozenset({"contradictory_evidence", "unresolvable_missing_evidence"}),
    "change_kind": frozenset(changes.KINDS),
    "suppressed": frozenset(changes.NOISE),
    "timing_stage": frozenset(snapshot.TIMING_STAGES),
    "error": frozenset({"TimeoutError"}),
    "wt_precision": frozenset({world_time.DAY, world_time.WEEK, world_time.MONTH, world_time.YEAR}),
    "wt_source": frozenset({world_time.CONTENT, world_time.SOURCE_TEXT, world_time.MODEL}),
    "confidence": frozenset({"high", "medium", "low"}),
}


def label(value: Any, vocab: str) -> str:
    """*value* when it is a known label of *vocab*, else ``other`` (``unset`` for None)."""
    if value is None:
        return UNSET
    if isinstance(value, bool):
        return "true" if value else "false"
    return value if isinstance(value, str) and value in VOCAB[vocab] else OTHER


def percentile(values: Iterable[float], q: float) -> float | None:
    """The *q*-th percentile (0-100) by linear interpolation; None when empty.

    The same rule as ``numpy.percentile``'s default and PostgreSQL's
    ``percentile_cont``: rank ``q/100 * (n - 1)`` between the sorted values.
    """
    xs = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not xs:
        return None
    rank = (q / 100) * (len(xs) - 1)
    lo, hi = math.floor(rank), math.ceil(rank)
    return xs[lo] + (xs[hi] - xs[lo]) * (rank - lo)


def spread(values: Sequence[float | None]) -> dict[str, float | int | None]:
    xs = [float(v) for v in values if v is not None]
    return {
        "n": len(xs),
        "p50": _round(percentile(xs, 50)),
        "p95": _round(percentile(xs, 95)),
        "max": _round(max(xs)) if xs else None,
    }


def rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _round(v: float | None) -> float | None:
    return None if v is None else round(v, 2)


# ── Queries (read only, tenant-scoped, labels and numbers only) ─────

#: The trace of one turn, as an array-safe JSON path.
_SNAP = "t.result->'trace'->'context_snapshot'"
_CHG = "t.result->'trace'->'context_changes'"
_TURNS = (
    "FROM agent_tasks t WHERE t.tenant_id = :tenant AND t.created_at >= :since"
    " AND jsonb_typeof(t.result->'trace') = 'object'"
)


def _arr(path: str) -> str:
    return f"(CASE WHEN jsonb_typeof({path}) = 'array' THEN {path} ELSE '[]'::jsonb END)"


def _num(path: str, key: str) -> str:
    return (
        f"(CASE WHEN jsonb_typeof({path}->'{key}') = 'number' THEN ({path}->>'{key}')::float END)"
    )


def _bool(path: str, key: str) -> str:
    return f"(CASE WHEN jsonb_typeof({path}->'{key}') = 'boolean' THEN ({path}->>'{key}')::boolean END)"


def _obj(path: str) -> str:
    """*path* when it is an object whose values are all numbers, else null (no strings out)."""
    return (
        f"(CASE WHEN jsonb_typeof({path}) = 'object' AND NOT EXISTS ("
        f"SELECT 1 FROM jsonb_each({path}) e WHERE jsonb_typeof(e.value) <> 'number')"
        f" THEN {path} END)"
    )


def _each(path: str, alias: str) -> str:
    """``FROM`` the tenant's traced turns, one row per element of the array at *path*."""
    return _TURNS.replace(
        "FROM agent_tasks t",
        f"FROM agent_tasks t CROSS JOIN LATERAL jsonb_array_elements({_arr(path)}) AS {alias}",
        1,
    )


QUERIES: dict[str, str] = {
    # One row per traced turn: its day, booleans and numbers. No ref, no fp.
    "turns": f"""
        SELECT (t.created_at AT TIME ZONE 'UTC')::date AS day,
               ({_SNAP}) IS NOT NULL AS has_snapshot,
               jsonb_typeof({_SNAP}->'items') = 'array' AS snapshot_ok,
               {_SNAP}->>'error' AS snapshot_error,
               {_bool(_SNAP, "abstain")} AS abstain,
               {_bool(_SNAP, "insufficient")} AS insufficient,
               {_num(_SNAP, "ms")} AS ms,
               {_obj(_SNAP + "->'timings_ms'")} AS timings_ms,
               jsonb_array_length({_arr(_SNAP + "->'items'")}) AS items,
               (SELECT count(*) FROM jsonb_array_elements({_arr(_SNAP + "->'items'")}) i
                 WHERE i->>'ref' LIKE 'memory:%') AS memory_items,
               (SELECT count(*) FROM jsonb_array_elements({_arr(_SNAP + "->'items'")}) i
                 WHERE i->>'ref' LIKE 'memory:%'
                   AND i->'world_time_known' = 'true'::jsonb) AS world_time_known,
               jsonb_array_length({_arr(_SNAP + "->'relations'")}) AS relations,
               jsonb_array_length({_arr(_SNAP + "->'conflicts'")}) AS conflicts,
               ({_CHG}) IS NOT NULL AS has_changes,
               jsonb_typeof({_CHG}->'changes') = 'array' AS changes_ok,
               {_CHG}->>'error' AS changes_error,
               jsonb_typeof({_CHG}->'baseline') = 'object' AS baseline_found,
               {_bool(_CHG, "insufficient")} AS changes_insufficient,
               {_bool(_CHG, "read_failed")} AS read_failed,
               {_num(_CHG, "ms")} AS changes_ms,
               jsonb_array_length({_arr(_CHG + "->'changes'")}) AS changes,
               {_obj(_CHG + "->'suppressed'")} AS suppressed
        {_TURNS} AND (({_SNAP}) IS NOT NULL OR ({_CHG}) IS NOT NULL)
        ORDER BY t.created_at""",
    "item_kinds": f"""
        SELECT split_part(i->>'ref', ':', 1) AS label, count(*) AS n,
               count(*) FILTER (WHERE i->'world_time_known' = 'true'::jsonb) AS world_time_known
        {_each(_SNAP + "->'items'", "i")}
        GROUP BY 1""",
    "relation_types": f"""
        SELECT r->>'type' AS label, count(*) AS n
        {_each(_SNAP + "->'relations'", "r")}
        GROUP BY 1""",
    "conflict_kinds": f"""
        SELECT c->>'kind' AS label, count(*) AS n
        {_each(_SNAP + "->'conflicts'", "c")}
        GROUP BY 1""",
    "decision_items": f"""
        SELECT i->>'status' AS label, i->'confirmed' = 'true'::jsonb AS confirmed, count(*) AS n
        {_each(_SNAP + "->'items'", "i")}
          AND i->>'ref' LIKE 'decision:%'
        GROUP BY 1, 2""",
    "abstention_reasons": f"""
        SELECT {_SNAP}->>'abstention_reason' AS label, count(*) AS n
        {_TURNS} AND {_SNAP}->'abstain' = 'true'::jsonb
        GROUP BY 1""",
    "change_kinds": f"""
        SELECT c->>'kind' AS label, c->'acknowledged' = 'true'::jsonb AS acknowledged,
               count(*) AS n
        {_each(_CHG + "->'changes'", "c")}
        GROUP BY 1, 2""",
    # ── Ingestion side ─────────────────────────────────────────
    "memories": """
        SELECT count(*) AS created,
               count(*) FILTER (WHERE m.properties->'world_time' ? 'start') AS with_world_time,
               count(*) FILTER (WHERE m.properties->'world_time' ? 'end') AS with_world_end
        FROM memories m WHERE m.tenant_id = :tenant AND m.created_at >= :since""",
    "world_time": """
        SELECT m.properties->'world_time'->>'precision' AS precision,
               m.properties->'world_time'->>'source' AS source, count(*) AS n
        FROM memories m WHERE m.tenant_id = :tenant AND m.created_at >= :since
          AND jsonb_typeof(m.properties->'world_time') = 'object'
          AND m.properties->'world_time' ? 'start'
        GROUP BY 1, 2""",
    "supersession": """
        SELECT count(*) FILTER (WHERE m.properties->>'valid_until_by' = :by) AS ended_all,
               count(*) FILTER (WHERE m.properties->>'valid_until_by' = :by
                                  AND m.updated_at >= :since) AS ended_since,
               count(*) FILTER (WHERE m.status = 'superseded'
                                  AND m.updated_at >= :since) AS superseded_since
        FROM memories m WHERE m.tenant_id = :tenant""",
    "typed_links": """
        SELECT l.link_type AS label, count(*) AS n
        FROM memory_links l WHERE l.tenant_id = :tenant AND l.created_at >= :since
          AND l.properties->>'why' LIKE :why
        GROUP BY 1""",
    "decisions": """
        SELECT d.status AS label, count(*) AS n,
               count(*) FILTER (WHERE d.created_at >= :since) AS created_since
        FROM life_graph.decisions d WHERE d.tenant_id = :tenant
        GROUP BY 1""",
    "contradictions": """
        SELECT a.payload->>'confidence' AS label,
               a.payload->'applied' = 'true'::jsonb AS applied, count(*) AS n,
               count(*) FILTER (WHERE a.created_at >= :since) AS created_since,
               COALESCE(sum(CASE WHEN jsonb_typeof(a.payload->'not_queued') = 'number'
                                 THEN (a.payload->>'not_queued')::int END), 0) AS not_queued
        FROM approvals a WHERE a.tenant_id = :tenant
          AND a.kind = 'contradiction' AND a.status = 'pending'
        GROUP BY 1, 2""",
}

#: Bound values besides tenant and since: code constants, never input.
CONSTANTS = {"by": supersession.VALID_UNTIL_BY, "why": typed_links.WHY_PREFIX + "%"}


@asynccontextmanager
async def read_only(engine: Any) -> AsyncIterator[AsyncConnection]:
    """A connection inside one ``SET TRANSACTION READ ONLY`` transaction, rolled back."""
    async with engine.connect() as conn:
        await conn.execute(text("SET TRANSACTION READ ONLY"))
        try:
            yield conn
        finally:
            await conn.rollback()


async def collect(conn: Any, tenant: str, since: datetime) -> dict[str, list[dict[str, Any]]]:
    """Every query's rows, as plain dicts. *conn* is in a read-only transaction."""
    params = {"tenant": tenant, "since": since, **CONSTANTS}
    raw: dict[str, list[dict[str, Any]]] = {}
    for name, sql in QUERIES.items():
        wanted = {k: v for k, v in params.items() if f":{k}" in sql}
        result = await conn.execute(text(sql), wanted)
        raw[name] = [dict(r) for r in result.mappings().all()]
    return raw


# ── Summary (pure) ─────────────────────────────────────────────


def _count_by(rows: Iterable[Mapping[str, Any]], vocab: str, *keys: str) -> dict[str, Any]:
    """Sum ``n`` (and *keys*) per known label; unknown labels fold into ``other``."""
    out: dict[str, Any] = {}
    for r in rows:
        name = label(r.get("label"), vocab)
        if keys:
            slot = out.setdefault(name, dict.fromkeys(("n", *keys), 0))
            for k in ("n", *keys):
                slot[k] += int(r.get(k) or 0)
        else:
            out[name] = out.get(name, 0) + int(r.get("n") or 0)
    return dict(sorted(out.items()))


def _flag_split(rows: Iterable[Mapping[str, Any]], vocab: str, flag: str) -> dict[str, Any]:
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        slot = out.setdefault(label(r.get("label"), vocab), {"n": 0, flag: 0})
        slot["n"] += int(r.get("n") or 0)
        slot[flag] += int(r.get("n") or 0) if r.get(flag) else 0
    return dict(sorted(out.items()))


def _stages(rows: Iterable[Mapping[str, Any]], key: str, vocab: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        stages = r.get(key)
        if isinstance(stages, str):  # a driver that hands back JSON text
            stages = json.loads(stages)
        if not isinstance(stages, Mapping):
            continue
        for stage, ms in stages.items():
            if isinstance(ms, int | float) and not isinstance(ms, bool):
                out[label(stage, vocab)].append(float(ms))
    return out


def summarise(
    raw: Mapping[str, Sequence[Mapping[str, Any]]], *, tenant: str, since: datetime
) -> dict[str, Any]:
    """Counts, rates and percentiles from *raw* (:func:`collect`). Labels pass :func:`label`."""
    turns = raw.get("turns", [])
    snaps = [t for t in turns if t.get("has_snapshot")]
    ok = [t for t in snaps if t.get("snapshot_ok")]
    errors = Counter(
        label(t.get("snapshot_error"), "error") for t in snaps if not t.get("snapshot_ok")
    )
    chg = [t for t in turns if t.get("has_changes")]
    chg_ok = [t for t in chg if t.get("changes_ok")]
    chg_errors = Counter(
        label(t.get("changes_error"), "error") for t in chg if not t.get("changes_ok")
    )

    days: dict[str, dict[str, int]] = {}
    for t in turns:
        day = t["day"].isoformat() if hasattr(t.get("day"), "isoformat") else str(t.get("day"))
        d = days.setdefault(
            day,
            dict.fromkeys(
                (
                    "snapshots",
                    "memory_items",
                    "world_time_known",
                    "relations",
                    "conflicts",
                    "changes",
                ),
                0,
            ),
        )
        d["snapshots"] += 1 if t.get("snapshot_ok") else 0
        for k in ("memory_items", "world_time_known", "relations", "conflicts"):
            d[k] += int(t.get(k) or 0) if t.get("snapshot_ok") else 0
        d["changes"] += int(t.get("changes") or 0) if t.get("changes_ok") else 0

    memory_items = sum(int(t.get("memory_items") or 0) for t in ok)
    wtk = sum(int(t.get("world_time_known") or 0) for t in ok)
    suppressed: Counter[str] = Counter()
    for name, values in _stages(chg_ok, "suppressed", "suppressed").items():
        suppressed[name] += int(sum(values))

    mem = (raw.get("memories") or [{}])[0]
    sup = (raw.get("supersession") or [{}])[0]
    world: dict[str, Counter[str]] = {"precision": Counter(), "source": Counter()}
    for r in raw.get("world_time", []):
        world["precision"][label(r.get("precision"), "wt_precision")] += int(r.get("n") or 0)
        world["source"][label(r.get("source"), "wt_source")] += int(r.get("n") or 0)
    contradictions: dict[str, dict[str, int]] = {}
    for r in raw.get("contradictions", []):
        slot = contradictions.setdefault(
            label(r.get("label"), "confidence"),
            {"pending": 0, "applied": 0, "created_since": 0, "not_queued": 0},
        )
        slot["pending"] += int(r.get("n") or 0)
        slot["applied"] += int(r.get("n") or 0) if r.get("applied") else 0
        slot["created_since"] += int(r.get("created_since") or 0)
        slot["not_queued"] += int(r.get("not_queued") or 0)

    return {
        "tenant": tenant,
        "since": since.isoformat(),
        "snapshot": {
            "turns_traced": len(snaps),
            "turns_with_snapshot": len(ok),
            "errors": dict(sorted(errors.items())),
            "abstain_rate": rate(sum(1 for t in ok if t.get("abstain")), len(ok)),
            "insufficient_rate": rate(sum(1 for t in ok if t.get("insufficient")), len(ok)),
            "abstention_reasons": _count_by(raw.get("abstention_reasons", []), "abstention_reason"),
            "items_per_turn": spread([t.get("items") for t in ok]),
            "items_by_kind": _count_by(raw.get("item_kinds", []), "ref_kind", "world_time_known"),
            "memory_items": memory_items,
            "world_time_known": wtk,
            "world_time_known_share": rate(wtk, memory_items),
            "relations_per_turn": spread([t.get("relations") for t in ok]),
            "relation_types": _count_by(raw.get("relation_types", []), "relation_type"),
            "conflict_kinds": _count_by(raw.get("conflict_kinds", []), "conflict_kind"),
            "decision_items": _flag_split(
                raw.get("decision_items", []), "decision_status", "confirmed"
            ),
            "ms": spread([t.get("ms") for t in snaps]),
            "timings_ms": {
                s: spread(v) for s, v in sorted(_stages(ok, "timings_ms", "timing_stage").items())
            },
        },
        "changes": {
            "turns_traced": len(chg),
            "turns_compared": len(chg_ok),
            "errors": dict(sorted(chg_errors.items())),
            "baseline_found_rate": rate(
                sum(1 for t in chg_ok if t.get("baseline_found")), len(chg_ok)
            ),
            "insufficient_rate": rate(
                sum(1 for t in chg_ok if t.get("changes_insufficient")), len(chg_ok)
            ),
            "read_failed": sum(1 for t in chg_ok if t.get("read_failed")),
            "changes_per_turn": spread([t.get("changes") for t in chg_ok]),
            "kinds": _flag_split(raw.get("change_kinds", []), "change_kind", "acknowledged"),
            "suppressed": dict(sorted(suppressed.items())),
            "ms": spread([t.get("changes_ms") for t in chg]),
        },
        "days": dict(sorted(days.items())),
        "ingestion": {
            "memories_created": int(mem.get("created") or 0),
            "with_world_time": int(mem.get("with_world_time") or 0),
            "world_time_precision": dict(sorted(world["precision"].items())),
            "world_time_source": dict(sorted(world["source"].items())),
            "valid_until_by_supersession": int(sup.get("ended_all") or 0),
            "valid_until_by_supersession_since": int(sup.get("ended_since") or 0),
            "superseded_since": int(sup.get("superseded_since") or 0),
            "typed_links_by_type": _count_by(raw.get("typed_links", []), "relation_type"),
            "decisions_by_status": _count_by(
                raw.get("decisions", []), "decision_status", "created_since"
            ),
            "pending_contradictions_by_confidence": dict(sorted(contradictions.items())),
        },
    }


# ── Output ─────────────────────────────────────────────────────


def _pct(v: float | None) -> str:
    return "-" if v is None else f"{100 * v:.1f}%"


def _sp(s: Mapping[str, Any]) -> str:
    return f"p50 {s['p50'] if s['p50'] is not None else '-'}  p95 {s['p95'] if s['p95'] is not None else '-'}  max {s['max'] if s['max'] is not None else '-'}  (n {s['n']})"


def _kv(d: Mapping[str, Any]) -> str:
    if not d:
        return "none"
    return ", ".join(
        f"{k} {v}"
        if not isinstance(v, Mapping)
        else f"{k} " + "/".join(f"{x}:{y}" for x, y in v.items())
        for k, v in d.items()
    )


def render(s: Mapping[str, Any]) -> str:
    sn, ch, ing = s["snapshot"], s["changes"], s["ingestion"]
    lines = [
        f"shadow context structure: tenant {s['tenant']}, since {s['since']}",
        "",
        "== snapshot",
        f"  turns traced {sn['turns_traced']}, with a snapshot {sn['turns_with_snapshot']}, errors {_kv(sn['errors'])}",
        f"  abstain {_pct(sn['abstain_rate'])} ({_kv(sn['abstention_reasons'])}), insufficient {_pct(sn['insufficient_rate'])}",
        f"  items per turn: {_sp(sn['items_per_turn'])}",
        f"  items by kind: {_kv(sn['items_by_kind'])}",
        f"  memory items {sn['memory_items']}, world_time_known {sn['world_time_known']} ({_pct(sn['world_time_known_share'])})",
        f"  relations per turn: {_sp(sn['relations_per_turn'])}",
        f"  relation types: {_kv(sn['relation_types'])}",
        f"  conflict kinds: {_kv(sn['conflict_kinds'])}",
        f"  decision items by status: {_kv(sn['decision_items'])}",
        f"  ms: {_sp(sn['ms'])}",
    ]
    lines += [f"    {stage:<11} {_sp(v)}" for stage, v in sn["timings_ms"].items()]
    lines += [
        "",
        "== changes",
        f"  turns traced {ch['turns_traced']}, compared {ch['turns_compared']}, errors {_kv(ch['errors'])}",
        f"  baseline found {_pct(ch['baseline_found_rate'])}, insufficient {_pct(ch['insufficient_rate'])}, read_failed {ch['read_failed']}",
        f"  changes per turn: {_sp(ch['changes_per_turn'])}",
        f"  kinds (n/acknowledged): {_kv(ch['kinds'])}",
        f"  suppressed: {_kv(ch['suppressed'])}",
        f"  ms: {_sp(ch['ms'])}",
        "",
        "== per day (snapshots, memory items, world_time_known, relations, conflicts, changes)",
    ]
    lines += [
        f"  {day}  {d['snapshots']:>4} {d['memory_items']:>6} {d['world_time_known']:>6} "
        f"{d['relations']:>5} {d['conflicts']:>5} {d['changes']:>5}"
        for day, d in s["days"].items()
    ] or ["  none"]
    lines += [
        "",
        "== ingestion",
        f"  memories created {ing['memories_created']}, with properties.world_time {ing['with_world_time']}",
        f"  world time precision: {_kv(ing['world_time_precision'])}; source: {_kv(ing['world_time_source'])}",
        f"  valid_until_by=supersession: {ing['valid_until_by_supersession']} all time, "
        f"{ing['valid_until_by_supersession_since']} updated since; superseded since {ing['superseded_since']}",
        f"  extraction links by type: {_kv(ing['typed_links_by_type'])}",
        f"  decisions by status (n/created_since): {_kv(ing['decisions_by_status'])}",
        f"  pending contradictions by confidence: {_kv(ing['pending_contradictions_by_confidence'])}",
    ]
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────

_DAYS = re.compile(r"^(\d{1,4})d?$")


def parse_since(value: str, now: datetime | None = None) -> datetime:
    """``7`` or ``7d`` (days back from now), or an ISO date or time (UTC when naive)."""
    now = now or datetime.now(UTC)
    m = _DAYS.match(value.strip())
    if m:
        return now - timedelta(days=int(m.group(1)))
    try:
        when = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--since: days (7, 7d) or an ISO date, got {value!r}"
        ) from exc
    return when if when.tzinfo else when.replace(tzinfo=UTC)


async def run(tenant: str, since: datetime) -> dict[str, Any]:
    from life_graph.storage.database import engine

    try:
        async with read_only(engine) as conn:
            raw = await collect(conn, tenant, since)
    finally:
        await engine.dispose()
    return summarise(raw, tenant=tenant, since=since)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--since", type=parse_since, default=parse_since("7"))
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = ap.parse_args(argv)
    summary = asyncio.run(run(args.tenant, args.since))
    print(json.dumps(summary, indent=2, sort_keys=True) if args.json else render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
