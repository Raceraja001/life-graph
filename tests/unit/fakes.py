"""Shared fakes for unit tests of database- and git-backed code.

Forty-odd test files each define their own ``_FakeSession``/``_FakeResult``.
The dev agent, given a function that queries the database, wrote tests that
only asserted ``callable()``, "since proper mocking of SQLAlchemy async
operations is complex" (task 90033c3e, 2026-10-18). Use these instead::

    from tests.unit.fakes import FakeSession, fake_landed_diff, sql

    async def test_found(monkeypatch):
        session = FakeSession(approval)          # what each execute() returns
        fake_landed_diff(monkeypatch, "diff --git a/x b/x\\n")
        result = await task_diff(session, "t1", "id")
        assert result["files"] == ["x"]
        assert "'driver_pr'" in sql(session.statements[0])

``FakeSession(*results)``: each ``execute()`` returns the next result in
order (the last one repeats). A result may be a :class:`FakeResult`, a list
of rows, a single row (any object), or ``None`` for "no row".
"""

from __future__ import annotations

from typing import Any


class FakeResult:
    """A SQLAlchemy ``Result`` over fixed rows: the accessors tests touch."""

    def __init__(self, rows: list[Any] | None = None, rowcount: int | None = None):
        self.rows = list(rows or [])
        self.rowcount = len(self.rows) if rowcount is None else rowcount

    # single row
    def scalar_one_or_none(self) -> Any:
        return self.rows[0] if self.rows else None

    def scalar_one(self) -> Any:
        if len(self.rows) != 1:
            raise AssertionError(f"scalar_one() on {len(self.rows)} rows")
        return self.rows[0]

    def scalar(self) -> Any:
        return self.rows[0] if self.rows else None

    def first(self) -> Any:
        return self.rows[0] if self.rows else None

    def one_or_none(self) -> Any:
        return self.rows[0] if self.rows else None

    # many rows
    def scalars(self) -> FakeResult:
        return self

    def all(self) -> list[Any]:
        return list(self.rows)

    def fetchall(self) -> list[Any]:
        return list(self.rows)

    def __iter__(self):
        return iter(self.rows)


def _as_result(value: Any) -> FakeResult:
    if isinstance(value, FakeResult):
        return value
    if value is None:
        return FakeResult([])
    if isinstance(value, list):
        return FakeResult(value)
    return FakeResult([value])


class FakeSession:
    """An ``AsyncSession`` stand-in: queued results, recorded statements.

    ``statements`` holds every statement passed to ``execute()``; ``added``
    every object passed to ``add()``; ``commits`` counts ``commit()``.
    ``get(Model, pk)`` reads from ``objects`` (``{(Model, pk): obj}``).
    """

    def __init__(self, *results: Any, objects: dict | None = None):
        self._results = [_as_result(r) for r in results] or [FakeResult([])]
        self.statements: list[Any] = []
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.objects = dict(objects or {})
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, stmt, *_a, **_k) -> FakeResult:
        self.statements.append(stmt)
        index = min(len(self.statements) - 1, len(self._results) - 1)
        return self._results[index]

    async def scalar(self, stmt, *_a, **_k) -> Any:
        return (await self.execute(stmt)).scalar()

    async def scalars(self, stmt, *_a, **_k) -> FakeResult:
        return (await self.execute(stmt)).scalars()

    async def get(self, model, pk, **_kwargs) -> Any:
        return self.objects.get((model, pk))

    def add(self, obj) -> None:
        self.added.append(obj)

    def add_all(self, objs) -> None:
        self.added.extend(objs)

    async def delete(self, obj) -> None:
        self.deleted.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def flush(self) -> None:
        pass

    async def refresh(self, _obj) -> None:
        pass

    async def close(self) -> None:
        pass

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False


def session_factory(session: FakeSession):
    """For code that takes ``async_sessionmaker``-style factories:
    ``async with factory() as s`` yields *session*."""
    return lambda: session


def sql(stmt) -> str:
    """A statement as SQL text with its values inlined, for assertions such as
    ``"'driver_pr'" in sql(session.statements[0])``. PostgreSQL dialect, so
    JSONB operators render."""
    from sqlalchemy.dialects import postgresql

    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def fake_landed_diff(monkeypatch, text: str) -> list[tuple]:
    """Replace ``github_pr.landed_diff`` (it shells out to git) with one that
    returns *text*. Returns the list its calls are recorded in."""
    from life_graph.services import github_pr

    calls: list[tuple] = []

    async def landed_diff(repo_path, base_commit, head_commit):
        calls.append((repo_path, base_commit, head_commit))
        return text

    monkeypatch.setattr(github_pr, "landed_diff", landed_diff)
    return calls
