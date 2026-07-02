"""Life Graph core — high-level orchestrators.

Exports the MemoryManager which coordinates ingestion,
contradiction detection, and supersession chains.
"""

from life_graph.core.memory_manager import MemoryManager

__all__ = [
    "MemoryManager",
]
