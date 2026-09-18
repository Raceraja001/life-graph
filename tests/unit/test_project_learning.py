"""Learning a project's conventions into preferences.

The cold-start analyzers used to write only a JSON file. These pin the sync
into the preference store: scoped to the project, refreshed rather than
duplicated on re-run, and never touching another project's rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from life_graph.cold_start.git_analyzer import GitAnalyzer
from life_graph.services import project_learning as pl

PROJECT = {"id": str(uuid.uuid4()), "name": "demo", "path": "/repo"}


@dataclass
class FakePref:
    topic: str
    choice: str
    properties: dict
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: str = "active"
    source: str = "cold_start"


class FakeStore:
    def __init__(self) -> None:
        self.rows: list[FakePref] = []

    async def list(self, tenant_id, *, source=None, limit=50, offset=0, **_):
        rows = [r for r in self.rows if r.status == "active" and r.source == source]
        return rows[offset : offset + limit]

    async def create(self, tenant_id, data: dict[str, Any]):
        self.rows.append(
            FakePref(data["topic"], data["choice"], data["properties"], source=data["source"])
        )

    async def update(self, tenant_id, pref_id, data):
        next(r for r in self.rows if r.id == pref_id).choice = data["choice"]

    async def delete(self, tenant_id, pref_id):
        next(r for r in self.rows if r.id == pref_id).status = "archived"

    def active(self):
        return [r for r in self.rows if r.status == "active"]


def _finding(content, tags, source="cold_start:code_analysis"):
    return {"content": content, "tags": tags, "source": source, "type_tag": "pattern"}


def _analyzer(findings):
    return lambda path, authors=None: (list(findings), [])


def test_finding_key_ignores_measured_numbers():
    a = _finding("Docstring rate: 40% of functions (232/587)", [])
    b = _finding("Docstring rate: 45% of functions (250/590)", [])
    assert pl.finding_key(a) == pl.finding_key(b)
    c = _finding("Uses ruff linter with line-length=100", [], "cold_start:config_parse")
    d = _finding("Ruff lint rules selected: E, W", [], "cold_start:config_parse")
    assert pl.finding_key(c) != pl.finding_key(d)


async def test_first_run_creates_project_scoped_preferences(monkeypatch):
    store = FakeStore()
    monkeypatch.setattr(
        pl,
        "analyze",
        _analyzer(
            [
                _finding("Uses pytest as the testing framework", ["preference", "testing"]),
                _finding("Peak coding hours: 22:00", ["pattern", "time", "work-schedule"]),
            ]
        ),
    )
    result = await pl.learn_project(store, "t", PROJECT)
    assert result["created"] == 1  # schedule habits are not coding guidance
    (pref,) = store.active()
    assert pref.properties["project_id"] == PROJECT["id"]
    assert pref.topic == "demo: testing"


async def test_rerun_updates_in_place_and_archives_vanished(monkeypatch):
    store = FakeStore()
    monkeypatch.setattr(
        pl,
        "analyze",
        _analyzer(
            [
                _finding("Docstring rate: 40%", ["documentation"]),
                _finding("Uses Python dataclasses", ["dataclass"]),
            ]
        ),
    )
    await pl.learn_project(store, "t", PROJECT)

    monkeypatch.setattr(
        pl, "analyze", _analyzer([_finding("Docstring rate: 55%", ["documentation"])])
    )
    result = await pl.learn_project(store, "t", PROJECT)

    assert (result["created"], result["updated"], result["archived"]) == (0, 1, 1)
    assert [p.choice for p in store.active()] == ["Docstring rate: 55%"]


async def test_other_projects_preferences_untouched(monkeypatch):
    store = FakeStore()
    other = FakePref(
        "other: typing", "Type hints everywhere", {"project_id": "other", "finding_key": "k"}
    )
    store.rows.append(other)
    monkeypatch.setattr(pl, "analyze", _analyzer([]))
    await pl.learn_project(store, "t", PROJECT)
    assert other.status == "active"


def test_git_author_filter_matches_any_identity_by_name_or_email():
    def commit(name, email):
        return SimpleNamespace(
            author=SimpleNamespace(name=name, email=email),
            msg="feat: x",
            author_date=__import__("datetime").datetime(2026, 9, 1, 10),
            modified_files=[],
        )

    seen_kwargs = {}

    class FakeRepo:
        def __init__(self, path, **kwargs):
            seen_kwargs.update(kwargs)

        def traverse_commits(self):
            return [
                commit("raja4lmx", "raja@logimaxindia.com"),
                commit("Race", "raceraja001@gmail.com"),
                commit("test", "test@test.com"),
            ]

    result = GitAnalyzer()._mine_commits(FakeRepo, "/r", ["raceraja001@gmail.com", "raja4lmx"])
    assert result["total_commits"] == 2
    assert seen_kwargs == {"order": "reverse"}  # newest first, so the cap keeps recent habits


def test_registration_refuses_path_outside_roots(tmp_path, monkeypatch):
    from life_graph.config import settings
    from life_graph.kernel.project_registry import _confined_project_path

    inside = tmp_path / "root" / "repo"
    inside.mkdir(parents=True)
    monkeypatch.setattr(settings, "tool_fs_roots", str(tmp_path / "root"))
    assert _confined_project_path(str(inside)) == str(inside.resolve())
    with pytest.raises(ValueError, match="outside the permitted roots"):
        _confined_project_path(str(tmp_path))
