"""Every persona's allowed_tools must name a real registered tool, OR be one
of the explicitly-deferred aspirational names (memory_search — see
kernel/personas.py). This is the regression guard for the bug found during
the B2 final review: several personas referenced "terminal"/"git"/
"file_read"/"file_write"/"docker"/"ssh" — none of which matched any
registered tool name, so persona tool-scoping silently produced an empty
toolset for most personas.
"""

from __future__ import annotations

import life_graph.tools.browser  # noqa: F401
import life_graph.tools.calculator  # noqa: F401
import life_graph.tools.datetime_tool  # noqa: F401
import life_graph.tools.delegate  # noqa: F401
import life_graph.tools.filesystem  # noqa: F401
import life_graph.tools.git  # noqa: F401
import life_graph.tools.system_inspect  # noqa: F401
import life_graph.tools.terminal  # noqa: F401
import life_graph.tools.web_search  # noqa: F401
from life_graph.kernel.personas import _BUILTIN_PERSONAS
from life_graph.tools.registry import registry

# Deferred, documented-unregistered names — NOT a bug, do not "fix" by
# removing these from personas.py. See kernel/ambient.py's comment.
DEFERRED_NAMES = {"memory_search"}


def test_every_persona_allowed_tool_is_registered_or_deferred():
    registered = set(registry.tool_names)
    unexplained = {}
    for defn in _BUILTIN_PERSONAS:
        allowed = defn.get("allowed_tools")
        if not allowed:
            continue
        bad = [
            name for name in allowed
            if name not in registered and name not in DEFERRED_NAMES
        ]
        if bad:
            unexplained[defn["name"]] = bad
    assert unexplained == {}, f"Unregistered, unexplained tool names: {unexplained}"


def test_cody_can_actually_read_and_write_files():
    cody = next(p for p in _BUILTIN_PERSONAS if p["name"] == "cody")
    assert "file_read" in cody["allowed_tools"]
    assert "file_write" in cody["allowed_tools"]
    assert "run_command" in cody["allowed_tools"]
    assert "terminal" not in cody["allowed_tools"]  # old, unregistered name gone


def test_ambient_repo_project_name_constant():
    from life_graph.kernel.ambient import AMBIENT_REPO_PROJECT_NAME

    assert AMBIENT_REPO_PROJECT_NAME == "life-graph"
