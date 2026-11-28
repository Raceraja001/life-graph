"""Context change detection (M8 Stage 2): what changed since the last snapshot.

A derived read model over existing records, never a new fact. It compares the
compact snapshot an earlier turn of the same conversation kept in its trace
(the *baseline*) with the snapshot of this turn, and re-reads every earlier
reference by id. Design: docs/design/adr-m8-context-change-detection.md.

The contract
============

Pure comparison. :func:`compare_context` does no I/O, reads no clock and calls
no model. Same baseline, same rows, same ``now``: byte-identical result.
Sorting is by fixed keys.

Small reads. :func:`find_baseline` reads the conversation's earlier turns
(``agent_tasks``, by tenant and session, newest first); :func:`resolve_refs`
reads the live state of the references by primary key, at most one query
per kind (memories, decisions, intentions, approvals) plus a few hops along a
supersession chain. No embedding, no search. Every read is scoped to the
tenant in the request context (core/tenant.py); a ref of another tenant
resolves to ``missing``.

Absence is not removal. A snapshot is "what bears on this question", so an
item missing from this turn's snapshot usually means a different question.
A removal or transition is reported only when the source row itself changed.

The window is ``from < t <= to``: from the baseline's ``reference_time`` to
this snapshot's. A turn whose own comparison failed, and any turn of a
temporary chat, is never a baseline. No baseline, a format 1 trace, an error trace, a baseline
over 30 days old or a failed read give ``insufficient`` and no changes, never
"everything is new". A baseline from another conversation of the tenant
(``same_conversation`` False) reports transitions, removals and approaching
items only; its additions are ``newly_relevant``.

Change kinds (:data:`PRIORITY`): additions (``added``), removals
(``deleted``, ``rejected``, ``archived``, ``expired``, ``discarded``,
``disputed``),
transitions (``superseded``, ``confirmed``, ``edited``, ``decision_status``,
``decision_superseded``, ``intention_completed``, ``intention_expired``,
``intention_dismissed``), approaching or due (``decision_review_due``,
``intention_approaching``), conflicts (``conflict_appeared``,
``conflict_resolved``) and staleness (``became_stale``, ``reconfirmed``).

Noise rules, each counted in ``suppressed``: ``hostile`` and ``pending_only``
subjects are dropped, with one exception: an active memory the owner marked
wrong in the window ("this memory was wrong", api/jarvis.py, which moves it to
pending and writes ``properties.disputed.at``) is reported as ``disputed``,
acknowledged, since the owner did it (D13); ``cosmetic`` edits (the fingerprint did not move, only
``updated_at``); ``duplicate`` (one change per kind and ref, a supersession
chain is one change, ``deleted`` beats every other kind and ``superseded``
beats ``edited``); ``low_confidence`` (a model-proposed, unconfirmed addition
or edit, or a candidate decision appearing; an *active* memory is held back
only when it is Life Graph's own conclusion, an inference or a day summary,
not merely because a model extracted it from what the owner said);
``newly_relevant`` (in this
snapshot only, but recorded before the window); ``over_budget`` (more than
20 changes, in fixed priority order). A change the owner made himself (a
review stamp, a correction or a /deny, a memory saved in this conversation)
stays in the list with ``acknowledged`` True.

Every change carries ``evidence`` (the refs that prove it), the window and a
``reason`` from a fixed template filled with statuses and kinds only: no
record text, no query. The trace form also leaves out fingerprints.

Shadow mode (settings.context_change_shadow, effective only with
settings.context_snapshot_shadow): :func:`shadow_trace` adds
``trace.context_changes`` next to ``trace.context_snapshot``; the prompt is
unchanged, nothing is sent, and a failure or timeout is recorded as
``{"error": <type>}`` without costing the turn.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import or_, select
from sqlalchemy.orm import defer

from life_graph.core import evidence as ev
from life_graph.core.tenant import get_current_tenant_id, tenant_scope
from life_graph.core.trust import is_excluded_from_agents
from life_graph.models.db import AgentSession, AgentTask, Approval, Decision, Intention, Memory
from life_graph.services import decision_lifecycle
from life_graph.services.chat_history import versions_of
from life_graph.services.memory import retrieval
from life_graph.services.memory import snapshot as snapshot_mod
from life_graph.storage.database import async_session

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from life_graph.services.memory.snapshot import ContextConflict, ContextItem, ContextSnapshot

logger = logging.getLogger(__name__)

#: Most changes one comparison reports; the rest are ``over_budget``.
MAX_CHANGES = 20
#: A baseline older than this is not compared against.
BASELINE_MAX_AGE = timedelta(days=30)
#: A decision's review date is "due" this long ahead.
REVIEW_AHEAD = timedelta(days=7)
#: An open intention's time is "approaching" this long ahead.
APPROACH_AHEAD = timedelta(hours=48)
#: Earlier turns of the conversation read for a baseline (regenerations included).
SESSION_SCAN = 30
#: Earlier turns of the tenant read when the conversation has no baseline.
TENANT_SCAN = 10
#: Extra reads along a memory supersession chain (A -> B -> C ...).
CHAIN_HOPS = 3

#: Priority group of each kind (lower first): removals and supersessions, then
#: status transitions, then conflicts, then approaching or due, then
#: additions, then staleness (ADR §5.4 rule 6).
PRIORITY = {
    "deleted": 0,
    "rejected": 0,
    "archived": 0,
    "expired": 0,
    "discarded": 0,
    "disputed": 0,
    "superseded": 0,
    "decision_superseded": 0,
    "confirmed": 1,
    "edited": 1,
    "decision_status": 1,
    "intention_completed": 1,
    "intention_expired": 1,
    "intention_dismissed": 1,
    "conflict_appeared": 2,
    "conflict_resolved": 2,
    "decision_review_due": 3,
    "intention_approaching": 3,
    "added": 4,
    "became_stale": 5,
    "reconfirmed": 5,
}
KINDS = tuple(PRIORITY)
#: Why a change was held back (``suppressed`` keys).
NOISE = (
    "hostile",
    "pending_only",
    "cosmetic",
    "duplicate",
    "low_confidence",
    "newly_relevant",
    "over_budget",
)

#: Fixed reason templates. Filled with statuses and freshness classes only.
REASONS = {
    "deleted": "the record no longer exists",
    "rejected": "status went {before} -> rejected",
    "archived": "status went {before} -> archived",
    "expired": "its valid time ended in the window",
    "discarded": "status went {before} -> discarded",
    "disputed": "the owner said it was wrong: status went {before} -> pending",
    "superseded": "replaced by a newer record",
    "decision_superseded": "replaced by a newer decision",
    "confirmed": "the owner confirmed it",
    "edited": "its content changed",
    "decision_status": "status went {before} -> {after}",
    "intention_completed": "status went {before} -> completed",
    "intention_expired": "the intention expired",
    "intention_dismissed": "status went {before} -> dismissed",
    "conflict_appeared": "a {conflict} conflict appeared",
    "conflict_resolved": "the {conflict} conflict was resolved: {cause}",
    "decision_review_due": "its review date is {when}",
    "intention_approaching": "its {field} is within 48 hours",
    "added": "{how} in the window",
    "became_stale": "freshness went {before} -> stale",
    "reconfirmed": "freshness went {before} -> fresh: the owner restated it",
}

CURRENT_DECISIONS = tuple(snapshot_mod.DECISION_LABEL)
OPEN_INTENTIONS = snapshot_mod.OPEN_INTENTION_STATUSES
NOT_STALE = ("fresh", "recent", "aging")
WAS_STALE = ("stale", "aging")
#: Memory statuses that end a conflict when a side reaches them.
ENDS_CONFLICT = ("rejected", "superseded", "archived")


# ── Inputs ────────────────────────────────────────────────────


def _ts(value: Any) -> datetime | None:
    return retrieval._as_utc(value)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


@dataclass(frozen=True)
class BaselineItem:
    ref: str
    status: str
    fp: str
    rec: datetime | None
    freshness: str
    origin: str
    confirmed: bool


@dataclass(frozen=True)
class BaselineConflict:
    kind: str
    refs: tuple[str, ...]
    statuses: tuple[str, ...]
    approval: str | None

    @property
    def key(self) -> str:
        return conflict_key(self.kind, self.refs)


@dataclass(frozen=True)
class Baseline:
    """The compact snapshot of an earlier turn, read back from its trace."""

    reference_time: datetime
    items: tuple[BaselineItem, ...] = ()
    conflicts: tuple[BaselineConflict, ...] = ()
    task_id: str | None = None
    same_conversation: bool = True

    @classmethod
    def from_compact(
        cls, compact: Any, *, task_id: str | None = None, same_conversation: bool = True
    ) -> Baseline | None:
        """The baseline in *compact*, or None when it is not usable.

        Not usable: not a dict, an error trace, format 1 (no ``v`` 2 or no
        ``reference_time``), or a snapshot whose reads failed (no sources).
        """
        if not isinstance(compact, dict) or compact.get("error") is not None:
            return None
        ref_time = _ts(compact.get("reference_time"))
        if compact.get("v") != snapshot_mod.COMPACT_FORMAT or ref_time is None:
            return None
        if not compact.get("sources"):
            return None
        items = tuple(
            BaselineItem(
                ref=str(i.get("ref")),
                status=str(i.get("status") or ""),
                fp=str(i.get("fp") or ""),
                rec=_ts(i.get("rec")),
                freshness=str(i.get("freshness") or ""),
                origin=str(i.get("origin") or ""),
                confirmed=bool(i.get("confirmed")),
            )
            for i in compact.get("items") or []
            if isinstance(i, dict) and i.get("ref")
        )
        conflicts = tuple(
            BaselineConflict(
                kind=str(c.get("kind") or ""),
                refs=tuple(str(r) for r in c.get("refs") or []),
                statuses=tuple(str(x) for x in c.get("statuses") or []),
                approval=str(c["approval"]) if c.get("approval") else None,
            )
            for c in compact.get("conflicts") or []
            if isinstance(c, dict)
        )
        return cls(ref_time, items, conflicts, task_id, same_conversation)


@dataclass(frozen=True)
class RowState:
    """The live state of one referenced row (no content: a fingerprint at most)."""

    ref: str
    missing: bool = False
    status: str = ""
    fp: str = ""
    hostile: bool = False
    origin: str = ""
    owner_confirmed: bool = False
    #: A memory's evidence kind (core/evidence.py), "" when not known.
    evidence: str = ""
    recorded_at: datetime | None = None
    updated_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by_owner: bool = False
    superseded_by: str | None = None
    superseded_at: datetime | None = None
    valid_until: datetime | None = None
    last_reinforced: datetime | None = None
    #: The turn a memory was saved in (properties.task_id), "" otherwise.
    task_id: str = ""
    #: The row is the owner's own correction, or the replacement a /deny wrote.
    owner_correction: bool = False
    #: The owner /denied this row (storage/postgres.py deny).
    denied: bool = False
    #: When the owner marked this memory wrong (properties.disputed.at), else None.
    disputed_at: datetime | None = None
    decided_at: datetime | None = None
    #: A decision's newest lifecycle move into its current status: when, and
    #: whether the owner made it (services/decision_lifecycle.py).
    status_at: datetime | None = None
    status_by_owner: bool = False
    review_due: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    trigger_time: datetime | None = None
    resolved_at: datetime | None = None

    @property
    def kind(self) -> str:
        return self.ref.split(":", 1)[0]


# ── Output ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ContextChange:
    kind: str
    ref: str
    evidence: tuple[str, ...]
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    at: str | None
    reason: str
    origin: str
    acknowledged: bool = False

    @property
    def key(self) -> str:
        """Stable dedup key: kind + ref + after-state (a later stage drops repeats)."""
        raw = json.dumps([self.kind, self.ref, self.after], sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def sort_key(self) -> tuple[int, str, str]:
        return (PRIORITY[self.kind], self.kind, self.ref)

    def to_dict(self, *, fingerprints: bool = True) -> dict[str, Any]:
        def state(value: dict[str, Any] | None) -> dict[str, Any] | None:
            if value is None or fingerprints:
                return value
            return {k: v for k, v in value.items() if k != "fp"}

        return {
            "kind": self.kind,
            "ref": self.ref,
            "evidence": list(self.evidence),
            "before": state(self.before),
            "after": state(self.after),
            "at": self.at,
            "reason": self.reason,
            "origin": self.origin,
            "acknowledged": self.acknowledged,
            "key": self.key,
        }


@dataclass(frozen=True)
class ContextChangeSet:
    window: tuple[str | None, str | None]
    baseline: dict[str, Any] | None
    changes: tuple[ContextChange, ...] = ()
    suppressed: tuple[tuple[str, int], ...] = ()
    insufficient: bool = True
    explanation: str = ""
    #: The re-read failed: nothing was compared, and this turn is no baseline
    #: for the next one (find_baseline), so the next window still covers it.
    read_failed: bool = False

    def to_dict(self, *, fingerprints: bool = True) -> dict[str, Any]:
        return {
            "window": {"from": self.window[0], "to": self.window[1]},
            "baseline": self.baseline,
            "changes": [c.to_dict(fingerprints=fingerprints) for c in self.changes],
            "suppressed": dict(self.suppressed),
            "insufficient": self.insufficient,
            "explanation": self.explanation,
            "read_failed": self.read_failed,
        }

    def trace(self) -> dict[str, Any]:
        """The form kept in ``trace.context_changes``: no fingerprints."""
        return self.to_dict(fingerprints=False)


def conflict_key(kind: str, refs: Iterable[str]) -> str:
    return f"{kind}:{','.join(refs)}"


def _insufficient(
    why: str, window: tuple[str | None, str | None] = (None, None), baseline: Any = None
) -> ContextChangeSet:
    return ContextChangeSet(window=window, baseline=baseline, insufficient=True, explanation=why)


# ── Comparison (pure) ─────────────────────────────────────────


@dataclass
class _Run:
    """One comparison's inputs and what it has found so far."""

    start: datetime
    end: datetime
    same_conversation: bool
    resolved: Mapping[str, RowState]
    current: dict[str, ContextItem]
    conversation_tasks: frozenset[str]
    changes: dict[tuple[str, str], ContextChange] = field(default_factory=dict)
    suppressed: dict[str, int] = field(default_factory=dict)

    def within(self, t: datetime | None) -> bool:
        return t is not None and self.start < t <= self.end

    def hold(self, reason: str, n: int = 1) -> None:
        if n:
            self.suppressed[reason] = self.suppressed.get(reason, 0) + n

    def add(self, change: ContextChange) -> None:
        if (change.kind, change.ref) in self.changes:
            self.hold("duplicate")
            return
        self.changes[(change.kind, change.ref)] = change

    def row(self, ref: str) -> RowState:
        return self.resolved.get(ref) or RowState(ref=ref, missing=True)


