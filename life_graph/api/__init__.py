"""Life Graph API — FastAPI route modules.

Exports routers for inclusion in the main application:
  - memories: Memory CRUD (T-043)
  - search: Semantic search and proactive recall (T-044)
  - intentions: Prospective memory management (T-045)
  - admin: Health, stats, gaps, and raw ingestion (T-048)
  - graph: Knowledge graph queries via Apache AGE (T-071)
  - multimodal: Multi-modal ingest (T-077, T-078)
"""

from life_graph.api import admin, graph, intentions, memories, multimodal, search

__all__ = [
    "admin",
    "graph",
    "intentions",
    "memories",
    "multimodal",
    "search",
]
