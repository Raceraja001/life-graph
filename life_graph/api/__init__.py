"""Life Graph API — FastAPI route modules.

Exports routers for inclusion in the main application:
  - memories: Memory CRUD (T-043)
  - search: Semantic search and proactive recall (T-044)
  - intentions: Prospective memory management (T-045)
  - admin: Health, stats, gaps, and raw ingestion (T-048)
  - graph: Knowledge graph queries via Apache AGE (T-071)
  - multimodal: Multi-modal ingest (T-077, T-078)
  - sessions: Session lifecycle management (Phase B)
  - identity: Identity timeline and belief management (Phase B)
  - agent: Agent framework bridge (Phase B)
"""

from life_graph.api import (
    admin,
    agent,
    graph,
    identity,
    intentions,
    memories,
    multimodal,
    search,
    sessions,
)

__all__ = [
    "admin",
    "agent",
    "graph",
    "identity",
    "intentions",
    "memories",
    "multimodal",
    "search",
    "sessions",
]
