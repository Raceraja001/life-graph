"""The decision lifecycle (services/decision_lifecycle.py, ADR M8 §5.4), pure.

Every move of the table, allowed and refused, for the owner, for anyone else
and for the system's mirror; the trail each move leaves; tenant scoping; the
owner routes; the memory side behind ``settings.decision_lifecycle`` (on and
off); and the readers (snapshot ``confirmed``, change detection ``at`` and
``acknowledged``, failure mining). No database: sessions are stand-ins.
"""

from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import life_graph.api.judgment as judgment_api
from life_graph.config import settings
from life_graph.core.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from life_graph.core.trust import UNVERIFIED, Ingress
from life_graph.models.schemas import DECISION_STATUSES, DecisionSupersede
from life_graph.services import decision_lifecycle as lc
from life_graph.services import failure_mining
from life_graph.services.judgment import JudgmentService
from life_graph.services.memory import changes, snapshot, supersession

OWNER = Ingress(actor="owner:api_key", owner_verified=True)
PHONE = Ingress(actor="device:d1", owner_verified=True, device_id="d1")
NOW = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)

OWNER_MOVES = {
    ("candidate", "decided"),
    ("candidate", "discarded"),
    ("decided", "reviewed"),
    ("decided", "superseded"),
    ("reviewed", "superseded"),
}
MIRROR_MOVES = {("candidate", "superseded"), ("superseded", "candidate")}
ALL_PAIRS = list(itertools.product(DECISION_STATUSES, repeat=2))


# ── Stand-ins ─────────────────────────────────────────────────


def _decision(tenant: str = "A", status: str = "candidate", **kw):
    base = {
        "id": uuid.uuid4(),
        "tenant_id": tenant,
        "status": status,
        "superseded_by": None,
        "superseded_at": None,
        "decided_at": None,
        "reviewed_at": None,
        "properties": {},
    }
    base.update(kw)
    return SimpleNamespace(**base)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(first=lambda: self._rows[0] if self._rows else None)


class _Session:
    """Answers ``select(Decision).where(tenant_id, id)`` like the database would."""

    def __init__(self, *rows):
        self.rows = rows
        self.queries = 0

    async def execute(self, stmt):
        self.queries += 1
        params = stmt.compile().params
        tenant = next(v for k, v in params.items() if k.startswith("tenant_id"))
        ident = next(v for k, v in params.items() if k.startswith("id"))
        return _Result([r for r in self.rows if r.tenant_id == tenant and r.id == ident])


def _snapshot(d):
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in vars(d).items()}


# ── The table ─────────────────────────────────────────────────


@pytest.mark.parametrize(("current", "to"), sorted(OWNER_MOVES))
def test_the_owner_may_make_every_owner_move(current, to):
    lc.check(current, to, owner=True)


@pytest.mark.parametrize(("current", "to"), sorted(OWNER_MOVES))
def test_nobody_else_may_make_an_owner_move(current, to):
    with pytest.raises(ForbiddenError):
        lc.check(current, to, owner=False)
    with pytest.raises(ForbiddenError):
        lc.check(current, to, owner=False, mirror=True)  # not even as a mirror


@pytest.mark.parametrize(("current", "to"), sorted(MIRROR_MOVES))
def test_a_system_move_only_as_a_mirror(current, to):
    lc.check(current, to, owner=False, mirror=True)
    for owner in (True, False):
        with pytest.raises(ForbiddenError):
            lc.check(current, to, owner=owner)


@pytest.mark.parametrize(
    ("current", "to"), [p for p in ALL_PAIRS if p not in OWNER_MOVES | MIRROR_MOVES]
)
def test_every_other_move_is_refused_for_everyone(current, to):
    for owner, mirror in itertools.product((True, False), repeat=2):
        with pytest.raises(ConflictError):
            lc.check(current, to, owner=owner, mirror=mirror)


def test_inferred_context_never_reaches_decided_without_the_owner():
    """No (from, decided) move is open to anyone but the owner."""
    into_decided = [k for k in lc.TRANSITIONS if k[1] == "decided"]
    assert into_decided == [("candidate", "decided")]
    assert lc.TRANSITIONS[("candidate", "decided")] == lc.OWNER


