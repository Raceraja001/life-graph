#!/usr/bin/env python3
"""Does the M8 context layer assemble useful personal context? (synthetic, local only)

The other context evals check single rules on tiny cases (evals/context,
evals/context_changes). This one asks the owner's real questions -- current
priorities, active goals, open commitments, decisions, what changed at work,
blocked projects, deadlines, money constraints, what is missing -- over one
invented person's whole life (`evals/context_quality/dataset.json`), and scores
what `assemble_context` hands back against gold labels
(`evals/context_quality/questions.json`). Question O6 runs the Stage 2 path
(`changes.detect`) against an earlier turn's trace.

The data is stored the way Life Graph stores it: memories with their
provenance columns, status, valid time and supersession; entities and
memory_entities through services/entities.py ``link``; ASSOCIATED links
through services/memory/associations.py ``said_together``; typed memory_links
rows; life_graph.decisions; intentions; pending contradiction approvals. A
look-alike second tenant (same names, other facts) is seeded next to it, and
some records carry prompt-injection text. Every row lives in throwaway
tenants (``m3eval_<hex>``) of the integration test database and is deleted
again, also on failure.

Arms
====

* ``hashing`` -- the deterministic hashing embedder of
  life_graph/evals/production_retrieval_arm.py. No network. This is the CI arm.
* ``bge-m3`` -- production's embedding model served by the local Ollama
  (``--ollama-url``, default http://127.0.0.1:11434). Every text is embedded
  once, up front. Local only; skipped with a note when Ollama is not there.
* ``ingest`` -- the same world built through the save path instead of seeded
  rows (scripts/context_quality_ingest.py): each record's owner message
  (English, Tamil or Tanglish, ``evals/context_quality/ingest_fixtures.json``)
  goes through the capture spine, Jarvis's memory_save or distillation with
  the M8 ingestion flags on, the extractor replaying the *recorded*
  output of the local extraction model (no model call), and the owner's
  decision moves through the owner's service calls. Hashing embedder. The
  same questions then show what ingestion writes against the gold structure,
  and the report adds "ingestion vs gold" (supersession chains, typed links,
  pending contradictions, memory states, decisions). Record the extractor's
  answers again with ``--record-fixtures`` (local Ollama only).
* ``answer`` (optional, ``--answer``) -- the existing local synthesis path
  (services/synthesis.py SynthesisService, ``chat_local_only``) on the local
  Ollama (``--answer-model``, default qwen3:14b), fed the snapshot items of
  the bge-m3 arm (hashing when bge-m3 did not run). Rule-based checks against
  gold words. Skipped with a note when Ollama chat does not answer.

No model is ever built for the cloud: the cloud chat route, the resilient
(cloud) chain and LiteLLM's completion count a call and raise while the eval
runs, and the snapshot arms also refuse any chat client at all.

Metrics, reported per category and per question, never as one score
=================================================================

* precision -- items that are required or acceptable / all items;
* recall -- required records that are items / required records;
* forbidden_as_current -- an item that must not be current (superseded,
  expired, archived, pending, hostile, other tenant, completed/dismissed
  intention, discarded decision, or one the question forbids) -- target 0;
* current_vs_historical / temporal -- per labelled record: a current one is an
  item, a historical one is not; a ``future_due`` one is an item that carries
  a machine-readable due time; a ``resolved`` one is absent or explicitly tied
  to what resolved it (a conflict or a relation between the two);
* relationships -- both ends of each expected pair present, and separately
  whether the snapshot carries an explicit relation between them (a conflict,
  or a typed link in ``relations``, either direction) or only co-occurrence;
* conflicts -- each expected disagreement present with both sides;
* provenance coverage -- items that resolve to a seeded record and carry an
  origin, evidence label and recorded time; origin accuracy -- origin and
  confirmed match the record's gold;
* abstention -- ``insufficient`` as the gold says; ``flag_missing`` questions
  need an explicit "something is missing" signal;
* cross-tenant leakage (ids or look-alike facts) -- target 0;
* cloud model calls -- target 0; latency p50/p95 of assemble_context;
* answer arm: evidence-supported answers, unsupported claims, abstention.

`--verify` (hashing arm) exits non-zero when a zero-tolerance count is not
zero (leakage, cloud calls, forbidden-as-current, rows left behind) or a rate
falls more than 0.05 (or one item, for a rate out of fewer than 20) below the
committed baseline
(`evals/context_quality/baseline.json`). The baseline records what the system
does today, weak categories included; it is a floor against regressions, not
a target. Record it on purpose with `--write-baseline`, which writes the floors
of the arms that ran and keeps the others.

With the ``ingest`` arm in ``--arms``, `--verify` also fails when its
fixtures do not fit the dataset, or on leaks, cloud model calls or rows left
behind; its rates and its forbidden-as-current count are held to the
``ingest`` floors in the baseline once they are recorded. Forbidden-as-current
is not zero-tolerance there: a superseded record that ingestion failed to
supersede is shown as current, and that is what the arm measures.

    set -a; . <(grep -E '^LIFE_GRAPH_(DATABASE_URL|DATABASE_URL_SYNC|REDIS_URL)=' .env); set +a
    python scripts/eval_context_quality.py --verify                 # hashing arm only
    python scripts/eval_context_quality.py --arms hashing,ingest --verify   # the CI step
    python scripts/eval_context_quality.py --arms ingest --write-baseline --write-report
    python scripts/eval_context_quality.py --record-fixtures         # local Ollama, no DB
    python scripts/eval_context_quality.py --arms hashing,bge-m3 --answer --write-report

Precision experiments (services/memory/snapshot_experiments.py, eval-only):
``--experiments A,B,...`` (letters or names: A rank, B query_type, C links,
D dedupe, E evidence, F budget, G hub, H undated, I goals, J overview,
K domain) runs the snapshot questions with those
options on. ``--xp-set NAME=VALUE`` sets one of the module's TUNABLE
constants for the run (passed with each call, never set on the module),
``--mode recall|precision`` a production precision mode (MODES: its fixed set
and values; --experiments and --xp-set add to it), ``--max-items N`` a
tighter hard budget, and
``--split tune|test`` only half of the questions, by a stable hash of the
question id (tune on one half, report on the other). All four are recorded
in the report JSON (``run``); with none of them the run and the report are
what they were. They cannot write the committed report or baseline: use
``--output``. Change detection (O6's ``changes`` mode) always runs without
experiments.

    python scripts/eval_context_quality.py --arms bge-m3 --experiments B,F --split tune \
        --output /tmp/xp_bf_tune.json

Each snapshot question's row carries ``item_log`` (per item: gold key, kind,
reason, score and source block; labels only, no content) and the
standing-block counts, and every summary gives ``precision_without_standing``
next to ``precision``.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import logging
import os
import statistics
import sys
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import context_quality_ingest as ingest  # noqa: E402 — needs ROOT on sys.path

DIR = ROOT / "evals" / "context_quality"
DATASET_PATH = DIR / "dataset.json"
QUESTIONS_PATH = DIR / "questions.json"
BASELINE_PATH = DIR / "baseline.json"
REPORT_JSON = DIR / "report.json"
REPORT_MD = DIR / "report.md"

CATEGORIES = ("O", "A", "B", "C", "D", "E", "F", "G")
#: Question-independent reasons (services/memory/snapshot.STANDING_REASONS).
STANDING = frozenset({"due_intention", "current_decision"})
#: Reason -> the block of the snapshot that brought the item.
BLOCKS = {
    "search_hit": "search",
    "entity_link": "expansion",
    "neighbour": "expansion",
    "dated_episode": "expansion",
    "cold_tier": "expansion",
    "decision": "keyword",
    "open_intention": "keyword",
    "due_intention": "standing",
    "current_decision": "standing",
    "linked_evidence": "typed_link",
}
SPLITS = ("tune", "test")
CATEGORY_NAMES = {
    "O": "owner's ten",
    "A": "personal",
    "B": "professional",
    "C": "financial",
    "D": "learning",
    "E": "temporal",
    "F": "relationships",
    "G": "uncertainty",
}
#: Record states that must never be an item (unless a question asks for that time).
NOT_CURRENT = frozenset(
    {
        "superseded",
        "expired",
        "archived",
        "pending",
        "hostile",
        "completed",
        "dismissed",
        "discarded",
    }
)
#: Temporal labels read as "this is history, not now".
HISTORICAL = frozenset(
    {"superseded", "expired", "historical", "pending", "completed", "dismissed", "not_yet_valid"}
)
CURRENT_VS_HISTORICAL = frozenset({"current", "resolved"}) | HISTORICAL
#: Item fields that would carry a machine-readable due time (none exists today).
DUE_FIELDS = ("due", "due_at", "trigger_time", "expires_at", "deadline")
ZERO_TOLERANCE = ("cross_tenant_leaks", "cloud_model_calls", "forbidden_as_current")
#: The ingest arm's zero-tolerance counts (forbidden-as-current is a floor there).
INGEST_ZERO = ("cross_tenant_leaks", "cloud_model_calls", "rows_left_after_cleanup")
RATES = (
    "precision",
    "recall",
    "current_vs_historical",
    "temporal",
    "relationship_both_ends",
    "conflict_recall",
    "provenance_coverage",
    "origin_accuracy",
    "field_accuracy",
    "abstention_accuracy",
)
#: Slack below the baseline: 0.05, or one item when a rate is out of fewer than 20.
TOLERANCE = 0.05
OLLAMA_URL = "http://127.0.0.1:11434"


# ── Database ──────────────────────────────────────────────────


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


def load() -> tuple[dict[str, Any], dict[str, Any]]:
    data = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    return data, questions


# ── Seeding ───────────────────────────────────────────────────


def _at(now: datetime, days: float | None) -> datetime | None:
    return None if days is None else now + timedelta(days=float(days))


@dataclass
class World:
    """One throwaway tenant: its rows by dataset key."""

    tenant: str
    now: datetime
    kind: dict[str, str] = field(default_factory=dict)
    rows: dict[str, Any] = field(default_factory=dict)
    specs: dict[str, dict[str, Any]] = field(default_factory=dict)

    def ids(self) -> dict[str, str]:
        return {str(row.id): key for key, row in self.rows.items()}


def _memory_row(tenant: str, m: dict[str, Any], now: datetime) -> Any:
    from life_graph.evals import production_retrieval_arm as arm
    from life_graph.models.db import Memory

    created = _at(now, m.get("created_d", -3))
    props: dict[str, Any] = {}
    if m.get("fact_type"):
        props["fact_type"] = m["fact_type"]
    if m.get("entities"):
        props["entities"] = list(m["entities"])
    return Memory(
        id=uuid.uuid4(),
        tenant_id=tenant,
        content=m["content"],
        content_hash=hashlib.sha256(f"{m['content']}{uuid.uuid4()}".encode()).hexdigest(),
        properties=props,
        tags=m.get("tags"),
        importance=0.6,
        confidence=0.9,
        source_type=m.get("source_type", "chat"),
        trust_tier=m.get("trust_tier", "self"),
        extraction_tier=m.get("extraction_tier"),
        status=m.get("status", "active"),
        created_at=created,
        updated_at=created,
        valid_from=_at(now, m.get("valid_from_d", m.get("created_d", -3))),
        valid_until=_at(now, m.get("valid_until_d")),
        embedding=arm._embed(m["content"]),
    )


def _decision_row(tenant: str, d: dict[str, Any], now: datetime) -> Any:
    from life_graph.models.db import Decision

    return Decision(
        id=uuid.uuid4(),
        tenant_id=tenant,
        title=d["title"],
        reasoning=d.get("reasoning"),
        status=d.get("status", "candidate"),
        source=d.get("source", "conversation"),
        domain_tags=d.get("domain_tags") or [],
        created_at=_at(now, d.get("created_d", -2)),
        decided_at=_at(now, d.get("decided_d")),
        review_at=_at(now, d.get("review_d")),
    )


def _intention_row(tenant: str, i: dict[str, Any], now: datetime) -> Any:
    from life_graph.models.db import Intention

    return Intention(
        id=uuid.uuid4(),
        tenant_id=tenant,
        content=i["content"],
        trigger_type=i.get("trigger_type", "time"),
        trigger_time=_at(now, i.get("trigger_d")),
        context_match=i.get("context_match"),
        status=i.get("status", "pending"),
        created_at=_at(now, i.get("created_d", -2)),
        expires_at=_at(now, i.get("expires_d")),
        completed_at=_at(now, i.get("completed_d")),
    )


async def seed(world: World, spec: dict[str, Any]) -> None:
    """Write *spec*'s records into *world*'s tenant, through the real link paths."""
    from life_graph.models.db import Approval, MemoryLink
    from life_graph.services import entities
    from life_graph.services.memory import associations
    from life_graph.storage.database import async_session

    new_keys: list[str] = []
    async with async_session() as s:
        for kind, build, group in (
            ("memory", _memory_row, "memories"),
            ("decision", _decision_row, "decisions"),
            ("intention", _intention_row, "intentions"),
        ):
            for rec in spec.get(group, []):
                row = build(world.tenant, rec, world.now)
                s.add(row)
                world.rows[rec["key"]] = row
                world.kind[rec["key"]] = kind
                world.specs[rec["key"]] = rec
                new_keys.append(rec["key"])
        await s.flush()
        for key in new_keys:
            rec, row = world.specs[key], world.rows[key]
            newer = rec.get("superseded_by")
            if not newer or newer not in world.rows:
                continue
            new_row = world.rows[newer]
            row.superseded_by = new_row.id
            if world.kind[key] == "memory":
                row.status = rec.get("status", "superseded")
                row.properties = {**row.properties, "superseded_at": new_row.created_at.isoformat()}
                new_row.supersedes = row.id
        for link in spec.get("typed_links", []):
            s.add(
                MemoryLink(
                    source_memory_id=world.rows[link["a"]].id,
                    target_memory_id=world.rows[link["b"]].id,
                    link_type=link["type"],
                    strength=0.7,
                    properties={"why": link.get("why", "")},
                    tenant_id=world.tenant,
                )
            )
        for a in spec.get("approvals", []):
            old, new = str(world.rows[a["old"]].id), str(world.rows[a["new"]].id)
            s.add(
                Approval(
                    tenant_id=world.tenant,
                    kind="contradiction",
                    source="judgment",
                    source_ref=f"{old}|{new}",
                    title="Review a suspected contradiction",
                    payload={"memory_id_old": old, "memory_id_new": new, "applied": False},
                    created_at=_at(world.now, a.get("created_d", -1)),
                )
            )
        await s.commit()
    groups: dict[str, list[Any]] = {}
    for key in new_keys:
        rec = world.specs[key]
        if world.kind[key] != "memory":
            continue
        if rec.get("entities"):
            await entities.link(world.tenant, world.rows[key].id, rec["entities"])
        if rec.get("said_with"):
            groups.setdefault(rec["said_with"], []).append(world.rows[key].id)
    for ids in groups.values():
        await associations.said_together(world.tenant, ids)


async def cleanup(tenant: str) -> int:
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
def model_guard(counter: dict[str, int], *, allow_local_chat: bool = False):
    """Count and refuse every cloud model route; with *allow_local_chat* off, any chat client.

    Patched for the block: LMStudioClient._cloud_chat, the resilient (cloud)
    chain getters and constructor, LiteLLM's completion; and, for the snapshot
    arms, LMStudioClient construction itself (the snapshot must call no model).
    """
    from life_graph import runtime
    from life_graph.services.llm import client as llm_client
    from life_graph.services.llm import resilient

    def refuse(name: str):
        def boom(*_a: Any, **_kw: Any) -> Any:
            counter[name] = counter.get(name, 0) + 1
            raise RuntimeError(f"model route {name} used during the context quality eval")

        return boom

    saved: list[tuple[Any, str, Any]] = [
        (llm_client.LMStudioClient, "_cloud_chat", refuse("cloud_chat")),
        (resilient.ResilientLLM, "__init__", refuse("resilient_chain")),
        (runtime, "get_resilient_llm", refuse("resilient_chain")),
        (llm_client, "get_resilient_llm", refuse("resilient_chain")),
    ]
    if not allow_local_chat:
        saved.append((llm_client.LMStudioClient, "__init__", refuse("chat_client")))
    with contextlib.suppress(ImportError):
        import litellm

        saved += [
            (litellm, "completion", refuse("litellm")),
            (litellm, "acompletion", refuse("litellm")),
        ]
    originals = [(owner, name, getattr(owner, name)) for owner, name, _ in saved]
    for owner, name, fake in saved:
        setattr(owner, name, fake)
    try:
        yield
    finally:
        for owner, name, value in originals:
            setattr(owner, name, value)


# ── Scoring ───────────────────────────────────────────────────


def _rate(num: float, den: float) -> float | None:
    return round(num / den, 4) if den else None


def _conflict_pairs(snap: Any, key_of: dict[str, str]) -> set[frozenset[str]]:
    return {
        frozenset(key_of.get(s.source_ref.id, s.source_ref.id) for s in c.sides)
        for c in snap.conflicts
    }


def _relation_pairs(snap: Any, key_of: dict[str, str]) -> set[frozenset[str]]:
    """The snapshot's typed relations as unordered pairs (none on an older snapshot)."""
    return {
        frozenset((key_of.get(r.from_ref.id, r.from_ref.id), key_of.get(r.to_ref.id, r.to_ref.id)))
        for r in getattr(snap, "relations", ())
    }


