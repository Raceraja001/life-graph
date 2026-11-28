#!/usr/bin/env python3
"""Does ingestion write the right structure? (M8 ingestion ADR §6.1; synthetic, no DB, no model)

Scores the labelled cases in ``evals/ingestion_structure/cases.json`` against
the real save-path code, with all the M8 ingestion flags on
(``ingest_world_time``, ``ingest_supersession_tiers``, ``ingest_slot_pairing``,
``ingest_typed_links``, ``decision_lifecycle``, ``ingest_world_end``):

* ``world_time`` -- extraction/world_time.py ``world_time_of`` on one fact.
* ``world_end`` -- services/memory/world_time.py ``end_of`` on one fact: the
  rules' "until 20 November" / "March varaikum", then the model's
  ``valid_until`` only when a rule agrees.
* ``supersession`` -- an active old memory and a new fact (the extractor's raw
  item, read through extraction/llm.py's own checks) go through
  ``MemoryManager._process_fact`` with the real contradiction detector, the
  real tier rules and the real ``supersession.apply``; only the store, the
  slot lookup and the approval queue are plain in-memory stand-ins. The
  outcome is the tier the save path chose: ``high`` (applied at once),
  ``medium`` (a contradiction approval that waits), ``low`` (a review item),
  ``merged`` (a near duplicate) or ``none``.
* ``links`` -- one message's raw facts through ``MemoryManager.store_facts`` and
  services/memory/typed_links.py; the links ``links.create_link`` would write.
* ``decisions`` -- the capture spine's decision rules and its owner-only gate
  (services/capture_processors.py), and decision moves through the gates the
  routes, a memory review, a create and the system's mirror use
  (api/judgment.py, services/decision_lifecycle.py).

Zero-tolerance counts (``--verify`` fails on any):

* ``world_time_set_where_unknown`` -- a start where the gold has none;
* ``world_time_future_given_start`` -- a plan given a start;
* ``world_end_set_where_unknown`` -- an end where the gold has none;
* ``world_end_before_start`` -- an end at or before the fact's own start;
* ``wrong_auto_supersede`` -- a supersede applied at once (high tier) where
  the gold says the two facts are not one attribute;
* ``decision_confirmed_without_owner`` -- a decision moved to decided, or read
  as owner-confirmed, in a case where the owner made no move;
* ``outside_supersede_or_link`` -- outside text (external, hostile_possible)
  superseding an owner's fact at once, filing a low-tier item against it, a
  typed link touching an earlier owner memory, or a capture candidate decision;
* ``correction_given_valid_until`` -- a correction ending the old fact's world time.

Precision and recall per structure type are reported, and ``--verify`` also
fails when one falls below ``evals/ingestion_structure/baseline.json`` (0.05
slack, or one case for a rate out of fewer than 20). Record the baseline on
purpose with ``--write-baseline``; ``--write-report`` writes report.json.

    python scripts/eval_ingestion_structure.py --verify
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import math
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DIR = ROOT / "evals" / "ingestion_structure"
CASES_PATH = DIR / "cases.json"
BASELINE_PATH = DIR / "baseline.json"
REPORT_PATH = DIR / "report.json"
TENANT = "ingest_eval"
OUTSIDE = frozenset({"external", "hostile_possible"})
SUPERSEDE_TIERS = frozenset({"high", "medium"})
ZERO = (
    "world_time_set_where_unknown",
    "world_time_future_given_start",
    "world_end_set_where_unknown",
    "world_end_before_start",
    "wrong_auto_supersede",
    "decision_confirmed_without_owner",
    "outside_supersede_or_link",
    "correction_given_valid_until",
)
TOLERANCE = 0.05
#: The server's label for each actor (api/approval_identity.py resolver labels).
ACTOR_LABEL = {
    "owner": "owner",
    "phone": "phone:eval-device",
    "service_key": "key:agent-service",
    "mcp": "mcp",
    "agent": "agent:jarvis",
    "auto_keep": "auto_kept",
    "rule": "system:rule",
    "system": "system:memory_supersede",
}
OWNER_ACTORS = frozenset({"owner", "phone"})


def load() -> dict[str, Any]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


# ── World time ────────────────────────────────────────────────


def score_world_time(data: dict[str, Any]) -> dict[str, Any]:
    from life_graph.extraction.world_time import world_time_of

    tz = ZoneInfo(data["tz"])
    rows = []
    for c in data.get("world_time", []):
        anchor = datetime.fromisoformat(c.get("said_at") or data["anchor"])
        found = world_time_of(c["content"], c.get("source_text"), anchor, tz)
        got = None if found is None else (found.start.date().isoformat(), found.precision)
        want = c["expect"]
        gold = (
            None
            if want is None
            else (date.fromisoformat(want["start"]).isoformat(), want["precision"])
        )
        rows.append((c, got, gold))
    made = [r for r in rows if r[1] is not None]
    has = [r for r in rows if r[2] is not None]
    return {
        "cases": len(rows),
        "precision": _rate(sum(g == w for _, g, w in made), len(made)),
        "recall": _rate(sum(g == w for _, g, w in has), len(has)),
        "denominators": {"precision": len(made), "recall": len(has)},
        "set_where_unknown": [c["id"] for c, g, w in made if w is None],
        "future_given_start": [c["id"] for c, g, _ in made if c["category"] == "future"],
        "misses": [f"{c['id']}: {g} != {w}" for c, g, w in rows if g != w],
    }


# ── World end ─────────────────────────────────────────────────


def score_world_end(data: dict[str, Any]) -> dict[str, Any]:
    from life_graph.extraction.world_time import world_time_of
    from life_graph.services.memory.world_time import end_of

    tz = ZoneInfo(data["tz"])
    rows = []
    before_start = []
    for c in data.get("world_end", []):
        anchor = datetime.fromisoformat(c.get("said_at") or data["anchor"])
        found = end_of(
            c["content"], c.get("source_text"), anchor, tz, model_value=c.get("model_valid_until")
        )
        got = None if found is None else (found.end.date().isoformat(), found.precision)
        want = c["expect"]
        gold = (
            None
            if want is None
            else (date.fromisoformat(want["end"]).isoformat(), want["precision"])
        )
        rows.append((c, got, gold))
        started = world_time_of(c["content"], c.get("source_text"), anchor, tz)
        if found is not None and started is not None and found.end <= started.start:
            before_start.append(c["id"])
    made = [r for r in rows if r[1] is not None]
    has = [r for r in rows if r[2] is not None]
    return {
        "cases": len(rows),
        "precision": _rate(sum(g == w for _, g, w in made), len(made)),
        "recall": _rate(sum(g == w for _, g, w in has), len(has)),
        "denominators": {"precision": len(made), "recall": len(has)},
        "set_where_unknown": [c["id"] for c, g, w in made if w is None],
        "before_start": before_start,
        "misses": [f"{c['id']}: {g} != {w}" for c, g, w in rows if g != w],
    }


# ── Facts from raw extractor items ────────────────────────────


def to_fact(item: dict[str, Any], source_text: str) -> Any:
    """An ExtractedFact from one raw extractor item, through extraction/llm.py's own checks."""
    from life_graph.extraction import llm
    from life_graph.extraction.rules import ExtractedFact

    return ExtractedFact(
        content=item["content"],
        fact_type=item.get("fact_type", "fact"),
        confidence=float(item.get("confidence", 0.5)),
        entities=[str(e) for e in item.get("entities", []) if e],
        source_text=source_text,
        **llm._validity(item),
        **llm._meaning(item),
    )


