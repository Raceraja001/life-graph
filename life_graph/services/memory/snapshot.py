"""Context snapshot (M8 Stage 1): what Life Graph holds that bears on a question.

A read model, not a store. ``assemble_context`` reads existing records — the
current tenant's memories, decisions and open intentions — and returns them as
references with labels: where each came from, how sure it is, how fresh, and
why it was picked. It writes nothing, keeps no cache and adds no table
(docs/specs/personal-context-intelligence.md §5).

The contract
============

Locality. No model is called. The only model touch is the query embedding,
made once through the normal memory path (MemoryManager.generate_embedding,
local), and reused for both searches. The relevance judge is off
(``retrieve(judge=False)``). If the query cannot be embedded, or the database
fails, the snapshot says ``insufficient`` and holds nothing; it never falls
back to anything else.

Determinism. The same records, query and ``as_of`` give the same snapshot.
Items are ordered by score (high first), then recorded time (newest first),
then kind and id. Scores are the search's own fused rank score for a search
hit; every other reason has a fixed prior (``REASON_SCORE``), which only
orders, it does not claim relevance.

Tenant. Every read is scoped to the tenant in the request context
(core/tenant.py), the same contextvar the store reads.

Retrieved text is data. ``content`` is the source text, whitespace-collapsed
and truncated; nothing in it is read as an instruction or changes a label.

Each item (:class:`ContextItem`) carries:

* ``source_ref`` — ``{"kind": "memory" | "decision" | "intention", "id"}``.
* ``dimension`` — a free label from the record (a memory's ``fact_type``,
  else its first tag; "decision"; "intention"). Never an enum.
* ``origin`` — ``user_stated`` (the owner's own words, core/evidence.py
  "said"), ``imported`` (a document, or content from outside: API, MCP, web,
  mail), ``extracted`` (deterministic extraction or Life Graph's own records)
  or ``model_proposed`` (a model wrote it: an LLM extraction, a conclusion,
  a day summary, a decision detected in conversation).
* ``confirmed`` — True only for an active memory that is the owner's own word
  or that the owner approved (core/evidence.py ``owner_confirmed``). A
  pending or model-proposed memory is never confirmed, and neither is any
  decision or intention: their state is in ``status`` and ``label`` ("decided",
  "proposed, not decided", "open intention"), not a claim about the owner.
* ``evidence`` — the core/evidence.py kind ("said", "inferred", …) and
  ``label``, the words for it ("owner said"; a candidate decision is
  "proposed, not decided").
* ``valid_from`` / ``recorded_at`` — world time and when Life Graph learned it
  (retrieval.recorded_time_of). ``world_time_known`` is False when the two are
  the same to the second: the row only says "since recorded".
* ``freshness`` — from the age of the last confirmation (recorded time or the
  owner's last reinforcement) at the snapshot's reference time:
  ``fresh`` < 7 days, ``recent`` < 30, ``aging`` < 180, ``stale`` beyond,
  ``unknown`` with no time at all.
* ``reason`` — why it was included: ``search_hit`` (vector or keyword match,
  fused), ``entity_link``, ``neighbour``, ``dated_episode``, ``decision``
  (a keyword match on a decision), ``open_intention`` (a keyword match on an
  open intention).

``conflicts`` pairs records that disagree, both sides by reference, never
merged or resolved: a memory and the one it superseded, a pending
contradiction approval touching an included memory, a decision and the one it
superseded.

``exclusions`` counts what was held back and why: ``expired`` (valid time
ended), ``not_yet_valid``, ``superseded``, ``pending_only`` (awaiting review),
``hostile`` (trust tier hostile_possible), ``discarded`` (a discarded
decision) and ``over_budget``. They come from a second search over all
statuses with the same embedding, so they describe near matches, not the
whole store.

``insufficient`` is True when nothing passed, or memory could not be searched;
``explanation`` says which.

``timings_ms`` is how long each stage took, in milliseconds (``time.monotonic``):
``embed`` (the query embedding), ``retrieve`` (retrieve(): search, entity
links, neighbours, day summaries), ``exclusions`` (the second search),
``conflicts`` (supersession and contradiction reads), ``decisions``,
``intentions`` and ``total``. A stage that did not run is absent. Timings are
numbers only, never content, and they are not part of the snapshot's identity:
they are left out of equality, and a determinism check must leave them out too
(:func:`without_timings`).

The budget (:class:`Budget`, default 40 items / 6000 characters of content,
300 per item) is hard: what does not fit is counted as ``over_budget``.

What Stage 1 does not do: projects, tasks, connectors, feedback, prompts.
The kernel only builds a snapshot in shadow mode
(settings.context_snapshot_shadow) and keeps :meth:`ContextSnapshot.compact`
— references, labels, reasons and counts, no content — in the turn trace.

The compact form is format 2 (``"v": 2``, M8 Stage 2,
docs/design/adr-m8-context-change-detection.md §5.7): it also keeps the
snapshot's ``reference_time`` and, per item, ``fp`` (a 16-hex fingerprint of
the record's normalised text, salted with its id, :func:`fingerprint`) and
``rec`` (its recorded time). That is what lets the next turn tell an edit
from no change (services/memory/changes.py). Still no content.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import defer

from life_graph import runtime
from life_graph.core import evidence as ev
from life_graph.core.tenant import get_current_tenant_id, tenant_scope
from life_graph.core.trust import is_excluded_from_agents
from life_graph.models.db import Approval, Decision, Intention, Memory
from life_graph.services.memory import retrieval
from life_graph.services.memory.context import search_text
from life_graph.storage.database import async_session

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

PURPOSES = ("conversation", "project_task", "daily_brief", "decision", "question")

# Origins
USER_STATED = "user_stated"
IMPORTED = "imported"
EXTRACTED = "extracted"
MODEL_PROPOSED = "model_proposed"

# Reasons beyond retrieve's own (retrieval.SEARCH_HIT, ENTITY_LINK, …)
DECISION = "decision"
OPEN_INTENTION = "open_intention"

#: Ordering score for a reason that has no search score of its own. Below a
#: typical search hit (fused scores run ~0.5-1.0 for the top ranks), so a
#: direct match goes first; these are priors for ordering, not relevance.
REASON_SCORE = {
    retrieval.DATED_EPISODE: 0.40,
    retrieval.ENTITY_LINK: 0.30,
    DECISION: 0.25,
    OPEN_INTENTION: 0.25,
    retrieval.NEIGHBOUR: 0.20,
    retrieval.COLD_TIER: 0.10,
}

#: Freshness classes: (upper bound in days, name), checked in order.
FRESHNESS = ((7, "fresh"), (30, "recent"), (180, "aging"))
STALE = "stale"
UNKNOWN = "unknown"

#: Decision statuses that are current, and the label each one gets.
DECISION_LABEL = {
    "candidate": "proposed, not decided",
    "decided": "decided",
    "reviewed": "decided and reviewed",
}
#: Intention statuses that are still open (services/commitments.py nudges too).
OPEN_INTENTION_STATUSES = ("pending", "nudged")
#: Most decisions / intentions one snapshot reads.
SIDE_LIMIT = 5
#: Near matches inspected for the exclusion counts.
EXCLUSION_POOL = 20
#: Statuses of the exclusion search (archived and rejected are not counted).
POOL_STATUSES = ("active", "pending", "superseded")
#: Shadow mode's time box (kernel/process_manager.py).
SHADOW_TIMEOUT_S = 1.0
#: The clock stage timings read (a test replaces it; the event loop keeps its own).
_clock = time.monotonic
#: The stages ``timings_ms`` reports, in this order.
TIMING_STAGES = (
    "embed",
    "retrieve",
    "exclusions",
    "conflicts",
    "decisions",
    "intentions",
    "total",
)

_WORD = re.compile(r"\w+")
#: Format of :meth:`ContextSnapshot.compact` (2: reference_time, fp, rec).
COMPACT_FORMAT = 2
#: Hex characters of a record fingerprint (64 bits).
FINGERPRINT_HEX = 16


def normalise_text(text_: str | None) -> str:
    """*text_* for fingerprinting: NFKC, lower case, punctuation gone, spaces collapsed.

    A case, spacing or punctuation edit (a trailing full stop included) gives
    the same text, so it is not an edit. Letters and marks of every script
    are kept: only Unicode punctuation (category P*) is dropped.
    """
    folded = unicodedata.normalize("NFKC", text_ or "").lower()
    kept = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in folded)
    return " ".join(kept.split())


def fingerprint(record_id: object, text_: str | None) -> str:
    """16 hex characters of sha256(id + newline + normalised text).

    Salted with the record id, so two records with the same words differ and
    the value says nothing about the text on its own. Tags, importance and
    access counts are not part of it.
    """
    raw = f"{record_id}\n{normalise_text(text_)}".encode()
    return hashlib.sha256(raw).hexdigest()[:FINGERPRINT_HEX]


@dataclass(frozen=True)
class Budget:
    """Hard caps on one snapshot."""

    max_items: int = 40
    max_chars: int = 6000
    item_chars: int = 300


DEFAULT_BUDGET = Budget()


@dataclass(frozen=True)
class SourceRef:
    kind: str  # memory | decision | intention
    id: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.id}

    def key(self) -> str:
        return f"{self.kind}:{self.id}"


@dataclass(frozen=True)
class ContextItem:
    source_ref: SourceRef
    dimension: str
    origin: str
    confirmed: bool
    evidence: str
    label: str
    status: str
    reason: str
    score: float
    valid_from: str | None
    recorded_at: str | None
    world_time_known: bool
    freshness: str
    content: str
    #: :func:`fingerprint` of the full record text ("" when not known). Kept
    #: only in the compact (trace) form, never in to_dict or an API.
    fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_ref": self.source_ref.to_dict(),
            "dimension": self.dimension,
            "origin": self.origin,
            "confirmed": self.confirmed,
            "evidence": self.evidence,
            "label": self.label,
            "status": self.status,
            "reason": self.reason,
            "score": self.score,
            "valid_from": self.valid_from,
            "recorded_at": self.recorded_at,
            "world_time_known": self.world_time_known,
            "freshness": self.freshness,
            "content": self.content,
        }


@dataclass(frozen=True)
class ConflictSide:
    source_ref: SourceRef
    role: str  # current | previous | existing | proposed
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"source_ref": self.source_ref.to_dict(), "role": self.role, "status": self.status}


@dataclass(frozen=True)
class ContextConflict:
    kind: str  # supersession | pending_contradiction | decision_supersession
    sides: tuple[ConflictSide, ...]
    approval_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "sides": [s.to_dict() for s in self.sides],
            "approval_id": self.approval_id,
        }


@dataclass(frozen=True)
class ContextSnapshot:
    query: str
    purpose: str
    as_of: str | None
    reference_time: str
    budget: Budget
    items: tuple[ContextItem, ...] = ()
    conflicts: tuple[ContextConflict, ...] = ()
    exclusions: tuple[tuple[str, int], ...] = ()
    insufficient: bool = True
    explanation: str = ""
    content_chars: int = 0
    sources: tuple[str, ...] = field(default=())
    #: (stage, milliseconds) in TIMING_STAGES order; not part of equality.
    timings_ms: tuple[tuple[str, float], ...] = field(default=(), compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "purpose": self.purpose,
            "as_of": self.as_of,
            "reference_time": self.reference_time,
            "budget": {
                "max_items": self.budget.max_items,
                "max_chars": self.budget.max_chars,
                "item_chars": self.budget.item_chars,
            },
            "items": [i.to_dict() for i in self.items],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "exclusions": dict(self.exclusions),
            "insufficient": self.insufficient,
            "explanation": self.explanation,
            "content_chars": self.content_chars,
            "sources": list(self.sources),
            "timings_ms": dict(self.timings_ms),
        }

    def compact(self) -> dict[str, Any]:
        """References, labels, reasons and counts only: no content, no query.

        Format 2 (``v``) adds ``reference_time``, ``sources`` and, per item,
        ``fp`` and ``rec``; a conflict keeps its sides' statuses and its
        approval id. All of it is what the next turn's comparison needs
        (services/memory/changes.py); none of it is record text.
        """
        return {
            "v": COMPACT_FORMAT,
            "reference_time": self.reference_time,
            "sources": list(self.sources),
            "items": [
                {
                    "ref": i.source_ref.key(),
                    "dimension": i.dimension,
                    "origin": i.origin,
                    "confirmed": i.confirmed,
                    "evidence": i.evidence,
                    "status": i.status,
                    "reason": i.reason,
                    "freshness": i.freshness,
                    "world_time_known": i.world_time_known,
                    "fp": i.fingerprint,
                    "rec": i.recorded_at,
                }
                for i in self.items
            ],
            "conflicts": [
                {
                    "kind": c.kind,
                    "refs": [s.source_ref.key() for s in c.sides],
                    "statuses": [s.status for s in c.sides],
                    "approval": c.approval_id,
                }
                for c in self.conflicts
            ],
            "exclusions": dict(self.exclusions),
            "insufficient": self.insufficient,
            "timings_ms": dict(self.timings_ms),
        }


def without_timings(snapshot_dict: dict[str, Any]) -> dict[str, Any]:
    """*snapshot_dict* (to_dict or compact) without ``timings_ms``: for determinism checks."""
    return {k: v for k, v in snapshot_dict.items() if k != "timings_ms"}


# ── Labels (pure) ─────────────────────────────────────────────


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _props(m: Any) -> dict[str, Any]:
    props = getattr(m, "properties", None)
    return props if isinstance(props, dict) else {}


def freshness_of(last: datetime | None, ref: datetime) -> str:
    """The documented freshness class of something last confirmed at *last*."""
    if last is None:
        return UNKNOWN
    days = (ref - last).total_seconds() / 86400
    for bound, name in FRESHNESS:
        if days < bound:
            return name
    return STALE


def world_time_known(valid_from: datetime | None, recorded: datetime | None) -> bool:
    """False when the row has no world time of its own (valid_from = recorded, to the second)."""
    if valid_from is None:
        return False
    if recorded is None:
        return True
    return int(valid_from.timestamp()) != int(recorded.timestamp())


def memory_origin(m: Any) -> str:
    """user_stated / imported / extracted / model_proposed, from the row's own provenance."""
    kind = ev.evidence_of(
        getattr(m, "source_type", None), getattr(m, "trust_tier", None), _props(m)
    )
    tier = str(getattr(m, "extraction_tier", "") or "").lower()
    if kind in (ev.INFERRED, ev.SUMMARY) or tier == "llm":
        return MODEL_PROPOSED
    if kind in (ev.OUTSIDE, ev.DOCUMENT):
        return IMPORTED
    if tier in ("regex", "spacy"):
        return EXTRACTED
    if kind == ev.SAID:
        return USER_STATED
    # OBSERVED: recorded by Life Graph's own systems (scans, agent results).
    return EXTRACTED


