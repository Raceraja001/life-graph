"""Driver context packets carry only the dispatched project's memories.

Regression for 2026-11-28: dev task c545707e (project race-app, claude_code
driver) was handed git-conflict alerts about another project (apptx-v2 /
"luminaux") inside its "Untrusted data" block. ``_load_memories`` drew the
top-10 tenant memories by importance with no project filter at all, so any
loud memory from any repository reached every coding agent.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from life_graph.drivers.claude_code import ClaudeCodeDriver
from life_graph.drivers.context import (
    ContextPacketBuilder,
    ProjectScope,
    _scope_clause,
    memory_in_scope,
)
from life_graph.models.db import Memory

RACE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
APPTX_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
RACE = {"name": "race-app", "path": "/mnt/h/DevTools/Projects/race-app"}
RACE_SCOPE = ProjectScope.from_project(RACE_ID, RACE)

LEAK = "git conflict in apptx-v2 (luminaux): packages/ui/theme.ts unmerged"


def _row(content: str, *, props: dict | None = None, tags: list[str] | None = None,
         tier: str = "external", importance: float = 0.9) -> SimpleNamespace:  # fmt: skip
    return SimpleNamespace(
        content=content,
        importance=importance,
        tags=tags or [],
        source_type="mcp",
        trust_tier=tier,
        properties=props or {},
    )


class _Session:
    """Returns *rows* for the memories query, as the SQL pre-filter would not."""

    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        self.statements.append(stmt)
        rows = self.rows
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))


async def _packet(rows, project_id, project_context, monkeypatch):
    builder = ContextPacketBuilder()

    async def _project(*_a, **_k):
        return dict(project_context)

    async def _empty_list(*_a, **_k):
        return []

    async def _empty_dict(*_a, **_k):
        return {}

    monkeypatch.setattr(builder, "_load_project", _project)
    monkeypatch.setattr(builder, "_load_procedures", _empty_list)
    monkeypatch.setattr(builder, "_load_preferences", _empty_list)
    monkeypatch.setattr(builder, "_load_calibration_profile", _empty_dict)
    session = _Session(rows)
    packet = await builder.build_packet(
        tenant_id="raja",
        task_type="code",
        instruction="Nightly health check for race-app",
        project_id=project_id,
        session=session,  # type: ignore[arg-type]
    )
    return packet, session


# ── the leak ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_other_projects_git_items_never_reach_the_packet(monkeypatch):
    rows = [
        _row(LEAK, props={"project": "apptx-v2"}, tags=["git", "conflict"]),
        _row(LEAK + " (id)", props={"project_id": str(APPTX_ID)}),
        _row(LEAK + " (path)", props={"cwd": "/mnt/h/DevTools/Projects/apptx-v2"}),
        _row(LEAK + " (repo)", props={"repo": "raja/apptx-v2"}),
        _row(LEAK + " (tag)", tags=["git", "project:apptx-v2"]),
        # The incident's shape: no attribution at all, high importance.
        _row("git conflict: luminaux branch feat/hero diverged", tags=["git", "conflict"]),
    ]
    packet, _ = await _packet(rows, RACE_ID, RACE, monkeypatch)
    assert packet.memories == []
    prompt = ClaudeCodeDriver._format_prompt(packet)
    assert "apptx" not in prompt and "luminaux" not in prompt
    assert "Untrusted data" not in prompt


@pytest.mark.asyncio
async def test_same_project_items_still_arrive(monkeypatch):
    rows = [
        _row("race-app: biome flags noExplicitAny", props={"project": "race-app"}),
        _row("by id", props={"project_id": str(RACE_ID)}, tier="verified"),
        _row("by cwd", props={"cwd": "/mnt/h/DevTools/Projects/race-app/apps/web"}),
        _row("by repo", props={"repo": "raja/race-app"}),
        _row("by tag", tags=["project:race-app"]),
        _row("old skill row", tags=["skill", "race-app"]),
        _row(LEAK, props={"project": "apptx-v2"}),
    ]
    packet, _ = await _packet(rows, RACE_ID, RACE, monkeypatch)
    contents = [m["content"] for m in packet.memories]
    assert LEAK not in contents
    assert len(contents) == 6
    prompt = ClaudeCodeDriver._format_prompt(packet)
    assert "biome flags noExplicitAny" in prompt and "by id" in prompt


@pytest.mark.asyncio
async def test_unregistered_project_gets_no_memories(monkeypatch):
    rows = [_row("race-app thing", props={"project": "race-app"})]
    packet, session = await _packet(rows, RACE_ID, {}, monkeypatch)
    assert packet.memories == []
    assert session.statements == []  # not even queried


@pytest.mark.asyncio
async def test_no_project_packet_keeps_unattributed_drops_attributed(monkeypatch):
    rows = [
        _row("general note", tier="verified"),
        _row(LEAK, props={"project": "apptx-v2"}),
        _row("race-app note", tags=["project:race-app"]),
    ]
    packet, _ = await _packet(rows, None, {}, monkeypatch)
    assert [m["content"] for m in packet.memories] == ["general note"]


# ── memory_in_scope: fail-closed edges ───────────────────────────────


def test_contradicting_attribution_is_excluded():
    props = {"project": "race-app", "project_id": str(APPTX_ID)}
    assert not memory_in_scope(props, [], RACE_SCOPE)


def test_lookalike_path_is_not_a_match():
    props = {"cwd": "/mnt/h/DevTools/Projects/race-app-old"}
    assert not memory_in_scope(props, [], RACE_SCOPE)


def test_unknown_project_value_counts_as_unattributed():
    assert not memory_in_scope({"project": "unknown"}, [], RACE_SCOPE)
    assert memory_in_scope({"project": "unknown"}, [], None)


def test_name_match_is_case_insensitive_and_uses_path_basename():
    scope = ProjectScope.from_project(RACE_ID, {"name": "Race App", "path": "C:\\code\\race-app\\"})
    assert memory_in_scope({"project": "race-app"}, [], scope)
    assert memory_in_scope({"project": "RACE APP"}, [], scope)
    assert memory_in_scope({"cwd": "C:/code/race-app/src"}, [], scope)


# ── the SQL pre-filter is actually applied ───────────────────────────


def _compiled(stmt: Any) -> str:
    """Bound values inlined, so the JSON keys the filter reads are visible."""
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _sql(scope: ProjectScope | None) -> str:
    return _compiled(_scope_clause(Memory, scope))


def test_scoped_query_filters_on_project_attribution():
    sql = _sql(RACE_SCOPE)
    for key in ("'project_id'", "'project'", "'cwd'", "'repo'"):
        assert key in sql
    assert "'11111111-1111-1111-1111-111111111111'" in sql
    assert "'project:race-app'" in sql and "tags" in sql


def test_unscoped_query_excludes_attributed_rows():
    sql = _sql(None)
    assert "IS NULL" in sql and "'project_id'" in sql and "'cwd'" in sql


@pytest.mark.asyncio
async def test_memories_query_carries_the_scope_clause(monkeypatch):
    _, session = await _packet([], RACE_ID, RACE, monkeypatch)
    (stmt,) = session.statements
    compiled = _compiled(stmt)
    assert "'project_id'" in compiled and "'race-app'" in compiled