def test_the_table_uses_only_known_statuses():
    assert {s for pair in lc.TRANSITIONS for s in pair} <= set(DECISION_STATUSES)


# ── move(): confirm, discard, review ─────────────────────────


async def test_owner_confirm_sets_decided_at_and_the_trail():
    d = _decision()
    out = await lc.move(_Session(d), "A", d.id, "decided", by="owner", owner=True, now=NOW)

    assert out is d and d.status == "decided" and d.decided_at == NOW
    assert d.properties["lifecycle"] == [
        {"from": "candidate", "to": "decided", "at": NOW.isoformat(), "by": "owner", "owner": True}
    ]


async def test_owner_discard_and_review_leave_their_own_entries():
    d = _decision()
    session = _Session(d)
    await lc.move(session, "A", d.id, "discarded", by="phone:d1", owner=True, now=NOW)
    assert d.status == "discarded" and d.decided_at is None

    r = _decision(status="decided")
    await lc.move(_Session(r), "A", r.id, "reviewed", by="owner", owner=True, now=NOW)
    assert r.status == "reviewed" and r.reviewed_at == NOW
    assert [e["to"] for e in r.properties["lifecycle"]] == ["reviewed"]


@pytest.mark.parametrize("to", ["decided", "discarded"])
async def test_a_non_owner_move_writes_nothing(to):
    d = _decision()
    before = _snapshot(d)
    with pytest.raises(ForbiddenError):
        await lc.move(_Session(d), "A", d.id, to, by="service-key:abcd1234", owner=False)
    assert _snapshot(d) == before


async def test_a_refused_move_writes_nothing():
    d = _decision(status="discarded")
    before = _snapshot(d)
    with pytest.raises(ConflictError):
        await lc.move(_Session(d), "A", d.id, "decided", by="owner", owner=True)
    assert _snapshot(d) == before


async def test_move_cannot_reach_another_tenants_decision():
    theirs = _decision("B")
    with pytest.raises(NotFoundError):
        await lc.move(_Session(theirs), "A", theirs.id, "decided", by="owner", owner=True)
    assert theirs.status == "candidate" and theirs.properties == {}


async def test_move_does_not_supersede():
    d = _decision(status="decided")
    with pytest.raises(InvalidInputError):
        await lc.move(_Session(d), "A", d.id, "superseded", by="owner", owner=True)


async def test_the_trail_appends_and_keeps_other_properties():
    d = _decision(properties={"memory_id": "m1"})
    await lc.move(_Session(d), "A", d.id, "decided", by="owner", owner=True, now=NOW)
    later = NOW + timedelta(days=30)
    await lc.move(_Session(d), "A", d.id, "reviewed", by="phone:d1", owner=True, now=later)

    assert d.properties["memory_id"] == "m1"
    trail = d.properties["lifecycle"]
    assert [(e["from"], e["to"], e["by"]) for e in trail] == [
        ("candidate", "decided", "owner"),
        ("decided", "reviewed", "phone:d1"),
    ]
    assert trail[1]["at"] == later.isoformat()


# ── supersede() ──────────────────────────────────────────────


@pytest.mark.parametrize("status", ["decided", "reviewed"])
async def test_owner_supersede_sets_superseded_at_and_names_the_replacement(status):
    old, new = _decision(status=status), _decision(status="decided")
    await lc.supersede(_Session(old, new), "A", old.id, new.id, by="owner", owner=True, now=NOW)

    assert old.status == "superseded"
    assert old.superseded_by == new.id and old.superseded_at == NOW
    (entry,) = old.properties["lifecycle"]
    assert entry == {
        "from": status,
        "to": "superseded",
        "at": NOW.isoformat(),
        "by": "owner",
        "owner": True,
        "replaced_by": str(new.id),
    }
    assert new.status == "decided" and new.properties == {}


