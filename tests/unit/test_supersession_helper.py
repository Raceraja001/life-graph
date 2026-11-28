"""services/memory/supersession.py: the one place a memory is replaced (ADR M8 §5.2).

The helper only changes ORM objects, so plain stand-ins are enough here; the
database round trip is in tests/integration/test_supersession_pg.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from life_graph.services.memory import supersession

NOW = datetime(2026, 11, 28, 9, 30, tzinfo=UTC)


def _mem(tenant: str = "t1", status: str = "active", **props) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant,
        status=status,
        superseded_by=None,
        supersedes=None,
        updated_at=None,
        valid_until=None,
        properties=dict(props),
    )


def test_apply_writes_the_same_columns_every_writer_wrote():
    old, new = _mem(slot="home.city"), _mem(status="pending")

    assert supersession.apply("t1", old, new, why="test", now=NOW)

    assert old.status == "superseded"
    assert old.superseded_by == new.id
    assert old.updated_at == NOW
    assert old.properties == {"slot": "home.city", "superseded_at": NOW.isoformat()}
    assert new.supersedes == old.id
    # Not activated unless asked, and no world-time end (ADR step 5).
    assert new.status == "pending"
    assert old.valid_until is None and new.valid_until is None
    assert "superseded_at" not in new.properties


def test_apply_reassigns_properties_so_the_orm_sees_the_change():
    props = {"slot": "home.city"}
    old, new = _mem(), _mem()
    old.properties = props

    supersession.apply("t1", old, new, why="test", now=NOW)

    assert old.properties is not props
    assert props == {"slot": "home.city"}


def test_activate_new_and_a_note():
    old, new = _mem(), _mem(status="pending")

    supersession.apply(
        "t1", old, new, why="merge", activate_new=True, note={"merged_into": str(new.id)}
    )

    assert new.status == "active"
    assert old.properties["merged_into"] == str(new.id)
    assert "superseded_at" in old.properties


@pytest.mark.parametrize("which", ["old", "new"])
def test_a_row_of_another_tenant_is_refused_and_nothing_changes(which):
    old, new = _mem(), _mem()
    (old if which == "old" else new).tenant_id = "t2"

    assert not supersession.apply("t1", old, new, why="test")

    assert old.status == "active" and old.superseded_by is None
    assert old.properties == {} and new.supersedes is None


@pytest.mark.parametrize(
    ("old_status", "new_status", "kwargs", "applied"),
    [
        # tools/memory_search.py: only an active old memory is replaced.
        ("superseded", "active", {}, False),
        ("active", "rejected", {}, True),
        # MemoryManager.supersede: any old status, as before.
        ("superseded", "active", {"old_statuses": None}, True),
        # The approvals' deferred supersede: new must be pending or active.
        ("active", "rejected", {"new_statuses": supersession.PENDING_OR_ACTIVE}, False),
        ("active", "pending", {"new_statuses": supersession.PENDING_OR_ACTIVE}, True),
    ],
)
def test_each_callers_status_rule_is_a_parameter(old_status, new_status, kwargs, applied):
    old, new = _mem(status=old_status), _mem(status=new_status)

    assert supersession.apply("t1", old, new, why="test", **kwargs) is applied
    assert (old.status == "superseded" and old.superseded_by == new.id) is applied


def test_missing_rows_and_the_same_row_are_refused():
    m = _mem()
    assert not supersession.apply("t1", None, m, why="test")
    assert not supersession.apply("t1", m, None, why="test")
    assert not supersession.apply("t1", m, m, why="test", old_statuses=None)
    assert m.status == "active" and m.supersedes is None


def test_the_world_change_seam_is_not_built_yet():
    with pytest.raises(NotImplementedError):
        supersession.apply("t1", _mem(), _mem(), why="test", world_change=True)


def test_undo_round_trip_restores_the_old_memory():
    old, new = _mem(slot="home.city"), _mem()
    supersession.apply("t1", old, new, why="test", now=NOW)

    assert supersession.undo("t1", old, new)

    assert old.status == "active"
    assert old.superseded_by is None
    assert old.properties == {"slot": "home.city"}
    assert new.supersedes is None


def test_undo_without_the_new_memory_still_restores_the_old_one():
    old, new = _mem(), _mem()
    supersession.apply("t1", old, new, why="test")

    assert supersession.undo("t1", old, None)
    assert old.status == "active" and old.superseded_by is None


def test_undo_leaves_a_later_edit_alone():
    old, new, other = _mem(), _mem(), _mem()
    supersession.apply("t1", old, new, why="test")

    # Replaced by a different memory since: not this item's supersede.
    assert not supersession.undo("t1", old, other)
    assert old.status == "superseded" and old.superseded_by == new.id
    # Not superseded at all: nothing to undo.
    fresh = _mem()
    assert not supersession.undo("t1", fresh, new)
    assert fresh.status == "active"


@pytest.mark.parametrize("which", ["old", "new"])
def test_undo_refuses_another_tenants_row(which):
    old, new = _mem(), _mem()
    supersession.apply("t1", old, new, why="test")
    (old if which == "old" else new).tenant_id = "t2"

    assert not supersession.undo("t1", old, new)
    assert old.status == "superseded" and new.supersedes == old.id
