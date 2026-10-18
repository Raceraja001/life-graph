"""The shared fakes in tests/unit/fakes.py behave like what they replace."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from life_graph.models.db import Approval
from tests.unit.fakes import FakeResult, FakeSession, fake_landed_diff, session_factory, sql


async def test_results_come_back_in_order_and_the_last_repeats():
    one, many = SimpleNamespace(id=1), [SimpleNamespace(id=2), SimpleNamespace(id=3)]
    session = FakeSession(one, many, None)
    assert (await session.execute("a")).scalar_one_or_none() is one
    assert [r.id for r in (await session.execute("b")).scalars().all()] == [2, 3]
    assert (await session.execute("c")).scalar_one_or_none() is None
    assert (await session.execute("d")).first() is None  # last repeats
    assert session.statements == ["a", "b", "c", "d"]


def test_scalar_one_is_strict_like_sqlalchemy():
    with pytest.raises(AssertionError):
        FakeResult([]).scalar_one()
    with pytest.raises(AssertionError):
        FakeResult([1, 2]).scalar_one()
    assert FakeResult([7]).scalar_one() == 7


async def test_add_commit_get_and_the_context_manager():
    pk = uuid.uuid4()
    row = SimpleNamespace(id=pk)
    session = FakeSession(objects={(Approval, pk): row})
    factory = session_factory(session)
    async with factory() as s:
        s.add("x")
        await s.commit()
        assert await s.get(Approval, pk) is row
        assert await s.get(Approval, uuid.uuid4()) is None
    assert session.added == ["x"] and session.commits == 1


def test_sql_inlines_values_including_jsonb_lookups():
    stmt = select(Approval).where(
        Approval.tenant_id == "t1",
        Approval.kind == "driver_pr",
        Approval.payload["task_id"].astext == "abc",
    )
    text = sql(stmt)
    assert "'t1'" in text and "'driver_pr'" in text and "'abc'" in text and "->>" in text


async def test_fake_landed_diff_records_its_calls(monkeypatch):
    from life_graph.services import github_pr

    calls = fake_landed_diff(monkeypatch, "diff --git a/x b/x\n")
    assert await github_pr.landed_diff("/r", "a", "b") == "diff --git a/x b/x\n"
    assert calls == [("/r", "a", "b")]