def _row(content: str, *, now: datetime, **kw: Any) -> Any:
    row = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        content=content,
        content_hash=hashlib.sha256(content.strip().lower().encode()).hexdigest(),
        status="active",
        trust_tier="self",
        superseded_by=None,
        supersedes=None,
        updated_at=None,
        created_at=now,
        valid_from=now,
        valid_until=None,
        embedding=[1.0, 0.0],
        properties={},
        importance=0.5,
        tags=[],
        old=False,
    )
    for k, v in kw.items():
        setattr(row, k, v)
    return row


class Harness:
    """A MemoryManager over in-memory stand-ins; records what the save path decided."""

    def __init__(self, now: datetime, rows: list[Any], similarity: float = 0.0) -> None:
        from life_graph.core import slots
        from life_graph.core.memory_manager import MemoryManager
        from life_graph.services.contradiction import ContradictionDetector
        from life_graph.services.memory import supersession

        self.now = now
        self.rows = {str(r.id): r for r in rows}
        self.similarity = similarity
        self.superseded: list[tuple[str, str, bool]] = []
        self.queued: list[tuple[str, bool, str | None]] = []
        self.low: list[str] = []
        self.merged: list[str] = []
        self.links: list[tuple[Any, Any, str]] = []
        mgr = MemoryManager.__new__(MemoryManager)
        mgr._tagger = SimpleNamespace(score=lambda content, context: (0.5, "normal"))
        mgr._contradiction_detector = ContradictionDetector(store=None)  # type: ignore[arg-type]
        harness = self

        async def find_exact_duplicate(content_hash: str) -> Any:
            return next((r for r in harness.rows.values() if r.content_hash == content_hash), None)

        async def find_similarity_candidates(embedding: Any, limit: int = 15) -> list:
            return [(r, harness.similarity) for r in harness.rows.values() if r.old]

        async def store(memory_create: Any, **kw: Any) -> Any:
            row = _row(
                memory_create.content,
                now=harness.now,
                status=kw.get("status", "pending"),
                trust_tier=kw.get("trust_tier"),
                properties=dict(memory_create.properties or {}),
                valid_from=kw.get("valid_from") or harness.now,
                valid_until=kw.get("valid_until"),
                old=False,
            )
            harness.rows[str(row.id)] = row
            return row

        async def retrieve(mid: Any) -> Any:
            return harness.rows.get(str(mid))

        async def update(mid: Any, upd: Any) -> Any:
            harness.merged.append(str(mid))
            return harness.rows.get(str(mid))

        async def touch(mid: Any) -> None:
            return None

        mgr._store = SimpleNamespace(
            find_exact_duplicate=find_exact_duplicate,
            find_similarity_candidates=find_similarity_candidates,
            store=store,
            retrieve=retrieve,
            update=update,
            touch=touch,
        )

        async def no_op(*_a: Any, **_k: Any) -> None:
            return None

        async def same_slot(slot: str) -> list[tuple[str, str]]:
            out = []
            for r in harness.rows.values():
                props = r.properties or {}
                if not r.old or r.status != "active" or not props.get("slot"):
                    continue
                again = slots.normalise(
                    props["slot"], subject=props.get("subject") or "owner", content=r.content
                )
                if again == slot:
                    out.append((str(r.id), f"New value for {slot}"))
            return out

        async def supersede(old_id: str, new_id: str, reason: str, **kw: Any) -> None:
            old, new = harness.rows.get(str(old_id)), harness.rows.get(str(new_id))
            world = bool(kw.get("world_change"))
            supersession.apply(TENANT, old, new, why=reason, old_statuses=None, world_change=world)
            harness.superseded.append((str(old_id), str(new_id), world))

        async def queue(old_id: str, new_id: str, reason: str, **kw: Any) -> None:
            harness.queued.append(
                (str(old_id), bool(kw.get("applied", True)), kw.get("confidence"))
            )

        async def embed(text_: str) -> list[float]:
            return [harness.similarity, math.sqrt(max(0.0, 1 - harness.similarity**2))]

        mgr._file_slot = no_op
        mgr._learn_names = no_op
        mgr._same_slot_active = same_slot
        mgr.supersede = supersede
        mgr._queue_contradiction_approval = queue
        mgr._generate_embedding = embed
        self.mgr = mgr

    @contextlib.contextmanager
    def patched(self):
        """The DB-backed helpers the save path calls, recorded instead."""
        from life_graph.services.memory import associations, links, supersession

        async def file_low(tenant: str, old_id: Any, new_id: Any, reason: str, **_k: Any) -> bool:
            self.low.append(str(old_id))
            return True

        async def create_link(source: Any, target: Any, link_type: str, **_k: Any) -> Any:
            self.links.append((source, target, link_type))
            return None

        async def said_together(*_a: Any, **_k: Any) -> None:
            return None

        with (
            mock.patch.object(supersession, "file_possible_update", file_low),
            mock.patch.object(links, "create_link", create_link),
            mock.patch.object(associations, "said_together", said_together),
        ):
            yield