def _gold_origin(world: World, key: str) -> dict[str, Any]:
    return (world.specs.get(key) or {}).get("gold") or {}


def _temporal_ok(status: str, key: str, ctx: dict[str, Any]) -> bool:
    included, items, pairs, world = ctx["included"], ctx["items"], ctx["pairs"], ctx["world"]
    if status == "current":
        return key in included
    if status in HISTORICAL:
        return key not in included
    if status == "resolved":
        by = _gold_origin(world, key).get("resolved_by")
        return key not in included or frozenset({key, by}) in pairs | ctx["related"]
    if status == "future_due":
        item = items.get(key)
        return item is not None and any(item.to_dict().get(f) for f in DUE_FIELDS)
    return False


def _leaks(snap: Any, other: World, tokens: list[str]) -> list[str]:
    blob = json.dumps(snap.to_dict(), ensure_ascii=False)
    found = [f"id:{key}" for key, row in other.rows.items() if str(row.id) in blob]
    found += [f"text:{t}" for t in tokens if t in blob]
    return found


def _current_at_as_of(q: dict[str, Any], world: World, keys: set[str]) -> set[str]:
    """Superseded records that were still true at the question's ``as_of_d``.

    The gold ``temporal`` label describes *now*. A question about an earlier
    date (``as_of_d``) may rightly see a record replaced only later: its
    successor was created after ``as_of_d``. Such a record is history today but
    current at that date, so it is not "forbidden as current" for that question.
    """
    as_of = q.get("as_of_d")
    if as_of is None:
        return set()
    out: set[str] = set()
    for k in keys:
        spec = world.specs.get(k) or {}
        newer = spec.get("superseded_by")
        if _gold_origin(world, k).get("temporal") != "superseded" or not newer:
            continue
        succ = world.specs.get(newer) or {}
        if spec.get("created_d", 0) <= as_of < succ.get("created_d", 0):
            out.add(k)
    return out