@pytest.mark.parametrize("status", ["decided", "reviewed"])
async def test_the_system_never_supersedes_the_owners_decision(status):
    old, new = _decision(status=status), _decision()
    before = _snapshot(old)
    for mirror in (None, {"memory_old": "m1", "memory_new": "m2"}):
        with pytest.raises(ForbiddenError):
            await lc.supersede(_Session(old, new), "A", old.id, new.id, by="x", mirror=mirror)
    assert _snapshot(old) == before


async def test_a_mirror_supersedes_a_candidate_and_promotes_nothing():
    old, new = _decision(), _decision()
    mirror = {"memory_old": "m-old", "memory_new": "m-new"}
    await lc.supersede(
        _Session(old, new), "A", old.id, new.id, by=lc.MIRROR_BY, mirror=mirror, now=NOW
    )
    assert old.status == "superseded" and old.superseded_at == NOW
    (entry,) = old.properties["lifecycle"]
    assert entry["by"] == lc.MIRROR_BY and entry["owner"] is False
    assert entry["memory_old"] == "m-old" and entry["memory_new"] == "m-new"
    assert new.status == "candidate"  # the new decision keeps its own status


async def test_the_owner_does_not_supersede_a_candidate():
    """Confirm or discard it instead; superseding a candidate is the mirror's alone."""
    old, new = _decision(), _decision(status="decided")
    with pytest.raises(ForbiddenError):
        await lc.supersede(_Session(old, new), "A", old.id, new.id, by="owner", owner=True)
    assert old.status == "candidate"


@pytest.mark.parametrize("status", ["superseded", "discarded"])
async def test_a_finished_decision_cannot_be_superseded(status):
    old, new = _decision(status=status), _decision(status="decided")
    with pytest.raises(ConflictError):
        await lc.supersede(_Session(old, new), "A", old.id, new.id, by="owner", owner=True)


async def test_supersede_refuses_a_loop():
    old = _decision(status="decided")
    mid = _decision(status="superseded", superseded_by=old.id)
    new = _decision(status="superseded", superseded_by=mid.id)
    with pytest.raises(ConflictError):
        await lc.supersede(_Session(old, mid, new), "A", old.id, new.id, by="owner", owner=True)
    assert old.status == "decided" and old.superseded_by is None


async def test_supersede_refuses_another_tenants_old_decision():
    theirs, mine = _decision("B", status="decided"), _decision("A", status="decided")
    with pytest.raises(NotFoundError):
        await lc.supersede(_Session(theirs, mine), "A", theirs.id, mine.id, by="owner", owner=True)
    assert theirs.status == "decided" and theirs.superseded_at is None


async def test_supersede_refuses_another_tenants_replacement():
    mine, theirs = _decision("A", status="decided"), _decision("B", status="decided")
    with pytest.raises(NotFoundError):
        await lc.supersede(_Session(mine, theirs), "A", mine.id, theirs.id, by="owner", owner=True)
    assert mine.status == "decided" and mine.superseded_at is None


async def test_the_service_emits_after_the_lifecycle_supersede():
    old, new = _decision(status="decided"), _decision(status="decided")
    bus = SimpleNamespace(emit=AsyncMock())
    out = await JudgmentService(_Session(old, new), bus).supersede_decision(
        "A", old.id, new.id, by="owner", owner=True
    )
    assert out is old and old.superseded_at is not None
    bus.emit.assert_awaited_once()


async def test_the_service_emits_nothing_when_refused():
    old, new = _decision(status="decided"), _decision()
    bus = SimpleNamespace(emit=AsyncMock())
    with pytest.raises(ForbiddenError):
        await JudgmentService(_Session(old, new), bus).supersede_decision("A", old.id, new.id)
    bus.emit.assert_not_awaited()


# ── Create ───────────────────────────────────────────────────


async def test_an_owner_create_starts_the_trail():
    session = SimpleNamespace(add=lambda _row: None, flush=AsyncMock())
    d = await JudgmentService(session).create_decision(
        "A", "Use Postgres", status="decided", by="owner", owner=True
    )
    (entry,) = d.properties["lifecycle"]
    assert entry["from"] is None and entry["to"] == "decided" and entry["owner"] is True
    assert lc.owner_confirmed(d)


