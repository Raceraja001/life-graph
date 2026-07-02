"""Life Graph core — high-level orchestrators.

Exports the MemoryManager which coordinates ingestion,
contradiction detection, and supersession chains.
"""


def __getattr__(name):
    """Lazy imports to avoid circular import chains."""
    if name == "MemoryManager":
        from life_graph.core.memory_manager import MemoryManager
        return MemoryManager
    if name == "QueryRouter":
        from life_graph.core.router import QueryRouter
        return QueryRouter
    raise AttributeError(f"module 'life_graph.core' has no attribute {name!r}")


__all__ = [
    "MemoryManager",
    "QueryRouter",
]