def _change(
    kind: str,
    ref: str,
    *,
    evidence: Iterable[str] | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    at: datetime | None = None,
    origin: str = "",
    acknowledged: bool = False,
    **fill: str,
) -> ContextChange:
    values = {
        "before": (before or {}).get("status", ""),
        "after": (after or {}).get("status", ""),
        **fill,
    }
    return ContextChange(
        kind=kind,
        ref=ref,
        evidence=tuple(evidence) if evidence is not None else (ref,),
        before=before,
        after=after,
        at=_iso(at),
        reason=REASONS[kind].format(**values),
        origin=origin,
        acknowledged=acknowledged,
    )


def _owner_made(r: RowState, run: _Run) -> bool:
    """The owner made this change himself (ADR §5.4 rule 5, until Stage 3)."""
    return r.reviewed_by_owner or r.owner_correction or (r.task_id in run.conversation_tasks)


def _chain_end(run: _Run, start: str) -> tuple[str, int]:
    """(newest memory ref of the chain from *start*, hops); stops at a row not read."""
    at, hops, seen = start, 0, {start}
    while (nxt := run.row(at).superseded_by) and f"memory:{nxt}" not in seen:
        at = f"memory:{nxt}"
        seen.add(at)
        hops += 1
        if at not in run.resolved:
            break
    return at, hops