@pytest.mark.parametrize(
    ("status", "by"), [("candidate", "owner"), ("decided", None), ("candidate", None)]
)
async def test_other_creates_have_no_trail(status, by):
    session = SimpleNamespace(add=lambda _row: None, flush=AsyncMock())
    d = await JudgmentService(session).create_decision("A", "x", status=status, by=by)
    assert d.properties == {}
    assert not lc.owner_confirmed(d)


# ── Routes ───────────────────────────────────────────────────


def _as(monkeypatch, ingress):
    monkeypatch.setattr(judgment_api, "ingress_for", lambda _request: ingress)


ROUTES = [
    (judgment_api.confirm_decision, "decided"),
    (judgment_api.discard_decision, "discarded"),
    (judgment_api.review_decision, "reviewed"),
]


@pytest.mark.parametrize(("route", "to"), ROUTES)
async def test_a_move_route_refuses_a_non_owner(monkeypatch, route, to):
    _as(monkeypatch, UNVERIFIED)
    monkeypatch.setattr(settings, "approvals_require_owner", False)  # always on regardless
    svc = SimpleNamespace(move_decision=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await route(decision_id=uuid.uuid4(), request=SimpleNamespace(), svc=svc, tenant_id="A")
    assert exc.value.status_code == 403
    svc.move_decision.assert_not_awaited()


@pytest.mark.parametrize(("ingress", "label"), [(OWNER, "owner"), (PHONE, "phone:d1")])
@pytest.mark.parametrize(("route", "to"), ROUTES)
async def test_a_move_route_records_the_owner(monkeypatch, route, to, ingress, label):
    _as(monkeypatch, ingress)
    d = _decision(status=to)
    row = SimpleNamespace(
        **{**vars(d)},
        title="x",
        reasoning=None,
        options=[],
        chosen_option=None,
        source="conversation",
        domain_tags=[],
        importance=0.5,
        capture_event_id=None,
        review_at=None,
        created_at=NOW,
    )
    svc = SimpleNamespace(move_decision=AsyncMock(return_value=row))
    resp = await route(decision_id=d.id, request=SimpleNamespace(), svc=svc, tenant_id="A")
    svc.move_decision.assert_awaited_once_with("A", d.id, to, by=label, owner=True)
    assert resp["data"].status == to


async def test_the_supersede_route_refuses_a_non_owner(monkeypatch):
    _as(monkeypatch, UNVERIFIED)
    svc = SimpleNamespace(supersede_decision=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await judgment_api.supersede_decision(
            decision_id=uuid.uuid4(),
            body=DecisionSupersede(replaced_by=uuid.uuid4()),
            request=SimpleNamespace(),
            svc=svc,
            tenant_id="A",
        )
    assert exc.value.status_code == 403
    svc.supersede_decision.assert_not_awaited()


async def test_the_supersede_route_passes_the_owner_and_the_replacement(monkeypatch):
    _as(monkeypatch, OWNER)
    old, new = _decision(status="decided"), _decision(status="decided")
    svc = JudgmentService(_Session(old, new))
    for k, v in {
        "title": "x",
        "reasoning": None,
        "options": [],
        "chosen_option": None,
        "source": "explicit",
        "domain_tags": [],
        "importance": 0.5,
        "capture_event_id": None,
        "review_at": None,
        "created_at": NOW,
    }.items():
        setattr(old, k, v)
    resp = await judgment_api.supersede_decision(
        decision_id=old.id,
        body=DecisionSupersede.model_validate({"by": str(new.id)}),  # the ADR's name
        request=SimpleNamespace(),
        svc=svc,
        tenant_id="A",
    )
    assert resp["data"].status == "superseded"
    assert resp["data"].superseded_at is not None
    assert old.properties["lifecycle"][-1]["by"] == "owner"


def test_the_supersede_body_needs_a_replacement():
    with pytest.raises(ValidationError):
        DecisionSupersede.model_validate({})


# ── Readers ──────────────────────────────────────────────────


def _trail(*entries):
    return {"lifecycle": [dict(e) for e in entries]}


OWNER_DECIDED = {
    "from": "candidate",
    "to": "decided",
    "at": NOW.isoformat(),
    "by": "owner",
    "owner": True,
}


@pytest.mark.parametrize(
    ("status", "props", "confirmed"),
    [
        ("decided", _trail(OWNER_DECIDED), True),
        (
            "reviewed",
            _trail(OWNER_DECIDED, {**OWNER_DECIDED, "from": "decided", "to": "reviewed"}),
            True,
        ),
        ("decided", {}, False),  # no trail: who decided is unknown
        ("decided", _trail({**OWNER_DECIDED, "by": "service-key:ab", "owner": False}), False),
        ("decided", _trail({**OWNER_DECIDED, "owner": "yes"}), False),
        ("decided", _trail({**OWNER_DECIDED, "by": "service-key:ab"}), False),
        ("candidate", _trail(OWNER_DECIDED), False),
        ("superseded", _trail(OWNER_DECIDED), False),
    ],
)
def test_owner_confirmed(status, props, confirmed):
    assert lc.owner_confirmed(_decision(status=status, properties=props)) is confirmed


def test_snapshot_confirms_only_an_owner_decided_decision():
    def item(**kw):
        d = _decision(
            status="decided",
            source="conversation",
            title="Move the backups",
            reasoning=None,
            created_at=NOW,
            review_at=None,
            **kw,
        )
        return snapshot.decision_item(d, NOW, snapshot.DEFAULT_BUDGET)

    assert item(properties=_trail(OWNER_DECIDED)).confirmed is True
    assert item(properties={}).confirmed is False


def test_changes_reads_superseded_at_and_the_trail():
    sup = _decision(
        status="superseded",
        superseded_by=uuid.uuid4(),
        superseded_at=NOW,
        source="conversation",
        title="t",
        reasoning=None,
        created_at=NOW - timedelta(days=3),
        review_at=None,
        properties=_trail({**OWNER_DECIDED, "from": "decided", "to": "superseded"}),
    )
    row = changes.decision_state(sup)
    assert row.superseded_at == NOW and row.status_at == NOW and row.status_by_owner is True

    mirrored = _decision(
        status="superseded",
        superseded_by=uuid.uuid4(),
        superseded_at=NOW,
        source="conversation",
        title="t",
        reasoning=None,
        created_at=NOW,
        review_at=None,
        properties=_trail(
            {
                "from": "candidate",
                "to": "superseded",
                "at": NOW.isoformat(),
                "by": lc.MIRROR_BY,
                "owner": False,
            }
        ),
    )
    assert changes.decision_state(mirrored).status_by_owner is False

    bare = _decision(
        status="discarded",
        source="explicit",
        title="t",
        reasoning=None,
        created_at=NOW,
        review_at=None,
    )
    row = changes.decision_state(bare)
    assert row.status_at is None and row.status_by_owner is False


def test_failure_mining_reads_only_real_statuses():
    assert set(failure_mining._FAILURE_STATUSES) <= set(DECISION_STATUSES)
    assert "discarded" not in failure_mining._FAILURE_STATUSES


# ── The memory side: settings.decision_lifecycle ─────────────


class _NoDb:
    """A session that must not be used."""

    async def execute(self, _stmt):  # pragma: no cover - failing is the point
        raise AssertionError("read the database with the flag off")


@pytest.fixture
def flag(monkeypatch):
    def set_(on: bool) -> None:
        monkeypatch.setattr(settings, "decision_lifecycle", on)

    set_(False)
    return set_


def test_the_flag_is_off_by_default():
    from life_graph.config import Settings

    assert Settings.model_fields["decision_lifecycle"].default is False


async def test_flag_off_the_memory_side_does_nothing(flag):
    old, new = SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())
    assert await supersession.mirror_decisions(_NoDb(), "A", old, new) is False
    assert await supersession.undo_decision_mirror(_NoDb(), "A", old_id=old.id) == 0
    assert await lc.link_capture_memory(_NoDb(), "A", _decision(), uuid.uuid4()) is False
    assert await lc.follow_memory_review("A", uuid.uuid4(), "approve", "owner") is False


@pytest.fixture
def linked(monkeypatch):
    """``_linked`` answered from a {memory id: decision} map, honouring statuses and tenant."""
    links: dict[str, object] = {}

    async def fake(_session, tenant_id, memory_id, statuses=None):
        d = links.get(str(memory_id))
        if d is None or d.tenant_id != tenant_id:
            return None
        if statuses is not None and d.status not in statuses:
            return None
        return d

    monkeypatch.setattr(lc, "_linked", fake)
    return links


async def test_flag_on_a_memory_supersede_supersedes_the_old_candidate(flag, linked):
    flag(True)
    m_old, m_new = SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())
    d_old, d_new = _decision(), _decision()
    linked[str(m_old.id)], linked[str(m_new.id)] = d_old, d_new

    assert await supersession.mirror_decisions(_Session(d_old, d_new), "A", m_old, m_new) is True
    assert d_old.status == "superseded" and d_old.superseded_by == d_new.id
    entry = d_old.properties["lifecycle"][-1]
    assert entry["memory_old"] == str(m_old.id) and entry["memory_new"] == str(m_new.id)
    assert d_new.status == "candidate"