@contextlib.contextmanager
def flags_on():
    from scripts.context_quality_ingest import flags_on as on

    with on():
        yield


# ── Supersession ──────────────────────────────────────────────


async def run_supersession_case(case: dict[str, Any], now: datetime) -> dict[str, Any]:
    from life_graph.core.tenant import tenant_scope

    o = case["old"]
    props = {k: o[k] for k in ("slot", "subject", "changes_over_time", "project") if k in o}
    if o.get("fact_type"):
        props["fact_type"] = o["fact_type"]
    began = now - timedelta(days=float(o.get("created_d", 400)))
    old = _row(
        o["content"],
        now=began,
        status=o.get("status", "active"),
        trust_tier=o.get("trust_tier", "self"),
        properties=props,
        old=True,
    )
    h = Harness(now, [old], similarity=float(case.get("similarity", 0.8)))
    fact = to_fact(case["new"], case.get("source_text") or case["new"]["content"])
    with h.patched(), tenant_scope(TENANT):
        await h.mgr._process_fact(
            fact,
            case.get("context"),
            "chat",
            trust_tier=case.get("trust_tier", "self"),
            embedding=await h.mgr._generate_embedding(fact.content),
        )
    if h.merged:
        tier = "merged"
    elif h.superseded:
        tier = "high"
    elif any(not applied for _, applied, _ in h.queued):
        tier = "medium"
    elif h.low:
        tier = "low"
    else:
        tier = "none"
    return {"tier": tier, "world_end": old.valid_until is not None}