def memory_confirmed(m: Any, origin: str) -> bool:
    """Active, and the owner's own word or approved by the owner. Pending never is."""
    if str(getattr(m, "status", "") or "") != "active":
        return False
    if ev.owner_confirmed(_props(m)):
        return True
    return origin == USER_STATED


def memory_dimension(m: Any) -> str:
    fact_type = _props(m).get("fact_type")
    if isinstance(fact_type, str) and fact_type.strip():
        return fact_type.strip().lower()[:40]
    tags = getattr(m, "tags", None) or []
    for tag in tags:
        if isinstance(tag, str) and tag.strip():
            return tag.strip().lower()[:40]
    return "memory"


def _clip(content: str | None, limit: int) -> str:
    flat = " ".join((content or "").split())
    return flat if len(flat) <= limit else flat[: max(0, limit - 1)] + "…"


def _last_confirmed(recorded: datetime | None, reinforced: Any) -> datetime | None:
    seen = [t for t in (recorded, retrieval._as_utc(reinforced)) if t is not None]
    return max(seen) if seen else None


def memory_item(m: Any, ref: datetime, budget: Budget) -> ContextItem:
    origin = memory_origin(m)
    kind = ev.evidence_of(
        getattr(m, "source_type", None), getattr(m, "trust_tier", None), _props(m)
    )
    recorded = retrieval.recorded_time_of(m)
    valid_from = retrieval._temporal(m, "valid_from")
    reason = getattr(m, "retrieval_reason", None) or retrieval.SEARCH_HIT
    raw_score = getattr(m, "retrieval_score", None)
    score = float(raw_score) if raw_score is not None else REASON_SCORE.get(reason, 0.0)
    return ContextItem(
        source_ref=SourceRef("memory", str(m.id)),
        dimension=memory_dimension(m),
        origin=origin,
        confirmed=memory_confirmed(m, origin),
        evidence=kind,
        label=ev.PROMPT_LABEL.get(kind, kind),
        status=str(getattr(m, "status", "") or ""),
        reason=reason,
        score=round(score, 4),
        valid_from=_iso(valid_from),
        recorded_at=_iso(recorded),
        world_time_known=world_time_known(valid_from, recorded),
        freshness=freshness_of(_last_confirmed(recorded, getattr(m, "last_reinforced", None)), ref),
        content=_clip(getattr(m, "content", ""), budget.item_chars),
        fingerprint=fingerprint(m.id, getattr(m, "content", "")),
    )


