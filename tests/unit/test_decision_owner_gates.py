"""Owner gates on decisions (docs/design/adr-m8-ingestion-structure.md §5.4, §10 item 4).

Inferred context must never become the owner's confirmed intent:

* ``POST /judgment/decisions`` validates ``status`` and keeps ``decided``,
  ``discarded`` and the other owner statuses only for an owner-verified
  caller. Anyone else gets a ``candidate``, and ``meta`` says so.
* ``JudgmentService.supersede_decision`` refuses a replacement that is not a
  decision of the same tenant, and writes nothing then.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

import life_graph.api.judgment as judgment
from life_graph.core.errors import InvalidInputError, NotFoundError
from life_graph.core.trust import UNVERIFIED, Ingress
from life_graph.models.schemas import (
    DECISION_STATUSES,
    OWNER_DECISION_STATUSES,
    DecisionCreate,
)
from life_graph.services.judgment import JudgmentService

OWNER = Ingress(actor="owner:api_key", owner_verified=True)
PHONE = Ingress(actor="device:d1", owner_verified=True, device_id="d1")


def _row(**kw):
    """What create_decision returns, enough for DecisionResponse."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=kw["tenant_id"],
        title=kw["title"],
        reasoning=kw.get("reasoning"),
        options=kw.get("options") or [],
        chosen_option=kw.get("chosen_option"),
        status=kw["status"],
        source=kw.get("source"),
        domain_tags=kw.get("domain_tags") or [],
        importance=kw.get("importance", 0.5),
        capture_event_id=None,
        superseded_by=None,
        decided_at=None,
        review_at=None,
        reviewed_at=None,
        properties={},
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def svc():
    return SimpleNamespace(create_decision=AsyncMock(side_effect=lambda **kw: _row(**kw)))


def _as(monkeypatch, ingress: Ingress) -> None:
    monkeypatch.setattr(judgment, "ingress_for", lambda _request: ingress)


async def _create(svc, **body):
    return await judgment.create_decision(
        body=DecisionCreate(title="Use Postgres", **body),
        request=SimpleNamespace(),
        svc=svc,
        tenant_id="t-gates",
    )


# ── Status validation ─────────────────────────────────────────


@pytest.mark.parametrize("status", DECISION_STATUSES)
def test_every_known_status_is_accepted(status):
    assert DecisionCreate(title="x", status=status).status == status


@pytest.mark.parametrize("status", ["confirmed", "DECIDED", "", "abandoned", "decided "])
def test_an_unknown_status_is_refused(status):
    with pytest.raises(ValidationError):
        DecisionCreate(title="x", status=status)


def test_only_candidate_is_open_to_everyone():
    assert set(DECISION_STATUSES) - OWNER_DECISION_STATUSES == {"candidate"}


async def test_the_service_refuses_an_unknown_status_too():
    session = SimpleNamespace(add=lambda _row: None, flush=AsyncMock())
    with pytest.raises(InvalidInputError):
        await JudgmentService(session).create_decision("t", "x", status="confirmed")
    session.flush.assert_not_awaited()


# ── Owner gate on create ──────────────────────────────────────


@pytest.mark.parametrize("status", sorted(OWNER_DECISION_STATUSES))
async def test_a_non_owner_gets_a_candidate_and_is_told(monkeypatch, svc, status):
    _as(monkeypatch, UNVERIFIED)

    resp = await _create(svc, status=status)

    assert svc.create_decision.await_args.kwargs["status"] == "candidate"
    assert resp["data"].status == "candidate"
    assert resp["meta"]["status_downgraded"] is True
    assert resp["meta"]["requested_status"] == status


async def test_a_non_owner_relying_on_the_old_default_gets_a_candidate(monkeypatch, svc):
    """The default is still "decided"; it is now kept for the owner only."""
    _as(monkeypatch, UNVERIFIED)

    resp = await _create(svc)

    assert svc.create_decision.await_args.kwargs["status"] == "candidate"
    assert resp["meta"]["requested_status"] == "decided"


async def test_a_non_owner_asking_for_a_candidate_is_not_flagged(monkeypatch, svc):
    _as(monkeypatch, UNVERIFIED)

    resp = await _create(svc, status="candidate")

    assert svc.create_decision.await_args.kwargs["status"] == "candidate"
    assert "meta" not in resp


@pytest.mark.parametrize("ingress", [OWNER, PHONE], ids=["owner-key", "paired-phone"])
@pytest.mark.parametrize("status", ["decided", "discarded"])
async def test_the_owner_keeps_the_status_asked_for(monkeypatch, svc, ingress, status):
    _as(monkeypatch, ingress)

    resp = await _create(svc, status=status)

    assert svc.create_decision.await_args.kwargs["status"] == status
    assert resp["data"].status == status
    assert "meta" not in resp


async def test_the_gate_does_not_depend_on_approvals_require_owner(monkeypatch, svc):
    """require_owner() is a no-op with that setting off; this gate is not."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "approvals_require_owner", False)
    _as(monkeypatch, UNVERIFIED)

    await _create(svc, status="decided")

    assert svc.create_decision.await_args.kwargs["status"] == "candidate"


# ── supersede_decision fails closed ───────────────────────────


class _Result:
    def __init__(self, row):
        self._row = row

    def scalars(self):
        return SimpleNamespace(first=lambda: self._row)


class _Session:
    """Answers a select by the tenant and id it filters on."""

    def __init__(self, *rows):
        self.rows = rows
        self.queries = 0

    async def execute(self, stmt):
        self.queries += 1
        params = stmt.compile().params
        tenant = next(v for k, v in params.items() if k.startswith("tenant_id"))
        ident = next(v for k, v in params.items() if k.startswith("id"))
        hit = next((r for r in self.rows if r.tenant_id == tenant and r.id == ident), None)
        return _Result(hit)


def _decision(tenant: str, status: str = "decided"):
    return SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant, status=status, superseded_by=None)


async def test_supersede_with_a_same_tenant_replacement_works():
    old, new = _decision("A"), _decision("A")
    bus = SimpleNamespace(emit=AsyncMock())

    await JudgmentService(_Session(old, new), bus).supersede_decision(
        "A", old.id, new.id, by="owner", owner=True
    )

    assert old.status == "superseded"
    assert old.superseded_by == new.id
    bus.emit.assert_awaited_once()


async def test_supersede_refuses_another_tenants_replacement():
    old, theirs = _decision("A"), _decision("B")
    bus = SimpleNamespace(emit=AsyncMock())

    with pytest.raises(NotFoundError):
        await JudgmentService(_Session(old, theirs), bus).supersede_decision("A", old.id, theirs.id)

    assert old.status == "decided"
    assert old.superseded_by is None
    bus.emit.assert_not_awaited()


async def test_supersede_refuses_a_replacement_that_does_not_exist():
    old = _decision("A")

    with pytest.raises(NotFoundError):
        await JudgmentService(_Session(old)).supersede_decision("A", old.id, uuid.uuid4())

    assert old.status == "decided"
    assert old.superseded_by is None


async def test_supersede_refuses_a_decision_replacing_itself():
    old = _decision("A")
    session = _Session(old)

    with pytest.raises(InvalidInputError):
        await JudgmentService(session).supersede_decision("A", old.id, old.id)

    assert old.status == "decided"
    assert session.queries == 0
