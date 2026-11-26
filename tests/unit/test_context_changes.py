"""compare_context (services/memory/changes.py): one rule at a time, pure.

Each change kind has a case that fires and a near miss that does not. The noise
rules (hostile, pending, cosmetic, duplicate, low confidence, newly relevant,
acknowledged, the cap) each have their own case. No database, no clock, no model:
the baseline is a real format 2 compact snapshot read back, the live rows are
RowState values, and ``now`` is passed in.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from life_graph.services.memory import changes
from life_graph.services.memory.changes import (
    MAX_CHANGES,
    Baseline,
    RowState,
    compare_context,
    refs_to_resolve,
)
from life_graph.services.memory.snapshot import (
    DEFAULT_BUDGET,
    ConflictSide,
    ContextConflict,
    ContextItem,
    ContextSnapshot,
    SourceRef,
    fingerprint,
    normalise_text,
)

T0 = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)  # the baseline's reference time
T1 = T0 + timedelta(days=1)  # this turn's reference time
IN = T0 + timedelta(hours=6)  # inside the window
BEFORE = T0 - timedelta(days=10)  # before the window


def _id(n: int) -> str:
    return f"00000000-0000-0000-0000-{n:012d}"


def _item(kind: str, n: int, **kw) -> ContextItem:
    text_ = kw.pop("text", f"record {n}")
    base = {
        "source_ref": SourceRef(kind, _id(n)),
        "dimension": kind,
        "origin": "user_stated",
        "confirmed": kind == "memory",
        "evidence": "said",
        "label": "owner said",
        "status": {"memory": "active", "decision": "decided", "intention": "pending"}[kind],
        "reason": "search_hit",
        "score": 0.5,
        "valid_from": None,
        "recorded_at": BEFORE.isoformat(),
        "world_time_known": False,
        "freshness": "recent",
        "content": "SECRET-CONTENT",
        "fingerprint": fingerprint(_id(n), text_),
    }
    return ContextItem(**{**base, **kw})


def _snap(items=(), conflicts=(), at: datetime = T1) -> ContextSnapshot:
    return ContextSnapshot(
        query="SECRET-QUERY",
        purpose="conversation",
        as_of=None,
        reference_time=at.isoformat(),
        budget=DEFAULT_BUDGET,
        items=tuple(items),
        conflicts=tuple(conflicts),
        insufficient=not items,
        sources=("memories", "decisions", "intentions"),
    )


def _base(items=(), conflicts=(), *, same=True, at: datetime = T0) -> Baseline:
    found = Baseline.from_compact(
        _snap(items, conflicts, at).compact(), task_id="task-prev", same_conversation=same
    )
    assert found is not None
    return found


def _row(item: ContextItem, **kw) -> RowState:
    """The live row behind *item*, unchanged unless *kw* says so."""
    base = {
        "ref": item.source_ref.key(),
        "status": item.status,
        "fp": item.fingerprint,
        "origin": item.origin,
        "owner_confirmed": item.confirmed,
        "recorded_at": BEFORE,
        "updated_at": BEFORE,
    }
    return RowState(**{**base, **kw})


def _rows(*rows: RowState) -> dict[str, RowState]:
    return {r.ref: r for r in rows}


def _run(prev, cur, rows, **kw):
    return compare_context(prev, cur, rows, T1, **kw)


def _kinds(result) -> list[tuple[str, str]]:
    return [(c.kind, c.ref) for c in result.changes]


M1, M2, M3 = _item("memory", 1), _item("memory", 2), _item("memory", 3)


# ── Absence is not removal ────────────────────────────────────


def test_an_item_missing_from_this_snapshot_but_unchanged_is_no_change():
    result = _run(_base([M1, M2]), _snap([M2]), _rows(_row(M1), _row(M2)))
    assert result.insufficient is False
    assert result.changes == ()
    assert result.window == (T0.isoformat(), T1.isoformat())


# ── Removals ─────────────────────────────────────────────────


def test_deleted_when_the_row_is_gone_and_it_beats_every_other_kind():
    result = _run(_base([M1]), _snap([]), _rows(RowState(ref=M1.source_ref.key(), missing=True)))
    (change,) = result.changes
    assert (change.kind, change.ref, change.evidence) == (
        "deleted",
        "memory:" + _id(1),
        (change.ref,),
    )
    assert change.after is None
    near = _run(_base([M1]), _snap([]), _rows(_row(M1)))
    assert near.changes == ()


@pytest.mark.parametrize("status", ["rejected", "archived"])
def test_rejected_or_archived(status):
    result = _run(_base([M1]), _snap([]), _rows(_row(M1, status=status, reviewed_at=IN)))
    (change,) = result.changes
    assert change.kind == status and change.reason == f"status went active -> {status}"
    assert change.at == IN.isoformat()


def test_expired_only_when_valid_time_ends_in_the_window():
    result = _run(_base([M1]), _snap([]), _rows(_row(M1, valid_until=IN)))
    assert _kinds(result) == [("expired", M1.source_ref.key())]
    later = _run(_base([M1]), _snap([]), _rows(_row(M1, valid_until=T1 + timedelta(days=3))))
    assert later.changes == ()


def test_discarded_decision():
    d = _item("decision", 5, status="candidate", origin="model_proposed", confirmed=False)
    result = _run(_base([d]), _snap([]), _rows(_row(d, status="discarded")))
    assert _kinds(result) == [("discarded", d.source_ref.key())]
    assert result.changes[0].reason == "status went candidate -> discarded"


# ── Transitions ──────────────────────────────────────────────


def test_superseded_reports_the_newest_memory_of_the_chain_once():
    a, b, c = M1, M2, M3
    rows = _rows(
        _row(a, status="superseded", superseded_by=_id(2), superseded_at=IN),
        _row(b, status="superseded", superseded_by=_id(3), superseded_at=IN),
        _row(c, recorded_at=IN),
    )
    c_new = replace(c, recorded_at=IN.isoformat(), freshness="fresh")
    # Both A and B were in the baseline: one change, from A to C.
    result = _run(_base([a, b]), _snap([c_new]), rows)
    (change,) = result.changes
    assert change.kind == "superseded" and change.ref == a.source_ref.key()
    assert change.evidence == (a.source_ref.key(), c.source_ref.key())
    assert change.after["by"] == c.source_ref.key()
    # B's link and C's appearance are the same change, held back as duplicates.
    assert dict(result.suppressed)["duplicate"] == 2


def test_superseded_wins_over_edited():
    rows = _rows(
        _row(M1, status="superseded", superseded_by=_id(2), fp="ffffffffffffffff"),
        _row(M2),
    )
    result = _run(_base([M1]), _snap([]), rows)
    assert _kinds(result) == [("superseded", M1.source_ref.key())]


def test_confirmed_when_the_owner_confirmed_a_model_proposal():
    m = _item("memory", 7, origin="model_proposed", confirmed=False)
    result = _run(_base([m]), _snap([]), _rows(_row(m, owner_confirmed=True, reviewed_at=IN)))
    assert _kinds(result) == [("confirmed", m.source_ref.key())]
    assert result.changes[0].acknowledged is True
    near = _run(_base([m]), _snap([]), _rows(_row(m)))
    assert near.changes == ()


def test_a_cosmetic_edit_is_no_edit_but_a_word_change_is():
    m = _item("memory", 8, text="Car insurance renews in March.")
    cosmetic = fingerprint(_id(8), "car   insurance renews, in MARCH")
    assert cosmetic == m.fingerprint
    result = _run(_base([m]), _snap([]), _rows(_row(m, fp=cosmetic, updated_at=IN)))
    assert result.changes == () and dict(result.suppressed) == {"cosmetic": 1}
    worded = fingerprint(_id(8), "Car insurance renews in April.")
    result = _run(_base([m]), _snap([]), _rows(_row(m, fp=worded, updated_at=IN)))
    (change,) = result.changes
    assert change.kind == "edited" and change.reason == "its content changed"


def test_a_model_proposed_edit_is_held_back():
    m = _item("memory", 9, origin="model_proposed", confirmed=False)
    rows = _rows(_row(m, fp="0123456789abcdef", owner_confirmed=False))
    result = _run(_base([m]), _snap([]), rows)
    assert result.changes == () and dict(result.suppressed) == {"low_confidence": 1}


def test_decision_status_counts_even_when_the_decision_was_model_proposed():
    d = _item("decision", 10, status="candidate", origin="model_proposed", confirmed=False)
    result = _run(_base([d]), _snap([]), _rows(_row(d, status="decided", decided_at=IN)))
    (change,) = result.changes
    assert change.kind == "decision_status"
    assert change.reason == "status went candidate -> decided"
    assert _run(_base([d]), _snap([]), _rows(_row(d))).changes == ()


def test_decision_superseded_names_both_decisions():
    d = _item("decision", 11)
    rows = _rows(_row(d, status="superseded", superseded_by=_id(12)))
    (change,) = _run(_base([d]), _snap([]), rows).changes
    assert change.kind == "decision_superseded"
    assert change.evidence == (d.source_ref.key(), "decision:" + _id(12))


def test_decision_review_due_once_when_it_comes_within_seven_days():
    d = _item("decision", 13)
    due = T1 + timedelta(days=5)  # already within 7 days of the window start
    crossing = _run(
        _base([d]), _snap([d]), _rows(_row(d, review_due=T0 + timedelta(days=7, hours=12)))
    )
    assert _kinds(crossing) == [("decision_review_due", d.source_ref.key())]
    assert crossing.changes[0].reason == "its review date is within 7 days"
    in_window = _run(_base([d]), _snap([d]), _rows(_row(d, review_due=IN)))
    assert in_window.changes[0].reason == "its review date is due"
    # Already within 7 days at the start: reported by an earlier turn, not again.
    assert _run(_base([d]), _snap([d]), _rows(_row(d, review_due=due))).changes == ()
    # Far off: nothing yet.
    far = _rows(_row(d, review_due=T1 + timedelta(days=20)))
    assert _run(_base([d]), _snap([d]), far).changes == ()


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        ("completed", "intention_completed"),
        ("dismissed", "intention_dismissed"),
        ("expired", "intention_expired"),
    ],
)
def test_intention_status_changes(status, kind):
    i = _item("intention", 14, origin="extracted", confirmed=False)
    result = _run(_base([i]), _snap([]), _rows(_row(i, status=status, completed_at=IN)))
    assert _kinds(result) == [(kind, i.source_ref.key())]


def test_an_open_intention_whose_expiry_passed_in_the_window_expired():
    i = _item("intention", 15, origin="extracted", confirmed=False)
    result = _run(_base([i]), _snap([]), _rows(_row(i, expires_at=IN)))
    assert _kinds(result) == [("intention_expired", i.source_ref.key())]


def test_intention_approaching_once_per_threshold_crossing():
    i = _item("intention", 16, origin="extracted", confirmed=False)
    soon = T1 + timedelta(hours=30)  # within 48 h of to, not of from
    result = _run(_base([i]), _snap([i]), _rows(_row(i, trigger_time=soon)))
    (change,) = result.changes
    assert change.kind == "intention_approaching" and change.after["due"] == soon.isoformat()
    # Already within 48 h at the start of the window: not again.
    already = T1 + timedelta(hours=10)
    assert _run(_base([i]), _snap([i]), _rows(_row(i, trigger_time=already))).changes == ()
    # A closed intention is never approaching.
    done = _rows(_row(i, status="completed", trigger_time=soon))
    assert [c.kind for c in _run(_base([i]), _snap([]), done).changes] == ["intention_completed"]


# ── Conflicts ────────────────────────────────────────────────


def _contradiction(a: ContextItem, b_id: int, approval: str = "a-1") -> ContextConflict:
    return ContextConflict(
        "pending_contradiction",
        (
            ConflictSide(a.source_ref, "existing", "active"),
            ConflictSide(SourceRef("memory", _id(b_id)), "proposed", "pending"),
        ),
        approval_id=_id(900) if approval else None,
    )


def test_conflict_appeared_when_its_approval_is_new():
    c = _contradiction(M1, 20)
    rows = _rows(
        _row(M1),
        RowState(ref="memory:" + _id(20), status="pending", recorded_at=IN),
        RowState(ref="approval:" + _id(900), status="pending", recorded_at=IN),
    )
    result = _run(_base([M1]), _snap([M1], [c]), rows)
    (change,) = result.changes
    assert change.kind == "conflict_appeared"
    assert change.evidence == (M1.source_ref.key(), "memory:" + _id(20), "approval:" + _id(900))
    # The same pair with old sides and an old approval: only newly relevant.
    old = _rows(
        _row(M1),
        RowState(ref="memory:" + _id(20), status="pending", recorded_at=BEFORE),
        RowState(ref="approval:" + _id(900), status="pending", recorded_at=BEFORE),
    )
    near = _run(_base([M1]), _snap([M1], [c]), old)
    assert near.changes == () and dict(near.suppressed) == {"newly_relevant": 1}


def test_conflict_resolved_needs_a_cause_in_the_rows():
    c = _contradiction(M1, 21)
    resolved = _rows(
        _row(M1),
        RowState(ref="memory:" + _id(21), status="rejected"),
        RowState(
            ref="approval:" + _id(900),
            status="rejected",
            resolved_at=IN,
            reviewed_by_owner=True,
        ),
    )
    result = _run(_base([M1], [c]), _snap([M1]), resolved)
    (change,) = result.changes
    assert change.kind == "conflict_resolved" and change.acknowledged is True
    assert (
        change.reason
        == "the pending contradiction conflict was resolved: its approval was resolved"
    )
    # Not retrieved this time, nothing changed: not resolved.
    still = _rows(
        _row(M1),
        RowState(ref="memory:" + _id(21), status="pending"),
        RowState(ref="approval:" + _id(900), status="pending"),
    )
    assert _run(_base([M1], [c]), _snap([M1]), still).changes == ()


# ── Staleness ────────────────────────────────────────────────


def test_became_stale_but_aging_is_not_reported():
    aging, stale = replace(M1, freshness="aging"), replace(M1, freshness="stale")
    result = _run(_base([aging]), _snap([stale]), _rows(_row(M1)))
    assert _kinds(result) == [("became_stale", M1.source_ref.key())]
    recent = replace(M1, freshness="recent")
    assert _run(_base([recent]), _snap([aging]), _rows(_row(M1))).changes == ()


def test_reconfirmed_when_the_owner_restated_it():
    stale, fresh = replace(M1, freshness="stale"), replace(M1, freshness="fresh")
    result = _run(_base([stale]), _snap([fresh]), _rows(_row(M1, last_reinforced=IN)))
    assert _kinds(result) == [("reconfirmed", M1.source_ref.key())]
    assert _run(_base([stale]), _snap([fresh]), _rows(_row(M1))).changes == ()


# ── Additions ────────────────────────────────────────────────


def test_added_only_when_recorded_in_the_window():
    new = replace(M2, recorded_at=IN.isoformat(), freshness="fresh")
    result = _run(_base([M1]), _snap([M1, new]), _rows(_row(M1), _row(new, recorded_at=IN)))
    assert _kinds(result) == [("added", M2.source_ref.key())]
    assert result.changes[0].reason == "recorded in the window"
    old = _run(_base([M1]), _snap([M1, M2]), _rows(_row(M1), _row(M2)))
    assert old.changes == () and dict(old.suppressed) == {"newly_relevant": 1}


def test_added_when_it_became_active_in_the_window():
    rows = _rows(_row(M1), _row(M2, reviewed_at=IN))
    result = _run(_base([M1]), _snap([M1, M2]), rows)
    assert result.changes[0].reason == "became active in the window"


def test_a_model_proposed_addition_and_a_candidate_decision_are_held_back():
    guess = _item(
        "memory", 30, origin="model_proposed", confirmed=False, recorded_at=IN.isoformat()
    )
    cand = _item(
        "decision",
        31,
        status="candidate",
        origin="imported",
        confirmed=False,
        recorded_at=IN.isoformat(),
    )
    rows = _rows(_row(M1), _row(guess, recorded_at=IN), _row(cand, recorded_at=IN))
    result = _run(_base([M1]), _snap([M1, guess, cand]), rows)
    assert result.changes == () and dict(result.suppressed) == {"low_confidence": 2}


def test_a_baseline_from_another_conversation_reports_no_additions():
    new = replace(M2, recorded_at=IN.isoformat())
    gone = RowState(ref=M1.source_ref.key(), missing=True)
    result = _run(_base([M1], same=False), _snap([new]), _rows(gone, _row(new, recorded_at=IN)))
    assert _kinds(result) == [("deleted", M1.source_ref.key())]
    assert dict(result.suppressed) == {"newly_relevant": 1}
    assert result.baseline["same_conversation"] is False


# ── Noise: hostile, pending, acknowledged ─────────────────────


def test_hostile_and_pending_subjects_are_dropped():
    rows = _rows(_row(M1, hostile=True, status="rejected"), _row(M2, status="pending"))
    result = _run(_base([M1, M2]), _snap([]), rows)
    assert result.changes == ()
    assert dict(result.suppressed) == {"hostile": 1, "pending_only": 1}


def test_the_owners_own_changes_are_flagged_acknowledged():
    # Saved in this conversation (properties.task_id is one of its turns).
    new = replace(M2, recorded_at=IN.isoformat())
    rows = _rows(_row(M1), _row(new, recorded_at=IN, task_id="turn-1"))
    (added,) = _run(_base([M1]), _snap([M1, new]), rows, conversation_tasks={"turn-1"}).changes
    assert added.acknowledged is True
    (other,) = _run(_base([M1]), _snap([M1, new]), rows, conversation_tasks={"turn-2"}).changes
    assert other.acknowledged is False
    # Replaced by the owner's correction.
    corrected = _rows(
        _row(M1, status="superseded", superseded_by=_id(2)), _row(M2, owner_correction=True)
    )
    (sup,) = _run(_base([M1]), _snap([]), corrected).changes
    assert sup.kind == "superseded" and sup.acknowledged is True
    # A /deny.
    denied = _rows(_row(M1, status="superseded", denied=True))
    (deny,) = _run(_base([M1]), _snap([]), denied).changes
    assert deny.acknowledged is True and deny.evidence == (M1.source_ref.key(),)
    # Rejected by the owner in review.
    owner = _rows(_row(M1, status="rejected", reviewed_by_owner=True))
    assert _run(_base([M1]), _snap([]), owner).changes[0].acknowledged is True
    # Replaced by a model's extraction: not the owner's doing.
    plain = _rows(_row(M1, status="superseded", superseded_by=_id(2)), _row(M2))
    assert _run(_base([M1]), _snap([]), plain).changes[0].acknowledged is False


# ── Cap, order, determinism, coverage ─────────────────────────


def test_the_cap_holds_at_twenty_in_priority_order():
    gone = [_item("memory", 100 + n) for n in range(18)]
    aging = [replace(_item("memory", 200 + n), freshness="aging") for n in range(3)]
    new = [_item("memory", 300 + n, recorded_at=IN.isoformat()) for n in range(3)]
    rows = _rows(
        *(RowState(ref=g.source_ref.key(), missing=True) for g in gone),
        *(_row(a) for a in aging),
        *(_row(n, recorded_at=IN) for n in new),
    )
    stale = [replace(a, freshness="stale") for a in aging]
    result = _run(_base([*gone, *aging]), _snap([*stale, *new]), rows)
    assert len(result.changes) == MAX_CHANGES
    kinds = [c.kind for c in result.changes]
    assert kinds == ["deleted"] * 18 + ["added"] * 2
    assert dict(result.suppressed)["over_budget"] == 4


def test_the_same_input_gives_byte_identical_output():
    new = replace(M2, recorded_at=IN.isoformat())
    rows = _rows(_row(M1, status="rejected"), _row(new, recorded_at=IN), _row(M3, valid_until=IN))
    args = (_base([M1, M3]), _snap([new]), rows)
    first = json.dumps(_run(*args).to_dict(), sort_keys=False)
    second = json.dumps(_run(*args).to_dict(), sort_keys=False)
    assert first == second


def test_a_moved_baseline_does_not_repeat_a_change():
    worded = fingerprint(_id(1), "something else entirely")
    edited = replace(M1, fingerprint=worded)
    rows = _rows(_row(M1, fp=worded, updated_at=IN))
    first = _run(_base([M1]), _snap([edited]), rows)
    assert _kinds(first) == [("edited", M1.source_ref.key())]
    # Next turn: this turn's snapshot is the baseline.
    moved = Baseline.from_compact(_snap([edited]).compact(), task_id="this-turn")
    again = compare_context(moved, _snap([edited], at=T1 + timedelta(hours=1)), rows, T1)
    assert again.changes == ()


def test_every_change_has_evidence_a_reason_and_a_stable_key():
    new = replace(M2, recorded_at=IN.isoformat())
    rows = _rows(_row(M1, status="archived"), _row(new, recorded_at=IN))
    result = _run(_base([M1]), _snap([new]), rows)
    assert result.changes
    for c in result.changes:
        assert c.evidence and c.reason and len(c.key) == 16
    again = _run(_base([M1]), _snap([new]), rows)
    assert [c.key for c in again.changes] == [c.key for c in result.changes]


def test_the_trace_form_holds_no_content_no_query_and_no_fingerprint():
    worded = fingerprint(_id(1), "other words")
    result = _run(_base([M1]), _snap([]), _rows(_row(M1, fp=worded)))
    blob = json.dumps(result.trace())
    assert "SECRET" not in blob
    assert worded not in blob and M1.fingerprint not in blob
    assert result.trace()["changes"][0]["kind"] == "edited"


# ── Insufficient ─────────────────────────────────────────────


def test_no_baseline_is_insufficient_never_everything_new():
    result = _run(None, _snap([M1]), {})
    assert result.insufficient is True and result.changes == ()
    assert result.explanation == "No earlier snapshot to compare with."


@pytest.mark.parametrize(
    "compact",
    [
        {"items": [], "conflicts": []},  # format 1: no v, no reference_time
        {"v": 1, "reference_time": T0.isoformat(), "sources": ["memories"], "items": []},
        {"error": "TimeoutError", "ms": 1000},
        {"v": 2, "reference_time": T0.isoformat(), "sources": [], "items": []},  # reads failed
        None,
    ],
)
def test_an_unusable_trace_is_no_baseline(compact):
    assert Baseline.from_compact(compact) is None


def test_a_baseline_over_thirty_days_old_is_insufficient():
    old = _base([M1], at=T1 - timedelta(days=31))
    result = _run(old, _snap([]), _rows(RowState(ref=M1.source_ref.key(), missing=True)))
    assert result.insufficient is True and result.changes == ()


def test_a_failed_read_is_insufficient():
    result = _run(_base([M1]), _snap([]), None)
    assert result.insufficient is True and "failed" in result.explanation


# ── Fingerprint, compact v2, refs ─────────────────────────────


def test_normalisation_keeps_words_and_drops_case_space_and_punctuation():
    assert normalise_text("  Car Insurance,  renews in MARCH. ") == "car insurance renews in march"
    assert normalise_text("ｃａｒ") == "car"  # NFKC
    assert fingerprint("x", "காப்பீடு மார்ச்.") == fingerprint("x", "காப்பீடு  மார்ச்")
    assert fingerprint("x", "காப்பீடு மார்ச்") != fingerprint("x", "காப்பீடு ஏப்ரல்")
    assert fingerprint("x", "same") != fingerprint("y", "same")  # salted with the id
    assert len(fingerprint("x", "same")) == 16


def test_compact_v2_keeps_reference_time_fingerprint_and_recorded_time():
    compact = _snap([M1]).compact()
    assert compact["v"] == 2 and compact["reference_time"] == T1.isoformat()
    (item,) = compact["items"]
    assert item["fp"] == M1.fingerprint and item["rec"] == BEFORE.isoformat()
    assert "SECRET" not in json.dumps(compact)
    # to_dict (the API form) never carries the fingerprint.
    assert "fingerprint" not in M1.to_dict() and "fp" not in M1.to_dict()


def test_refs_to_resolve_covers_both_snapshots_and_conflicts():
    c = _contradiction(M1, 40)
    refs, approvals = refs_to_resolve(_base([M2], [c]), _snap([M3]))
    assert refs == sorted(
        [M1.source_ref.key(), M2.source_ref.key(), M3.source_ref.key(), "memory:" + _id(40)]
    )
    assert approvals == [_id(900)]


def test_compare_reads_no_clock(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("compare_context read the clock")

    class _NoClock(datetime):
        now = boom
        utcnow = boom

    monkeypatch.setattr(changes, "datetime", _NoClock)
    rows = _rows(_row(M1, status="rejected"))
    assert _kinds(_run(_base([M1]), _snap([]), rows)) == [("rejected", M1.source_ref.key())]


# ── Review of #405: past-due times, failed comparisons, temporary chats ──


def test_a_time_that_passed_in_the_window_is_not_approaching():
    i = _item("intention", 50, origin="extracted", confirmed=False)
    three_days = T1 - timedelta(days=3)  # a window longer than 48 h
    passed = T1 - timedelta(hours=2)  # crossed the 48 h line, then passed
    result = _run(_base([i], at=three_days), _snap([i]), _rows(_row(i, trigger_time=passed)))
    assert result.changes == ()
    # An expiry that passed is the expired kind, never "within 48 hours".
    gone = _run(_base([i], at=three_days), _snap([]), _rows(_row(i, expires_at=passed)))
    assert _kinds(gone) == [("intention_expired", i.source_ref.key())]


def test_a_failed_re_read_is_marked_so_the_next_turn_skips_it():
    assert _run(_base([M1]), _snap([]), None).trace()["read_failed"] is True
    assert _run(_base([M1]), _snap([]), _rows(_row(M1))).trace()["read_failed"] is False
    assert changes.compare_failed({"error": "TimeoutError", "ms": 1000}) is True
    assert changes.compare_failed({"read_failed": True, "insufficient": True}) is True
    # No earlier snapshot is not a failure; nor is "compare was off".
    assert changes.compare_failed(_run(None, _snap([M1]), {}).trace()) is False
    assert changes.compare_failed(None) is False


def _turn_row(n: int, at: datetime, *, chg=None, **inp):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=f"turn-{n}", input={"message": "x", **inp}, snap=_snap([M1], at=at).compact(), chg=chg
    )


def test_the_baseline_skips_failed_comparisons_and_temporary_turns():
    from types import SimpleNamespace

    cur = SimpleNamespace(id="turn-9", input={"message": "x"})
    ok = _turn_row(1, T0)  # compare was off: still a baseline
    failed = _turn_row(2, T0 + timedelta(hours=2), chg={"error": "TimeoutError"})
    unread = _turn_row(3, T0 + timedelta(hours=3), chg={"read_failed": True})
    temporary = _turn_row(4, T0 + timedelta(hours=4), temporary=True)
    rows = [temporary, unread, failed, ok]  # newest first, as the lookup reads them
    found = changes._pick(rows, cur, same_conversation=True)
    assert found is not None and found.task_id == "turn-1"
    fine = _turn_row(5, T0 + timedelta(hours=5), chg={"insufficient": True, "read_failed": False})
    assert changes._pick([fine, *rows], cur, same_conversation=True).task_id == "turn-5"
    assert changes._pick([temporary], cur, same_conversation=True) is None