def _memory_removal(p: BaselineItem, r: RowState, run: _Run) -> ContextChange | None:
    before = {"status": p.status, "fp": p.fp}
    if p.status == "active" and r.status in ("rejected", "archived"):
        return _change(
            r.status,
            p.ref,
            before=before,
            after={"status": r.status},
            at=r.reviewed_at,
            origin=p.origin,
            acknowledged=_owner_made(r, run),
        )
    if p.status != "superseded" and (r.status == "superseded" or r.superseded_by):
        target, _ = _chain_end(run, p.ref)
        ack = r.denied or (target != p.ref and _owner_made(run.row(target), run))
        return _change(
            "superseded",
            p.ref,
            evidence=(p.ref, target) if target != p.ref else (p.ref,),
            before=before,
            after={"status": r.status, "by": target if target != p.ref else None},
            at=r.superseded_at,
            origin=p.origin,
            acknowledged=ack,
        )
    if run.within(r.valid_until):
        return _change(
            "expired",
            p.ref,
            before=before,
            after={"status": r.status, "valid_until": _iso(r.valid_until)},
            at=r.valid_until,
            origin=p.origin,
            acknowledged=_owner_made(r, run),
        )
    return None


#: Evidence kinds that are Life Graph's own conclusions, not anyone's words.
LOW_EVIDENCE = frozenset({ev.INFERRED, ev.SUMMARY})


def _low_confidence(
    origin: str, confirmed: bool, *, kind: str = "", status: str = "", evidence: str = ""
) -> bool:
    """An addition or edit too weak to report (ADR §5.4 rule 4).

    A model-proposed record the owner has not confirmed is held back, with one
    exception: an **active** memory whose evidence is known and is not one of
    :data:`LOW_EVIDENCE`. Origin alone is not enough there: most facts from
    chat are extracted by a model (``extraction_tier`` "llm" makes the origin
    ``model_proposed``), yet they are the owner's own words. A pending memory,
    an inference or a day summary, and a memory whose evidence is not known
    are still held back, as are model-proposed decisions and intentions.
    """
    if origin != snapshot_mod.MODEL_PROPOSED or confirmed:
        return False
    return not (
        kind == "memory" and status == "active" and evidence and evidence not in LOW_EVIDENCE
    )


def _edited(p: BaselineItem, r: RowState, run: _Run) -> None:
    if p.fp and r.fp and p.fp != r.fp:
        c = run.current.get(p.ref)
        evidence = r.evidence or (c.evidence if c is not None else "")
        if _low_confidence(
            r.origin or p.origin, r.owner_confirmed, kind=r.kind, status=r.status, evidence=evidence
        ):
            run.hold("low_confidence")
            return
        run.add(
            _change(
                "edited",
                p.ref,
                before={"status": p.status, "fp": p.fp},
                after={"status": r.status, "fp": r.fp},
                at=r.updated_at,
                origin=r.origin or p.origin,
                acknowledged=_owner_made(r, run),
            )
        )
    elif p.fp and p.fp == r.fp and run.within(r.updated_at):
        run.hold("cosmetic")


