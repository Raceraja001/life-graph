"""Life Graph core — high-level orchestrators.

Exports the MemoryManager which coordinates ingestion,
contradiction detection, and supersession chains. Also
exports the EventBus for pub-sub events and the PluginManager
for plugin discovery and loading.
"""


def __getattr__(name):
    """Lazy imports to avoid circular import chains."""
    if name == "MemoryManager":
        from life_graph.core.memory_manager import MemoryManager
        return MemoryManager
    if name == "QueryRouter":
        from life_graph.core.router import QueryRouter
        return QueryRouter
    if name in ("EventBus", "EventType", "event_bus"):
        import life_graph.core.events as events_mod
        return getattr(events_mod, name)
    if name == "PluginManager":
        from life_graph.core.plugins import PluginManager
        return PluginManager
    raise AttributeError(f"module 'life_graph.core' has no attribute {name!r}")


__all__ = [
    "MemoryManager",
    "QueryRouter",
    "EventBus",
    "EventType",
    "event_bus",
    "PluginManager",
]

