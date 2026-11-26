#!/usr/bin/env python3
"""Synthetic evaluation of the M8 context snapshot (services/memory/snapshot.py).

Each case in `evals/context/cases.json` is seeded into a throwaway tenant
(``m3eval_<hex>``, the production retrieval arm's pattern and cleanup), plus a
second throwaway tenant when the case tests isolation. The snapshot is then
assembled through the shipped code -- retrieve() with the judge off, the
exclusion search, decisions, intentions, conflicts -- with the arm's
deterministic hashing embedder (no network, no model), and every row is
deleted again, also on failure. Synthetic data only.

Reported per category, never as one score (spec section 8):

* precision / recall of the records the case says must be current;
* current_violations: a record the case says must never be current was
  included (expired, superseded, pending, hostile) -- target 0;
* conflicts_found / conflicts_expected, and unexpected conflicts;
* field_mismatches: origin, confirmed, label, freshness ... as the case says;
* cross_tenant_items: an id of the other tenant anywhere in the snapshot;
* provenance_coverage: items whose source_ref resolves to a seeded record;
* insufficient_correct, budget_violations, determinism_failures;
* latency p50/p95 (ms) of assemble_context, over --repeat runs per case.

`--verify` exits non-zero when a zero-target count is not zero, or when a
rate is more than 0.05 below the committed baseline
(`evals/context/baseline.json`). Latency is reported, not gated: CI machines
vary. Record a new baseline on purpose with `--write-baseline`.

Needs Postgres with pgvector. By default it uses the integration test
database (the configured name with `_test` appended), as
scripts/eval_production_retrieval.py does:

    set -a; . <(grep -E '^LIFE_GRAPH_(DATABASE_URL|DATABASE_URL_SYNC|REDIS_URL)=' .env); set +a
    python scripts/eval_context_snapshot.py --verify
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES_PATH = ROOT / "evals" / "context" / "cases.json"
BASELINE_PATH = ROOT / "evals" / "context" / "baseline.json"
#: Counts whose target is zero, always gated.
ZERO_TARGETS = (
    "current_violations",
    "field_mismatches",
    "cross_tenant_items",
    "budget_violations",
    "determinism_failures",
    "unexpected_conflicts",
)
#: Rates gated against the baseline, with this much slack.
RATES = ("precision", "recall", "conflict_recall", "provenance_coverage", "insufficient_accuracy")
TOLERANCE = 0.05


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


def _ago(now: datetime, days: float | None) -> datetime | None:
    return None if days is None else now - timedelta(days=float(days))


async def _seed(tenant: str, spec: dict[str, Any], now: datetime) -> dict[str, str]:
    """Write *spec*'s records for *tenant*; returns key -> id."""
    from life_graph.evals import production_retrieval_arm as arm
    from life_graph.models.db import Approval, Decision, Intention, Memory
    from life_graph.storage.database import async_session

    ids: dict[str, str] = {}
    mems: dict[str, Any] = {}
    decs: dict[str, Any] = {}
    async with async_session() as s:
        for m in spec.get("memories", []):
            created = _ago(now, m.get("days_ago", 3))
            props = dict(m.get("properties") or {})
            row = Memory(
                id=uuid.uuid4(),
                tenant_id=tenant,
                content=m["content"],
                content_hash=hashlib.sha256(f"{m['content']}{uuid.uuid4()}".encode()).hexdigest(),
                properties=props,
                importance=0.6,
                confidence=0.9,
                source_type=m.get("source_type", "chat"),
                trust_tier=m.get("trust_tier", "self"),
                extraction_tier=m.get("extraction_tier"),
                status=m.get("status", "active"),
                created_at=created,
                updated_at=created,
                valid_from=_ago(now, m.get("valid_from_days_ago")) or created,
                valid_until=_ago(now, m.get("valid_until_days_ago")),
                embedding=arm._embed(m["content"]),
            )
            s.add(row)
            mems[m["key"]] = (row, m)
        for d in spec.get("decisions", []):
            row = Decision(
                id=uuid.uuid4(),
                tenant_id=tenant,
                title=d["title"],
                status=d.get("status", "candidate"),
                source=d.get("source", "conversation"),
                created_at=_ago(now, d.get("days_ago", 2)),
            )
            s.add(row)
            decs[d["key"]] = (row, d)
        for i in spec.get("intentions", []):
            row = Intention(
                id=uuid.uuid4(),
                tenant_id=tenant,
                content=i["content"],
                status=i.get("status", "pending"),
                created_at=_ago(now, i.get("days_ago", 2)),
                expires_at=_ago(now, i.get("expires_days_ago")),
            )
            s.add(row)
            ids[i["key"]] = str(row.id)
        await s.flush()
        # Supersession: the old row points at the new one and is marked replaced.
        for _key, (row, m) in mems.items():
            newer = m.get("superseded_by")
            if newer:
                new_row = mems[newer][0]
                row.superseded_by = new_row.id
                row.status = m.get("status", "superseded")
                row.properties = {**row.properties, "superseded_at": new_row.created_at.isoformat()}
                new_row.supersedes = row.id
        for _key, (row, d) in decs.items():
            if d.get("superseded_by"):
                row.superseded_by = decs[d["superseded_by"]][0].id
        for a in spec.get("approvals", []):
            old, new = str(mems[a["old"]][0].id), str(mems[a["new"]][0].id)
            s.add(
                Approval(
                    tenant_id=tenant,
                    kind="contradiction",
                    source="judgment",
                    source_ref=f"{old}|{new}",
                    title="Review a suspected contradiction",
                    payload={"memory_id_old": old, "memory_id_new": new, "applied": False},
                )
            )
        await s.commit()
    ids.update({k: str(v[0].id) for k, v in mems.items()})
    ids.update({k: str(v[0].id) for k, v in decs.items()})
    return ids