def score_supersession(rows: list[tuple[dict, dict]]) -> dict[str, Any]:
    proposed = [(c, r) for c, r in rows if r["tier"] in SUPERSEDE_TIERS]
    s12 = [(c, r) for c, r in rows if c["category"] in ("s1", "s2", "correction")]
    ends = [(c, r) for c, r in rows if r["world_end"]]
    want_end = [(c, r) for c, r in rows if c["gold"].get("world_end")]
    low = [c for c, r in rows if r["tier"] == "low"]
    return {
        "cases": len(rows),
        "precision": _rate(sum(c["gold"]["same_attribute"] for c, _ in proposed), len(proposed)),
        "recall": _rate(sum(r["tier"] in SUPERSEDE_TIERS for _, r in s12), len(s12)),
        "tier_accuracy": _rate(sum(r["tier"] == c["gold"]["tier"] for c, r in rows), len(rows)),
        "world_end_precision": _rate(
            sum(bool(c["gold"].get("world_end")) for c, _ in ends), len(ends)
        ),
        "world_end_recall": _rate(sum(r["world_end"] for _, r in want_end), len(want_end)),
        "low_items_per_100_facts": round(100 * len(low) / max(len(rows), 1), 1),
        "denominators": {
            "precision": len(proposed),
            "recall": len(s12),
            "tier_accuracy": len(rows),
            "world_end_precision": len(ends),
            "world_end_recall": len(want_end),
        },
        "wrong_auto_supersede": [
            c["id"] for c, r in rows if r["tier"] == "high" and not c["gold"]["same_attribute"]
        ],
        "outside": [
            c["id"]
            for c, r in rows
            if c.get("trust_tier", "self") in OUTSIDE and r["tier"] in ("high", "low")
        ],
        "correction_given_valid_until": [
            c["id"] for c, r in rows if c["new"].get("correction") and r["world_end"]
        ],
        "misses": [
            f"{c['id']}: {r['tier']}{' +end' if r['world_end'] else ''} (gold {c['gold']['tier']}"
            f"{' +end' if c['gold'].get('world_end') else ''})"
            for c, r in rows
            if r["tier"] != c["gold"]["tier"] or r["world_end"] != bool(c["gold"].get("world_end"))
        ],
    }


# ── Typed links ───────────────────────────────────────────────