@pytest.mark.parametrize("status", ["decided", "reviewed", "discarded"])
async def test_flag_on_the_mirror_never_moves_a_non_candidate(flag, linked, status):
    flag(True)
    m_old, m_new = SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())
    d_old, d_new = _decision(status=status), _decision()
    linked[str(m_old.id)], linked[str(m_new.id)] = d_old, d_new

    assert await supersession.mirror_decisions(_Session(d_old, d_new), "A", m_old, m_new) is False
    assert d_old.status == status and d_old.properties == {}


async def test_flag_on_the_mirror_needs_both_linked_decisions(flag, linked):
    flag(True)
    m_old, m_new = SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())
    d_old = _decision()
    linked[str(m_old.id)] = d_old
    assert await supersession.mirror_decisions(_Session(d_old), "A", m_old, m_new) is False
    assert d_old.status == "candidate"


async def test_flag_on_the_mirror_stays_in_the_tenant(flag, linked):
    flag(True)
    m_old, m_new = SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())
    theirs, mine = _decision("B"), _decision("A")
    linked[str(m_old.id)], linked[str(m_new.id)] = theirs, mine
    assert await supersession.mirror_decisions(_Session(theirs, mine), "A", m_old, m_new) is False
    assert theirs.status == "candidate"


class _Rows:
    """A session whose one select answers *rows* (the undo's candidates)."""

    def __init__(self, *rows):
        self.rows = rows

    async def execute(self, _stmt):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: list(self.rows)))


