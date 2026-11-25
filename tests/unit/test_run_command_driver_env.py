"""run_command in ``full`` mode inside a driver run gets no secrets.

``tool_shell_mode=full`` runs an arbitrary shell string. It used to inherit
the API process's whole environment, so an agent working in a task worktree
under the local driver (``confine_to``) could read the database URL,
provider keys and every ``LIFE_GRAPH_*`` setting with ``env`` (Stage 0,
2026-11-25). Inside ``confine_to`` the shell now gets ``child_env()``.
"""

from __future__ import annotations

import json

import pytest

from life_graph.config import settings
from life_graph.tools import terminal as term
from life_graph.tools._guards import confine_to, confined

SECRET_URL = "postgresql://user:pw-7731@db/x"
SECRET_KEY = "sk-or-v1-" + "s" * 32


@pytest.fixture
def full_shell(monkeypatch):
    monkeypatch.setattr(settings, "tool_shell_enabled", True)
    monkeypatch.setattr(settings, "tool_shell_mode", "full")
    monkeypatch.setattr(settings, "tool_privileged_tenants", "")
    monkeypatch.setenv("LIFE_GRAPH_DATABASE_URL", SECRET_URL)
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET_KEY)


async def test_full_mode_inside_a_driver_run_sees_no_secrets(full_shell, tmp_path):
    # confine_to is what the local driver wraps its whole run in
    # (drivers/local.py) and what self_check uses.
    with confine_to(tmp_path):
        out = json.loads(await term.run_command("env; echo done", working_directory=str(tmp_path)))

    assert out["exit_code"] == 0, out
    stdout = out["stdout"]
    assert "done" in stdout  # the shell still works
    assert "PATH=" in stdout
    assert "LIFE_GRAPH_" not in stdout
    assert SECRET_URL not in stdout
    assert "OPENROUTER_API_KEY" not in stdout and SECRET_KEY not in stdout


async def test_full_mode_inside_a_driver_run_cannot_expand_a_secret(full_shell, tmp_path):
    with confine_to(tmp_path):
        out = json.loads(
            await term.run_command(
                'printf "[%s]" "$LIFE_GRAPH_DATABASE_URL"', working_directory=str(tmp_path)
            )
        )
    assert out["stdout"] == "[]"


def test_confined_tracks_confine_to(tmp_path):
    assert confined() is False
    with confine_to(tmp_path):
        assert confined() is True
    assert confined() is False
