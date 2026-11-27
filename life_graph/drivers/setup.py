"""Register the agent drivers a process can dispatch to.

One function, so the API (``dev_task_runner_mode=api``) and the dedicated
dev-task worker (``workers/dev_runner.py``) register exactly the same set.
"""

from __future__ import annotations

from life_graph.drivers.registry import driver_registry


def register_default_drivers() -> list[str]:
    """Register every built-in driver; returns their names."""
    from life_graph.drivers.claude_code import ClaudeCodeDriver
    from life_graph.drivers.cloud import CloudDriver
    from life_graph.drivers.codex import CodexDriver
    from life_graph.drivers.gemini import GeminiDriver
    from life_graph.drivers.local import LocalDriver
    from life_graph.drivers.opencode import OpencodeDriver

    for driver in (
        LocalDriver(),
        ClaudeCodeDriver(),
        OpencodeDriver(),
        CloudDriver(),
        CodexDriver(),
        GeminiDriver(),
    ):
        driver_registry.register(driver)
    return [d.name for d in driver_registry.list_all()]
