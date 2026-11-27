"""Reading or scoring a memory must not mark it as edited (M8 eval D9).

``Memory.updated_at`` has ``onupdate=_utcnow``, so a Core ``update(Memory)``
that does not name the column stamps it with "now". The access counters
(``touch``, ``touch_many``) and the impact scorer ran such updates, so every
memory recalled last turn looked freshly edited to Stage 2 change detection
(services/memory/changes.py counted it ``cosmetic``). Each of these updates
must now set ``updated_at`` to its own current value.

No database: the statements are captured and compiled for Postgres.
"""

from __future__ import annotations

import re
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from life_graph.core.tenant import tenant_scope
from life_graph.services import impact
from life_graph.storage import postgres

KEEPS = re.compile(r"updated_at=(\w+\.)?memories\.updated_at\b")


class _Session:
    def __init__(self, rows=()):
        self.statements = []
        self._rows = list(rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self.statements.append(stmt)
        return SimpleNamespace(rowcount=1, all=lambda: [(r,) for r in self._rows])

    async def commit(self):
        return None


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def _updates(session: _Session) -> list[str]:
    return [s for s in map(_sql, session.statements) if s.startswith("UPDATE")]


@pytest.mark.parametrize("method", ["touch", "touch_many"])
async def test_an_access_keeps_updated_at(monkeypatch, method):
    session = _Session()
    monkeypatch.setattr(postgres, "async_session", lambda: session)
    store = postgres.PostgresMemoryStore()
    mid = uuid.uuid4()
    with tenant_scope("d9_unit"):
        await getattr(store, method)(mid if method == "touch" else [mid])
    (sql,) = _updates(session)
    assert "access_count" in sql and "last_accessed" in sql
    assert KEEPS.search(sql), sql


async def test_impact_scoring_keeps_updated_at(monkeypatch):
    session = _Session(rows=[uuid.uuid4()])
    monkeypatch.setattr(impact, "async_session", lambda: session)
    with tenant_scope("d9_unit"):
        await impact.ImpactScorer().record_outcome(uuid.uuid4(), "success")
    (sql,) = _updates(session)
    assert "impact_score" in sql
    assert KEEPS.search(sql), sql
