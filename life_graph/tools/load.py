"""Register every agent tool (importing a module runs its @tool decorators).

The API registers them at startup (main.py); the worker does too
(workers/settings.py on_startup), because scheduled persona turns — ambient
jobs and the owner's scheduled asks — run there and would otherwise see no tools.
"""

from __future__ import annotations

from importlib import import_module

MODULES = (
    "life_graph.tools.assistant",
    "life_graph.tools.browser",
    "life_graph.tools.calculator",
    "life_graph.tools.code",
    "life_graph.tools.datetime_tool",
    "life_graph.tools.delegate",
    "life_graph.tools.filesystem",
    "life_graph.tools.git",
    "life_graph.tools.memory_search",
    "life_graph.tools.reminders",
    "life_graph.tools.run_tests",
    "life_graph.tools.schedules",
    "life_graph.tools.system_inspect",
    "life_graph.tools.terminal",
    "life_graph.tools.web_search",
)


def register_all() -> list[str]:
    """Import every tool module (idempotent); the registered names back."""
    for name in MODULES:
        import_module(name)
    from life_graph.tools.registry import registry

    return list(registry.tool_names)