async def run_links_case(case: dict[str, Any], now: datetime) -> dict[str, Any]:
    from life_graph.core.tenant import tenant_scope
    from scripts.context_quality_ingest import _replay_class

    raw = json.dumps({"facts": case["facts"]}, ensure_ascii=False)
    # The real parse (extraction/llm.py), leads_to positions included.
    facts = await _replay_class()({case["source_text"]: raw})._extract_local(case["source_text"])
    existing = []
    ex = case.get("existing")
    if ex is not None:
        item = case["facts"][ex["index"]]
        existing.append(
            _row(item["content"], now=now, trust_tier=ex.get("trust_tier", "self"), old=False)
        )
    h = Harness(now, existing)
    owner_ids = {r.id for r in existing}
    with h.patched(), tenant_scope(TENANT):
        await h.mgr.store_facts(facts, source="chat", trust_tier=case.get("trust_tier", "self"))
    index_of = {}
    for row in h.rows.values():
        for i, item in enumerate(case["facts"]):
            if row.content.strip().lower() == item["content"].strip().lower():
                index_of.setdefault(row.id, i)
    got = {(index_of.get(s), index_of.get(t), k) for s, t, k in h.links}
    return {
        "links": sorted(got, key=str),
        "touch_owner": sum(1 for s, t, _ in h.links if s in owner_ids or t in owner_ids),
    }


def score_links(rows: list[tuple[dict, dict]]) -> dict[str, Any]:
    out: dict[str, Any] = {"cases": len(rows), "denominators": {}}
    for kind in ("BECAUSE", "LEADS_TO"):
        made = [(c, link) for c, r in rows for link in r["links"] if link[2] == kind]
        gold = [(c, g) for c, _ in rows for g in c["gold"] if g["type"] == kind]
        golds = {(c["id"], g["from"], g["to"]) for c, g in gold}
        mades = {(c["id"], link[0], link[1]) for c, link in made}
        key = kind.lower()
        out[f"{key}_precision"] = _rate(len(mades & golds), len(mades))
        out[f"{key}_recall"] = _rate(len(mades & golds), len(golds))
        out["denominators"][f"{key}_precision"] = len(mades)
        out["denominators"][f"{key}_recall"] = len(golds)
    out["outside"] = [c["id"] for c, r in rows if r["touch_owner"]]
    out["misses"] = [
        f"{c['id']}: {r['links']} (gold {[(g['from'], g['to'], g['type']) for g in c['gold']]})"
        for c, r in rows
        if set(map(tuple, r["links"])) != {(g["from"], g["to"], g["type"]) for g in c["gold"]}
    ]
    return out


# ── Decisions ─────────────────────────────────────────────────


def run_capture_case(case: dict[str, Any]) -> int:
    """Candidate decisions the capture spine would emit for *case*'s words."""
    from life_graph.services.capture_processors import CaptureProcessors

    evt = SimpleNamespace(surface=case["surface"], trust_tier=case.get("trust_tier"))
    if not CaptureProcessors._is_self(evt):
        return 0
    return len(CaptureProcessors._detect_decisions(case["text"]))


