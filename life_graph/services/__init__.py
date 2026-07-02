"""Life Graph services — proactive recall, triggers, context, identity, and agent bridge.

Exports the core service classes for memory retrieval and management:
  - ContextBuilder / ContextFingerprint: session context matching
  - RecallEngine: proactive push-based memory recall
  - TriggerMatcher: intention and stale memory triggers
  - ContradictionDetector / Contradiction: memory consistency checks
  - IdentityService: identity timeline and belief state management
  - LifeGraphBridge: agent framework integration bridge
"""


def __getattr__(name):
    """Lazy imports to avoid circular import chains."""
    _map = {
        "LifeGraphBridge": ("life_graph.services.agent_bridge", "LifeGraphBridge"),
        "ContextBuilder": ("life_graph.services.context", "ContextBuilder"),
        "ContextFingerprint": ("life_graph.services.context", "ContextFingerprint"),
        "ContradictionDetector": ("life_graph.services.contradiction", "ContradictionDetector"),
        "Contradiction": ("life_graph.services.contradiction", "Contradiction"),
        "IdentityService": ("life_graph.services.identity", "IdentityService"),
        "RecallEngine": ("life_graph.services.recall", "RecallEngine"),
        "TriggerMatcher": ("life_graph.services.triggers", "TriggerMatcher"),
    }
    if name in _map:
        import importlib
        module = importlib.import_module(_map[name][0])
        return getattr(module, _map[name][1])
    raise AttributeError(f"module 'life_graph.services' has no attribute {name!r}")


__all__ = [
    "ContextBuilder",
    "ContextFingerprint",
    "ContradictionDetector",
    "Contradiction",
    "IdentityService",
    "LifeGraphBridge",
    "RecallEngine",
    "TriggerMatcher",
]
