"""Decision owner gates against a real Postgres (services/judgment.py).

``supersede_decision`` must not point one tenant's decision at another
tenant's row, nor at a row that does not exist, and must write nothing when
it refuses. A same-tenant replacement still works. ``create_decision``
refuses a status the model does not know.
(docs/design/adr-m8-ingestion-structure.md §5.4, §10 item 4)
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

from life_graph.core.errors import InvalidInputError, NotFoundError
from life_graph.models.db import Decision
from life_graph.services.judgment import JudgmentService
from life_graph.storage.database import async_session
from tests.integration.conftest import skip_on_db_error


def _tenant(tag: str) -> str:
    return f"decgate_{tag}_{uuid.uuid4().hex[:8]}"


async def _make(tenant: str, title: str) -> uuid.UUID:
    async with async_session() as s:
        row = await JudgmentService(s).create_decision(tenant, title, status="decided")
        await s.commit()
        return row.id


async def _get(decision_id: uuid.UUID) -> Decision:
    async with async_session() as s:
        return (await s.execute(select(Decision).where(Decision.id == decision_id))).scalar_one()


async def _cleanup(*tenants: str) -> None:
    async with async_session() as s:
        for t in tenants:
            await s.execute(
                text("UPDATE life_graph.decisions SET superseded_by = NULL WHERE tenant_id = :t"),
                {"t": t},
            )
        for t in tenants:
            await s.execute(text("DELETE FROM life_graph.decisions WHERE tenant_id = :t"), {"t": t})
        await s.commit()


@skip_on_db_error
async def test_supersede_refuses_a_cross_tenant_replacement():
    a, b = _tenant("a"), _tenant("b")
    try:
        mine = await _make(a, "Use Postgres")
        theirs = await _make(b, "Use MySQL")

        async with async_session() as s:
            with pytest.raises(NotFoundError):
                await JudgmentService(s).supersede_decision(a, mine, theirs)
            await s.commit()

        row = await _get(mine)
        assert row.status == "decided"
        assert row.superseded_by is None
    finally:
        await _cleanup(a, b)


@skip_on_db_error
async def test_supersede_refuses_a_missing_replacement():
    a = _tenant("a")
    try:
        mine = await _make(a, "Use Postgres")

        async with async_session() as s:
            with pytest.raises(NotFoundError):
                await JudgmentService(s).supersede_decision(a, mine, uuid.uuid4())
            await s.commit()

        row = await _get(mine)
        assert row.status == "decided"
        assert row.superseded_by is None
    finally:
        await _cleanup(a)


@skip_on_db_error
async def test_supersede_within_the_tenant_still_works():
    a = _tenant("a")
    try:
        old = await _make(a, "Use Postgres 15")
        new = await _make(a, "Use Postgres 17")

        async with async_session() as s:
            await JudgmentService(s).supersede_decision(a, old, new)
            await s.commit()

        row = await _get(old)
        assert row.status == "superseded"
        assert row.superseded_by == new
    finally:
        await _cleanup(a)


@skip_on_db_error
async def test_create_refuses_an_unknown_status():
    a = _tenant("a")
    try:
        async with async_session() as s:
            with pytest.raises(InvalidInputError):
                await JudgmentService(s).create_decision(a, "x", status="confirmed")
        async with async_session() as s:
            count = (
                await s.execute(
                    text("SELECT count(*) FROM life_graph.decisions WHERE tenant_id = :t"),
                    {"t": a},
                )
            ).scalar()
        assert count == 0
    finally:
        await _cleanup(a)
