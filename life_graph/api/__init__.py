"""Life Graph API — FastAPI route modules.

Exports routers for inclusion in the main application:
  - memories: Memory CRUD (T-043)
  - search: Semantic search and proactive recall (T-044)
  - intentions: Prospective memory management (T-045)
  - admin: Health, stats, gaps, and raw ingestion (T-048)
"""

from life_graph.api import admin, intentions, memories, search

__all__ = [
    "admin",
    "intentions",
    "memories",
    "search",
]