def _memory(p: BaselineItem, r: RowState, run: _Run) -> None:
    removal = _memory_removal(p, r, run)
    if removal is not None:
        run.add(removal)
    if not p.confirmed and r.status == "active" and r.owner_confirmed:
        run.add(
            _change(
                "confirmed",
                p.ref,
                before={"status": p.status, "confirmed": False},
                after={"status": r.status, "confirmed": True},
                at=r.reviewed_at,
                origin=r.origin or p.origin,
                acknowledged=True,
            )
        )
    if removal is not None and removal.kind == "superseded":
        if p.fp and r.fp and p.fp != r.fp:
            run.hold("duplicate")  # superseded wins over edited
        return
    _edited(p, r, run)


def _decision(p: BaselineItem, r: RowState, run: _Run) -> None:
    """A decision's status move. ``at`` is the column for it (``superseded_at``,
    ``decided_at``, ``reviewed_at``), else the lifecycle trail (a discard);
    a move the owner made is ``acknowledged`` (ADR M8 §5.4)."""
    before = {"status": p.status}
    after = {"status": r.status}
    ack = r.status_by_owner
    if r.status != p.status:
        if r.status == "discarded":
            run.add(
                _change(
                    "discarded",
                    p.ref,
                    before=before,
                    after=after,
                    at=r.status_at,
                    origin=p.origin,
                    acknowledged=ack,
                )
            )
        elif r.status == "superseded" and r.superseded_by:
            new = f"decision:{r.superseded_by}"
            run.add(
                _change(
                    "decision_superseded",
                    p.ref,
                    evidence=(p.ref, new),
                    before=before,
                    after={**after, "by": new},
                    at=r.superseded_at,
                    origin=p.origin,
                    acknowledged=ack,
                )
            )
        else:
            at = r.reviewed_at if r.status == "reviewed" else r.decided_at
            run.add(
                _change(
                    "decision_status",
                    p.ref,
                    before=before,
                    after=after,
                    at=at,
                    origin=p.origin,
                    acknowledged=ack,
                )
            )
    _edited(p, r, run)


def _intention(p: BaselineItem, r: RowState, run: _Run) -> None:
    before = {"status": p.status}
    after = {"status": r.status}
    if r.status != p.status and r.status == "completed":
        run.add(
            _change(
                "intention_completed",
                p.ref,
                before=before,
                after=after,
                at=r.completed_at,
                origin=p.origin,
            )
        )
    elif r.status != p.status and r.status == "dismissed":
        run.add(_change("intention_dismissed", p.ref, before=before, after=after, origin=p.origin))
    elif (r.status != p.status and r.status == "expired") or (
        r.status in OPEN_INTENTIONS and run.within(r.expires_at)
    ):
        run.add(
            _change(
                "intention_expired",
                p.ref,
                before=before,
                after={**after, "expires_at": _iso(r.expires_at)},
                at=r.expires_at,
                origin=p.origin,
            )
        )
    _edited(p, r, run)


def _staleness(p: BaselineItem, c: ContextItem, r: RowState, run: _Run) -> None:
    before = {"status": p.status, "freshness": p.freshness}
    after = {"status": c.status, "freshness": c.freshness}
    if p.freshness in NOT_STALE and c.freshness == snapshot_mod.STALE:
        run.add(_change("became_stale", p.ref, before=before, after=after, origin=c.origin))
    elif p.freshness in WAS_STALE and c.freshness == "fresh" and run.within(r.last_reinforced):
        run.add(
            _change(
                "reconfirmed",
                p.ref,
                before=before,
                after=after,
                at=r.last_reinforced,
                origin=c.origin,
                acknowledged=True,
            )
        )


def _previous_item(p: BaselineItem, run: _Run) -> None:
    r = run.row(p.ref)
    if r.missing:
        # Deleted wins over every other kind; nothing of the row (or of
        # another tenant's row) is read or shown.
        run.add(_change("deleted", p.ref, before={"status": p.status, "fp": p.fp}, origin=p.origin))
        return
    if r.hostile:
        run.hold("hostile")
        return
    if r.kind == "memory" and r.status == "pending":
        if p.status == "active" and run.within(r.disputed_at):
            run.add(_disputed(p, r))
        else:
            run.hold("pending_only")
        return
    {"memory": _memory, "decision": _decision, "intention": _intention}.get(
        r.kind, lambda *_: None
    )(p, r, run)
    c = run.current.get(p.ref)
    if c is not None:
        _staleness(p, c, r, run)


def _disputed(p: BaselineItem, r: RowState) -> ContextChange:
    """The owner said this active memory was wrong; it is back in review (D13).

    Only the owner's "this memory was wrong" (api/jarvis.py memory_was_wrong)
    writes ``properties.disputed.at`` as it moves an active memory to pending,
    so the signal is the marker's time inside the window, not the status
    alone: any other way back to pending stays ``pending_only``.
    """
    return _change(
        "disputed",
        p.ref,
        before={"status": p.status, "fp": p.fp},
        after={"status": r.status},
        at=r.disputed_at,
        origin=p.origin,
        acknowledged=True,
    )


def _crossed(run: _Run, t: datetime | None, ahead: timedelta) -> bool:
    """*t* came within *ahead* of the window's end, and was not so at its start."""
    return t is not None and run.start + ahead < t <= run.end + ahead


def _approaching(ref: str, run: _Run) -> None:
    r = run.row(ref)
    if r.missing or r.hostile:
        return
    if r.kind == "decision" and r.status in CURRENT_DECISIONS:
        rv = r.review_due
        if run.within(rv) or _crossed(run, rv, REVIEW_AHEAD):
            when = "due" if rv is not None and rv <= run.end else "within 7 days"
            run.add(
                _change(
                    "decision_review_due",
                    ref,
                    after={"status": r.status, "review_at": _iso(rv)},
                    at=rv,
                    origin=r.origin,
                    when=when,
                )
            )
    elif r.kind == "intention" and r.status in OPEN_INTENTIONS:
        if ("intention_expired", ref) in run.changes:
            return
        times = [
            (t, name)
            for t, name in ((r.trigger_time, "trigger time"), (r.expires_at, "expiry"))
            # Still ahead at the end of the window: a time that already
            # passed is not "within 48 hours" (an expiry has its own kind).
            if t is not None and t > run.end and _crossed(run, t, APPROACH_AHEAD)
        ]
        if times:
            t, name = min(times, key=lambda x: (x[0], x[1]))
            run.add(
                _change(
                    "intention_approaching",
                    ref,
                    after={"status": r.status, "due": _iso(t)},
                    at=t,
                    origin=r.origin,
                    field=name,
                )
            )


