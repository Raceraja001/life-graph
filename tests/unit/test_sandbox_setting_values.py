"""The sandbox settings accept only their known values (Stage 0, M1.3).

An unknown driver_claude_sandbox ("Task", "tasks") used to fall through
sandbox.driver_sandbox_enabled()'s ``in ("docker", "task")`` check and mean
host execution without a word. Now it stops startup.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from life_graph.config import Settings
from life_graph.config.drivers import DriverSettings


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("driver_claude_sandbox", "Task"),
        ("driver_claude_sandbox", "tasks"),
        ("driver_claude_sandbox", "container"),
        ("driver_claude_sandbox", ""),
        ("verifier_sandbox", "Docker"),
        ("verifier_sandbox", "task"),
        ("verifier_sandbox", "on"),
    ],
)
def test_an_unknown_sandbox_value_is_refused(field, value):
    with pytest.raises(ValidationError):
        DriverSettings(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("driver_claude_sandbox", "none"),
        ("driver_claude_sandbox", "docker"),
        ("driver_claude_sandbox", "task"),
        ("verifier_sandbox", "none"),
        ("verifier_sandbox", "docker"),
    ],
)
def test_the_known_values_load(field, value):
    assert getattr(DriverSettings(**{field: value}), field) == value


def test_a_typo_in_the_environment_stops_startup(monkeypatch):
    monkeypatch.setenv("LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX", "Task")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_the_production_values_load_from_the_environment(monkeypatch):
    monkeypatch.setenv("LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX", "task")
    monkeypatch.setenv("LIFE_GRAPH_VERIFIER_SANDBOX", "docker")
    loaded = Settings(_env_file=None)
    assert (loaded.driver_claude_sandbox, loaded.verifier_sandbox) == ("task", "docker")