def score_snapshot(q: dict[str, Any], snap: Any, world: World, other: World, tokens: list[str]):
    """One question's snapshot against its gold labels (counts, so categories can sum)."""
    key_of = world.ids()
    items = {key_of[i.source_ref.id]: i for i in snap.items if i.source_ref.id in key_of}
    included = set(items)
    required, acceptable = set(q.get("required", [])), set(q.get("acceptable", []))
    ok = required | acceptable
    state_bad = {k for k in world.specs if _gold_origin(world, k).get("temporal") in NOT_CURRENT}
    state_bad -= _current_at_as_of(q, world, state_bad)
    forbidden = (set(q.get("forbidden", [])) | state_bad) - ok
    pairs = _conflict_pairs(snap, key_of)
    in_conflicts = {k for p in pairs for k in p}
    related = _relation_pairs(snap, key_of)
    ctx = {"included": included, "items": items, "pairs": pairs, "world": world, "related": related}
    standing = {k for k, i in items.items() if i.reason in STANDING}
    out: dict[str, Any] = {
        "items": len(snap.items),
        "unresolved_items": len(snap.items) - len(items),
        "ok_items": len(included & ok),
        "required": len(required),
        "found_required": len(included & required),
        "missed_required": sorted(required - included),
        "forbidden_as_current": sorted(included & forbidden),
        "noise": sorted(included - ok - forbidden),
        "standing_items": len(standing),
        "ok_standing": len(standing & ok),
        "item_log": _item_log(snap, key_of),
        "insufficient": snap.insufficient,
        "missing": list(getattr(snap, "missing", ())),
        "reasons": _reasons(snap),
    }
    t_checks = q.get("temporal", {})
    t_ok = {k: _temporal_ok(v, k, ctx) for k, v in t_checks.items()}
    cvh = [k for k, v in t_checks.items() if v in CURRENT_VS_HISTORICAL]
    out["temporal_checks"], out["temporal_correct"] = len(t_ok), sum(t_ok.values())
    out["cvh_checks"], out["cvh_correct"] = len(cvh), sum(t_ok[k] for k in cvh)
    out["temporal_wrong"] = sorted(k for k, v in t_ok.items() if not v)
    rels = q.get("relations", [])
    both = [r for r in rels if all(k in included or k in in_conflicts for k in r["pair"])]
    explicit = [r for r in rels if frozenset(r["pair"]) in pairs | related]
    out["relations"], out["relations_both_ends"] = len(rels), len(both)
    out["relations_explicit"] = len(explicit)
    out["relation_detail"] = [
        {
            "pair": r["pair"],
            "relation": r["relation"],
            "stored_as": r.get("structured", "none"),
            "both_ends": r in both,
            "explicit_in_snapshot": r in explicit,
        }
        for r in rels
    ]
    want = q.get("conflicts", [])
    found = [c for c in want if frozenset(c["pair"]) in pairs]
    out["conflicts_expected"], out["conflicts_found"] = len(want), len(found)
    out["conflicts_missed"] = [
        {"pair": c["pair"], "source": c["source"]} for c in want if c not in found
    ]
    covered = [
        i
        for k, i in items.items()
        if i.origin and i.evidence and i.label and i.recorded_at and world.specs.get(k)
    ]
    out["provenance_covered"] = len(covered)
    origin_checked = origin_right = 0
    origin_wrong: list[str] = []
    for k, i in items.items():
        gold = _gold_origin(world, k)
        if "origin" not in gold:
            continue
        origin_checked += 1
        want_confirmed = gold.get("confirmed", False)
        if i.origin == gold["origin"] and i.confirmed == want_confirmed:
            origin_right += 1
        else:
            origin_wrong.append(
                f"{k}: {i.origin}/{i.confirmed} != {gold['origin']}/{want_confirmed}"
            )
    out["origin_checked"], out["origin_correct"], out["origin_wrong"] = (
        origin_checked,
        origin_right,
        origin_wrong,
    )
    field_checks = field_right = 0
    field_wrong: list[str] = []
    for k, fields in q.get("fields", {}).items():
        for name, value in fields.items():
            field_checks += 1
            got = getattr(items[k], name) if k in items else "<not included>"
            if got == value:
                field_right += 1
            else:
                field_wrong.append(f"{k}.{name}: {got!r} != {value!r}")
    out["field_checks"], out["field_correct"], out["field_wrong"] = (
        field_checks,
        field_right,
        field_wrong,
    )
    if q.get("snapshot_insufficient"):
        abstain_ok = snap.insufficient
    elif q.get("flag_missing"):
        abstain_ok = snap.insufficient  # the snapshot has no other "something is missing" signal
    else:
        abstain_ok = not snap.insufficient
    out["abstention_correct"] = int(bool(abstain_ok))
    out["flag_missing"] = bool(q.get("flag_missing"))
    out["leaks"] = _leaks(snap, other, tokens)
    out["injection_mislabelled"] = sorted(
        k
        for k, i in items.items()
        if world.specs[k].get("injection") and (i.confirmed or i.origin == "user_stated")
    )
    return out


def _item_log(snap: Any, key_of: dict[str, str]) -> list[dict[str, Any]]:
    """Per item, in snapshot order: gold key, kind, reason, score, block. No content."""
    return [
        {
            "key": key_of.get(i.source_ref.id, "?"),
            "kind": i.source_ref.kind,
            "reason": i.reason,
            "score": i.score,
            "block": BLOCKS.get(i.reason, "other"),
        }
        for i in snap.items
    ]


def question_split(qid: str) -> str:
    """ "tune" or "test": the first byte of sha256(question id), even or odd. Stable."""
    return SPLITS[hashlib.sha256(qid.encode()).digest()[0] % 2]


def _reasons(snap: Any) -> dict[str, int]:
    """How many items each inclusion reason brought (search_hit, entity_link, ...)."""
    out: dict[str, int] = {}
    for i in snap.items:
        out[i.reason] = out.get(i.reason, 0) + 1
    return dict(sorted(out.items()))


