"""seed_builtins must RECONCILE already-seeded built-ins, not only insert
missing ones.

The bug this guards: a tenant seeded under an older version of
``_BUILTIN_PERSONAS`` keeps its old DB row forever, because the method
diffed by NAME only. Every consumer that matters (``TaskDispatcher.
_load_persona``, ``kernel/process_manager._run_agent``) reads the DB row,
never the constant — so a fix to a built-in's ``allowed_tools`` /
``system_prompt`` was a no-op on any real deployment while the in-memory
regression tests stayed green.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import Update

from life_graph.kernel.personas import _BUILTIN_PERSONAS, PersonaService


class _FakeRow:
    """Mimics a SQLAlchemy Row of the (name, is_builtin, allowed_tools,
    system_prompt) select seed_builtins issues — indexable AND attribute
    accessible, like the real thing."""

    def __init__(
        self,
        name: str,
        is_builtin: bool = True,
        allowed_tools: list[str] | None = None,
        system_prompt: str = "",
    ) -> None:
        self.name = name
        self.is_builtin = is_builtin
        self.allowed_tools = allowed_tools
        self.system_prompt = system_prompt

    def __getitem__(self, idx: int):
        return (self.name, self.is_builtin, self.allowed_tools, self.system_prompt)[idx]


class _FakeSelectResult:
    def __init__(self, rows: list[_FakeRow]) -> None:
        self._rows = rows

    def all(self) -> list[_FakeRow]:
        return self._rows


class _NullNested:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


class _FakeSession:
    def __init__(self, rows: list[_FakeRow]) -> None:
        self._rows = rows
        self.updates: list[Update] = []
        self.added: list[Any] = []
        self.committed = False

    async def execute(self, stmt):
        if isinstance(stmt, Update):
            self.updates.append(stmt)
            return _FakeSelectResult([])
        return _FakeSelectResult(self._rows)

    def begin_nested(self):
        return _NullNested()

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


def _service(rows: list[_FakeRow]) -> tuple[PersonaService, _FakeSession]:
    session = _FakeSession(rows)
    return PersonaService(session_factory=lambda: session), session


def _defn(name: str) -> dict[str, Any]:
    return next(p for p in _BUILTIN_PERSONAS if p["name"] == name)


def _update_values(stmt: Update) -> dict[str, Any]:
    """The SET clause of an UPDATE, as {column_name: value}."""
    return {col.name: getattr(val, "value", val) for col, val in stmt._values.items()}


def _rows_matching_current_definitions() -> list[_FakeRow]:
    return [
        _FakeRow(
            name=d["name"],
            is_builtin=True,
            allowed_tools=d["allowed_tools"],
            system_prompt=d["system_prompt"],
        )
        for d in _BUILTIN_PERSONAS
    ]


@pytest.mark.asyncio
async def test_stale_allowed_tools_are_reconciled_on_reseed():
    """A tenant seeded BEFORE this branch: cody's row still carries the old,
    unregistered tool names. Re-seeding must repair it in place."""
    rows = _rows_matching_current_definitions()
    cody_row = next(r for r in rows if r.name == "cody")
    cody_row.allowed_tools = ["file_read", "file_write", "terminal", "git"]

    svc, session = _service(rows)
    changed = await svc.seed_builtins("t1")

    # Nothing was missing — the whole count is the reconcile, which is
    # exactly what a caller/log needs to see happen.
    assert changed == 1
    assert session.added == []
    assert len(session.updates) == 1
    values = _update_values(session.updates[0])
    assert values["allowed_tools"] == _defn("cody")["allowed_tools"]
    assert "terminal" not in values["allowed_tools"]
    assert "system_prompt" not in values  # unchanged field not rewritten
    assert session.committed is True


@pytest.mark.asyncio
async def test_stale_system_prompt_is_reconciled():
    rows = _rows_matching_current_definitions()
    ops_row = next(r for r in rows if r.name == "ops")
    ops_row.system_prompt = "an old prompt from a previous release"

    svc, session = _service(rows)
    await svc.seed_builtins("t1")

    assert len(session.updates) == 1
    values = _update_values(session.updates[0])
    assert values["system_prompt"] == _defn("ops")["system_prompt"]
    assert "allowed_tools" not in values


@pytest.mark.asyncio
async def test_already_reconciled_tenant_issues_no_update():
    """No no-op write on every startup for every tenant."""
    svc, session = _service(_rows_matching_current_definitions())

    changed = await svc.seed_builtins("t1")

    assert changed == 0
    assert session.updates == []


@pytest.mark.asyncio
async def test_user_owned_persona_sharing_a_builtin_name_is_never_touched():
    rows = _rows_matching_current_definitions()
    cody_row = next(r for r in rows if r.name == "cody")
    cody_row.is_builtin = False
    cody_row.allowed_tools = ["terminal"]
    cody_row.system_prompt = "my own customized cody"

    svc, session = _service(rows)
    await svc.seed_builtins("t1")

    assert session.updates == []
    assert session.added == []


@pytest.mark.asyncio
async def test_missing_personas_are_still_inserted_alongside_reconciles():
    """Insert-and-reconcile in one pass: the pre-existing backfill behavior
    must survive."""
    rows = _rows_matching_current_definitions()
    rows = [r for r in rows if r.name != "penny"]  # penny not seeded yet
    next(r for r in rows if r.name == "cody").allowed_tools = ["terminal"]

    svc, session = _service(rows)
    changed = await svc.seed_builtins("t1")

    assert changed == 2  # 1 insert + 1 reconcile
    assert [p.name for p in session.added] == ["penny"]
    assert len(session.updates) == 1


@pytest.mark.asyncio
async def test_reconcile_update_is_tenant_and_builtin_scoped():
    rows = _rows_matching_current_definitions()
    next(r for r in rows if r.name == "cody").allowed_tools = ["terminal"]

    tenant = f"t_{uuid.uuid4().hex[:6]}"
    svc, session = _service(rows)
    await svc.seed_builtins(tenant)

    compiled = session.updates[0].compile()
    where_sql = str(compiled).split("WHERE", 1)[1]
    assert "tenant_id" in where_sql
    assert "name" in where_sql
    assert "is_builtin" in where_sql
    assert tenant in compiled.params.values()