def _addition(c: ContextItem, run: _Run, targets: set[str]) -> None:
    ref = c.source_ref.key()
    r = run.row(ref)
    if not run.same_conversation:
        run.hold("newly_relevant")
        return
    rec = _ts(c.recorded_at)
    activated = r.kind == "memory" and r.status == "active" and run.within(r.reviewed_at)
    if not (run.within(rec) or activated):
        run.hold("newly_relevant")
        return
    if ref in targets:
        run.hold("duplicate")  # the newer side of a supersession already reported
        return
    if (c.source_ref.kind == "decision" and c.status == "candidate") or _low_confidence(
        c.origin, c.confirmed, kind=c.source_ref.kind, status=c.status, evidence=c.evidence
    ):
        run.hold("low_confidence")
        return
    run.add(
        _change(
            "added",
            ref,
            after={"status": c.status, "fp": c.fingerprint},
            at=rec if run.within(rec) else r.reviewed_at,
            origin=c.origin,
            acknowledged=_owner_made(r, run),
            how="recorded" if run.within(rec) else "became active",
        )
    )


def _side_recorded(ref: str, run: _Run) -> datetime | None:
    c = run.current.get(ref)
    return _ts(c.recorded_at) if c is not None else run.row(ref).recorded_at


def _conflict_appeared(c: ContextConflict, run: _Run, covered: set[str]) -> None:
    refs = tuple(s.source_ref.key() for s in c.sides)
    key = conflict_key(c.kind, refs)
    if any(run.row(r).hostile for r in refs):
        run.hold("hostile")
        return
    if not run.same_conversation:
        run.hold("newly_relevant")
        return
    approval = f"approval:{c.approval_id}" if c.approval_id else None
    approval_new = approval is not None and run.within(run.row(approval).recorded_at)
    if not (approval_new or any(run.within(_side_recorded(r, run)) for r in refs)):
        run.hold("newly_relevant")
        return
    if c.kind != "pending_contradiction" and covered & set(refs):
        run.hold("duplicate")  # the supersession change already says it
        return
    run.add(
        _change(
            "conflict_appeared",
            key,
            evidence=(*refs, approval) if approval else refs,
            after={"statuses": [s.status for s in c.sides]},
            at=run.row(approval).recorded_at if approval_new and approval else None,
            conflict=c.kind.replace("_", " "),
        )
    )


def _conflict_resolved(b: BaselineConflict, run: _Run, covered: set[str]) -> None:
    approval = f"approval:{b.approval}" if b.approval else None
    evidence = (*b.refs, approval) if approval else b.refs
    a = run.row(approval) if approval else None
    if a is not None and not a.missing and run.within(a.resolved_at):
        run.add(
            _change(
                "conflict_resolved",
                b.key,
                evidence=evidence,
                before={"statuses": list(b.statuses)},
                after={"cause": "approval", "status": a.status},
                at=a.resolved_at,
                acknowledged=a.reviewed_by_owner,
                conflict=b.kind.replace("_", " "),
                cause="its approval was resolved",
            )
        )
        return
    ended = [ref for i, ref in enumerate(b.refs) if _side_ended(run.row(ref), _at(b.statuses, i))]
    if not ended:
        return  # only not retrieved this time: not resolved
    if covered & set(ended):
        run.hold("duplicate")  # the supersession change already says it
        return
    row = run.row(ended[0])
    run.add(
        _change(
            "conflict_resolved",
            b.key,
            evidence=evidence,
            before={"statuses": list(b.statuses)},
            after={"cause": "side", "side": ended[0], "status": row.status},
            at=row.superseded_at if row.status == "superseded" else row.reviewed_at,
            acknowledged=_owner_made(row, run),
            conflict=b.kind.replace("_", " "),
            cause="a side was deleted" if row.missing else f"a side is now {row.status}",
        )
    )


def _side_ended(row: RowState, was: str) -> bool:
    """The side is gone, or reached an ending status it did not have before."""
    return row.missing or (row.status in ENDS_CONFLICT and row.status != was)


def _at(values: tuple[str, ...], i: int) -> str:
    return values[i] if i < len(values) else ""


def _collapse_chains(run: _Run) -> set[str]:
    """One ``superseded`` per chain (A -> B -> C is one change, from A); the targets."""
    by_target: dict[str, list[ContextChange]] = {}
    for (kind, _), ch in run.changes.items():
        if kind == "superseded" and ch.after and ch.after.get("by"):
            by_target.setdefault(ch.after["by"], []).append(ch)
    for group in by_target.values():
        if len(group) < 2:
            continue
        # The oldest link: the one no other member of the group replaced.
        inner = {run.row(ch.ref).superseded_by for ch in group}
        keep = sorted(group, key=lambda ch: (ch.ref.split(":", 1)[1] in inner, ch.ref))[0]
        for ch in group:
            if ch is not keep:
                del run.changes[(ch.kind, ch.ref)]
                run.hold("duplicate")
    return set(by_target)


def compare_context(
    previous: Baseline | None,
    current: ContextSnapshot,
    resolved: Mapping[str, RowState] | None,
    now: datetime,
    *,
    conversation_tasks: Iterable[str] = (),
) -> ContextChangeSet:
    """What changed between *previous* and *current*, from the live *resolved* rows.

    Pure: no I/O, no clock (*now* is passed), no model. *resolved* maps every
    ref of both snapshots (and their approvals, ``approval:<id>``) to its live
    state; None means the read failed. *conversation_tasks* are the turn ids
    of this conversation (a memory saved in one is the owner's own change).
    See the module docstring for the rules.
    """
    end = _ts(current.reference_time)
    if previous is None:
        return _insufficient("No earlier snapshot to compare with.", (None, _iso(end)))
    window = (_iso(previous.reference_time), _iso(end))
    source = {
        "source": "turn_trace",
        "task_id": previous.task_id,
        "same_conversation": previous.same_conversation,
    }
    if end is None or now - previous.reference_time > BASELINE_MAX_AGE:
        return _insufficient("The earlier snapshot is over 30 days old.", window, source)
    if end <= previous.reference_time:
        return _insufficient("The earlier snapshot is not earlier.", window, source)
    if resolved is None:
        failed = _insufficient(
            "Reading the records failed, so nothing was compared.", window, source
        )
        return replace(failed, read_failed=True)
    run = _Run(
        start=previous.reference_time,
        end=end,
        same_conversation=previous.same_conversation,
        resolved=resolved,
        current={i.source_ref.key(): i for i in current.items},
        conversation_tasks=frozenset(conversation_tasks),
    )
    _detect(previous, current, run)
    ordered = sorted(run.changes.values(), key=ContextChange.sort_key)
    kept = tuple(ordered[:MAX_CHANGES])
    run.hold("over_budget", len(ordered) - len(kept))
    return ContextChangeSet(
        window=window,
        baseline=source,
        changes=kept,
        suppressed=tuple(sorted(run.suppressed.items())),
        insufficient=False,
        explanation=_explain(kept, run),
    )