SUMS = (
    "items",
    "ok_items",
    "standing_items",
    "ok_standing",
    "required",
    "found_required",
    "temporal_checks",
    "temporal_correct",
    "cvh_checks",
    "cvh_correct",
    "relations",
    "relations_both_ends",
    "relations_explicit",
    "conflicts_expected",
    "conflicts_found",
    "provenance_covered",
    "origin_checked",
    "origin_correct",
    "field_checks",
    "field_correct",
    "abstention_correct",
)


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    t = {k: sum(r.get(k, 0) for r in rows) for k in SUMS}
    return {
        "questions": len(rows),
        "precision": _rate(t["ok_items"], t["items"]),
        # The same, the question-independent block left out of both counts.
        "precision_without_standing": _rate(
            t["ok_items"] - t["ok_standing"], t["items"] - t["standing_items"]
        ),
        "standing_items": t["standing_items"],
        "recall": _rate(t["found_required"], t["required"]),
        "forbidden_as_current": sum(len(r["forbidden_as_current"]) for r in rows),
        "noise_items": sum(len(r["noise"]) for r in rows),
        "current_vs_historical": _rate(t["cvh_correct"], t["cvh_checks"]),
        "temporal": _rate(t["temporal_correct"], t["temporal_checks"]),
        "relationship_both_ends": _rate(t["relations_both_ends"], t["relations"]),
        "relationship_explicit": _rate(t["relations_explicit"], t["relations"]),
        "conflict_recall": _rate(t["conflicts_found"], t["conflicts_expected"]),
        "provenance_coverage": _rate(t["provenance_covered"], t["items"]),
        "origin_accuracy": _rate(t["origin_correct"], t["origin_checked"]),
        "field_accuracy": _rate(t["field_correct"], t["field_checks"]),
        "abstention_accuracy": _rate(t["abstention_correct"], len(rows)),
        "cross_tenant_leaks": sum(len(r["leaks"]) for r in rows),
        "injection_mislabelled": sum(len(r["injection_mislabelled"]) for r in rows),
        "determinism_failures": sum(r.get("determinism_failures", 0) for r in rows),
        "items_by_reason": _sum_reasons(rows),
        # What each rate is out of: --verify allows one item of slack on a small one.
        "denominators": {
            "precision": t["items"],
            "recall": t["required"],
            "current_vs_historical": t["cvh_checks"],
            "temporal": t["temporal_checks"],
            "relationship_both_ends": t["relations"],
            "relationship_explicit": t["relations"],
            "conflict_recall": t["conflicts_expected"],
            "provenance_coverage": t["items"],
            "origin_accuracy": t["origin_checked"],
            "field_accuracy": t["field_checks"],
            "abstention_accuracy": len(rows),
        },
    }


def _sum_reasons(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        for k, n in r.get("reasons", {}).items():
            out[k] = out.get(k, 0) + n
    return dict(sorted(out.items()))


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))], 2)


# ── One arm ───────────────────────────────────────────────────


def _main_spec(data: dict[str, Any]) -> dict[str, Any]:
    return {k: data[k] for k in ("memories", "decisions", "intentions", "typed_links", "approvals")}


async def _ask(
    q: dict[str, Any], tenant: str, now: datetime, repeat: int, snapshot_kw: dict | None = None
) -> tuple[Any, list, int]:
    from life_graph.core.tenant import tenant_scope
    from life_graph.services.memory.snapshot import assemble_context, without_timings

    as_of = _at(now, q.get("as_of_d"))
    latencies: list[float] = []
    dumps: set[str] = set()
    snap = None
    with tenant_scope(tenant):
        for _ in range(max(2, repeat)):
            t0 = time.perf_counter()
            snap = await assemble_context(q["query"], as_of=as_of, now=now, **(snapshot_kw or {}))
            latencies.append((time.perf_counter() - t0) * 1000.0)
            dumps.add(json.dumps(without_timings(snap.to_dict()), sort_keys=True))
    return snap, latencies, int(len(dumps) != 1)


async def build_world(
    world: World, spec: dict[str, Any], fx: dict | None, state: Any = None
) -> Any:
    """*spec*'s records in *world*: seeded rows, or through the save path with *fx*.

    The ingest arm (*fx* given) ingests the memories and decisions and seeds
    only the intentions; its approvals and typed links are whatever ingestion
    wrote. Returns the ingestion state (None for seeded rows).
    """
    if fx is None:
        await seed(world, spec)
        return None
    state = state or ingest.IngestState(fx, world.now)
    await ingest.build(world, spec, state)
    await seed(world, {"intentions": spec.get("intentions", [])})
    return state


async def run_snapshot_questions(
    data: dict[str, Any],
    questions: list[dict[str, Any]],
    repeat: int,
    fx: dict | None = None,
    snapshot_kw: dict | None = None,
) -> dict[str, Any]:
    """Build the main and look-alike tenants once, ask every snapshot question, clean up.

    With *fx* (the ingest arm) the main tenant is built through the save path
    and ``structure`` reports what ingestion wrote against the gold.
    """
    now = datetime.now(UTC)
    main, other = World(_new_tenant(), now), World(_new_tenant(), now)
    tokens = data["other_tenant"].get("leak_tokens", [])
    per_q: dict[str, Any] = {}
    snaps: dict[str, Any] = {}
    latencies: list[float] = []
    structure = None
    try:
        state = await build_world(main, _main_spec(data), fx)
        if state is not None:
            structure = await ingest.structure_report(main, data, state)
        await seed(other, data["other_tenant"])
        for q in questions:
            snap, lat, nondet = await _ask(q, main.tenant, now, repeat, snapshot_kw)
            row = score_snapshot(q, snap, main, other, tokens)
            row["determinism_failures"] = nondet
            row["p50_ms"] = round(statistics.median(lat), 2)
            latencies += lat
            per_q[q["id"]] = row
            snaps[q["id"]] = (snap, {str(r.id): k for k, r in main.rows.items()}, main.specs)
    finally:
        left = await cleanup(main.tenant) + await cleanup(other.tenant)
    return {
        "per_question": per_q,
        "snapshots": snaps,
        "latencies": latencies,
        "rows_left": left,
        "structure": structure,
    }


def _new_tenant() -> str:
    from life_graph.evals import production_retrieval_arm as arm

    return arm.new_tenant()


# ── O6: change detection against an earlier turn ──────────────


