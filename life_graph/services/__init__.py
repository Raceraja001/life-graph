"""Life Graph services — proactive recall, triggers, and context matching.

Exports the core service classes for memory retrieval and management:
  - ContextBuilder / ContextFingerprint: session context matching
  - RecallEngine: proactive push-based memory recall
  - TriggerMatcher: intention and stale memory triggers
  - ContradictionDetector / Contradiction: memory consistency checks
"""

from life_graph.services.context import ContextBuilder, ContextFingerprint
from life_graph.services.contradiction import Contradiction, ContradictionDetector
from life_graph.services.recall import RecallEngine
from life_graph.services.triggers import TriggerMatcher

__all__ = [
    "ContextBuilder",
    "ContextFingerprint",
    "ContradictionDetector",
    "Contradiction",
    "RecallEngine",
    "TriggerMatcher",
]
