"""GET /jarvis/notifications looks a little before the phone's cursor, so a row
committed late is still delivered (security review 2026-10-24, finding 7)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from tests.unit.fakes import FakeSession, session_factory

AFTER = datetime(2026, 10, 24, 9, 0, 0, tzinfo=UTC)


def _note(title, at):
    return SimpleNamespace(id=uuid.uuid4(), title=title, body="", priority="info", created_at=at)


async def _call(monkeypatch, session, **kw):
    from life_graph.api import jarvis
    from life_graph.core.tenant import tenant_scope

    monkeypatch.setattr(jarvis, "async_session", session_factory(session))
    with tenant_scope("t_notes"):
        return await jarvis.notifications(**kw)


def _bounds(stmt) -> list[datetime]:
    return sorted(v for v in stmt.compile().params.values() if isinstance(v, datetime))


@pytest.mark.asyncio
async def test_a_late_row_just_before_the_cursor_is_delivered(monkeypatch):
    from life_graph.api.jarvis import NOTIFICATION_OVERLAP_SECONDS

    late = _note("late", AFTER - timedelta(seconds=3))
    new = _note("new", AFTER + timedelta(seconds=5))
    session = FakeSession([late], [new])
    out = await _call(monkeypatch, session, after=AFTER.isoformat())
    assert [n["title"] for n in out["data"]] == ["late", "new"]

    overlap, fresh = session.statements
    assert _bounds(overlap) == [AFTER - timedelta(seconds=NOTIFICATION_OVERLAP_SECONDS), AFTER]
    assert _bounds(fresh) == [AFTER]


@pytest.mark.asyncio
async def test_repeats_do_not_use_up_the_page(monkeypatch):
    """A burst inside the overlap must not fill `limit`, or the cursor would
    never move past it."""
    burst = [_note(f"old{i}", AFTER - timedelta(seconds=i + 1)) for i in range(5)]
    new = _note("new", AFTER + timedelta(seconds=1))
    session = FakeSession(burst, [new])
    out = await _call(monkeypatch, session, after=AFTER.isoformat(), limit=1)
    assert out["data"][-1]["title"] == "new" and len(out["data"]) == 6


@pytest.mark.asyncio
async def test_no_cursor_means_one_query_from_the_start(monkeypatch):
    session = FakeSession([_note("first", AFTER)])
    out = await _call(monkeypatch, session)
    assert [n["title"] for n in out["data"]] == ["first"] and len(session.statements) == 1
