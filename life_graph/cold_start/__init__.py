"""Cold start bootstrap — extract 50+ memories from existing data.

Public API:
    ColdStartBootstrap — orchestrates the full pipeline
    GitAnalyzer        — mines Git commit history
    ConfigParser       — parses project config files
    CodeAnalyzer       — analyzes Python AST patterns
"""


def __getattr__(name):
    """Lazy imports to avoid pulling in heavy deps (pgvector, SQLAlchemy) at import time."""
    if name == "ColdStartBootstrap":
        from life_graph.cold_start.bootstrap import ColdStartBootstrap
        return ColdStartBootstrap
    if name == "GitAnalyzer":
        from life_graph.cold_start.git_analyzer import GitAnalyzer
        return GitAnalyzer
    if name == "ConfigParser":
        from life_graph.cold_start.config_parser import ConfigParser
        return ConfigParser
    if name == "CodeAnalyzer":
        from life_graph.cold_start.code_analyzer import CodeAnalyzer
        return CodeAnalyzer
    raise AttributeError(f"module 'life_graph.cold_start' has no attribute {name!r}")


__all__ = [
    "ColdStartBootstrap",
    "CodeAnalyzer",
    "ConfigParser",
    "GitAnalyzer",
]
