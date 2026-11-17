"""The ``life-graph`` CLI.

Was a single ``life_graph/cli.py`` until the transcript harvester arrived with
a standalone entry point of its own (``python -m life_graph.cli.harvest_transcripts``).
It is a package now, and this module re-exports every command the old module
exposed so that ``pyproject.toml``'s ``life-graph = "life_graph.cli:main"``
console script — and anything importing ``life_graph.cli.cmd_*`` — behaves
exactly as before.
"""

from typing import Any

from life_graph.cli.root import (
    cmd_cold_start,
    cmd_hooks_install,
    cmd_hooks_status,
    cmd_hooks_uninstall,
    cmd_judgment_stats,
    cmd_migrate,
    cmd_reembed,
    cmd_stats,
    main,
)


def __getattr__(name: str) -> Any:
    """Expose ``cmd_harvest_transcripts`` without importing its module here.

    ``python -m life_graph.cli.harvest_transcripts`` imports this package
    first; importing the submodule from here too would run it twice (runpy
    warns about exactly that). Resolved on first access instead.
    """
    if name == "cmd_harvest_transcripts":
        from life_graph.cli.harvest_transcripts import cmd_harvest_transcripts

        return cmd_harvest_transcripts
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "cmd_cold_start",
    "cmd_harvest_transcripts",
    "cmd_hooks_install",
    "cmd_hooks_status",
    "cmd_hooks_uninstall",
    "cmd_judgment_stats",
    "cmd_migrate",
    "cmd_reembed",
    "cmd_stats",
    "main",
]