def _detect(previous: Baseline, current: ContextSnapshot, run: _Run) -> None:
    before = {p.ref: p for p in previous.items}
    for ref in sorted(before):
        _previous_item(before[ref], run)
    targets = _collapse_chains(run)
    covered = {
        ref
        for (kind, _), ch in run.changes.items()
        if kind in ("superseded", "decision_superseded")
        for ref in ch.evidence
    }
    for ref in sorted(set(before) | set(run.current)):
        _approaching(ref, run)
    for ref in sorted(set(run.current) - set(before)):
        _addition(run.current[ref], run, targets)
    old = {b.key: b for b in previous.conflicts}
    new = {
        conflict_key(c.kind, (s.source_ref.key() for s in c.sides)): c for c in current.conflicts
    }
    for key in sorted(set(new) - set(old)):
        _conflict_appeared(new[key], run, covered)
    for key in sorted(set(old) - set(new)):
        _conflict_resolved(old[key], run, covered)


def _explain(kept: tuple[ContextChange, ...], run: _Run) -> str:
    held = sum(run.suppressed.values())
    text_ = f"{len(kept)} change{'s' if len(kept) != 1 else ''} since the earlier snapshot."
    if held:
        text_ += f" Held back {held}."
    if not run.same_conversation:
        text_ += " The earlier snapshot is from another conversation: additions are not reported."
    return text_


# ── Reads ─────────────────────────────────────────────────────


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def _owner_actor(by: Any) -> bool:
    """A review or resolution by the owner (api/approval_identity.resolver labels)."""
    who = str(by or "")
    return who == "owner" or who.startswith(("owner:", "phone:"))


def memory_state(m: Any) -> RowState:
    props = snapshot_mod._props(m)
    review = props.get("review") if isinstance(props.get("review"), dict) else {}
    origin = snapshot_mod.memory_origin(m)
    tags = getattr(m, "tags", None) or []
    superseded_at = _ts(props.get("superseded_at"))
    until = _ts(getattr(m, "valid_until", None))
    disputed = props.get("disputed") if isinstance(props.get("disputed"), dict) else {}
    return RowState(
        ref=f"memory:{m.id}",
        status=str(getattr(m, "status", "") or ""),
        fp=snapshot_mod.fingerprint(m.id, getattr(m, "content", "")),
        hostile=is_excluded_from_agents(getattr(m, "trust_tier", None)),
        origin=origin,
        owner_confirmed=snapshot_mod.memory_confirmed(m, origin),
        evidence=ev.evidence_of(
            getattr(m, "source_type", None), getattr(m, "trust_tier", None), props
        ),
        recorded_at=retrieval.recorded_time_of(m),
        updated_at=_ts(getattr(m, "updated_at", None)),
        reviewed_at=_ts(review.get("at")),
        reviewed_by_owner=_owner_actor(review.get("by")),
        superseded_by=str(m.superseded_by) if getattr(m, "superseded_by", None) else None,
        superseded_at=superseded_at,
        valid_until=until,
        last_reinforced=_ts(getattr(m, "last_reinforced", None)),
        task_id=str(props.get("task_id") or ""),
        # A correction the owner made (tools/memory_search.py, the memory
        # page: tagged "correction"), or the replacement a /deny wrote
        # (storage/postgres.py deny: source_type "reinforcement").
        owner_correction=(
            "correction" in tags or str(getattr(m, "source_type", "")) == "reinforcement"
        ),
        # A /deny ends the valid time at the moment it marks the row replaced;
        # no other supersession path sets valid_until.
        denied=(
            superseded_at is not None
            and until is not None
            and abs((until - superseded_at).total_seconds()) < 1
        ),
        # The owner's "this memory was wrong" (api/jarvis.py memory_was_wrong).
        disputed_at=_ts(disputed.get("at")),
    )


def decision_state(d: Any) -> RowState:
    explicit = str(getattr(d, "source", "") or "") == "explicit"
    move = decision_lifecycle.last_move_to(d, str(d.status)) or {}
    return RowState(
        ref=f"decision:{d.id}",
        status=str(d.status),
        fp=snapshot_mod.fingerprint(d.id, snapshot_mod.decision_text(d)),
        origin=snapshot_mod.IMPORTED if explicit else snapshot_mod.MODEL_PROPOSED,
        recorded_at=_ts(getattr(d, "created_at", None)),
        superseded_by=str(d.superseded_by) if getattr(d, "superseded_by", None) else None,
        decided_at=_ts(getattr(d, "decided_at", None)),
        reviewed_at=_ts(getattr(d, "reviewed_at", None)),
        review_due=_ts(getattr(d, "review_at", None)),
        superseded_at=_ts(getattr(d, "superseded_at", None)),
        status_at=_ts(move.get("at")),
        status_by_owner=move.get("owner") is True
        and decision_lifecycle.is_owner_label(move.get("by")),
    )


def intention_state(i: Any) -> RowState:
    return RowState(
        ref=f"intention:{i.id}",
        status=str(i.status),
        fp=snapshot_mod.fingerprint(i.id, getattr(i, "content", "")),
        origin=snapshot_mod.intention_origin(i),
        recorded_at=_ts(getattr(i, "created_at", None)),
        completed_at=_ts(getattr(i, "completed_at", None)),
        expires_at=_ts(getattr(i, "expires_at", None)),
        trigger_time=_ts(getattr(i, "trigger_time", None)),
    )


def approval_state(a: Any) -> RowState:
    return RowState(
        ref=f"approval:{a.id}",
        status=str(a.status),
        recorded_at=_ts(a.created_at),
        resolved_at=_ts(a.resolved_at),
        reviewed_by_owner=_owner_actor(a.resolved_by),
    )


