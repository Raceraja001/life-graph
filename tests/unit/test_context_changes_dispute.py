"""The owner's "this memory was wrong" as a Stage 2 change (D13, services/memory/changes.py).

api/jarvis.py ``memory_was_wrong`` moves an active memory to pending and writes
``properties.disputed = {at, task_id, note}``. Stage 2 used to drop every
pending subject as ``pending_only``, so the owner's own dispute vanished. It
is now a ``disputed`` change, acknowledged; any other way back to pending is
still dropped. Pure, as tests/unit/test_context_changes.py.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from life_graph.services.memory import changes
from life_graph.services.memory.changes import memory_state
from tests.unit import test_context_changes as base

M1, M2 = base.M1, base.M2
BEFORE, IN, T0, T1 = base.BEFORE, base.IN, base.T0, base.T1


def _disputed_row(item, at):
    return base._row(item, status="pending", disputed_at=at)


def test_an_owner_dispute_in_the_window_is_reported_and_acknowledged():
    result = base._run(base._base([M1]), base._snap([]), base._rows(_disputed_row(M1, IN)))
    (change,) = result.changes
    assert (change.kind, change.ref, change.evidence) == (
        "disputed",
        M1.source_ref.key(),
        (M1.source_ref.key(),),
    )
    assert change.acknowledged is True
    assert change.at == IN.isoformat()
    assert change.before == {"status": "active", "fp": M1.fingerprint}
    assert change.after == {"status": "pending"}
    assert change.reason == "the owner said it was wrong: status went active -> pending"
    assert dict(result.suppressed) == {}
    # The trace form: no fingerprint, no content, no query.
    trace = json.dumps(result.trace())
    assert "SECRET" not in trace and M1.fingerprint not in trace


def test_pending_without_the_owners_marker_is_still_dropped():
    rows = base._rows(base._row(M1, status="pending"))
    result = base._run(base._base([M1]), base._snap([]), rows)
    assert result.changes == () and dict(result.suppressed) == {"pending_only": 1}


def test_a_dispute_from_before_the_window_is_not_reported_again():
    rows = base._rows(_disputed_row(M1, BEFORE), _disputed_row(M2, T1 + (T1 - T0)))
    result = base._run(base._base([M1, M2]), base._snap([]), rows)
    assert result.changes == () and dict(result.suppressed) == {"pending_only": 2}


def test_a_hostile_subject_stays_dropped_even_when_disputed():
    rows = base._rows(base._row(M1, status="pending", disputed_at=IN, hostile=True))
    result = base._run(base._base([M1]), base._snap([]), rows)
    assert result.changes == () and dict(result.suppressed) == {"hostile": 1}


def test_a_dispute_is_a_transition_so_another_conversations_baseline_reports_it():
    rows = base._rows(_disputed_row(M1, IN))
    result = base._run(base._base([M1], same=False), base._snap([]), rows)
    assert base._kinds(result) == [("disputed", M1.source_ref.key())]


def test_disputed_is_a_removal_in_priority_and_has_a_fixed_reason():
    assert changes.PRIORITY["disputed"] == 0
    assert "disputed" in changes.KINDS
    assert "{" not in changes.REASONS["disputed"].format(before="active")


def _memory(props):
    return SimpleNamespace(
        id=uuid.uuid4(),
        content="the car insurance renews in March",
        status="pending",
        source_type="chat",
        trust_tier="self",
        extraction_tier=None,
        properties=props,
        tags=None,
        created_at=BEFORE,
        updated_at=IN,
        valid_from=BEFORE,
        valid_until=None,
        superseded_by=None,
        last_reinforced=None,
    )


def test_memory_state_reads_the_marker_the_endpoint_writes():
    # The exact shape api/jarvis.py memory_was_wrong merges into properties.
    marker = {"disputed": {"at": IN.isoformat(), "task_id": str(uuid.uuid4()), "note": None}}
    assert memory_state(_memory(marker)).disputed_at == IN
    assert memory_state(_memory({})).disputed_at is None
    assert memory_state(_memory({"disputed": "yes"})).disputed_at is None
    assert memory_state(_memory({"disputed": {"at": "not a time"}})).disputed_at is None