def _lookup(data: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    out = {}
    for group in ("memories", "decisions", "intentions"):
        for rec in data[group]:
            out[rec["key"]] = (group, rec)
    return out


def _subset(data: dict[str, Any], keys: list[str], overrides: dict[str, Any]) -> dict[str, Any]:
    lookup = _lookup(data)
    spec: dict[str, list[Any]] = {"memories": [], "decisions": [], "intentions": []}
    for key in keys:
        group, rec = lookup[key]
        spec[group].append({**rec, **overrides.get(key, {})})
    return spec


async def _turn(tenant: str, session_id: Any, at: datetime, compact: dict | None) -> uuid.UUID:
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    task = AgentTask(
        id=uuid.uuid4(),
        tenant_id=tenant,
        agent_name="jarvis",
        status="completed" if compact else "running",
        session_id=session_id,
        input={"message": "context quality eval"},
        result={"response": "ok", "trace": {"context_snapshot": compact}} if compact else {},
        created_at=at,
    )
    async with async_session() as s:
        s.add(task)
        await s.commit()
    return task.id


async def _conversation(tenant: str, at: datetime) -> Any:
    from life_graph.models.db import AgentSession
    from life_graph.storage.database import async_session

    conv = AgentSession(tenant_id=tenant, user_message="context quality eval", routed_to="jarvis")
    conv.created_at = at
    async with async_session() as s:
        s.add(conv)
        await s.commit()
    return conv.id


async def _apply_after(world: World, after: dict[str, Any], *, by_hand: bool = True) -> None:
    """The scenario's changes. Without *by_hand* (the ingest arm) the memory and
    decision supersedes are left to ingestion and the owner's actions; only the
    intentions are set."""
    from life_graph.models.db import Decision, Intention, Memory
    from life_graph.storage.database import async_session

    if not by_hand:
        after = {"set": after.get("set", [])}
    async with async_session() as s:
        for op in after.get("supersede", []):
            old = await s.get(Memory, world.rows[op["old"]].id)
            new = await s.get(Memory, world.rows[op["new"]].id)
            old.status, old.superseded_by = "superseded", new.id
            when = _at(world.now, op["at_d"])
            old.properties = {**(old.properties or {}), "superseded_at": when.isoformat()}
            new.supersedes = old.id
        for op in after.get("decision_supersede", []):
            old = await s.get(Decision, world.rows[op["old"]].id)
            old.status, old.superseded_by = "superseded", world.rows[op["new"]].id
        for op in after.get("set", []):
            row = await s.get(Intention, world.rows[op["key"]].id)
            row.status = op["status"]
            row.completed_at = _at(world.now, op.get("completed_d"))
        await s.commit()


def _change_key(ref: str, key_of: dict[str, str]) -> str:
    if ref.startswith(("pending_contradiction:", "supersession:", "decision_supersession:")):
        refs = ref.split(":", 1)[1].split(",")
        keys = sorted(key_of.get(r.split(":", 1)[1], r) for r in refs)
        return "conflict:" + "|".join(keys)
    return key_of.get(ref.split(":", 1)[1], ref)


async def run_change_question(
    data: dict[str, Any], q: dict[str, Any], tokens: list[str], fx: dict | None = None
) -> dict[str, Any]:
    """O6: the work records 7 days ago in a turn trace, the changes since, detect().

    With *fx* (the ingest arm) both the records of 7 days ago and the ones
    after are ingested; the supersede of the job comes from ingestion itself
    and the decision supersede from the owner's action.
    """
    from life_graph.core.tenant import tenant_scope
    from life_graph.services.memory import changes
    from life_graph.services.memory.snapshot import assemble_context

    sc = data["change_scenario"]
    now = datetime.now(UTC)
    base_at = now - timedelta(days=float(sc["baseline_days_ago"]))
    world, other = World(_new_tenant(), now), World(_new_tenant(), now)
    try:
        state = await build_world(
            world, _subset(data, sc["seed"], sc.get("seed_overrides", {})), fx
        )
        await seed(other, data["other_tenant"])
        conv = await _conversation(world.tenant, base_at - timedelta(minutes=1))
        with tenant_scope(world.tenant):
            before = await assemble_context(sc["query"], now=base_at)
        await _turn(world.tenant, conv, base_at, before.compact())
        after = sc["after"]
        created = _subset(data, after["create"], after.get("create_overrides", {}))
        await build_world(world, created, fx, state)
        if fx is None:
            await seed(world, {"approvals": after.get("approvals", [])})
        await _apply_after(world, after, by_hand=fx is None)
        task_id = await _turn(world.tenant, conv, now, None)
        with tenant_scope(world.tenant):
            t0 = time.perf_counter()
            snap = await assemble_context(sc["query"], now=now)
            snap_ms = (time.perf_counter() - t0) * 1000.0
            t1 = time.perf_counter()
            found = await changes.detect(snap, task_id, now=now)
            detect_ms = (time.perf_counter() - t1) * 1000.0
        key_of = world.ids()
        gold_q = {**q, **sc["snapshot_gold"]}
        row = score_snapshot(gold_q, snap, world, other, tokens)
        row["determinism_failures"] = 0
        row["p50_ms"] = round(snap_ms, 2)
        row["change_detection"] = _score_changes(sc, found, key_of, before, snap)
        row["change_detection"]["detect_ms"] = round(detect_ms, 2)
        row["change_detection"]["leaks"] = [
            t
            for t in tokens + [str(r.id) for r in other.rows.values()]
            if t in json.dumps(found.to_dict())
        ]
        snapshot = (snap, {str(r.id): k for k, r in world.rows.items()}, world.specs)
    finally:
        left = await cleanup(world.tenant) + await cleanup(other.tenant)
    return {"row": row, "snapshot": snapshot, "latency": snap_ms, "rows_left": left}


def _score_changes(sc: dict, found: Any, key_of: dict[str, str], before: Any, snap: Any) -> dict:
    reported = [(c.kind, _change_key(c.ref, key_of), c.acknowledged) for c in found.changes]
    got = {(k, ref) for k, ref, _ in reported}
    expected = []
    for e in sc["expect_changes"]:
        ref = e["key"]
        if ref.startswith("conflict:"):
            ref = "conflict:" + "|".join(sorted(ref.split(":", 1)[1].split("|")))
        expected.append((e["kind"], ref))
    hit = [e for e in expected if e in got]
    off_topic = [r for r in reported if r[1] in set(sc.get("off_topic_keys", []))]
    before_keys = sorted(key_of.get(i.source_ref.id, "?") for i in before.items)
    after_keys = sorted(key_of.get(i.source_ref.id, "?") for i in snap.items)
    return {
        "insufficient": found.insufficient,
        "explanation": found.explanation,
        "expected": len(expected),
        "found": len(hit),
        "recall": _rate(len(hit), len(expected)),
        "precision": _rate(
            len([r for r in reported if (r[0], r[1]) in set(expected)]), len(reported)
        ),
        "missed": [f"{k}:{r}" for k, r in expected if (k, r) not in got],
        "reported": [f"{k}:{r}{' (ack)' if a else ''}" for k, r, a in reported],
        "off_topic": len(off_topic),
        "suppressed": dict(found.suppressed),
        "baseline_items": before_keys,
        "current_items": after_keys,
    }


# ── Answer arm (optional, local Ollama only) ──────────────────


def _local_url(url: str) -> bool:
    return urlparse(url).hostname in ("127.0.0.1", "localhost", "::1")


def ollama_chat_available(url: str, model: str) -> str | None:
    """None when *model* is served by the local Ollama at *url*, else why not."""
    if not _local_url(url):
        return f"{url} is not a local address"
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=5) as resp:  # noqa: S310 — local URL
            names = {m["name"] for m in json.load(resp).get("models", [])}
    except Exception as exc:  # noqa: BLE001 — reported, never raised
        return f"Ollama not reachable at {url} ({type(exc).__name__})"
    if model not in names and f"{model}:latest" not in names:
        return f"model {model} is not pulled in Ollama"
    return None


def _answer_memories(snap: Any, key_of: dict[str, str], specs: dict[str, Any]) -> list[dict]:
    out = []
    for i in snap.items:
        spec = specs.get(key_of.get(i.source_ref.id, ""), {})
        out.append(
            {
                "id": i.source_ref.id,
                "content": i.content,
                "tags": [i.source_ref.kind, i.label, i.origin],
                "importance": 0.5,
                "created_at": (i.recorded_at or "")[:10],
                "status": "active" if i.status in ("active", "pending", "nudged") else i.status,
                "trust_tier": spec.get("trust_tier", "self"),
            }
        )
    return out


def _contains(text_: str, token: str) -> bool:
    return token.casefold() in text_.casefold()


def score_answer(q: dict[str, Any], result: dict[str, Any], key_of: dict, global_not: list[str]):
    answer = result.get("answer") or ""
    spec = q.get("answer") or {}
    groups = spec.get("must", [])
    must_hit = [any(_contains(answer, t) for t in g) for g in groups]
    bad = [t for t in spec.get("must_not", []) + global_not if _contains(answer, t)]
    abstain = bool(spec.get("abstain"))
    answered = bool(result.get("answered"))
    ok_keys = set(q.get("required", [])) | set(q.get("acceptable", []))
    cited = [key_of.get(c, c) for c in result.get("citations") or []]
    supported = all(must_hit) and not bad and (not abstain or not answered)
    return {
        "answered": answered,
        "evidence_supported": supported,
        "unsupported_claim": bool(bad) or (abstain and answered),
        "abstain_expected": abstain,
        "abstain_correct": (not answered) if abstain else None,
        "must_missing": [g for g, hit in zip(groups, must_hit, strict=True) if not hit],
        "must_not_found": bad,
        "cited": len(cited),
        "cited_ok": sum(1 for c in cited if c in ok_keys),
        "model": result.get("model"),
        "answer": answer[:600],
    }


async def run_answer_arm(
    questions: list[dict[str, Any]], snaps: dict[str, Any], url: str, model: str, gq: dict
) -> dict[str, Any]:
    from life_graph.config import settings
    from life_graph.services.llm.client import LMStudioClient
    from life_graph.services.synthesis import SynthesisService

    saved = (settings.ollama_api_base, settings.lm_reasoning_effort)
    settings.ollama_api_base, settings.lm_reasoning_effort = url, "none"
    per_q: dict[str, Any] = {}
    latencies: list[float] = []
    try:
        service = SynthesisService(LMStudioClient(base_url=url))
        for q in questions:
            if q["id"] not in snaps:
                continue
            snap, key_of, specs = snaps[q["id"]]
            t0 = time.perf_counter()
            result = await service.synthesize(
                q["query"], _answer_memories(snap, key_of, specs), model=model
            )
            latencies.append((time.perf_counter() - t0) * 1000.0)
            per_q[q["id"]] = score_answer(q, result, key_of, gq.get("global_answer_must_not", []))
    finally:
        settings.ollama_api_base, settings.lm_reasoning_effort = saved
    return {"per_question": per_q, "latencies": latencies}


def summarise_answers(rows: list[dict[str, Any]]) -> dict[str, Any]:
    abst = [r for r in rows if r["abstain_expected"]]
    rule_based = sum(1 for r in rows if r["model"] == "rule-based")
    return {
        "questions": len(rows),
        "evidence_supported_rate": _rate(sum(r["evidence_supported"] for r in rows), len(rows)),
        "unsupported_claim_rate": _rate(sum(r["unsupported_claim"] for r in rows), len(rows)),
        "abstention_accuracy": _rate(sum(bool(r["abstain_correct"]) for r in abst), len(abst)),
        "citation_precision": _rate(
            sum(r["cited_ok"] for r in rows), sum(r["cited"] for r in rows)
        ),
        "rule_based_fallbacks": rule_based,
    }