def refs_to_resolve(
    previous: Baseline | None, current: ContextSnapshot
) -> tuple[list[str], list[str]]:
    """(record refs, approval ids) a comparison needs, sorted and unique."""
    refs: set[str] = {i.source_ref.key() for i in current.items}
    approvals: set[str] = {c.approval_id for c in current.conflicts if c.approval_id}
    for c in current.conflicts:
        refs |= {s.source_ref.key() for s in c.sides}
    if previous is not None:
        refs |= {p.ref for p in previous.items}
        for b in previous.conflicts:
            refs |= set(b.refs)
            if b.approval:
                approvals.add(b.approval)
    return sorted(refs), sorted(approvals)


async def resolve_refs(
    refs: Iterable[str], approval_ids: Iterable[str] = ()
) -> dict[str, RowState]:
    """The live state of *refs* (``kind:id``) and approvals, for the current tenant.

    One query per kind, by primary key and tenant, plus at most
    :data:`CHAIN_HOPS` reads along supersession chains. A ref that is not
    found, is not a valid id, or belongs to another tenant is ``missing``:
    nothing of another tenant's row is ever returned. Raises without a tenant.
    """
    tenant_id = get_current_tenant_id()
    wanted = sorted(set(refs))
    by_kind: dict[str, list[uuid.UUID]] = {}
    for ref in wanted:
        kind, _, raw = ref.partition(":")
        if (rid := _uuid(raw)) is not None:
            by_kind.setdefault(kind, []).append(rid)
    found: list[RowState] = []
    async with async_session() as s:
        found += await _read_memories(s, tenant_id, by_kind.get("memory", []))
        for kind, model, state in (
            ("decision", Decision, decision_state),
            ("intention", Intention, intention_state),
        ):
            ids = by_kind.get(kind, [])
            if ids:
                stmt = (
                    select(model)
                    .options(defer(model.embedding))
                    .where(model.tenant_id == tenant_id, model.id.in_(ids))
                )
                found += [state(row) for row in (await s.execute(stmt)).scalars()]
        a_ids = [x for a in sorted(set(approval_ids)) if (x := _uuid(a)) is not None]
        if a_ids:
            rows = await s.execute(
                select(
                    Approval.id,
                    Approval.status,
                    Approval.created_at,
                    Approval.resolved_at,
                    Approval.resolved_by,
                ).where(Approval.tenant_id == tenant_id, Approval.id.in_(a_ids))
            )
            found += [approval_state(r) for r in rows]
    out = {st.ref: st for st in found}
    for ref in [*wanted, *(f"approval:{a}" for a in sorted(set(approval_ids)))]:
        out.setdefault(ref, RowState(ref=ref, missing=True))
    return out


async def _read_memories(s: Any, tenant_id: str, ids: list[uuid.UUID]) -> list[RowState]:
    """*ids* and the rows their supersession chains lead to (bounded), tenant only."""
    out: dict[str, RowState] = {}
    todo = list(ids)
    for _ in range(1 + CHAIN_HOPS):
        if not todo:
            break
        stmt = (
            select(Memory)
            .options(defer(Memory.embedding))
            .where(Memory.tenant_id == tenant_id, Memory.id.in_(todo))
        )
        for row in (await s.execute(stmt)).scalars():
            st = memory_state(row)
            out[st.ref] = st
        todo = [
            nxt
            for st in out.values()
            if st.superseded_by
            and f"memory:{st.superseded_by}" not in out
            and (nxt := _uuid(st.superseded_by)) is not None
        ]
    return list(out.values())


@dataclass(frozen=True)
class BaselineLookup:
    baseline: Baseline | None
    #: Turn ids of this conversation (the current one included).
    conversation_tasks: frozenset[str] = frozenset()


def _snap_col() -> Any:
    return AgentTask.result["trace"]["context_snapshot"]


def _changes_col() -> Any:
    return AgentTask.result["trace"]["context_changes"]


def compare_failed(changes_trace: Any) -> bool:
    """A turn's ``trace.context_changes`` says its comparison did not run through.

    An error (a timeout, a failed baseline read) or a failed re-read. Such a
    turn is skipped as a baseline, so the next window reaches back to the
    last turn whose comparison went through, and no change is lost. A turn
    with no ``context_changes`` at all (the change flag was off) is a
    baseline: nothing was promised for it, and its snapshot is still what
    Jarvis had in hand.
    """
    if not isinstance(changes_trace, dict):
        return False
    return changes_trace.get("error") is not None or changes_trace.get("read_failed") is True


def _temporary(row: Any) -> bool:
    """A turn of a temporary chat (chat_turn: input ``temporary``): never a baseline."""
    return (getattr(row, "input", None) or {}).get("temporary") is True


async def find_baseline(task_id: uuid.UUID | None) -> BaselineLookup:
    """The latest usable earlier snapshot for the turn *task_id*, current tenant only.

    The same conversation first: its latest earlier top-level turn with a
    format 2, non-error snapshot, skipping every version of the turn being
    regenerated (a regeneration compares with what the replaced turn would
    have) and every turn whose own comparison failed (:func:`compare_failed`).
    Failing that, the tenant's latest such turn of another conversation
    within 30 days (``same_conversation`` False). A temporary chat's turns
    are never a baseline. Raises without a tenant.
    """
    tenant_id = get_current_tenant_id()
    if task_id is None:
        return BaselineLookup(None)
    async with async_session() as s:
        cur = (
            await s.execute(
                select(AgentTask.id, AgentTask.session_id, AgentTask.created_at, AgentTask.input)
                .where(AgentTask.tenant_id == tenant_id, AgentTask.id == task_id)
                .limit(1)
            )
        ).first()
        if cur is None:
            return BaselineLookup(None)
        conversation: frozenset[str] = frozenset({str(cur.id)})
        # A temporary chat promises nothing is kept: neither its turns nor
        # its conversation are ever a baseline, for itself or another chat.
        temporary_chats = select(AgentSession.id).where(
            AgentSession.tenant_id == tenant_id,
            AgentSession.context["temporary"].astext == "true",
        )
        if cur.session_id is not None:
            rows = (
                await s.execute(
                    select(
                        AgentTask.id,
                        AgentTask.input,
                        _snap_col().label("snap"),
                        _changes_col().label("chg"),
                    )
                    .where(
                        AgentTask.tenant_id == tenant_id,
                        AgentTask.session_id == cur.session_id,
                        AgentTask.session_id.not_in(temporary_chats),
                        AgentTask.parent_task_id.is_(None),
                        AgentTask.id != cur.id,
                        AgentTask.created_at <= cur.created_at,
                    )
                    .order_by(AgentTask.created_at.desc(), AgentTask.id)
                    .limit(SESSION_SCAN)
                )
            ).all()
            conversation |= {str(r.id) for r in rows}
            found = _pick(rows, cur, same_conversation=True)
            if found is not None:
                return BaselineLookup(found, conversation)
        stmt = (
            select(
                AgentTask.id,
                AgentTask.input,
                _snap_col().label("snap"),
                _changes_col().label("chg"),
            )
            .where(
                AgentTask.tenant_id == tenant_id,
                AgentTask.parent_task_id.is_(None),
                AgentTask.id != cur.id,
                AgentTask.created_at < cur.created_at,
                AgentTask.created_at >= cur.created_at - BASELINE_MAX_AGE,
                _snap_col().is_not(None),
                AgentTask.input["temporary"].astext.is_distinct_from("true"),
                or_(AgentTask.session_id.is_(None), AgentTask.session_id.not_in(temporary_chats)),
            )
            .order_by(AgentTask.created_at.desc(), AgentTask.id)
            .limit(TENANT_SCAN)
        )
        if cur.session_id is not None:
            stmt = stmt.where(
                or_(AgentTask.session_id.is_(None), AgentTask.session_id != cur.session_id)
            )
        rows = (await s.execute(stmt)).all()
    return BaselineLookup(_pick(rows, cur, same_conversation=False), conversation)