def decision_text(d: Any) -> str:
    """The words of a decision that its fingerprint covers: title, then reasoning."""
    return f"{getattr(d, 'title', '') or ''}\n{getattr(d, 'reasoning', '') or ''}"


def decision_item(d: Any, ref: datetime, budget: Budget) -> ContextItem:
    # "explicit" is what the API caller declared (api/judgment.py), so it is
    # imported, like any other content over the API; the rest were detected
    # in conversation by Life Graph itself.
    explicit = str(getattr(d, "source", "") or "") == "explicit"
    status = str(d.status)
    recorded = retrieval._as_utc(getattr(d, "created_at", None))
    decided = retrieval._as_utc(getattr(d, "decided_at", None))
    title = str(getattr(d, "title", "") or "")
    reasoning = str(getattr(d, "reasoning", "") or "")
    return ContextItem(
        source_ref=SourceRef("decision", str(d.id)),
        dimension=DECISION,
        origin=IMPORTED if explicit else MODEL_PROPOSED,
        confirmed=False,
        evidence=ev.OUTSIDE if explicit else ev.INFERRED,
        label=DECISION_LABEL.get(status, status),
        status=status,
        reason=DECISION,
        score=REASON_SCORE[DECISION],
        valid_from=_iso(decided),
        recorded_at=_iso(recorded),
        world_time_known=world_time_known(decided, recorded),
        freshness=freshness_of(recorded, ref),
        content=_clip(f"{title}. {reasoning}" if reasoning else title, budget.item_chars),
        fingerprint=fingerprint(d.id, decision_text(d)),
    )