def _mirrored(m_old, m_new, **kw):
    entry = {
        "from": "candidate",
        "to": "superseded",
        "at": NOW.isoformat(),
        "by": lc.MIRROR_BY,
        "owner": False,
        "memory_old": str(m_old),
        "memory_new": str(m_new),
    }
    return _decision(
        status="superseded",
        superseded_by=uuid.uuid4(),
        superseded_at=NOW,
        properties=_trail(entry),
        **kw,
    )


async def test_flag_on_the_undo_takes_the_mirror_back(flag):
    flag(True)
    m_old, m_new, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    mine, unrelated = _mirrored(m_old, m_new), _mirrored(other, m_new)
    moved = await supersession.undo_decision_mirror(
        _Rows(mine, unrelated), "A", old_id=m_old, new_id=m_new
    )
    assert moved == 1
    assert mine.status == "candidate" and mine.superseded_by is None and mine.superseded_at is None
    assert mine.properties["lifecycle"][-1]["by"] == lc.MIRROR_UNDO_BY
    assert unrelated.status == "superseded"


async def test_flag_on_the_undo_never_overrides_a_later_owner_move(flag):
    flag(True)
    m_old, m_new = uuid.uuid4(), uuid.uuid4()
    mirrored = _mirrored(m_old, m_new)
    # The owner moved it after the mirror: a later entry, so the undo leaves it.
    mirrored.properties["lifecycle"].append(
        {**OWNER_DECIDED, "from": "superseded", "to": "superseded", "by": "owner"}
    )
    assert await supersession.undo_decision_mirror(_Rows(mirrored), "A", new_id=m_new) == 0
    assert mirrored.status == "superseded"