async def _cleanup(tenant: str) -> int:
    from sqlalchemy import text

    from life_graph.evals import production_retrieval_arm as arm
    from life_graph.storage.database import async_session

    # life_graph.decisions is outside the public schema the arm's cleanup walks.
    async with async_session() as s:
        await s.execute(
            text("DELETE FROM life_graph.decisions WHERE tenant_id = :t"), {"t": tenant}
        )
        await s.commit()
    return await arm.cleanup_tenant(tenant)


# ── Scoring ───────────────────────────────────────────────────


def _score_case(case: dict, snap: Any, ids: dict[str, str], other_ids: set[str]) -> dict:
    expect = case.get("expect", {})
    by_id = {v: k for k, v in ids.items()}
    items = {i.source_ref.id: i for i in snap.items}
    included = {by_id[i] for i in items if i in by_id}
    current = set(expect.get("current", []))
    forbidden = set(expect.get("not_current", []))
    out: dict[str, Any] = {
        "items": len(snap.items),
        "resolvable": sum(1 for i in items if i in by_id),
        "true_positive": len(included & current),
        "expected_current": len(current),
        "current_violations": len(included & forbidden),
    }
    pairs = {tuple(s.source_ref.id for s in c.sides) for c in snap.conflicts}
    expected_pairs = [tuple(ids[k] for k in pair) for pair in expect.get("conflicts", [])]
    out["conflicts_expected"] = len(expected_pairs)
    out["conflicts_found"] = sum(1 for p in expected_pairs if p in pairs)
    unexpected = len(pairs - set(expected_pairs))
    out["unexpected_conflicts"] = (
        unexpected if (expect.get("no_conflicts") or expected_pairs) else 0
    )
    mismatches = []
    for key, fields in expect.get("fields", {}).items():
        item = items.get(ids[key])
        if item is None:
            mismatches.append(f"{key}: not included")
            continue
        for name, want in fields.items():
            if getattr(item, name) != want:
                mismatches.append(f"{key}.{name}: {getattr(item, name)!r} != {want!r}")
    out["field_mismatches"] = len(mismatches)
    out["mismatch_detail"] = mismatches
    blob = json.dumps(snap.to_dict())
    out["cross_tenant_items"] = sum(1 for oid in other_ids if oid in blob)
    want_insufficient = bool(expect.get("insufficient", False))
    out["insufficient_cases"] = 1
    out["insufficient_correct"] = int(snap.insufficient == want_insufficient)
    budget = snap.budget
    over = dict(snap.exclusions).get("over_budget", 0)
    over_min = (expect.get("budget") or {}).get("over_budget_min", 0)
    out["budget_violations"] = int(
        len(snap.items) > budget.max_items
        or snap.content_chars > budget.max_chars
        or any(len(i.content) > budget.item_chars for i in snap.items)
        or over < over_min
    )
    out["score_retrieval"] = case.get("score_retrieval", True)
    return out