def intention_origin(i: Any) -> str:
    match = getattr(i, "context_match", None) or {}
    if str(getattr(i, "trigger_type", "")) == "nudge":
        return EXTRACTED  # a promise found in chat by services/commitments.py's rules
    if isinstance(match, dict) and match.get("set_by") == "jarvis":
        return MODEL_PROPOSED  # Jarvis set it from what it understood was asked
    # From mail (connector_item_id) or over the API/MCP: origin not vouched for.
    return IMPORTED


def intention_item(i: Any, ref: datetime, budget: Budget) -> ContextItem:
    recorded = retrieval._as_utc(getattr(i, "created_at", None))
    origin = intention_origin(i)
    return ContextItem(
        source_ref=SourceRef("intention", str(i.id)),
        dimension="intention",
        origin=origin,
        confirmed=False,
        evidence=ev.OBSERVED if origin == EXTRACTED else ev.OUTSIDE,
        label="open intention",
        status=str(i.status),
        reason=OPEN_INTENTION,
        score=REASON_SCORE[OPEN_INTENTION],
        valid_from=None,
        recorded_at=_iso(recorded),
        world_time_known=False,
        freshness=freshness_of(recorded, ref),
        content=_clip(getattr(i, "content", ""), budget.item_chars),
        fingerprint=fingerprint(i.id, getattr(i, "content", "")),
    )