async def test_flag_on_the_undo_of_a_restore_goes_by_the_new_memory(flag):
    flag(True)
    m_old, m_new = uuid.uuid4(), uuid.uuid4()
    d = _mirrored(m_old, m_new)
    # First the memories' UPDATE, then the undo's select of mirrored decisions.
    session = SimpleNamespace(execute=AsyncMock(side_effect=[None, await _Rows(d).execute(None)]))
    await supersession.restore_replaced_by(session, "A", m_new)
    assert d.status == "candidate"


class _Ctx:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


@pytest.mark.parametrize(("action", "to"), [("approve", "decided"), ("reject", "discarded")])
async def test_flag_on_the_owner_review_of_a_linked_memory_moves_the_candidate(
    flag, linked, monkeypatch, action, to
):
    flag(True)
    memory_id = uuid.uuid4()
    d = _decision()
    linked[str(memory_id)] = d
    session = SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(lc, "async_session", lambda: _Ctx(session))

    assert await lc.follow_memory_review("A", memory_id, action, "phone:d1") is True
    assert d.status == to
    entry = d.properties["lifecycle"][-1]
    assert entry["by"] == "phone:d1" and entry["owner"] is True and entry["via"] == "memory_review"
    session.commit.assert_awaited_once()


@pytest.mark.parametrize("by", [None, "", "service-key:abcd1234", "auto_kept", "system"])
async def test_flag_on_a_review_that_is_not_the_owners_moves_nothing(flag, linked, monkeypatch, by):
    """An auto-keep, a service key or an unnamed reviewer is no owner act."""
    flag(True)
    memory_id = uuid.uuid4()
    d = _decision()
    linked[str(memory_id)] = d
    monkeypatch.setattr(lc, "async_session", lambda: _Ctx(_NoDb()))

    assert await lc.follow_memory_review("A", memory_id, "approve", by) is False
    assert d.status == "candidate" and d.properties == {}


async def test_flag_on_a_review_leaves_a_decided_decision_alone(flag, linked, monkeypatch):
    flag(True)
    memory_id = uuid.uuid4()
    d = _decision(status="decided")
    linked[str(memory_id)] = d
    monkeypatch.setattr(lc, "async_session", lambda: _Ctx(SimpleNamespace(commit=AsyncMock())))
    assert await lc.follow_memory_review("A", memory_id, "reject", "owner") is False
    assert d.status == "decided"


class _MemoryRows:
    def __init__(self, *rows):
        self.rows = rows

    async def execute(self, _stmt):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: list(self.rows)))


async def test_flag_on_a_capture_links_its_one_decision_memory(flag):
    flag(True)
    memory = SimpleNamespace(id=uuid.uuid4(), tenant_id="A", properties={"fact_type": "decision"})
    d = _decision()
    assert await lc.link_capture_memory(_MemoryRows(memory), "A", d, uuid.uuid4()) is True
    assert d.properties["memory_id"] == str(memory.id)
    assert memory.properties == {"fact_type": "decision", "decision_id": str(d.id)}


async def test_flag_on_two_decision_memories_are_ambiguous(flag):
    flag(True)
    a = SimpleNamespace(id=uuid.uuid4(), tenant_id="A", properties={})
    b = SimpleNamespace(id=uuid.uuid4(), tenant_id="A", properties={})
    d = _decision()
    assert await lc.link_capture_memory(_MemoryRows(a, b), "A", d, uuid.uuid4()) is False
    assert d.properties == {} and a.properties == {} and b.properties == {}


