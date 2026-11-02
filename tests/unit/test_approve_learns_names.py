"""Approving a memory teaches the people table its names and roles.

Most captured facts wait for review, and only facts stored active taught names,
so in real use no entity ever got a role (prod, 2026-11-02: 0 of 41) and the
extractor's known-people hint had nothing to say.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from life_graph.api import memories as api
from life_graph.core.tenant import tenant_scope
from life_graph.services import entities, profile_card


class _Store:
    def __init__(self, row):
        self.row = row

    async def retrieve(self, memory_id):
        return self.row

    async def update(self, memory_id, update):
        self.row = SimpleNamespace(**{**vars(self.row), "status": update.status})
        return self.row


@pytest.fixture
def learned(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_learn(tenant_id, text_, *, evidence=""):
        calls.append((tenant_id, text_))
        return {"linked": 0, "held": 0, "roles": 1}

    async def nothing(*_a, **_k):
        return None

    monkeypatch.setattr(entities, "learn_aliases", fake_learn)
    monkeypatch.setattr(api, "_settle_contradictions", nothing)
    monkeypatch.setattr(api.event_bus, "emit", nothing)
    monkeypatch.setattr(profile_card, "invalidate", lambda _t: None)
    return calls


def _row(content, status="pending", **props):
    return SimpleNamespace(
        id=uuid.uuid4(), tenant_id="t1", status=status, content=content, properties=props
    )


@pytest.mark.asyncio
async def test_approving_a_memory_learns_its_names(learned):
    store = _Store(_row("My wife Priya teaches maths at DAV."))
    with tenant_scope("t1"):
        out = await api._transition(store.row.id, "approve", store)

    assert out.status == "active"
    assert learned == [("t1", "My wife Priya teaches maths at DAV.")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "props"),
    [
        ("Maha is not my wife.", {"polarity": "negate"}),
        ("Ravi might be short for Ravindran.", {"certainty": "hedged"}),
        ("Maybe Ravi is short for Ravindran.", {}),
    ],
)
async def test_hedged_or_negated_memories_teach_nothing(learned, content, props):
    store = _Store(_row(content, **props))
    with tenant_scope("t1"):
        await api._transition(store.row.id, "approve", store)

    assert learned == []


@pytest.mark.asyncio
async def test_an_already_active_or_rejected_memory_learns_nothing_more(learned):
    active = _Store(_row("My wife Priya teaches maths.", status="active"))
    pending = _Store(_row("My wife Priya teaches maths."))
    with tenant_scope("t1"):
        await api._transition(active.row.id, "approve", active)
        await api._transition(pending.row.id, "reject", pending)

    assert learned == []


@pytest.mark.asyncio
async def test_a_failed_lookup_still_approves(learned, monkeypatch):
    async def boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(entities, "learn_aliases", boom)
    store = _Store(_row("My wife Priya teaches maths."))
    with tenant_scope("t1"):
        out = await api._transition(store.row.id, "approve", store)

    assert out.status == "active"