def exclusion_reason(
    m: Any, ref: datetime, recorded_ref: datetime, included: set[str]
) -> str | None:
    """Why a near match was held back, or None when it was not (or is not counted)."""
    if str(m.id) in included:
        return None
    if is_excluded_from_agents(getattr(m, "trust_tier", None)):
        return "hostile"
    status = str(getattr(m, "status", "") or "")
    if status == "pending":
        return "pending_only"
    if (
        status == "superseded"
        or getattr(m, "superseded_by", None) is not None
        or not retrieval.is_known_at(m, recorded_ref)
    ):
        return "superseded"
    if not retrieval.is_valid_at(m, ref):
        valid_from = retrieval._temporal(m, "valid_from")
        return "not_yet_valid" if valid_from is not None and valid_from > ref else "expired"
    return None


def order_key(item: ContextItem) -> tuple[float, float, str, str]:
    recorded = retrieval._as_utc(item.recorded_at)
    return (
        -item.score,
        -(recorded.timestamp() if recorded else 0.0),
        item.source_ref.kind,
        item.source_ref.id,
    )


def apply_budget(items: list[ContextItem], budget: Budget) -> tuple[list[ContextItem], int, int]:
    """(kept items in order, content characters used, how many did not fit)."""
    kept: list[ContextItem] = []
    used = 0
    over = 0
    for item in sorted(items, key=order_key):
        if len(kept) >= budget.max_items or used + len(item.content) > budget.max_chars:
            over += 1
            continue
        kept.append(item)
        used += len(item.content)
    return kept, used, over


# ── Reads ─────────────────────────────────────────────────────


def _words(query: str) -> list[str]:
    out: list[str] = []
    for w in _WORD.findall(query.lower()):
        if w not in out:
            out.append(w)
    return out[:32]


def _tsquery(query: str) -> str:
    return " | ".join(_words(query))


async def _matching_decisions(
    tenant_id: str, query: str, ref: datetime, as_of: datetime | None
) -> list[Any]:
    tsq = _tsquery(query)
    if not tsq:
        return []
    doc = func.to_tsvector("english", Decision.title + " " + func.coalesce(Decision.reasoning, ""))
    stmt = (
        select(Decision)
        .options(defer(Decision.embedding))
        .where(Decision.tenant_id == tenant_id)
        .where(doc.op("@@")(func.to_tsquery("english", tsq)))
        .order_by(Decision.created_at.desc(), Decision.id)
        .limit(SIDE_LIMIT * 2)
    )
    if as_of is not None:
        stmt = stmt.where(Decision.created_at <= ref)
    async with async_session() as s:
        return list((await s.execute(stmt)).scalars().all())