def _rate(num: float, den: float) -> float:
    return round(num / den, 4) if den else 1.0


def _summarise(rows: list[dict]) -> dict:
    scored = [r for r in rows if r["score_retrieval"]]
    items = sum(r["items"] for r in scored)
    tp = sum(r["true_positive"] for r in scored)
    out = {
        "cases": len(rows),
        "precision": _rate(tp, items),
        "recall": _rate(tp, sum(r["expected_current"] for r in scored)),
        "conflict_recall": _rate(
            sum(r["conflicts_found"] for r in rows), sum(r["conflicts_expected"] for r in rows)
        ),
        "provenance_coverage": _rate(
            sum(r["resolvable"] for r in rows), sum(r["items"] for r in rows)
        ),
        "insufficient_accuracy": _rate(
            sum(r["insufficient_correct"] for r in rows), sum(r["insufficient_cases"] for r in rows)
        ),
    }
    for key in ZERO_TARGETS:
        out[key] = sum(r.get(key, 0) for r in rows)
    return out


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return round(ordered[idx], 2)


# ── Run ───────────────────────────────────────────────────────


async def _run_case(case: dict, repeat: int) -> tuple[dict, list[float]]:
    from life_graph.core.tenant import tenant_scope
    from life_graph.evals import production_retrieval_arm as arm
    from life_graph.services.memory.snapshot import DEFAULT_BUDGET, Budget, assemble_context

    now = datetime.now(UTC)
    tenant, other = arm.new_tenant(), arm.new_tenant()
    latencies: list[float] = []
    try:
        ids = await _seed(tenant, case, now)
        other_ids = set((await _seed(other, case.get("other_tenant", {}), now)).values())
        as_of = _ago(now, case.get("as_of_days_ago"))
        budget = Budget(**case["budget"]) if case.get("budget") else DEFAULT_BUDGET
        dumps = []
        snap = None
        with arm.production_fakes(), tenant_scope(tenant):
            for _ in range(max(2, repeat)):
                t0 = time.perf_counter()
                snap = await assemble_context(case["query"], as_of=as_of, budget=budget, now=now)
                latencies.append((time.perf_counter() - t0) * 1000.0)
                dumps.append(json.dumps(snap.to_dict(), sort_keys=True))
        row = _score_case(case, snap, ids, other_ids)
        row["determinism_failures"] = int(len(set(dumps)) != 1)
    finally:
        left = await _cleanup(tenant) + await _cleanup(other)
    row["rows_left"] = left
    return row, latencies