async def test_flag_on_an_already_linked_memory_is_not_relinked(flag):
    flag(True)
    memory = SimpleNamespace(id=uuid.uuid4(), tenant_id="A", properties={"decision_id": "other"})
    d = _decision()
    assert await lc.link_capture_memory(_MemoryRows(memory), "A", d, uuid.uuid4()) is False
    assert d.properties == {}


async def test_failure_mining_asks_for_decided_decisions_later_superseded():
    from sqlalchemy.dialects import postgresql

    captured: list[str] = []

    class _S:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            sql = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
            captured.append(str(sql))
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    await failure_mining.FailurePatternMiner(session_factory=_S).gather_failures("A")
    (sql,) = captured
    assert "decided_at IS NOT NULL" in sql
    assert "'superseded'" in sql
    assert "abandoned" not in sql and "reversed" not in sql and "'discarded'" not in sql


# ── The hooks: who calls the memory side ─────────────────────


def _mem(status: str):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="A",
        status=status,
        superseded_by=None,
        supersedes=None,
        properties={},
        updated_at=None,
    )


async def test_an_approved_contradiction_mirrors_and_its_reject_undoes(monkeypatch):
    from life_graph.services.approvals import ApprovalService

    old, new = _mem("active"), _mem("pending")
    rows = {old.id: old, new.id: new}
    session = SimpleNamespace(get=AsyncMock(side_effect=lambda _model, ident: rows.get(ident)))
    mirror, undo = AsyncMock(return_value=True), AsyncMock(return_value=1)
    monkeypatch.setattr(supersession, "mirror_decisions", mirror)
    monkeypatch.setattr(supersession, "undo_decision_mirror", undo)
    appr = SimpleNamespace(
        payload={"memory_id_old": str(old.id), "memory_id_new": str(new.id), "applied": False}
    )
    svc = ApprovalService(session)

    await svc._apply_contradiction("A", appr, True)
    mirror.assert_awaited_once_with(session, "A", old, new)
    assert old.status == "superseded"

    await svc._apply_contradiction("A", appr, False)
    undo.assert_awaited_once_with(session, "A", old_id=old.id, new_id=new.id)
    assert old.status == "active"


async def test_a_refused_memory_supersede_mirrors_nothing(monkeypatch):
    from life_graph.services.approvals import ApprovalService

    old, new = _mem("archived"), _mem("pending")  # old not active: refused
    rows = {old.id: old, new.id: new}
    session = SimpleNamespace(get=AsyncMock(side_effect=lambda _model, ident: rows.get(ident)))
    mirror = AsyncMock()
    monkeypatch.setattr(supersession, "mirror_decisions", mirror)
    appr = SimpleNamespace(
        payload={"memory_id_old": str(old.id), "memory_id_new": str(new.id), "applied": False}
    )
    await ApprovalService(session)._apply_contradiction("A", appr, True)
    mirror.assert_not_awaited()


@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_a_memory_review_hands_the_reviewer_to_the_decision_side(monkeypatch, action):
    from life_graph.services import profile_card
    from life_graph.services.memory import transitions

    memory_id = uuid.uuid4()
    row = SimpleNamespace(
        id=memory_id,
        tenant_id="A",
        status="pending",
        properties={},
        content="I decided to sell the bike",
        source_type="chat",
        trust_tier="self",
    )
    store = SimpleNamespace(
        retrieve=AsyncMock(return_value=row), update=AsyncMock(return_value=row)
    )
    follow = AsyncMock(return_value=False)
    monkeypatch.setattr(transitions.decision_lifecycle, "follow_memory_review", follow)
    monkeypatch.setattr(transitions, "settle_contradictions", AsyncMock())
    monkeypatch.setattr(transitions, "learn_names", AsyncMock())
    monkeypatch.setattr(transitions, "get_current_tenant_id", lambda: "A")
    monkeypatch.setattr(transitions.event_bus, "emit", AsyncMock())
    monkeypatch.setattr(profile_card, "invalidate", lambda _tenant: None)

    await transitions.transition(memory_id, action, store, decided_by="phone:d1")

    follow.assert_awaited_once_with("A", memory_id, action, "phone:d1")