async def _superseded_decisions(tenant_id: str, ids: list[uuid.UUID]) -> list[Any]:
    if not ids:
        return []
    stmt = (
        select(Decision)
        .options(defer(Decision.embedding))
        .where(Decision.tenant_id == tenant_id, Decision.superseded_by.in_(ids))
        .order_by(Decision.id)
    )
    async with async_session() as s:
        return list((await s.execute(stmt)).scalars().all())


async def _open_intentions(
    tenant_id: str, query: str, ref: datetime, as_of: datetime | None
) -> list[Any]:
    tsq = _tsquery(query)
    if not tsq:
        return []
    stmt = (
        select(Intention)
        .options(defer(Intention.embedding))
        .where(Intention.tenant_id == tenant_id)
        .where(Intention.status.in_(OPEN_INTENTION_STATUSES))
        .where(or_(Intention.expires_at.is_(None), Intention.expires_at > ref))
        .where(
            func.to_tsvector("english", Intention.content).op("@@")(func.to_tsquery("english", tsq))
        )
        .order_by(Intention.created_at.desc(), Intention.id)
        .limit(SIDE_LIMIT)
    )
    if as_of is not None:
        stmt = stmt.where(Intention.created_at <= ref)
    async with async_session() as s:
        return list((await s.execute(stmt)).scalars().all())


async def _memory_conflicts(tenant_id: str, included: list[Any]) -> list[ContextConflict]:
    """Supersession pairs and pending contradiction approvals touching *included*."""
    if not included:
        return []
    ids = [m.id for m in included]
    id_strs = [str(i) for i in ids]
    older = [m.supersedes for m in included if getattr(m, "supersedes", None) is not None]
    async with async_session() as s:
        chain = (
            await s.execute(
                select(Memory.id, Memory.status, Memory.superseded_by)
                .where(Memory.tenant_id == tenant_id)
                .where(or_(Memory.id.in_(older), Memory.superseded_by.in_(ids)))
            )
        ).all()
        approvals = (
            (
                await s.execute(
                    select(Approval)
                    .where(Approval.tenant_id == tenant_id)
                    .where(Approval.kind == "contradiction", Approval.status == "pending")
                    .where(
                        or_(
                            Approval.payload["memory_id_old"].astext.in_(id_strs),
                            Approval.payload["memory_id_new"].astext.in_(id_strs),
                        )
                    )
                    .order_by(Approval.id)
                )
            )
            .scalars()
            .all()
        )
        sides = {side for a in approvals for side in _approval_sides(a) if side}
        status_of: dict[str, str] = {str(m.id): str(m.status) for m in included}
        unknown = [uuid.UUID(x) for x in sides - set(status_of) if _is_uuid(x)]
        if unknown:
            rows = await s.execute(
                select(Memory.id, Memory.status)
                .where(Memory.tenant_id == tenant_id)
                .where(Memory.id.in_(unknown))
            )
            status_of.update({str(r[0]): str(r[1]) for r in rows})

    out: list[ContextConflict] = []
    by_id = {str(m.id): m for m in included}
    newer_of = {str(m.supersedes): m for m in included if getattr(m, "supersedes", None)}
    for old_id, old_status, superseded_by in chain:
        current = by_id.get(str(superseded_by)) or newer_of.get(str(old_id))
        if current is None or str(current.id) == str(old_id):
            continue
        out.append(
            ContextConflict(
                "supersession",
                (
                    ConflictSide(
                        SourceRef("memory", str(current.id)), "current", str(current.status)
                    ),
                    ConflictSide(SourceRef("memory", str(old_id)), "previous", str(old_status)),
                ),
            )
        )
    for a in approvals:
        old, new = _approval_sides(a)
        # Both sides must be this tenant's and readable; otherwise it is not shown.
        if old not in status_of or new not in status_of or not (old in by_id or new in by_id):
            continue
        out.append(
            ContextConflict(
                "pending_contradiction",
                (
                    ConflictSide(SourceRef("memory", old), "existing", status_of[old]),
                    ConflictSide(SourceRef("memory", new), "proposed", status_of[new]),
                ),
                approval_id=str(a.id),
            )
        )
    return out


def _approval_sides(a: Any) -> tuple[str, str]:
    """(old memory id, new memory id) of a contradiction approval; "" when missing."""
    p = a.payload if isinstance(a.payload, dict) else {}
    return str(p.get("memory_id_old") or ""), str(p.get("memory_id_new") or "")


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _conflict_key(c: ContextConflict) -> tuple[str, ...]:
    return (c.kind, *(s.source_ref.key() for s in c.sides))