async def run_moves_case(case: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Move one decision through the gates each path uses; the final status and trail."""
    from life_graph.core.errors import DomainError
    from life_graph.models.schemas import OWNER_DECISION_STATUSES
    from life_graph.services import decision_lifecycle as dl

    d = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        status=case.get("start") or dl.CANDIDATE,
        properties={},
        decided_at=None,
        reviewed_at=None,
        superseded_by=None,
        superseded_at=None,
    )

    class _Session:
        async def commit(self) -> None:
            return None

        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *_a: Any) -> None:
            return None

    async def linked(_s: Any, _t: Any, _m: Any, statuses: Any = None) -> Any:
        return d if statuses is None or d.status in statuses else None

    refused = 0
    for st in case["steps"]:
        actor, via, to = st["actor"], st["via"], st["to"]
        by = ACTOR_LABEL[actor]
        is_owner = actor in OWNER_ACTORS
        try:
            if via == "create":
                # api/judgment.py create_decision: owner statuses only for the owner.
                status = to if (to not in OWNER_DECISION_STATUSES or is_owner) else dl.CANDIDATE
                d.status = status
                if is_owner and status != dl.CANDIDATE:
                    d.properties = dl.with_entry({}, None, status, by=by, owner=True, at=now)
            elif via == "route":
                # api/judgment.py _owner: 403 unless the caller is the owner.
                if not is_owner:
                    refused += 1
                    continue
                dl.check(d.status, to, owner=True)
                if to == dl.SUPERSEDED:
                    d.superseded_at = now
                dl.apply_move(d, to, by=by, owner=True, now=now)
            elif via == "memory_review":
                action = {dl.DECIDED: "approve", dl.DISCARDED: "reject"}[to]
                with (
                    mock.patch.object(dl, "async_session", _Session),
                    mock.patch.object(dl, "_linked", linked),
                ):
                    if not await dl.follow_memory_review(TENANT, uuid.uuid4(), action, by):
                        refused += 1
            elif via == "mirror":
                dl.check(d.status, to, owner=False, mirror=True)
                dl.apply_move(d, to, by=dl.MIRROR_BY, owner=False, now=now)
        except DomainError:
            refused += 1
    return {"final": d.status, "confirmed": dl.owner_confirmed(d), "refused": refused}


def score_decisions(caps: list[tuple[dict, int]], moves: list[tuple[dict, dict]]) -> dict[str, Any]:
    from life_graph.services import decision_lifecycle as dl

    found = [(c, n) for c, n in caps if n > 0]
    gold = [(c, n) for c, n in caps if c["gold"]["candidates"] > 0]
    owner_less = [
        (c, r) for c, r in moves if not any(s["actor"] in OWNER_ACTORS for s in c["steps"])
    ]
    return {
        "capture_cases": len(caps),
        "moves_cases": len(moves),
        "detection_precision": _rate(
            sum(c["gold"]["candidates"] > 0 for c, _ in found), len(found)
        ),
        "detection_recall": _rate(sum(n > 0 for _, n in gold), len(gold)),
        "lifecycle_accuracy": _rate(
            sum(
                r["final"] == c["gold"]["final"] and r["confirmed"] == c["gold"]["confirmed"]
                for c, r in moves
            ),
            len(moves),
        ),
        "denominators": {
            "detection_precision": len(found),
            "detection_recall": len(gold),
            "lifecycle_accuracy": len(moves),
        },
        "confirmed_without_owner": [
            c["id"] for c, r in owner_less if r["final"] in dl.CONFIRMED_STATUSES or r["confirmed"]
        ],
        "outside": [
            c["id"]
            for c, n in caps
            if n > 0
            and (
                c.get("trust_tier") in OUTSIDE
                or c["surface"] in ("email", "mcp", "whatsapp", "api")
            )
        ],
        "misses": [
            f"{c['id']}: {n} candidates (gold {c['gold']['candidates']})"
            for c, n in caps
            if (n > 0) != (c["gold"]["candidates"] > 0)
        ]
        + [
            f"{c['id']}: {r['final']}/{r['confirmed']} (gold {c['gold']['final']}/{c['gold']['confirmed']})"
            for c, r in moves
            if r["final"] != c["gold"]["final"] or r["confirmed"] != c["gold"]["confirmed"]
        ],
    }


# ── Run, verify ───────────────────────────────────────────────


async def evaluate(data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Score every list in *data*; no DB, no model."""
    now = now or datetime.now(UTC)
    calls: dict[str, int] = {}
    with flags_on(), _no_models(calls):
        wt = score_world_time(data)
        we = score_world_end(data)
        sup = [(c, await run_supersession_case(c, now)) for c in data.get("supersession", [])]
        lnk = [(c, await run_links_case(c, now)) for c in data.get("links", [])]
        caps = [
            (c, run_capture_case(c)) for c in data.get("decisions", []) if c["kind"] == "capture"
        ]
        mvs = [
            (c, await run_moves_case(c, now))
            for c in data.get("decisions", [])
            if c["kind"] == "moves"
        ]
    s, li, de = score_supersession(sup), score_links(lnk), score_decisions(caps, mvs)
    all_cases = (
        data.get("world_time", [])
        + data.get("world_end", [])
        + data.get("supersession", [])
        + data.get("links", [])
        + data.get("decisions", [])
    )
    tamil = sum(1 for c in all_cases if c.get("lang") in ("ta", "tanglish"))
    zero = {
        "world_time_set_where_unknown": len(wt["set_where_unknown"]),
        "world_time_future_given_start": len(wt["future_given_start"]),
        "world_end_set_where_unknown": len(we["set_where_unknown"]),
        "world_end_before_start": len(we["before_start"]),
        "wrong_auto_supersede": len(s["wrong_auto_supersede"]),
        "decision_confirmed_without_owner": len(de["confirmed_without_owner"]),
        "outside_supersede_or_link": len(s["outside"]) + len(li["outside"]) + len(de["outside"]),
        "correction_given_valid_until": len(s["correction_given_valid_until"]),
        "model_calls": sum(calls.values()),
    }
    return {
        "benchmark": "life_graph_ingestion_structure_v1",
        "cases_sha256": hashlib.sha256(CASES_PATH.read_bytes()).hexdigest(),
        "cases": len(all_cases),
        "tamil_or_tanglish_share": round(tamil / max(len(all_cases), 1), 3),
        "zero_tolerance": zero,
        "world_time": wt,
        "world_end": we,
        "supersession": s,
        "links": li,
        "decisions": de,
    }


@contextlib.contextmanager
def _no_models(calls: dict[str, int]):
    """Any chat client or cloud route counts a call and raises (nothing here may call one)."""
    from life_graph.services.llm import client as llm_client

    def boom(*_a: Any, **_k: Any) -> Any:
        calls["chat_client"] = calls.get("chat_client", 0) + 1
        raise RuntimeError("a model was called during the ingestion structure eval")

    with mock.patch.object(llm_client.LMStudioClient, "__init__", boom):
        yield


#: The rates --verify holds to the baseline, per section.
RATES = {
    "world_time": ("precision", "recall"),
    "world_end": ("precision", "recall"),
    "supersession": (
        "precision",
        "recall",
        "tier_accuracy",
        "world_end_precision",
        "world_end_recall",
    ),
    "links": ("because_precision", "because_recall", "leads_to_precision", "leads_to_recall"),
    "decisions": ("detection_precision", "detection_recall", "lifecycle_accuracy"),
}


def baseline_of(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "about": "Floors for scripts/eval_ingestion_structure.py, recorded from a real run of today's code. Not targets: ADR §6.1 sets those.",
        **{
            sec: {k: report[sec][k] for k in keys if report[sec].get(k) is not None}
            for sec, keys in RATES.items()
        },
    }


def regressions(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    fails = [f"{k} = {v} (target 0)" for k, v in report["zero_tolerance"].items() if v]
    for sec, floors in baseline.items():
        if sec not in RATES:
            continue
        for key, floor in floors.items():
            got = report[sec].get(key)
            den = report[sec].get("denominators", {}).get(key) or 0
            slack = max(TOLERANCE, 1.0 / den) if den and den < 20 else TOLERANCE
            if got is None or got < floor - slack - 1e-9:
                fails.append(f"{sec}.{key} = {got} < baseline {floor} - {slack:.3f}")
    return fails


def markdown(report: dict[str, Any]) -> str:
    z = report["zero_tolerance"]
    lines = [
        "# Ingestion structure eval",
        "",
        f"{report['cases']} cases, {report['tamil_or_tanglish_share']:.0%} Tamil or Tanglish.",
        "",
        "Zero-tolerance: " + ", ".join(f"{k} {v}" for k, v in z.items()),
        "",
    ]
    for sec, keys in RATES.items():
        r = report[sec]
        lines.append(
            f"- {sec}: "
            + ", ".join(f"{k} {r.get(k)}" for k in keys)
            + (
                f", low items per 100 facts {r['low_items_per_100_facts']}"
                if sec == "supersession"
                else ""
            )
        )
        for m in r.get("misses", []):
            lines.append(f"  - miss: {m}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Exit non-zero on a zero-tolerance count or a regression",
    )
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    import logging

    logging.getLogger("life_graph").setLevel(logging.ERROR)
    report = asyncio.run(evaluate(load()))
    print(markdown(report))
    if args.write_report:
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if args.write_baseline:
        BASELINE_PATH.write_text(json.dumps(baseline_of(report), indent=2) + "\n", encoding="utf-8")
        print(f"Wrote baseline {BASELINE_PATH.name}")
    if args.verify:
        base = (
            json.loads(BASELINE_PATH.read_text(encoding="utf-8")) if BASELINE_PATH.exists() else {}
        )
        fails = regressions(report, base)
        if fails:
            print("FAIL:\n  " + "\n  ".join(fails), file=sys.stderr)
            return 1
        print("verify: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