# ── Orchestration ─────────────────────────────────────────────


def _by_category(questions: list[dict], per_q: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for cat in CATEGORIES:
        rows = [per_q[q["id"]] for q in questions if q["category"] == cat and q["id"] in per_q]
        if rows:
            out[cat] = summarise(rows)
    return out


async def run_arm(
    arm_name: str,
    data: dict[str, Any],
    gq: dict[str, Any],
    *,
    repeat: int = 3,
    only: set[str] | None = None,
    ollama_url: str = OLLAMA_URL,
    snapshot_kw: dict | None = None,
    split: str | None = None,
) -> dict[str, Any]:
    """One embedding arm over every (or *only* the, or one *split*'s) question(s).

    *snapshot_kw* goes to every snapshot question's assemble_context
    (``experiments``, ``budget``); change questions never get it.
    """
    from life_graph.evals import production_retrieval_arm as arm

    questions = [
        q
        for q in gq["questions"]
        if (only is None or q["id"] in only) and (split is None or question_split(q["id"]) == split)
    ]
    snap_qs = [q for q in questions if q.get("mode", "snapshot") == "snapshot"]
    change_qs = [q for q in questions if q.get("mode") == "changes"]
    fx = ingest.load_fixtures() if arm_name == "ingest" else None
    calls: dict[str, int] = {}
    embed_ctx: Any = contextlib.nullcontext()
    if arm_name == "bge-m3":
        texts = _all_texts(data, gq)
        embed_ctx = arm.using_embedder(
            arm.ollama_embedder(texts, model="bge-m3", base_url=ollama_url), "bge-m3"
        )
    # G's probe embeddings are cached per manager; this arm may embed differently.
    from life_graph.services.memory.snapshot import clear_probe_cache

    clear_probe_cache()
    with embed_ctx, arm.production_fakes(), model_guard(calls):
        main = await run_snapshot_questions(data, snap_qs, repeat, fx, snapshot_kw)
        per_q, snaps, latencies = main["per_question"], main["snapshots"], main["latencies"]
        rows_left = main["rows_left"]
        changes_out = None
        for q in change_qs:
            res = await run_change_question(
                data, q, data["other_tenant"].get("leak_tokens", []), fx
            )
            per_q[q["id"]] = res["row"]
            snaps[q["id"]] = res["snapshot"]
            rows_left += res["rows_left"]
            changes_out = res["row"]["change_detection"]
    by_cat = _by_category(questions, per_q)
    extra: dict[str, Any] = {}
    if fx is not None:
        extra = {
            "path": "save path (scripts/context_quality_ingest.py), hashing embedder, flags "
            + ", ".join(ingest.FLAGS),
            "fixtures": {
                "recorded": fx.get("recorded"),
                "messages": len(fx.get("messages", [])),
                "problems": ingest.check_fixtures(fx, data),
                "coverage": ingest.coverage(fx, data),
            },
            "ingestion": main.get("structure"),
        }
    return {
        "embedder": "hashing" if fx is not None else arm_name,
        "by_category": by_cat,
        "per_question": per_q,
        "change_detection": changes_out,
        "zero_tolerance": {
            "cross_tenant_leaks": sum(e["cross_tenant_leaks"] for e in by_cat.values())
            + len((changes_out or {}).get("leaks", [])),
            "cloud_model_calls": sum(calls.values()),
            "forbidden_as_current": sum(e["forbidden_as_current"] for e in by_cat.values()),
            "rows_left_after_cleanup": rows_left,
        },
        "model_calls_by_route": calls,
        "latency_ms": {
            "runs": len(latencies),
            "p50": _pct(latencies, 0.5),
            "p95": _pct(latencies, 0.95),
            "max": round(max(latencies), 2) if latencies else 0.0,
        },
        "_snapshots": snaps,
        **extra,
    }


def _all_texts(data: dict[str, Any], gq: dict[str, Any]) -> list[str]:
    texts = [m["content"] for m in data["memories"]]
    texts += [m["content"] for m in data["other_tenant"]["memories"]]
    texts += [q["query"] for q in gq["questions"]]
    texts.append(data["change_scenario"]["query"])
    # The hub experiment (G) embeds these; the lookup embedder refuses unknown texts.
    texts += list(_xp().HUB_PROBES)
    # The undated-intention experiment (H) embeds the text of open intentions.
    texts += [i["content"] for i in data.get("intentions", [])]
    texts += [i["content"] for i in data["other_tenant"].get("intentions", [])]
    return texts


def _xp() -> Any:
    from life_graph.services.memory import snapshot_experiments

    return snapshot_experiments


def experiment_run(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    """(the run's record for the report, assemble_context keywords) from the flags.

    Both empty without --mode / --experiments / --xp-set / --max-items / --split.
    The --xp-set values travel with each call (``tunables``); nothing is set
    on the experiments module. ``--mode`` alone runs the production code path
    itself (``assemble_context(mode=...)``); with --experiments or --xp-set
    too, the mode's set and values are the start and the flags add to them.
    """
    xp = _xp()
    record: dict[str, Any] = {}
    kw: dict[str, Any] = {}
    picked = xp.mode(getattr(args, "mode", "") or "")
    chosen = xp.parse(args.experiments)
    raw: dict[str, str] = {}
    for item in args.xp_set:
        name, _, value = item.partition("=")
        name = name.strip().upper()
        if name not in xp.TUNABLE or not value.strip():
            raise SystemExit(
                f"--xp-set {item!r}: use NAME=VALUE, NAME one of {', '.join(xp.TUNABLE)}"
            )
        raw[name] = value
    try:
        tunables = (picked.tunables if picked else xp.DEFAULT_TUNABLES).with_values(raw)
    except ValueError as exc:
        raise SystemExit(f"--xp-set: {exc}") from exc
    named = tunables.named()
    settings_ = {n: named[n] for n in raw}
    if picked is not None:
        record["mode"] = picked.name
        if not chosen and not raw:
            kw["mode"] = picked.name
        chosen = chosen | picked.experiments
    if chosen:
        record["experiments"] = xp.letters(chosen)
        record["experiment_names"] = sorted(chosen)
        if "mode" not in kw:
            kw["experiments"] = chosen
            kw["tunables"] = tunables
    if settings_:
        record["xp_set"] = settings_
    if chosen or settings_:
        record["constants"] = named
    if args.max_items:
        from life_graph.services.memory.snapshot import DEFAULT_BUDGET, Budget

        kw["budget"] = Budget(
            max_items=args.max_items,
            max_chars=DEFAULT_BUDGET.max_chars,
            item_chars=DEFAULT_BUDGET.item_chars,
        )
        record["max_items"] = args.max_items
    if args.split:
        record["split"] = args.split
        record["split_rule"] = "sha256(question id)[0] % 2: 0 tune, 1 test"
    return record, kw


def _strip(arm_report: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in arm_report.items() if not k.startswith("_")}


async def run(args: argparse.Namespace) -> dict[str, Any]:
    data, gq = load()
    only = set(args.only.split(",")) if args.only else None
    run_record, snapshot_kw = experiment_run(args)
    report: dict[str, Any] = {
        "benchmark": "life_graph_context_quality_v1",
        "dataset_sha256": hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest(),
        "questions_sha256": hashlib.sha256(QUESTIONS_PATH.read_bytes()).hexdigest(),
        "judge": "off (assemble_context calls retrieve(judge=False)); no model call",
        "arms": {},
        "skipped": {},
    }
    if run_record:
        # Only when set, so a plain run's report is what it was.
        report["run"] = run_record
    snaps_for_answer = None
    for name in [a.strip() for a in args.arms.split(",") if a.strip()]:
        if name == "bge-m3":
            why = _embed_unavailable(args.ollama_url)
            if why:
                report["skipped"]["bge-m3"] = why
                continue
        result = await run_arm(
            name,
            data,
            gq,
            repeat=args.repeat,
            only=only,
            ollama_url=args.ollama_url,
            snapshot_kw=snapshot_kw,
            split=args.split,
        )
        report["arms"][name] = _strip(result)
        if name == "bge-m3" or snaps_for_answer is None:
            snaps_for_answer = (name, result["_snapshots"])
    if args.answer and snaps_for_answer:
        why = ollama_chat_available(args.ollama_url, args.answer_model)
        if why:
            report["skipped"]["answer"] = why
        else:
            calls: dict[str, int] = {}
            questions = [
                q
                for q in gq["questions"]
                if (only is None or q["id"] in only)
                and (args.split is None or question_split(q["id"]) == args.split)
            ]
            with model_guard(calls, allow_local_chat=True):
                ans = await run_answer_arm(
                    questions, snaps_for_answer[1], args.ollama_url, args.answer_model, gq
                )
            report["arms"]["answer"] = _answer_report(
                ans, questions, calls, snaps_for_answer[0], args
            )
    return report


def _answer_report(ans: dict, questions: list[dict], calls: dict, source: str, args) -> dict:
    per_q = ans["per_question"]
    by_cat = {}
    for cat in CATEGORIES:
        rows = [per_q[q["id"]] for q in questions if q["category"] == cat and q["id"] in per_q]
        if rows:
            by_cat[cat] = summarise_answers(rows)
    lat = ans["latencies"]
    return {
        "model": f"{args.answer_model} on local Ollama {args.ollama_url} (think off)",
        "path": "services/synthesis.py SynthesisService.synthesize -> chat_local_only",
        "snapshots_from": source,
        "by_category": by_cat,
        "per_question": per_q,
        "zero_tolerance": {"cloud_model_calls": sum(calls.values())},
        "latency_ms": {"runs": len(lat), "p50": _pct(lat, 0.5), "p95": _pct(lat, 0.95)},
    }


def _embed_unavailable(url: str) -> str | None:
    if not _local_url(url):
        return f"{url} is not a local address"
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/api/embed",
            data=json.dumps({"model": "bge-m3", "input": ["ping"]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — local URL
            json.load(resp)
    except Exception as exc:  # noqa: BLE001 — reported as a skip
        return f"bge-m3 embedding not available at {url} ({type(exc).__name__})"
    return None


# ── Baseline, verify, report ──────────────────────────────────


def _floors(arm: dict[str, Any]) -> dict[str, Any]:
    return {
        "by_category": {
            cat: {k: v for k, v in e.items() if k in RATES and v is not None}
            for cat, e in arm["by_category"].items()
        },
        "change_detection_recall": (arm.get("change_detection") or {}).get("recall"),
    }


def baseline_of(report: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """The floors of the arms in *report*; an arm that did not run keeps *previous*'s.

    The hashing floors stay at the top level (as before); the ingest arm's go
    under ``ingest``, with its forbidden-as-current count as a ceiling.
    """
    out = dict(previous or {})
    if "hashing" in report["arms"]:
        out.update(
            {
                "about": "Floors for the hashing arm, recorded from a real run: what the context layer does today, weak categories included. Not a target.",
                "arm": "hashing",
                **_floors(report["arms"]["hashing"]),
            }
        )
    if "ingest" in report["arms"]:
        arm = report["arms"]["ingest"]
        out["ingest"] = {
            "about": "Floors for the ingest arm (the world built by the save path, all four M8 ingestion flags on, recorded extractor output), recorded from a real run. Not a target: the gaps are what ingestion does not write yet.",
            **_floors(arm),
            "forbidden_as_current_max": arm["zero_tolerance"]["forbidden_as_current"],
        }
    return out


def _floor_fails(arm: dict[str, Any], floors: dict[str, Any], prefix: str = "") -> list[str]:
    fails: list[str] = []
    for cat, per_cat in floors.get("by_category", {}).items():
        entry = arm["by_category"].get(cat)
        if entry is None:
            fails.append(f"{prefix}{cat}: category missing from this run")
            continue
        for key, floor in per_cat.items():
            got = entry.get(key)
            den = entry.get("denominators", {}).get(key) or 0
            slack = max(TOLERANCE, 1.0 / den) if den else TOLERANCE
            if got is None or got < floor - slack - 1e-9:
                fails.append(f"{prefix}{cat}.{key} = {got} < baseline {floor} - {slack:.3f}")
    floor = floors.get("change_detection_recall")
    got = (arm.get("change_detection") or {}).get("recall")
    if floor is not None and (got is None or got < floor - TOLERANCE):
        fails.append(f"{prefix}change_detection.recall = {got} < baseline {floor} - {TOLERANCE}")
    return fails


def regressions(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    arm = report["arms"].get("hashing")
    if arm is None:
        return ["the hashing arm did not run"]
    for key, value in arm["zero_tolerance"].items():
        if value:
            fails.append(f"{key} = {value} (target 0)")
    fails += _floor_fails(arm, baseline)
    if "ingest" in report["arms"]:
        fails += ingest_regressions(report["arms"]["ingest"], baseline.get("ingest"))
    return fails


def ingest_regressions(arm: dict[str, Any], floors: dict[str, Any] | None) -> list[str]:
    """The ingest arm's gate: usable fixtures and its zero counts always; floors once recorded."""
    fails = [f"ingest: fixtures: {p}" for p in arm.get("fixtures", {}).get("problems", [])]
    for key in INGEST_ZERO:
        value = arm["zero_tolerance"].get(key)
        if value:
            fails.append(f"ingest: {key} = {value} (target 0)")
    if floors is None:
        return fails
    fails += _floor_fails(arm, floors, prefix="ingest: ")
    ceiling = floors.get("forbidden_as_current_max")
    got = arm["zero_tolerance"].get("forbidden_as_current")
    if ceiling is not None and got is not None and got > ceiling:
        fails.append(f"ingest: forbidden_as_current = {got} > baseline {ceiling}")
    return fails


def _f(v: Any) -> str:
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


SNAP_COLS = (
    ("questions", "n"),
    ("precision", "P"),
    ("precision_without_standing", "P w/o standing"),
    ("recall", "R"),
    ("forbidden_as_current", "forb"),
    ("noise_items", "noise"),
    ("current_vs_historical", "cur/hist"),
    ("temporal", "temporal"),
    ("relationship_both_ends", "rel both"),
    ("relationship_explicit", "rel explicit"),
    ("conflict_recall", "conflicts"),
    ("provenance_coverage", "prov"),
    ("origin_accuracy", "origin"),
    ("field_accuracy", "fields"),
    ("abstention_accuracy", "abstain"),
    ("cross_tenant_leaks", "leaks"),
)


def markdown(report: dict[str, Any], questions: list[dict]) -> str:
    lines = ["# Context quality eval", ""]
    lines.append(
        f"Dataset `{report['dataset_sha256'][:12]}`, questions `{report['questions_sha256'][:12]}`."
    )
    for name, why in report.get("skipped", {}).items():
        lines.append(f"- **{name} arm skipped:** {why}")
    for name, arm in report["arms"].items():
        if name == "answer":
            continue
        lines += ["", f"## Arm `{name}`", "", _snap_table(arm["by_category"])]
        z, lat = arm["zero_tolerance"], arm["latency_ms"]
        lines.append("")
        lines.append(
            f"Zero-tolerance: leaks {z['cross_tenant_leaks']}, cloud model calls "
            f"{z['cloud_model_calls']}, forbidden-as-current {z['forbidden_as_current']}, "
            f"rows left {z['rows_left_after_cleanup']}. Latency over {lat['runs']} runs: "
            f"p50 {lat['p50']} ms, p95 {lat['p95']} ms."
        )
        cd = arm.get("change_detection")
        if cd:
            lines.append(
                f"O6 change detection: {cd['found']}/{cd['expected']} expected changes "
                f"(recall {_f(cd['recall'])}, precision {_f(cd['precision'])}); missed: "
                f"{', '.join(cd['missed']) or 'none'}; suppressed: {cd['suppressed']}."
            )
        if arm.get("ingestion"):
            lines += ["", _ingestion_lines(arm)]
        lines += ["", _question_table(arm["per_question"], questions)]
    if "answer" in report["arms"]:
        lines += ["", "## Answer arm", "", _answer_table(report["arms"]["answer"], questions)]
    return "\n".join(lines) + "\n"


def _ingestion_lines(arm: dict[str, Any]) -> str:
    """What the save path wrote, and each gold structure found or missed."""
    ing, fx = arm["ingestion"], arm.get("fixtures", {})
    gold = ing["gold"]
    rec = fx.get("recorded") or {}
    cov = fx.get("coverage", {})
    out = [
        "### Ingestion vs gold",
        "",
        f"{fx.get('messages')} messages through the {arm.get('path')}; extractor output "
        f"recorded with {rec.get('model', '?')} on {rec.get('anchor', '?')}. Fixture problems: "
        f"{len(fx.get('problems', []))}; records with no message: "
        f"{', '.join(cov.get('no_message', [])) or 'none'}; said but not extracted: "
        f"{', '.join(cov.get('not_extracted', [])) or 'none'}.",
        "",
        f"- Memories {ing['memories']} {ing['memories_by_status']}, {ing['extra_memories']} "
        f"beyond the dataset's; world time set {ing['world_time_set']} (known "
        f"{ing['world_time_known']}); valid_until set {ing['valid_until_set']}; superseded "
        f"{ing['superseded']}.",
        f"- Links: {ing['links_associated']} ASSOCIATED, typed {ing['links_typed'] or 'none'}; "
        f"contradiction approvals {ing['contradiction_approvals'] or 'none'}.",
        f"- Decisions {ing['decisions_by_status']}, owner-confirmed "
        f"{ing['decisions_owner_confirmed']}; found per decision message {ing['decisions_detected']}.",
        f"- Records with no row: {', '.join(ing['unmapped_records']) or 'none'}; replay misses "
        f"{len(ing['replay_misses'])}; owner actions refused: "
        f"{'; '.join(ing['owner_actions_failed']) or 'none'}.",
    ]
    for name in ("supersession", "typed_links", "pending_contradictions"):
        g = gold[name]
        out.append(
            f"- Gold {name}: {len(g['found'])}/{g['expected']} found; missed: "
            f"{', '.join(g['missed']) or 'none'}."
        )
    for name in ("memory_state", "decisions"):
        g = gold[name]
        out.append(
            f"- Gold {name}: {g['right']}/{g['of']} right; wrong: {'; '.join(g['wrong']) or 'none'}."
        )
    return "\n".join(out)


def _snap_table(by_cat: dict[str, Any]) -> str:
    head = "| category | " + " | ".join(label for _, label in SNAP_COLS) + " |"
    sep = "|" + "---|" * (len(SNAP_COLS) + 1)
    rows = [
        f"| {cat} {CATEGORY_NAMES[cat]} | " + " | ".join(_f(e.get(k)) for k, _ in SNAP_COLS) + " |"
        for cat, e in by_cat.items()
    ]
    return "\n".join([head, sep, *rows])


def _question_table(per_q: dict[str, Any], questions: list[dict]) -> str:
    head = "| q | items | req found | missed | forbidden | temporal ok | rel both/explicit | conflicts | abstain ok | p50 ms |"
    out = [head, "|" + "---|" * 10]
    for q in questions:
        r = per_q.get(q["id"])
        if r is None:
            continue
        out.append(
            f"| {q['id']} | {r['items']} | {r['found_required']}/{r['required']} | "
            f"{', '.join(r['missed_required']) or '–'} | {', '.join(r['forbidden_as_current']) or '–'} | "
            f"{r['temporal_correct']}/{r['temporal_checks']} | "
            f"{r['relations_both_ends']}/{r['relations_explicit']} of {r['relations']} | "
            f"{r['conflicts_found']}/{r['conflicts_expected']} | {r['abstention_correct']} | {r['p50_ms']} |"
        )
    return "\n".join(out)


def _answer_table(ans: dict[str, Any], questions: list[dict]) -> str:
    out = [f"Model: {ans['model']}; snapshots from the `{ans['snapshots_from']}` arm.", ""]
    out.append(
        "| category | n | evidence-supported | unsupported claims | abstention | citation precision |"
    )
    out.append("|---|---|---|---|---|---|")
    for cat, e in ans["by_category"].items():
        out.append(
            f"| {cat} {CATEGORY_NAMES[cat]} | {e['questions']} | {_f(e['evidence_supported_rate'])} | "
            f"{_f(e['unsupported_claim_rate'])} | {_f(e['abstention_accuracy'])} | {_f(e['citation_precision'])} |"
        )
    out += [
        "",
        "| q | supported | unsupported | missing words | forbidden words |",
        "|---|---|---|---|---|",
    ]
    for q in questions:
        r = ans["per_question"].get(q["id"])
        if r is None:
            continue
        out.append(
            f"| {q['id']} | {int(r['evidence_supported'])} | {int(r['unsupported_claim'])} | "
            f"{'; '.join('/'.join(g) for g in r['must_missing']) or '–'} | {', '.join(r['must_not_found']) or '–'} |"
        )
    return "\n".join(out)


def _local_openai_available(url: str, model: str) -> str | None:
    """None when *url* is a localhost OpenAI-compatible server that answers /v1/models.

    Only loopback hosts: fixtures are recorded with a local model, never a
    cloud one (the prod extraction server is llama.cpp on :11435).
    """
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return f"--extract-url must be a localhost server, not {host or url!r}"
    try:
        with urllib.request.urlopen(f"{url}/v1/models", timeout=5) as resp:  # noqa: S310 — loopback only
            json.loads(resp.read() or b"{}")
    except Exception as exc:  # noqa: BLE001
        return f"local server not reachable at {url} ({type(exc).__name__}); model {model}"
    return None


def _record(args: argparse.Namespace) -> int:
    """--record-fixtures: the local model's answers for the ingest arm's messages."""
    if args.extract_url:
        url, where = args.extract_url.rstrip("/"), f"local server {args.extract_url}"
        why = _local_openai_available(url, args.extract_model)
    else:
        url, where = args.ollama_url, "local Ollama"
        why = ollama_chat_available(url, args.extract_model)
    if why:
        print(f"cannot record: {why}", file=sys.stderr)
        return 1
    data, _ = load()
    calls: dict[str, int] = {}
    with model_guard(calls, allow_local_chat=True):
        out = asyncio.run(
            ingest.record_fixtures(data, url=url, model=args.extract_model, where=where)
        )
    print(json.dumps({**out, "cloud_model_calls": sum(calls.values())}, indent=2))
    return 1 if calls else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--arms", default="hashing", help="Comma list: hashing,bge-m3,ingest")
    parser.add_argument("--answer", action="store_true", help="Also run the local answer arm")
    parser.add_argument("--answer-model", default="qwen3:14b")
    parser.add_argument("--ollama-url", default=OLLAMA_URL)
    parser.add_argument("--only", default="", help="Comma list of question ids")
    parser.add_argument("--repeat", type=int, default=3, help="Snapshot runs per question (min 2)")
    parser.add_argument("--verify", action="store_true", help="Exit non-zero on a regression")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--write-report", action="store_true", help="Write report.json + report.md")
    parser.add_argument("--output", type=Path, default=None, help="Also write the report JSON here")
    parser.add_argument(
        "--record-fixtures",
        action="store_true",
        help="Record the ingest arm's extractor output with the local model (no DB), then exit",
    )
    parser.add_argument("--extract-model", default="qwen3:14b", help="Model for --record-fixtures")
    parser.add_argument(
        "--extract-url",
        default=None,
        help="Record with this localhost OpenAI-compatible server instead of Ollama "
        "(prod's extraction server: http://127.0.0.1:11435 with qwen2.5-coder-14b)",
    )
    parser.add_argument(
        "--db-suffix",
        default=os.environ.get("LIFE_GRAPH_TEST_DATABASE_SUFFIX", "_test"),
        help='Suffix for the database name (default "_test"; "" uses the configured DB)',
    )
    parser.add_argument(
        "--mode",
        choices=("recall", "precision"),
        default="",
        help="A production precision mode (snapshot_experiments.MODES): its fixed experiment "
        "set and values; --experiments/--xp-set add to it",
    )
    parser.add_argument(
        "--experiments",
        default="",
        help="Eval-only snapshot experiments, letters or names: A rank, B query_type, "
        "C links, D dedupe, E evidence, F budget, G hub, H undated, I goals, J overview, "
        "K domain (services/memory/snapshot_experiments.py)",
    )
    parser.add_argument(
        "--xp-set",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Set one experiment constant for this run (snapshot_experiments.TUNABLE)",
    )
    parser.add_argument(
        "--max-items", type=int, default=None, help="A tighter hard budget for every snapshot"
    )
    parser.add_argument(
        "--split", choices=SPLITS, default=None, help="Only one half of the questions (stable hash)"
    )
    args = parser.parse_args()
    tried = args.mode or args.experiments or args.xp_set or args.max_items or args.split
    if tried and (args.write_report or args.write_baseline):
        parser.error(
            "--mode/--experiments/--xp-set/--max-items/--split cannot write the committed report "
            "or baseline; use --output"
        )
    _point_at_test_database(args.db_suffix)
    logging.getLogger("life_graph").setLevel(logging.ERROR)
    if args.record_fixtures:
        return _record(args)

    report = asyncio.run(run(args))
    _, gq = load()
    text_ = markdown(report, gq["questions"])
    print(text_)
    if args.write_report:
        REPORT_JSON.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        REPORT_MD.write_text(text_, encoding="utf-8")
    if args.output:
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if args.write_baseline:
        previous = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        BASELINE_PATH.write_text(
            json.dumps(baseline_of(report, previous), indent=2) + "\n", encoding="utf-8"
        )
        print(f"Wrote baseline {BASELINE_PATH.name}")
    if args.verify:
        fails = regressions(report, json.loads(BASELINE_PATH.read_text(encoding="utf-8")))
        if fails:
            print("FAIL:\n  " + "\n  ".join(fails), file=sys.stderr)
            return 1
        print("verify: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