def _dedupe_conflicts(conflicts: list[ContextConflict]) -> tuple[ContextConflict, ...]:
    seen: dict[tuple[str, ...], ContextConflict] = {}
    for c in conflicts:
        seen.setdefault(_conflict_key(c), c)
    return tuple(sorted(seen.values(), key=_conflict_key))


# ── Assembly ──────────────────────────────────────────────────


@dataclass
class _Parts:
    items: list[ContextItem] = field(default_factory=list)
    conflicts: list[ContextConflict] = field(default_factory=list)
    excluded: dict[str, int] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)

    def exclude(self, reason: str, n: int = 1) -> None:
        if n:
            self.excluded[reason] = self.excluded.get(reason, 0) + n

    @contextlib.contextmanager
    def timed(self, stage: str) -> Iterator[None]:
        """Record how long the block took as *stage* (also when it raises)."""
        started = _clock()
        try:
            yield
        finally:
            self.timings[stage] = _ms_since(started)

    def timings_tuple(self) -> tuple[tuple[str, float], ...]:
        return tuple((k, self.timings[k]) for k in TIMING_STAGES if k in self.timings)


def _ms_since(started: float) -> float:
    return round((_clock() - started) * 1000, 1)


async def _memories(
    parts: _Parts,
    tenant_id: str,
    query: str,
    embedding: list[float],
    ref: datetime,
    as_of: datetime | None,
    budget: Budget,
) -> None:
    with parts.timed("retrieve"):
        found = await retrieval.retrieve(
            query,
            limit=budget.max_items,
            as_of=as_of,
            judge=False,
            query_embedding=embedding,
        )
    kept: list[Any] = []
    for m in found or []:
        if is_excluded_from_agents(getattr(m, "trust_tier", None)):
            parts.exclude("hostile")
        elif str(getattr(m, "status", "")) == "pending":
            parts.exclude("pending_only")
        else:
            kept.append(m)
    parts.items += [memory_item(m, ref, budget) for m in kept]
    parts.sources.append("memories")
    # Near matches that did not make it, by reason: a second search over
    # every status with the same embedding (no model call).
    recorded_ref = datetime.now(UTC)
    included = {str(m.id) for m in found or []}
    with parts.timed("exclusions"):
        pool = await runtime.get_store().hybrid_search(
            embedding=embedding,
            query_text=query,
            limit=EXCLUSION_POOL,
            statuses=POOL_STATUSES,
            include_expired=True,
            # Search leaves hostile rows out by default; this pool only counts
            # what was held back, so it asks for them to report "hostile".
            include_hostile=True,
        )
    for m, _ in pool:
        reason = exclusion_reason(m, ref, recorded_ref, included)
        if reason:
            parts.exclude(reason)
    with parts.timed("conflicts"):
        parts.conflicts += await _memory_conflicts(tenant_id, kept)


async def _decisions(
    parts: _Parts, tenant_id: str, query: str, ref: datetime, as_of: datetime | None, budget: Budget
) -> None:
    rows = await _matching_decisions(tenant_id, query, ref, as_of)
    current = [d for d in rows if d.status in DECISION_LABEL][:SIDE_LIMIT]
    for d in rows:
        if d.status == "superseded":
            parts.exclude("superseded")
        elif d.status == "discarded":
            parts.exclude("discarded")
    parts.items += [decision_item(d, ref, budget) for d in current]
    by_id = {d.id: d for d in current}
    for old in await _superseded_decisions(tenant_id, list(by_id)):
        new = by_id[old.superseded_by]
        parts.conflicts.append(
            ContextConflict(
                "decision_supersession",
                (
                    ConflictSide(SourceRef("decision", str(new.id)), "current", str(new.status)),
                    ConflictSide(SourceRef("decision", str(old.id)), "previous", str(old.status)),
                ),
            )
        )
    parts.sources.append("decisions")


async def _intentions(
    parts: _Parts, tenant_id: str, query: str, ref: datetime, as_of: datetime | None, budget: Budget
) -> None:
    rows = await _open_intentions(tenant_id, query, ref, as_of)
    parts.items += [intention_item(i, ref, budget) for i in rows]
    parts.sources.append("intentions")


def _explain(kept: list[ContextItem], parts: _Parts) -> str:
    if not kept:
        return "Nothing in memory, decisions or open intentions matched the query."
    counts: dict[str, int] = {}
    for item in kept:
        counts[item.source_ref.kind] = counts.get(item.source_ref.kind, 0) + 1
    found = ", ".join(f"{n} {k}{'s' if n != 1 else ''}" for k, n in sorted(counts.items()))
    held = sum(parts.excluded.values())
    text_ = f"Found {found}."
    if held:
        text_ += f" Held back {held} near match{'es' if held != 1 else ''}."
    for note in parts.notes:
        text_ += f" {note}"
    return text_