async def run(cases_path: Path, repeat: int) -> dict:
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    by_cat: dict[str, list[dict]] = {}
    per_case: dict[str, dict] = {}
    latencies: list[float] = []
    for case in data["cases"]:
        row, lat = await _run_case(case, repeat)
        latencies += lat
        by_cat.setdefault(case["category"], []).append(row)
        per_case[case["id"]] = {
            k: row[k] for k in ("items", "true_positive", "expected_current", "current_violations")
        } | {"mismatches": row["mismatch_detail"], "p50_ms": round(statistics.median(lat), 2)}
    return {
        "benchmark": "life_graph_context_snapshot_v1",
        "cases_file": str(cases_path.relative_to(ROOT)),
        "cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "embedder": "fake_embedding (hashed words + trigrams, deterministic, no network)",
        "judge": "off (retrieve(judge=False)); no model call",
        "by_category": {cat: _summarise(rows) for cat, rows in sorted(by_cat.items())},
        "overall": _summarise([r for rows in by_cat.values() for r in rows]),
        "latency_ms": {
            "runs": len(latencies),
            "p50": _pct(latencies, 0.5),
            "p95": _pct(latencies, 0.95),
            "max": round(max(latencies), 2) if latencies else 0.0,
        },
        "rows_left_after_cleanup": sum(r["rows_left"] for rows in by_cat.values() for r in rows),
        "cases": per_case,
    }


def baseline_of(report: dict) -> dict:
    return {
        "by_category": {
            cat: {k: v for k, v in entry.items() if k in RATES}
            for cat, entry in report["by_category"].items()
        }
    }


def regressions(report: dict, baseline: dict) -> list[str]:
    fails: list[str] = []
    for cat, entry in report["by_category"].items():
        for key in ZERO_TARGETS:
            if entry[key]:
                fails.append(f"{cat}.{key} = {entry[key]} (target 0)")
        for key, floor in baseline.get("by_category", {}).get(cat, {}).items():
            if entry.get(key, 0.0) < floor - TOLERANCE:
                fails.append(f"{cat}.{key} = {entry[key]} < baseline {floor} - {TOLERANCE}")
    for cat in baseline.get("by_category", {}):
        if cat not in report["by_category"]:
            fails.append(f"{cat}: category missing from this run")
    if report["rows_left_after_cleanup"]:
        fails.append(f"{report['rows_left_after_cleanup']} throwaway rows left behind")
    return fails


def _print(report: dict) -> None:
    print(f"Context snapshot eval ({report['embedder']}; judge {report['judge']})")
    head = (
        f"{'category':<28} {'n':>2} {'P':>6} {'R':>6} {'confl':>6} {'prov':>6} {'insuf':>6} "
        f"{'viol':>4} {'fld':>4} {'xten':>4} {'bud':>4} {'det':>4}"
    )
    print(head)
    print("-" * len(head))
    for cat, e in [*report["by_category"].items(), ("OVERALL", report["overall"])]:
        print(
            f"{cat:<28} {e['cases']:>2} {e['precision']:>6.3f} {e['recall']:>6.3f} "
            f"{e['conflict_recall']:>6.3f} {e['provenance_coverage']:>6.3f} "
            f"{e['insufficient_accuracy']:>6.3f} {e['current_violations']:>4} "
            f"{e['field_mismatches']:>4} {e['cross_tenant_items']:>4} "
            f"{e['budget_violations']:>4} {e['determinism_failures']:>4}"
        )
    lat = report["latency_ms"]
    print(
        f"latency over {lat['runs']} runs: p50 {lat['p50']} ms, p95 {lat['p95']} ms, max {lat['max']} ms"
    )
    for cid, c in report["cases"].items():
        if c["mismatches"]:
            print(f"  {cid}: {'; '.join(c['mismatches'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--output", type=Path, default=None, help="Write the report JSON here")
    parser.add_argument("--repeat", type=int, default=5, help="Snapshot runs per case (min 2)")
    parser.add_argument("--verify", action="store_true", help="Exit non-zero on a regression")
    parser.add_argument("--write-baseline", action="store_true")
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
    if args.write_baseline:
        args.baseline.write_text(json.dumps(baseline_of(report), indent=2) + "\n", encoding="utf-8")
        print(f"Wrote baseline {args.baseline.name}")
    fails = regressions(report, json.loads(args.baseline.read_text()) if args.verify else {})
    if fails:
        print("FAIL:\n  " + "\n  ".join(fails), file=sys.stderr)
        return 1 if (args.verify or report["rows_left_after_cleanup"]) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