def _pick(rows: list[Any], cur: Any, *, same_conversation: bool) -> Baseline | None:
    """The newest usable row: a v2 snapshot, not a version of *cur*'s turn,
    not a temporary chat's turn, and not a turn whose comparison failed."""
    everyone = [*rows, cur]
    mine = versions_of(everyone, cur.id)
    parent = {
        str(r.id): str(x)
        for r in everyone
        if (x := (getattr(r, "input", None) or {}).get("regenerates"))
    }

    def root(tid: str) -> str:
        seen = {tid}
        while (up := parent.get(tid)) and up not in seen:
            seen.add(up)
            tid = up
        return tid

    own_root = root(str(cur.id))
    for r in rows:
        if str(r.id) in mine or root(str(r.id)) == own_root:
            continue
        if _temporary(r) or compare_failed(getattr(r, "chg", None)):
            continue
        found = Baseline.from_compact(
            r.snap, task_id=str(r.id), same_conversation=same_conversation
        )
        if found is not None:
            return found
    return None


# ── Shadow mode ───────────────────────────────────────────────


async def detect(
    snap: ContextSnapshot | None, task_id: uuid.UUID | None, *, now: datetime | None = None
) -> ContextChangeSet:
    """Baseline lookup, re-read and comparison for this turn (current tenant)."""
    if snap is None or not snap.sources:
        return _insufficient("This turn's snapshot could not be built, so nothing was compared.")
    lookup = await find_baseline(task_id)
    resolved: dict[str, RowState] | None
    try:
        refs, approvals = refs_to_resolve(lookup.baseline, snap)
        resolved = await resolve_refs(refs, approvals) if lookup.baseline is not None else {}
    except Exception as exc:  # noqa: BLE001 — a failed read is "insufficient", never partial
        logger.warning("Context changes: a read failed (%s)", type(exc).__name__)
        resolved = None
    return compare_context(
        lookup.baseline,
        snap,
        resolved,
        now or datetime.now(UTC),
        conversation_tasks=lookup.conversation_tasks,
    )


async def shadow_changes(
    tenant_id: str,
    snap: ContextSnapshot | None,
    task_id: uuid.UUID | None,
    *,
    timeout: float,
) -> dict[str, Any]:
    """The trace form of :func:`detect`, time-boxed; never raises.

    A failure or timeout is logged (no content) and recorded as
    ``{"error": <type>}``. Either way it carries ``ms``.
    """
    started = time.monotonic()
    try:
        if timeout <= 0:
            raise TimeoutError
        with tenant_scope(tenant_id):
            out = (await asyncio.wait_for(detect(snap, task_id), timeout)).trace()
    except Exception as exc:  # noqa: BLE001 — shadow mode must never cost the turn
        logger.warning("Context changes (shadow) failed: %s", type(exc).__name__)
        out = {"error": type(exc).__name__}
    out["ms"] = round((time.monotonic() - started) * 1000)
    return out


async def shadow_trace(
    tenant_id: str,
    message: str,
    history: list[dict[str, Any]] | None = None,
    *,
    task_id: uuid.UUID | None = None,
    compare: bool = False,
    precision: str = "",
) -> dict[str, Any]:
    """The turn trace entries of shadow mode; never raises.

    Always ``context_snapshot`` (snapshot.shadow_compact's value). With
    *compare* (settings.context_change_shadow) also ``context_changes``,
    inside what is left of the same time box (snapshot.SHADOW_TIMEOUT_S).
    With *precision*, a precision mode's name (settings.context_precision_shadow),
    also ``context_precision``: the same question's snapshot under that mode
    compared with the default one (snapshot.shadow_precision; refs, labels
    and counts only), in its own time box (snapshot.SHADOW_PRECISION_TIMEOUT_S),
    so the whole stays under the two boxes together. The ``context_snapshot``
    the changes compare stays the default one.
    """
    started = time.monotonic()
    snap, compact = await snapshot_mod.shadow_snapshot(tenant_id, message, history)
    out: dict[str, Any] = {"context_snapshot": compact}
    if compare:
        left = snapshot_mod.SHADOW_TIMEOUT_S - (time.monotonic() - started)
        out["context_changes"] = await shadow_changes(tenant_id, snap, task_id, timeout=left)
    if precision:
        out["context_precision"] = await snapshot_mod.shadow_precision(
            tenant_id,
            message,
            history,
            precision,
            snap,
            timeout=snapshot_mod.SHADOW_PRECISION_TIMEOUT_S,
        )
    return out


__all__ = [
    "Baseline",
    "BaselineConflict",
    "BaselineItem",
    "BaselineLookup",
    "ContextChange",
    "ContextChangeSet",
    "RowState",
    "compare_context",
    "detect",
    "find_baseline",
    "refs_to_resolve",
    "resolve_refs",
    "shadow_changes",
    "shadow_trace",
]