async def assemble_context(
    query: str,
    *,
    purpose: str = "conversation",
    as_of: datetime | None = None,
    budget: Budget = DEFAULT_BUDGET,
    now: datetime | None = None,
) -> ContextSnapshot:
    """A bounded, read-only snapshot of what bears on *query* for the current tenant.

    *as_of* asks about an earlier instant (valid time); *now* is the wall clock
    (a test passes it for a byte-identical result). See the module docstring
    for the contract.
    """
    started = _clock()
    parts = _Parts()
    ref = retrieval._ensure_utc(as_of or now or datetime.now(UTC))
    base: dict[str, Any] = {
        "query": query,
        "purpose": purpose,
        "as_of": _iso(retrieval._ensure_utc(as_of)) if as_of is not None else None,
        "reference_time": _iso(ref) or "",
        "budget": budget,
    }
    tenant_id = get_current_tenant_id()
    if not query.strip():
        return ContextSnapshot(**base, explanation="Empty query: nothing was searched.")

    def timings() -> tuple[tuple[str, float], ...]:
        parts.timings["total"] = _ms_since(started)
        return parts.timings_tuple()

    try:
        with parts.timed("embed"):
            embedding = await runtime.get_memory_manager().generate_embedding(query)
    except Exception as exc:  # noqa: BLE001 — no vector means no memory search, never a fallback
        logger.warning("Context snapshot: embedding failed (%s)", type(exc).__name__)
        embedding = None
    if not embedding:
        return ContextSnapshot(
            **base,
            explanation="The query could not be embedded locally, so memory was not searched.",
            timings_ms=timings(),
        )
    try:
        await _memories(parts, tenant_id, query, embedding, ref, as_of, budget)
        with parts.timed("decisions"):
            await _decisions(parts, tenant_id, query, ref, as_of, budget)
        with parts.timed("intentions"):
            await _intentions(parts, tenant_id, query, ref, as_of, budget)
    except Exception as exc:  # noqa: BLE001 — a partial view must not pass as context
        logger.warning("Context snapshot: a read failed (%s)", type(exc).__name__)
        return ContextSnapshot(
            **base,
            explanation="Reading the records failed, so no context was assembled.",
            timings_ms=timings(),
        )
    kept, used, over = apply_budget(parts.items, budget)
    parts.exclude("over_budget", over)
    return ContextSnapshot(
        **base,
        items=tuple(kept),
        conflicts=_dedupe_conflicts(parts.conflicts),
        exclusions=tuple(sorted(parts.excluded.items())),
        insufficient=not kept,
        explanation=_explain(kept, parts),
        content_chars=used,
        sources=tuple(parts.sources),
        timings_ms=timings(),
    )


async def shadow_snapshot(
    tenant_id: str,
    message: str,
    history: list[dict[str, Any]] | None = None,
    *,
    timeout: float | None = None,
) -> tuple[ContextSnapshot | None, dict[str, Any]]:
    """(the snapshot or None, its compact form for the trace), time-boxed; never raises.

    A failure or timeout is logged (no content), the snapshot is None and
    the compact form is ``{"error": <type>}``. Either way it carries ``ms``.
    """
    started = time.monotonic()
    snap: ContextSnapshot | None = None
    try:
        with tenant_scope(tenant_id):
            snap = await asyncio.wait_for(
                assemble_context(search_text(message, history)), timeout or SHADOW_TIMEOUT_S
            )
        out = snap.compact()
    except Exception as exc:  # noqa: BLE001 — shadow mode must never cost the turn
        logger.warning("Context snapshot (shadow) failed: %s", type(exc).__name__)
        snap = None
        out = {"error": type(exc).__name__}
    out["ms"] = round((time.monotonic() - started) * 1000)
    return snap, out


async def shadow_compact(
    tenant_id: str,
    message: str,
    history: list[dict[str, Any]] | None = None,
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    """The compact snapshot for a turn's trace, time-boxed; never raises.

    Shadow mode (settings.context_snapshot_shadow): the kernel runs this
    (through services/memory/changes.py shadow_trace) next to the memory
    block and keeps the result in the turn trace. The prompt is not changed.
    A failure or timeout is logged (no content) and recorded as
    ``{"error": <type>}``.
    """
    return (await shadow_snapshot(tenant_id, message, history, timeout=timeout))[1]


__all__ = [
    "Budget",
    "ContextConflict",
    "ContextItem",
    "ContextSnapshot",
    "SourceRef",
    "assemble_context",
    "fingerprint",
    "normalise_text",
    "shadow_compact",
    "shadow_snapshot",
    "without_timings",
]
